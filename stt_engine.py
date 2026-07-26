"""
STT 引擎：封装阿里云百炼 Fun-ASR 1.5

参考：
    - 文档: https://help.aliyun.com/zh/model-studio/developer-reference/funasr-api
    - 模型: Fun-ASR 1.5（基于 MoE 架构，30 种语言 + 7 大中文方言）
    - 平台: 阿里云百炼（DashScope）

特点：
    - 自动识别语种/方言，无需指定 language
    - 字符错误率（CER）较前代下降 56.2%
    - 5 种方言准确率突破 90%，15 种超过 80%
    - 智能文本规范化：自动加标点、数字日期金额转标准格式

调用方式：
    - 文件模式（推荐本项目用）: Recognition.call(model='fun-asr', ...)
    - 流式模式: Recognition.start() + send_audio_frame() + stop()
"""
from __future__ import annotations
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

log = logging.getLogger("stt")


@dataclass
class STTResult:
    """STT 输出"""
    text: str
    language: str = ""          # 识别出的语种（zh / en / yue 等）
    confidence: float = 0.0
    engine: str = "fun-asr-1.5"
    latency_ms: int = 0
    sentences: list = None      # 句子级时间戳
    raw: dict = None

    def to_dict(self):
        return asdict(self)


class FunASREngine:
    """Fun-ASR 1.5 文件转写封装"""

    # Fun-ASR 1.5 在 DashScope 中的 model name
    # 注意：API 实际 model 字段是 "fun-asr-realtime"（已实测）
    # Fun-ASR 1.5 是产品名（MoE 架构），fun-asr-realtime 是 SDK 调用名
    MODEL_NAME = "fun-asr-realtime"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "").strip()
        if self.api_key:
            import dashscope
            dashscope.api_key = self.api_key

    def available(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict:
        return {
            "available": self.available(),
            "model": self.MODEL_NAME,
            "reason": "DASHSCOPE_API_KEY 已配置" if self.api_key else "未配置 DASHSCOPE_API_KEY",
        }

    def transcribe_file(
        self,
        wav_path: str,
        dialect_hint: Optional[str] = None,
        sample_rate: int = 16000,
    ) -> STTResult:
        """
        转写一个本地 wav 文件

        Args:
            wav_path: 已转为 wav/pcm 16kHz mono 的音频文件路径
            dialect_hint: 可选方言提示（zh / yue / en / ja / ko），Fun-ASR 1.5 也支持自动检测
            sample_rate: 采样率（应与 wav 文件一致）

        Returns:
            STTResult
        """
        if not self.available():
            raise RuntimeError("Fun-ASR 不可用：请设置 DASHSCOPE_API_KEY")

        from http import HTTPStatus
        from dashscope.audio.asr import Recognition

        t0 = time.time()

        # 可选：language_hints（Fun-ASR 1.5 也支持不传，自动检测）
        kwargs = {}
        if dialect_hint and dialect_hint != "auto":
            # Fun-ASR 1.5 完整方言/语言映射表
            # 七大方言体系 + 17 官话子方言 + 8 世界语言
            lang_map = {
                # 通用
                "普通话": "zh",
                "英语": "en",
                "日语": "ja",
                "韩语": "ko",
                # 七大方言体系
                "粤语": "yue",
                "吴语": "wuu",
                "闽语": "nan",
                "客家话": "hak",
                "湘语": "xiang",
                "赣语": "gan",
                # 17 官话子方言（hint 全部给 zh，Fun-ASR 自动识别细节口音）
                "东北话": "zh",
                "北京话": "zh",
                "天津话": "zh",
                "山东话": "zh",
                "河南话": "zh",
                "陕西话": "zh",
                "甘肃话": "zh",
                "宁夏话": "zh",
                "山西话": "zh",
                "四川话": "zh",
                "云南话": "zh",
                "贵州话": "zh",
                "湖北话": "zh",
                "湖南话": "zh",
                "江西话": "zh",
                # 吴语子方言
                "上海话": "wuu",
                "苏州话": "wuu",
                "杭州话": "wuu",
                "宁波话": "wuu",
                # 闽语子方言
                "闽南语": "nan",
                "潮汕话": "nan",
                "闽东话": "nan",
                "闽北话": "nan",
                # 其他世界语言
                "俄语": "ru",
                "法语": "fr",
                "西班牙语": "es",
                "阿拉伯语": "ar",
                "泰语": "th",
                "越南语": "vi",
                "印尼语": "id",
                "马来语": "ms",
            }
            hint = lang_map.get(dialect_hint, "zh")
            kwargs["language_hints"] = [hint]

        log.info("Fun-ASR call: model=%s file=%s hints=%s",
                 self.MODEL_NAME, wav_path, kwargs.get("language_hints"))

        recognition = Recognition(
            model=self.MODEL_NAME,
            format="wav",
            sample_rate=sample_rate,
            callback=None,
            **kwargs,
        )
        result = recognition.call(wav_path)

        latency_ms = int((time.time() - t0) * 1000)

        if result is None or getattr(result, "status_code", None) != HTTPStatus.OK:
            msg = getattr(result, "message", "unknown") if result else "no response"
            raise RuntimeError(f"Fun-ASR 调用失败: {msg}")

        # 解析结果
        text, conf, sentences, lang = self._parse_result(result)

        return STTResult(
            text=text,
            language=lang,
            confidence=conf,
            engine=f"{self.MODEL_NAME}-1.5",
            latency_ms=latency_ms,
            sentences=sentences,
            raw={"status": "ok", "request_id": getattr(result, "request_id", None)},
        )

    @staticmethod
    def _parse_result(result) -> tuple[str, float, list, str]:
        """从 DashScope RecognitionResult 提取文本、置信度、句子、语言"""
        text_parts = []
        sentences = []
        confidences = []
        lang = ""

        # 优先用 get_sentence()（SDK 推荐接口）
        try:
            for sent in result.get_sentence():
                t = sent.get("text", "")
                if t:
                    text_parts.append(t)
                sentences.append({
                    "text": t,
                    "begin_time": sent.get("begin_time"),
                    "end_time": sent.get("end_time"),
                })
                if sent.get("confidence") is not None:
                    confidences.append(sent["confidence"])
        except Exception as e:
            log.warning("get_sentence() 解析失败: %s", e)

        # 整体文本
        if not text_parts:
            try:
                output = result.output
                if isinstance(output, dict):
                    text_parts.append(output.get("text", ""))
            except Exception:
                pass

        text = "".join(text_parts).strip()
        conf = sum(confidences) / len(confidences) if confidences else 0.9
        return text, conf, sentences, lang


# 全局单例
_engine: Optional[FunASREngine] = None


def get_engine(api_key: Optional[str] = None) -> FunASREngine:
    global _engine
    if _engine is None:
        _engine = FunASREngine(api_key=api_key)
    return _engine
