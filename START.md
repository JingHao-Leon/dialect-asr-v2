# 🚀 5 步上手（Windows / macOS / Linux 通用）

> 解压后 **5 分钟跑起来**。

---

## 步骤 1：解压

| 系统 | 命令 |
|------|------|
| Windows | 右键 zip → "全部解压" |
| macOS / Linux | `unzip 方言语音识别.zip -d dialect-stt` |

进目录：

```bash
cd dialect-stt     # Windows 在资源管理器双击进入也行
```

---

## 步骤 2：装两个工具

| 工具 | 必装？ | Windows 装法 | macOS 装法 | Linux 装法 |
|------|--------|--------------|------------|------------|
| **Python 3.9+** | ✅ | [python.org](https://www.python.org/downloads/) 下载安装，**勾选 "Add Python to PATH"** | `brew install python` 或自带 | `sudo apt install python3` |
| **ffmpeg** | ✅ | `choco install ffmpeg` 或 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 下载解压 | `brew install ffmpeg` | `sudo apt install ffmpeg` |

**验证安装成功**（在终端/cmd 里跑）：

```bash
python --version     # 应显示 Python 3.9+
ffmpeg -version      # 应显示版本号
```

---

## 步骤 3：填 API Key（如果 `config/dialect_stt.env` 里是占位符）

```bash
# 1. 打开 config/dialect_stt.env
# 2. 把 sk-REPLACE_WITH_YOUR_KEY 替换成你的真实 key
#    （key 申请: https://bailian.console.aliyun.com/ → API-Key 管理）
# 3. 保存
```

> 如果 `config/dialect_stt.env` 里已经是真 key，跳过这步。

---

## 步骤 4：启动

**Windows 用户**（双击运行最方便）：

```
双击 run.bat         ← 批处理版本（兼容性最好）
或
右键 run.ps1 → "使用 PowerShell 运行"   ← 颜色更漂亮
```

**macOS / Linux 用户**：

```bash
chmod +x run.sh
./run.sh
```

---

## 步骤 5：打开浏览器

**http://127.0.0.1:5001**

- 选方言 → 点"开始录音" → 说话 → 点"停止并识别"
- 1 秒后看到识别结果

---

## 常见问题

**Q: Windows 双击 run.bat 一闪而过 / 立刻关了？**
→ 右键 run.bat → "以管理员身份运行"。如果还不行，用 PowerShell 跑 `run.ps1` 看错误。

**Q: 报错 "无法加载文件 ... 因为在此系统上禁止运行脚本"**
→ PowerShell 默认禁止运行 .ps1。管理员打开 PowerShell 跑：
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
然后再双击 `run.ps1`。

**Q: 报错 "DASHSCOPE_API_KEY not configured"**
→ 没读到 key。检查 `config\dialect_stt.env` 存在且内容对（每行 `export DASHSCOPE_API_KEY=sk-...`）。

**Q: 报错 "ffmpeg not found"**
→ 装 ffmpeg 后**重启 cmd/PowerShell**（PATH 修改要重开终端才生效）。

**Q: 麦克风没反应**
→ 浏览器地址栏左边的小锁图标 → 允许麦克风权限。

**Q: 端口 5001 被占用**
→ 编辑 `run.bat` / `run.sh` / `run.ps1`，把 `--port 5001` 改成 `--port 8080` 之类。

**Q: 想停服务**
→ 在跑脚本的窗口按 `Ctrl+C`。

---

## 完整目录结构

```
dialect-stt/
├── START.md                  ← 你正在看的文件
├── app.py                    # FastAPI 主程序
├── stt_engine.py             # Fun-ASR 1.5 引擎
├── audio_utils.py            # 音频转码
├── dialect_processor.py      # 方言处理
├── run.sh                    # macOS / Linux 启动
├── run.bat                   # Windows 启动（批处理）
├── run.ps1                   # Windows 启动（PowerShell）
├── README.md                 # 详细文档
├── config/
│   ├── dialect_stt.env           ← 真实 key（解压后可能已有）
│   └── dialect_stt.env.template  ← 模板（占位符 key）
├── templates/index.html      # Web UI
├── static/{style.css,app.js}
└── 实践报告.md                # 课程设计报告
```
