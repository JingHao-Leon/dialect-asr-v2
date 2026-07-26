"""
方言后处理 / Dialect Post-Processor

Fun-ASR 1.5 已经原生支持 7 大中文方言（自动识别），输出地道方言文字：
  - 普通话：标准书面语
  - 粤语：粤字 + 标准表达
  - 上海话："侬好""阿拉""今朝"
  - 闽南语："阮""食饭""厝"
  - 四川话："啥子""摆龙门阵"
  - 等

本模块提供三个增强能力（可选）：

1. `detect_dialect(text)`       — 根据输出文本粗判语种（用于 UI 显示）
2. `dialect_to_standard(text, dialect)` — 调用 Qwen LLM 把方言文本归一化为标准普通话
   （用于"对照展示"功能：原始方言 vs 标准普通话转写）
3. `highlight_words(text, dialect)`     — 把方言特征词高亮返回（用于前端高亮显示）

LLM 归一化是可选的：未配置 QWEN_API_KEY 时跳过，返回原文。
"""
from __future__ import annotations
import logging
import os
import re
from typing import Optional, Tuple

log = logging.getLogger("dialect")


# ============================================================
# 方言特征词字典（用于高亮显示 + 语种粗判）
# 覆盖 Fun-ASR 1.5 全部支持的 7 大方言 + 17 官话子方言 + 4 吴语 + 4 闽语
# ============================================================
DIALECT_MARKERS: dict[str, list[str]] = {
    # === 七大方言体系 ===
    "粤语": ["唔", "咁", "嘅", "睇", "食饭", "边个", "乜嘢", "点解", "系", "喺", "咩", "梗系", "嘅", "噉", "𠼱啲"],
    "吴语": ["阿拉", "侬", "伊", "额", "今朝", "邪气", "铜钿", "结棍", "小囡", "物事", "迭个", "覅", "蛮", "老"],
    "闽语": ["阮", "恁", "伊", "厝", "食饭", "头家", "厝边", "头毛", "目睭", "彼个", "按怎", "啥物", "汝", "即马"],
    "客家话": ["𠊎", "食朝", "食昼", "食夜", "𠊎屋下", "𠊎等", "今晡日", "𠊎兜", "你食过吂"],
    "湘语": ["堂客", "嬲塞", "几好", "咯只", "嗯只", "么子", "何解", "冇"],
    "赣语": ["几好", "嗯的", "样个", "里个", "几多", "冇"],
    # === 官话子方言 ===
    "东北话": ["整", "唠", "咋", "干哈", "嘎哈", "埋汰", "磕碜", "得瑟", "嘚嘚", "波棱盖", "老铁", "杠杠的"],
    "北京话": ["您", "哥们儿", "丫的", "甭", "您内", "咱", "搁", "哪门子", "怎么茬儿", "地道"],
    "天津话": ["姐姐", "二梆子", "嘛钱", "嘛呢", "崴泥", "嘛玩儿", "结界", "似了似了"],
    "山东话": ["么样", "杠赛来", "么", "恁", "俺", "啥", "白", "血", "杠好来", "忒好"],
    "河南话": ["弄啥嘞", "恁", "中", "咋", "啥", "哩", "恁弄", "可管", "得劲", "老鳖一"],
    "陕西话": ["嘹咋咧", "谝闲传", "撩", "嘹", "克里马擦", "囊", "得是", "谝", "咥", "么麻达"],
    "甘肃话": ["撒", "央个", "央", "尕", "阿", "咋", "呢吗", "撒子", "干撒"],
    "宁夏话": ["撒", "咧", "嘛", "嘎哈", "得是", "整撒", "嘞", "嘛达"],
    "山西话": ["圪蹴", "莜面", "圪", "咂", "兀", "孬", "后生", "兀那", "能行", "闹机机"],
    "四川话": ["啥子", "咋个", "巴适", "摆龙门阵", "莫得", "安逸", "雄起", "瓜娃子", "龟儿子", "恼火", "凶", "要得", "莫得", "晓得"],
    "云南话": ["整哪样", "给是", "咋个", "么么", "嘎", "整", "老庚", "呢咩", "咋整"],
    "贵州话": ["搞哪样", "嗯", "啥子", "咋个", "要得", "克哪点", "搞哪样", "老火"],
    "湖北话": ["么斯", "搞么斯", "冇得", "蛮", "几", "不", "晓得", "苕", "个板马", "弯管子"],
    "湖南话": ["堂客", "嬲塞", "几好", "咯只", "么子", "堂客们", "伢子", "妹陀", "醒豁"],
    "江西话": ["几好", "嗯的", "样个", "里个", "几多", "冇", "话事", "嗯个", "舌里"],
    # === 吴语子方言（沿用吴语 marker）===
    "上海话": ["阿拉", "侬", "伊", "额", "今朝", "邪气", "铜钿", "结棍", "小囡", "物事", "迭个", "覅", "阿拉"],
    "苏州话": ["阿拉", "侬", "伊", "倷", "今朝", "邪气", "结棍", "小囡", "物事", "勿"],
    "杭州话": ["阿拉", "侬", "伊", "儿", "个", "今朝", "个毛", "儿"],
    "宁波话": ["阿拉", "侬", "伊", "阿拉", "今朝", "邪气", "老", "结棍"],
    # === 闽语子方言（沿用闽语 marker）===
    "闽南语": ["阮", "恁", "伊", "厝", "食饭", "头家", "厝边", "头毛", "目睭", "彼个", "按怎", "啥物"],
    "潮汕话": ["阮", "恁", "伊", "厝", "食饭", "头家", "胶己人", "食糜", "今晡", "佮"],
    "闽东话": ["我", "汝", "伊", "厝", "食饭", "其", "𠮾", "乇"],
    "闽北话": ["我", "汝", "伊", "厝", "食饭", "其", "建瓯", "建阳"],
}


