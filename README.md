# 方言语音识别系统 v2.0 / Dialect Speech Recognition

> **基于 FastAPI + 阿里云百炼 Fun-ASR 1.5** 的多方言语音识别 Web 应用  
> 7 大方言体系 + 30 种语言 · 29 个可选项 · 自动检测语种

## ✨ 特性

- 🚀 **Fun-ASR 1.5** —— 阿里通义实验室 2026-04 发布的新一代语音识别大模型，MoE 架构
  - 字错误率（CER）较前代 ↓56.2%
  - 5 种方言准确率 > 90%，15 种 > 80%
  - 30 种语言 + 汉语七大方言 + 20+ 地方口音
  - 智能文本规范化（自动加标点、数字日期转标准格式）
- ⚡ **FastAPI 后端** —— 异步、高性能、自动生成 OpenAPI 文档
- 🪄 **自动语种检测** —— Fun-ASR 1.5 支持零样本跨语言识别
- 🎯 **方言提示** —— 可显式指定期望方言，提升识别准确度
- 📊 **可视化结果** —— 方言原文（高亮）+ 标准普通话归一化（Qwen LLM）+ 句子级时间戳
- 🎤 **浏览器原生录音** —— MediaRecorder + AudioContext 实时波形

## 🚀 快速开始（解压即用）

### 1. 解压 + 安装依赖

```bash
unzip 方言语音识别.zip
cd 方言语音识别
pip install fastapi uvicorn python-multipart dashscope
brew install ffmpeg        # macOS 装 ffmpeg；Linux: apt install ffmpeg
```

### 2. 启动

```bash
./run.sh
```

脚本会自动：
- 加载 `config/dialect_stt.env` 里的 API Key
- 启动 FastAPI 在 5001 端口

### 3. 访问

打开浏览器：**http://127.0.0.1:5001**

- **API 文档**（FastAPI 自动生成）：http://127.0.0.1:5001/docs
- **健康检查**：http://127.0.0.1:5001/api/health

## 🔑 API Key 管理

项目已经自带 key 在 `config/dialect_stt.env`（权限 600），**解压即用**。

**优先级**（`app.py` 启动时按这个顺序找）：

1. **环境变量**（最高优先）
   ```bash
   export DASHSCOPE_API_KEY=sk-xxx
   ```
2. **项目内** `config/dialect_stt.env`（解压即用版）
3. **用户级** `~/.config/dialect_stt.env`（你机器上其他项目可能也用）

**要换 key**，直接改 `config/dialect_stt.env` 那一个文件就行（chmod 600 自动设置）。

## 📁 项目结构

```
方言语音识别/
├── app.py                  # FastAPI 主程序
├── stt_engine.py           # Fun-ASR 1.5 封装（dashscope SDK）
├── audio_utils.py          # ffmpeg 音频转换
├── dialect_processor.py    # 方言特征检测 + Qwen 归一化
├── config/
│   └── dialect_stt.env     # API Key（chmod 600，解压即用）
├── templates/index.html    # Web UI（29 种方言选择）
├── static/{style.css,app.js}  # 前端
├── 实践报告.md              # 课程设计报告
└── run.sh                  # 一键启动
```

## 🛠️ API 接口

### `POST /api/transcribe`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | ✅ | 音频文件（wav/mp3/webm/opus/m4a/...） |
| dialect | str | ❌ | 方言提示：见下方 29 种选项 |

**支持的 dialect 值**（29 种）：
- **通用** (5)：`auto` `普通话` `英语` `日语` `韩语`
- **七大方言体系** (6)：`粤语` `吴语` `闽语` `客家话` `湘语` `赣语`
- **官话子方言** (15)：`东北话` `北京话` `天津话` `山东话` `河南话` `陕西话` `甘肃话` `宁夏话` `山西话` `四川话` `云南话` `贵州话` `湖北话` `湖南话` `江西话`
- **吴语子方言** (4)：`上海话` `苏州话` `杭州话` `宁波话`
- **闽语子方言** (4)：`闽南语` `潮汕话` `闽东话` `闽北话`
- **其他语言** (8)：`俄语` `法语` `西班牙语` `阿拉伯语` `泰语` `越南语` `印尼语` `马来语`

**返回**：
```json
{
  "ok": true,
  "engine": "fun-asr-realtime-1.5",
  "raw_text": "侬好，今朝天气真好啊",
  "detected_dialect": "上海话",
  "standard_text": "你好，今天天气真好",
  "highlights": [{"word": "侬", "start": 0, "end": 1}],
  "confidence": 0.96,
  "stt_latency_ms": 997,
  "total_latency_ms": 1050,
  "sentences": [{"text": "侬好，今朝天气真好啊", "begin_time": 0, "end_time": 2400}]
}
```

### `GET /api/health`

健康检查 + 引擎状态。

## ⚠️ 关于 key 泄露

`config/dialect_stt.env` 包含真实 API key，**整个项目目录请勿分享给第三方**（zip 整体发送 = 暴露 key）。

如果 key 被泄露（聊天记录、git push、邮件附件等），**立刻去** https://bailian.console.aliyun.com/ **删旧建新**。

## 💰 费用参考

- Fun-ASR 1.5：约 ¥0.0001/秒（每月有免费额度）
- Qwen-turbo：约 ¥0.003/千 tokens（用于方言归一化，可选）

## 📝 配套文档

- `实践报告.md` —— 8000 字课程设计报告（原理 + 步骤 + 总结）
