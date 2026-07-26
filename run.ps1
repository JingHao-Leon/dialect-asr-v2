# 方言语音识别系统 - Windows 启动脚本 (PowerShell)
# 双击运行 / 右键"用 PowerShell 运行"

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "方言语音识别 v2.0 (Windows)"

# 颜色输出
function Write-Step($msg) { Write-Host "[$msg]" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  [X] $msg" -ForegroundColor Red }

Clear-Host
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  方言语音识别系统 v2.0  (Windows)" -ForegroundColor Cyan
Write-Host "  FastAPI + Fun-ASR 1.5" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ---- Python ----
try {
    $py = (Get-Command python -ErrorAction Stop).Source
    $ver = & python --version 2>&1
    Write-OK "Python: $ver"
} catch {
    Write-Err "未找到 Python"
    Write-Warn "下载: https://www.python.org/downloads/"
    Write-Warn "安装时务必勾选 'Add Python to PATH'"
    Read-Host "按回车退出"
    exit 1
}

# ---- ffmpeg ----
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpeg) {
    Write-OK "ffmpeg: $($ffmpeg.Source)"
} else {
    Write-Warn "未检测到 ffmpeg（音频转码会失败）"
    Write-Warn "  安装: choco install ffmpeg"
    Write-Warn "     或: https://www.gyan.dev/ffmpeg/builds/"
}

Write-Host ""
Write-Step "1/3 安装 Python 依赖..."
& python -m pip install -q fastapi uvicorn python-multipart dashscope
if ($LASTEXITCODE -ne 0) {
    Write-Err "依赖安装失败"
    Write-Host ""
    Read-Host "按回车退出"
    exit 1
}

Write-Step "2/3 加载 API Key..."
$envFile = "config\dialect_stt.env"
if (-not (Test-Path $envFile)) {
    Write-Err "未找到 $envFile"
    Write-Warn "请从 config\dialect_stt.env.template 复制并填入 key"
    Read-Host "按回车退出"
    exit 1
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^export\s+DASHSCOPE_API_KEY=(.+)$') {
        $env:DASHSCOPE_API_KEY = $Matches[1].Trim().Trim('"').Trim("'")
    } elseif ($_ -match '^DASHSCOPE_API_KEY=(.+)$') {
        $env:DASHSCOPE_API_KEY = $Matches[1].Trim().Trim('"').Trim("'")
    }
}
Write-OK "Key: $($env:DASHSCOPE_API_KEY.Substring(0, 6))..."

Write-Step "3/3 启动服务（端口 5001）..."
Write-Host ""
Write-Host "  打开浏览器: " -NoNewline
Write-Host "http://127.0.0.1:5001" -ForegroundColor Green
Write-Host "  API 文档:   " -NoNewline
Write-Host "http://127.0.0.1:5001/docs" -ForegroundColor Green
Write-Host ""
Write-Host "  按 Ctrl+C 停止" -ForegroundColor DarkGray
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
& python -m uvicorn app:app --host 0.0.0.0 --port 5001

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Err "服务异常退出"
    Read-Host "按回车关闭"
}