def detect_dialect(text: str) -> str:
    """根据文本中的方言特征词粗判方言（不保证准确，仅供 UI 提示）"""
    if not text:
        return "未知"
    best, best_score = "普通话", 0
    for dialect, markers in DIALECT_MARKERS.items():
        score = sum(1 for m in markers if m in text)
        if score > best_score:
            best, best_score = dialect, score
    return best if best_score > 0 else "普通话"


def highlight_words(text: str, dialect: str) -> list[dict]:
    """
    把方言特征词在文本中的位置标出来
    返回: [{"word": "...", "start": int, "end": int}, ...]
    """
    markers = DIALECT_MARKERS.get(dialect, [])
    if not markers or not text:
        return []
    out = []
    for m in markers:
        for match in re.finditer(re.escape(m), text):
            out.append({"word": m, "start": match.start(), "end": match.end()})
    out.sort(key=lambda x: x["start"])
    return out


# ============================================================
# 可选：调用 Qwen 把方言归一化为标准普通话
# ============================================================
def dialect_to_standard(text: str, dialect: str) -> Tuple[str, dict]:
    """
    调用 Qwen LLM 把方言文本翻译/转写为标准普通话
    未配置 API 时返回原文
    """
    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip() or os.environ.get("QWEN_API_KEY", "").strip()
    if not api_key or not text:
        return text, {"applied": False, "reason": "no_api_key_or_empty"}

    if dialect in ("普通话", "auto", "未知"):
        return text, {"applied": False, "reason": "already_mandarin"}

    try:
        import dashscope
        dashscope.api_key = api_key
        from dashscope import Generation

        prompt = f"""请把下面这段【{dialect}】口语化表达转写为标准普通话书面语。
要求：
1. 保持原意不变
2. 转换为规范的书面表达
3. 去除方言语气词，保留核心信息
4. 直接输出转写结果，不要解释

方言原文：
{text}

标准普通话："""

        resp = Generation.call(
            model="qwen-turbo",
            prompt=prompt,
            result_format="message",
        )
        if resp.status_code == 200:
            standard = resp.output.choices[0].message.content.strip()
            return standard, {
                "applied": True,
                "dialect": dialect,
                "model": "qwen-turbo",
            }
        else:
            log.warning("Qwen 归一化失败: %s", resp.message)
            return text, {"applied": False, "reason": resp.message}
    except Exception as e:
        log.exception("方言归一化失败")
        return text, {"applied": False, "reason": str(e)}


class DialectProcessor:
    """统一接口"""
    def process(self, text: str, dialect_hint: str = "auto") -> dict:
        detected = detect_dialect(text)
        used = dialect_hint if dialect_hint and dialect_hint != "auto" else detected
        standard, llm_meta = dialect_to_standard(text, used)
        highlights = highlight_words(text, used)
        return {
            "detected_dialect": detected,
            "used_dialect": used,
            "dialect_text": text,                # Fun-ASR 原始输出（方言）
            "standard_text": standard,           # LLM 归一化（普通话）
            "highlights": highlights,            # 高亮位置
            "llm_normalize": llm_meta,           # 归一化元信息
        }
