# 系统架构详解

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        浏览器前端 (Browser)                       │
│  ┌───────────────┐   ┌──────────────┐   ┌──────────────────┐    │
│  │ getUserMedia  │ → │ MediaRecorder│ → │ AudioContext     │    │
│  │ 麦克风采集     │   │ 音频录制     │   │ + AnalyserNode   │    │
│  │               │   │ (webm 编码)  │   │ 实时波形可视化    │    │
│  └───────────────┘   └──────────────┘   └──────────────────┘    │
│           │                                       │              │
│           │ PCM 16kHz                            │ FFT          │
│           ▼                                       ▼              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Web Speech API (webkitSpeechRecognition)       │    │
│  │   实时识别 · 边录边出字 · 支持 zh-CN/zh-HK/en-US          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────────┘
                              │ 识别文本 + 音频 (base64)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Flask 后端 (Backend)                       │
│  ┌──────────────────┐                                            │
│  │ 接收请求           │  /api/transcribe                         │
│  │ 解析 dialect      │                                            │
│  │ 解析 engine       │                                            │
│  └────────┬─────────┘                                            │
│           ▼                                                       │
│  ┌──────────────────────────────────────────┐                   │
│  │         STT 引擎路由器 (Strategy)          │                   │
│  │  ┌─────────┐ ┌────────┐ ┌─────────────┐  │                   │
│  │  │ browser │ │whisper │ │ paraformer  │  │                   │
│  │  └─────────┘ └────────┘ └─────────────┘  │                   │
│  └──────────────────┬───────────────────────┘                   │
│                     │ STTResult {text, confidence, latency}      │
│                     ▼                                            │
│  ┌──────────────────────────────────────────┐                   │
│  │     方言后处理器 (DialectProcessor)        │                   │
│  │  · 字典匹配（词长降序）                    │                   │
│  │  · 替换 + 记录替换位置                      │                   │
│  │  · 返回原句 + 方言表达 + 替换元数据          │                   │
│  └──────────────────┬───────────────────────┘                   │
│                     │ JSON                                       │
└─────────────────────┼───────────────────────────────────────────┘
                      ▼
              ┌───────────────────┐
              │   结果展示 UI       │
              │  · 原始识别        │
              │  · 方言表达        │
              │  · 元数据          │
              └───────────────────┘
```

## 数据流图

```
 麦克风输入 ──→ PCM 采样 ──→ 分帧 (25ms)
                              │
                              ├──→ Web Speech API ──→ 文本 (实时间)
                              │
                              └──→ 录音缓存 (webm)
                                        │
                                        ├──→ base64 编码
                                        │       │
                                        │       ▼
                                        │   Flask /api/transcribe
                                        │       │
                                        │       ├──→ STT 引擎 (whisper/paraformer)
                                        │       │       │
                                        │       │       ▼
                                        │       │   STTResult
                                        │       │       │
                                        │       │       ▼
                                        │       └──→ DialectProcessor
                                        │                   │
                                        │                   ▼
                                        │           {raw_text, dialect_text, meta}
                                        │                   │
                                        │                   ▼
                                        └───────────→ JSON 响应
                                                            │
                                                            ▼
                                                     前端结果展示
```

## 模块设计

### 1. 浏览器前端 (static/app.js, templates/index.html)

**职责**：
- 音频采集（getUserMedia + MediaRecorder）
- 实时波形（AudioContext + AnalyserNode）
- 实时识别（SpeechRecognition）
- 用户交互（方言选择、引擎选择、按钮事件）

**状态机**：
```
[idle] ──click record──→ [recording] ──click stop──→ [processing] ──response──→ [done]
```

### 2. Flask 后端 (app.py)

**职责**：
- 路由分发（`/`、`/api/transcribe`、`/api/dialects`、`/api/health`）
- 参数解析
- 错误处理

### 3. STT 引擎 (stt_engine.py)

**接口契约**：
```python
def transcribe(engine, dialect, audio_b64, raw_text) -> STTResult
```

**注册表模式**：
```python
_ENGINES = {
    "browser": {"fn": _engine_browser, ...},
    "whisper": {"fn": _engine_whisper, ...},
    "paraformer": {"fn": _engine_paraformer, ...},
}
```

### 4. 方言后处理 (dialect_processor.py)

**算法**：
1. 方言类别判断（直通 vs 字典替换）
2. 字典按词长降序排列
3. 逐条正则替换
4. 记录替换位置用于前端展示

**复杂度**：O(n·m)，n 为文本长度，m 为字典条目数。

## 部署架构（可选）

```
                   Internet
                      │
                      ▼
            ┌──────────────────┐
            │   Nginx 反代      │
            │   (HTTPS + WSS)  │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐
            │   Flask + Gunicorn│
            │   (4 workers)    │
            └────────┬─────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   ┌────────┐  ┌──────────┐  ┌────────┐
   │Whisper │  │Paraformer│  │ Web    │
   │  API   │  │  API     │  │Speech  │
   └────────┘  └──────────┘  └────────┘
```
