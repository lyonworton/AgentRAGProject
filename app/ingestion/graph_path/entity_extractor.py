from collections import Counter
import math
import jieba.posseg as pseg

_POS_TYPE_MAP = {
    "n": "concept",
    "nr": "person",
    "ns": "location",
    "nt": "organization",
    "nz": "term",
}

_KEEP_POS = set(_POS_TYPE_MAP.keys())

_STOP_WORDS = {
    "文档", "页面", "文件", "部分", "内容", "信息", "数据",
    "问题", "方法", "方式", "过程", "结果", "情况", "方面",
    "时间", "系统", "用户", "功能", "使用", "可以", "需要",
}


def extract_candidate_entities(text: str, top_k: int = 50) -> list[dict]:
    """从文本中提取候选实体（jieba 分词 + TF-IDF 加权）。

    Args:
        text: 输入文本
        top_k: 返回的候选实体数量上限

    Returns:
        [{"name": str, "score": float, "type": str}, ...]
    """
    if not text or not text.strip():
        return []

    words = list(pseg.cut(text))

    nouns = [
        (w.word, w.flag)
        for w in words
        if w.flag in _KEEP_POS and len(w.word) >= 2 and w.word not in _STOP_WORDS
    ]

    if not nouns:
        return []

    word_counts = Counter(w[0] for w in nouns)

    seen = {}
    for word, flag in nouns:
        if word not in seen:
            seen[word] = flag

    total = sum(word_counts.values())
    doc_count = len(word_counts)

    scored = []
    for word, count in word_counts.items():
        tf = count / total
        idf = math.log((doc_count + 1) / (count + 1)) + 1
        score = tf * idf
        scored.append((word, score, seen[word]))

    scored.sort(key=lambda x: x[1], reverse=True)

    return [
        {"name": word, "score": round(score, 4), "type": _POS_TYPE_MAP.get(flag, "concept")}
        for word, score, flag in scored[:top_k]
    ]