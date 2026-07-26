"""
方言语音识别系统 - FastAPI 主程序
Dialect Speech Recognition Web App (Fun-ASR 1.5 + FastAPI)

流程：
    浏览器 (MediaRecorder 录 webm)
        ↓ POST /api/transcribe (multipart)
    FastAPI 后端
        ↓ ffmpeg 转 wav
        ↓ Fun-ASR 1.5 识别（自动判断语种 + 方言）
        ↓ 方言后处理（高亮 + 可选 LLM 归一化）
        ↓ JSON 返回
"""
import os
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from stt_engine import get_engine, STTResult
from dialect_processor import DialectProcessor
from audio_utils import webm_to_wav, save_tmp, has_ffmpeg

# ============================================================
# 配置（按需修改）
# ============================================================
APP_ROOT = Path(__file__).parent
SAMPLES_DIR = APP_ROOT / "samples"
SAMPLES_DIR.mkdir(exist_ok=True)


def _load_api_key() -> str:
    """
    按优先级加载 DASHSCOPE_API_KEY：
    1. 环境变量（最高优先，方便 CI/CD 覆盖）
    2. 项目内 config/dialect_stt.env（解压即用，权限 600）
    3. ~/.config/dialect_stt.env（用户级配置）
    """
    env_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if env_key:
        return env_key

    # 项目内 config（首次解压即用）
    proj_env = APP_ROOT / "config" / "dialect_stt.env"
    if proj_env.exists():
        for line in proj_env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export DASHSCOPE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
            if line.startswith("DASHSCOPE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    # 用户级 ~/.config
    home_env = Path.home() / ".config" / "dialect_stt.env"
    if home_env.exists():
        for line in home_env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export DASHSCOPE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
            if line.startswith("DASHSCOPE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    return ""


DASHSCOPE_API_KEY = _load_api_key()
MAX_AUDIO_MB = 25
ALLOWED_EXT = {"wav", "mp3", "m4a", "webm", "ogg", "flac", "opus", "mp4"}

# ============================================================
# 应用初始化
# ============================================================
app = FastAPI(
    title="方言语音识别系统",
    description="基于阿里云百炼 Fun-ASR 1.5 的多方言语音识别 Web 应用",
    version="2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态资源
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "static")), name="static")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("app")

stt = get_engine(api_key=DASHSCOPE_API_KEY or None)
dialect_proc = DialectProcessor()


# ============================================================
# 路由
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def index():
    """主页：方言语音识别 Web UI"""
    html = (APP_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/health")
async def health():
    from dialect_processor import DIALECT_MARKERS
    return {
        "ok": True,
        "engine": stt.status(),
        "ffmpeg": has_ffmpeg(),
        "max_audio_mb": MAX_AUDIO_MB,
        "dialects_supported": list(DIALECT_MARKERS.keys()) + ["普通话", "auto"],
        "dialect_markers_count": {d: len(m) for d, m in DIALECT_MARKERS.items()},
    }


@app.post("/api/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    dialect: str = Form("auto"),
):
    """
    转写接口

    Args:
        file: 音频文件（浏览器 webm / wav / mp3 等）
        dialect: 期望方言提示（auto / 普通话 / 粤语 / 上海话 / 四川话 / 闽南语 / 英语）

    Returns:
        JSON: {
            ok, dialect, raw_text, standard_text, detected_dialect,
            confidence, latency_ms, sentences, highlights, engine
        }
    """
    if not stt.available():
        raise HTTPException(503, "Fun-ASR 未配置：缺少 DASHSCOPE_API_KEY")

    if not file.filename:
        raise HTTPException(400, "no_file")

    suffix = Path(file.filename).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_EXT:
        raise HTTPException(400, f"unsupported_format: {suffix}")

    log.info("transcribe: dialect=%s filename=%s", dialect, file.filename)

    # 1. 读上传
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_AUDIO_MB * 1024 * 1024:
        raise HTTPException(413, f"file_too_large: {len(raw_bytes) / 1024 / 1024:.1f}MB > {MAX_AUDIO_MB}MB")

    t0 = time.time()
    try:
        # 2. 转 wav (webm/opus → wav/pcm 16kHz mono)
        if suffix == "wav":
            wav_bytes = raw_bytes
        else:
            wav_bytes = webm_to_wav(raw_bytes, sample_rate=16000)

        # 3. 落临时文件
        wav_path = save_tmp(".wav", wav_bytes)

        try:
            # 4. Fun-ASR 1.5 识别
            result: STTResult = stt.transcribe_file(
                wav_path=wav_path,
                dialect_hint=dialect,
                sample_rate=16000,
            )
        finally:
            try:
                Path(wav_path).unlink()
            except OSError:
                pass

        # 5. 方言后处理
        post = dialect_proc.process(result.text, dialect_hint=dialect)

        total_ms = int((time.time() - t0) * 1000)

        return JSONResponse({
            "ok": True,
            "engine": result.engine,
            "model_name": stt.MODEL_NAME,
            "dialect_hint": dialect,
            "raw_text": result.text,                # Fun-ASR 输出（可能是方言）
            "standard_text": post["standard_text"], # LLM 归一化（普通话）
            "detected_dialect": post["detected_dialect"],
            "used_dialect": post["used_dialect"],
            "highlights": post["highlights"],
            "confidence": round(result.confidence, 3),
            "stt_latency_ms": result.latency_ms,
            "total_latency_ms": total_ms,
            "sentences": result.sentences or [],
            "llm_normalize": post["llm_normalize"],
        })
    except HTTPException:
        raise
    except Exception as e:
        log.exception("transcribe failed")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  方言语音识别系统  v2.0")
    print("  Dialect Speech Recognition with Fun-ASR 1.5")
    print("=" * 60)
    print(f"  Fun-ASR 1.5:    {'✅ ' + stt.MODEL_NAME if stt.available() else '⚠️  未配置 DASHSCOPE_API_KEY'}")
    print(f"  ffmpeg:         {'✅' if has_ffmpeg() else '⚠️  未安装（需 brew install ffmpeg）'}")
    print(f"  端口:           5001")
    print("=" * 60)
    uvicorn.run("app:app", host="0.0.0.0", port=5001, reload=False)
