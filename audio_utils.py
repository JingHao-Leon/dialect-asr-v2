"""
音频工具：使用 ffmpeg 在 webm (浏览器录音) ↔ wav/pcm (Fun-ASR 输入) 之间转换
"""
from __future__ import annotations
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger("audio")

FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")


def has_ffmpeg() -> bool:
    try:
        subprocess.run([FFMPEG_BIN, "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def webm_to_wav(webm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """
    把浏览器 MediaRecorder 录的 webm (Opus) 转成 Fun-ASR 需要的 16kHz mono PCM wav
    使用 ffmpeg 子进程
    """
    if not has_ffmpeg():
        raise RuntimeError("ffmpeg 未安装，请先 `brew install ffmpeg`")

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as in_f:
        in_f.write(webm_bytes)
        in_path = in_f.name

    out_path = in_path.replace(".webm", ".wav")
    try:
        cmd = [
            FFMPEG_BIN, "-y", "-loglevel", "error",
            "-i", in_path,
            "-ar", str(sample_rate),     # 采样率
            "-ac", "1",                  # 单声道
            "-f", "wav",
            "-acodec", "pcm_s16le",       # 16-bit PCM
            out_path,
        ]
        log.info("ffmpeg: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 转换失败: {result.stderr}")

        wav_bytes = Path(out_path).read_bytes()
        log.info("webm %.1fKB → wav %.1fKB", len(webm_bytes) / 1024, len(wav_bytes) / 1024)
        return wav_bytes
    finally:
        for p in (in_path, out_path):
            try:
                Path(p).unlink()
            except OSError:
                pass


def save_tmp(suffix: str, data: bytes) -> str:
    """保存字节到临时文件，返回路径"""
    f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    f.write(data)
    f.close()
    return f.name
