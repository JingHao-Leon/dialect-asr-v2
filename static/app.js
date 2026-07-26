/* ============================================
   方言语音识别系统 v2.0 - 前端逻辑
   ============================================ */
(function() {
    'use strict';

    const $ = (id) => document.getElementById(id);

    // 状态
    let mediaRecorder = null;
    let audioChunks = [];
    let audioContext = null;
    let analyser = null;
    let animFrameId = null;
    let isProcessing = false;   // 防止重复点击
    let stream = null;          // 显式保存 stream，方便关闭

    // ============================================================
    // 初始化
    // ============================================================
    document.addEventListener('DOMContentLoaded', () => {
        $('btn-record').addEventListener('click', startRecord);
        $('btn-stop').addEventListener('click', stopRecord);
        $('btn-playback').addEventListener('click', playAudio);

        // 显示方言选项总数
        const total = document.querySelectorAll('input[name="dialect"]').length;
        const badge = $('count-badge');
        if (badge) badge.textContent = total + ' 种';

        checkHealth();
    });

    async function checkHealth() {
        try {
            const r = await fetch('/api/health', { cache: 'no-store' });
            const data = await r.json();
            const tag = $('engine-tag');
            if (data.engine?.available && data.ffmpeg) {
                tag.textContent = `✅ ${data.engine.model} 就绪 · ffmpeg OK`;
                tag.style.background = 'rgba(154, 230, 180, 0.3)';
            } else {
                const issues = [];
                if (!data.engine?.available) issues.push('未配置 DASHSCOPE_API_KEY');
                if (!data.ffmpeg) issues.push('未安装 ffmpeg');
                tag.textContent = '⚠️ ' + issues.join(' · ');
                tag.style.background = 'rgba(245, 101, 101, 0.3)';
            }
        } catch (e) {
            $('engine-tag').textContent = '❌ 后端未响应';
        }
    }

    function getDialect() {
        const sel = document.querySelector('input[name="dialect"]:checked');
        return sel ? sel.value : 'auto';
    }

    function setStatus(text, cls) {
        const el = $('status');
        el.textContent = text;
        el.className = 'status ' + (cls || '');
    }

    // 清空上次结果（开始新一轮录音时）
    function clearPreviousResult() {
        $('result-raw').innerHTML = '<span style="color:#a0aec0;font-style:italic;">识别中...</span>';
        $('result-standard').textContent = '—';
        $('standard-cell').style.display = 'none';
        $('sentences-list').innerHTML = '';
        $('sentences-details').style.display = 'none';
        $('meta-engine').textContent = '—';
        $('meta-dialect').textContent = '—';
        $('meta-confidence').textContent = '—';
        $('meta-stt-latency').textContent = '—';
        $('meta-total-latency').textContent = '—';
    }

    // 关闭上一次的 audioContext 和 stream（防止泄漏）
    function cleanupPreviousStream() {
        if (stream) {
            try { stream.getTracks().forEach(t => t.stop()); } catch (e) {}
            stream = null;
        }
        if (audioContext && audioContext.state !== 'closed') {
            try { audioContext.close(); } catch (e) {}
            audioContext = null;
        }
        if (analyser) {
            try { analyser.disconnect(); } catch (e) {}
            analyser = null;
        }
        if (animFrameId) {
            cancelAnimationFrame(animFrameId);
            animFrameId = null;
        }
    }

    // ============================================================
    // 录音
    // ============================================================
    async function startRecord() {
        if (isProcessing) {
            console.warn('正在识别中，忽略新的录音请求');
            return;
        }

        try {
            // 清理上一次的 stream / context（防止占用麦克风）
            cleanupPreviousStream();

            stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000,
                }
            });

            audioChunks = [];
            // 优先 webm (Opus 编码，体积小)
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4');
            mediaRecorder = new MediaRecorder(stream, { mimeType });
            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };

            // 用 Promise 包装 onstop，stopRecord() await 这个 promise
            mediaRecorder._stopPromise = new Promise(resolve => {
                mediaRecorder.onstop = () => {
                    // 关键：只读本次的 audioChunks，不用全局 audioBlob
                    const blob = new Blob(audioChunks, { type: mimeType });
                    $('btn-playback').disabled = false;
                    $('audio-playback').src = URL.createObjectURL(blob);
                    $('audio-playback').style.display = 'block';
                    resolve(blob);
                };
            });

            mediaRecorder.start();
            setupWaveform(stream);

            // 清空旧结果（让用户明确看到"新一轮开始了"）
            clearPreviousResult();

            $('btn-record').disabled = true;
            $('btn-stop').disabled = false;
            setStatus('录音中...', 'recording');
        } catch (e) {
            console.error('录音启动失败', e);
            setStatus('麦克风权限被拒', 'error');
            alert('请允许浏览器使用麦克风');
        }
    }

    async function stopRecord() {
        if (isProcessing) return;
        if (!mediaRecorder || mediaRecorder.state === 'inactive') {
            setStatus('没有在录音', 'error');
            return;
        }

        isProcessing = true;
        $('btn-record').disabled = true;
        $('btn-stop').disabled = true;
        setStatus('Fun-ASR 1.5 识别中...', 'processing');

        try {
            // 停止录音（触发 onstop → _stopPromise resolve）
            mediaRecorder.stop();
            // 关掉 mic，避免持续占用
            if (stream) {
                stream.getTracks().forEach(t => t.stop());
            }

            // 等 onstop 真正完成
            const blob = await mediaRecorder._stopPromise;

            // 停波形
            if (animFrameId) cancelAnimationFrame(animFrameId);

            if (blob && blob.size > 0) {
                await uploadToServer(blob);
            } else {
                setStatus('没有录到音频', 'error');
            }
        } catch (e) {
            console.error('停止录音出错', e);
            setStatus('停止失败: ' + e.message, 'error');
        } finally {
            isProcessing = false;
            $('btn-record').disabled = false;
            $('btn-stop').disabled = true;
        }
    }

    function playAudio() {
        const a = $('audio-playback');
        if (a.paused) a.play(); else a.pause();
    }

    // ============================================================
    // 波形可视化
    // ============================================================
    function setupWaveform(s) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(s);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        source.connect(analyser);

        const canvas = $('waveform');
        const ctx = canvas.getContext('2d');
        const bufLen = analyser.frequencyBinCount;
        const data = new Uint8Array(bufLen);

        function draw() {
            animFrameId = requestAnimationFrame(draw);
            analyser.getByteTimeDomainData(data);
            ctx.fillStyle = '#1a202c';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#667eea';
            ctx.beginPath();
            const sliceW = canvas.width / bufLen;
            let x = 0;
            for (let i = 0; i < bufLen; i++) {
                const v = data[i] / 128.0;
                const y = (v * canvas.height) / 2;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
                x += sliceW;
            }
            ctx.stroke();
        }
        draw();
    }

    // ============================================================
    // 上传到 FastAPI 后端
    // ============================================================
    async function uploadToServer(blob) {
        const dialect = getDialect();
        const fd = new FormData();
        const ext = blob.type.includes('webm') ? 'webm'
                  : blob.type.includes('mp4') ? 'mp4'
                  : 'wav';
        // 用时间戳做文件名后端可调试 + 防缓存
        const filename = `recording_${Date.now()}.${ext}`;
        fd.append('file', blob, filename);
        fd.append('dialect', dialect);

        try {
            const r = await fetch('/api/transcribe?_t=' + Date.now(), {
                method: 'POST',
                body: fd,
                cache: 'no-store',
            });
            const data = await r.json();
            if (!data.ok) throw new Error(data.error || '识别失败');
            handleResult(data);
        } catch (e) {
            console.error(e);
            setStatus('错误: ' + e.message, 'error');
            alert('识别失败: ' + e.message);
        }
    }

    function handleResult(data) {
        setStatus('识别完成 ✅', 'done');

        // 元信息
        $('meta-engine').textContent = data.engine || '—';
        $('meta-dialect').textContent = data.detected_dialect || '—';
        $('meta-confidence').textContent =
            data.confidence != null ? data.confidence.toFixed(2) : '—';
        $('meta-stt-latency').textContent =
            (data.stt_latency_ms || 0) + ' ms';
        $('meta-total-latency').textContent =
            (data.total_latency_ms || 0) + ' ms';

        // 方言原文（高亮）
        const rawEl = $('result-raw');
        rawEl.innerHTML = '';   // 显式清空
        if (data.raw_text) {
            renderWithHighlights(rawEl, data.raw_text, data.highlights || []);
        } else {
            rawEl.textContent = '（无识别结果）';
        }

        // 标准普通话
        if (data.standard_text && data.standard_text !== data.raw_text) {
            $('standard-cell').style.display = 'block';
            $('result-standard').textContent = data.standard_text;
        } else {
            $('standard-cell').style.display = 'none';
        }

        // 句子时间戳
        const sents = data.sentences || [];
        if (sents.length > 0) {
            $('sentences-details').style.display = 'block';
            $('sent-count').textContent = sents.length;
            const list = $('sentences-list');
            list.innerHTML = '';
            sents.forEach((s, i) => {
                const div = document.createElement('div');
                div.className = 'sentence-item';
                const begin = s.begin_time != null ? formatMs(s.begin_time) : '—';
                const end = s.end_time != null ? formatMs(s.end_time) : '—';
                div.innerHTML = `<span class="sentence-time">#${i + 1}  ${begin} → ${end}</span><span class="sentence-text">${escapeHtml(s.text || '')}</span>`;
                list.appendChild(div);
            });
        } else {
            $('sentences-details').style.display = 'none';
        }

        $('result-panel').style.display = 'block';
        $('result-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });

        console.log('完整结果:', data);
    }

    function renderWithHighlights(el, text, highlights) {
        el.innerHTML = '';
        if (!text) {
            el.textContent = '—';
            return;
        }
        if (!highlights || highlights.length === 0) {
            el.textContent = text;
            return;
        }
        let cursor = 0;
        const sorted = highlights.slice().sort((a, b) => a.start - b.start);
        for (const h of sorted) {
            if (h.start > cursor) {
                el.appendChild(document.createTextNode(text.slice(cursor, h.start)));
            }
            const m = document.createElement('mark');
            m.textContent = text.slice(h.start, h.end);
            el.appendChild(m);
            cursor = h.end;
        }
        if (cursor < text.length) {
            el.appendChild(document.createTextNode(text.slice(cursor)));
        }
    }

    function formatMs(ms) {
        if (ms < 1000) return ms + 'ms';
        return (ms / 1000).toFixed(2) + 's';
    }

    function escapeHtml(s) {
        return s.replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[c]);
    }
})();
