@echo off
REM ========================================
REM  方言语音识别系统 v2.0 - Windows 启动
REM  这个 .bat 是双击入口
REM  实际启动在 PowerShell 独立窗口里跑（避开 cmd 编码坑）
REM ========================================

REM 在新窗口启动 PowerShell 执行 run.ps1
start "方言语音识别 v2.0" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
