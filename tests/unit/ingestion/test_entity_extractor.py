import pytest
from app.ingestion.graph_path.entity_extractor import extract_candidate_entities


def test_extract_basic_nouns():
    text = "阿里巴巴集团成立于1999年，总部位于杭州，创始人马云。"
    entities = extract_candidate_entities(text, top_k=10)

    assert isinstance(entities, list)
    assert len(entities) > 0
    assert all("name" in e and "score" in e and "type" in e for e in entities)
    names = [e["name"] for e in entities]
    assert any("杭州" in n for n in names) or any("阿里巴巴" in n for n in names)


def test_filter_non_nouns():
    text = "的 了 在 是 和 很 都 也 就 把"
    entities = extract_candidate_entities(text, top_k=10)
    assert len(entities) == 0


def test_empty_text():
    entities = extract_candidate_entities("", top_k=10)
    assert entities == []


def test_returns_top_k():
    text = """
    机器学习是人工智能的一个分支。深度神经网络在图像识别、自然语言处理和
    语音识别等领域取得了突破性进展。卷积神经网络和循环神经网络是两种常见架构。
    谷歌、微软、百度等公司投入大量资源研发。PyTorch和TensorFlow是主流框架。
    """
    entities = extract_candidate_entities(text, top_k=5)
    assert len(entities) <= 5