# -*- coding: utf-8 -*-
"""Recovery RAG 真实数据检索测试 —— 直接搜已入库的三本跑步指南。

前提：需先运行 python -m training_agents.rag.build_index 完成入库。
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


# ── 检查 Milvus 是否可用 ─────────────────────────────────────

def _milvus_ready():
    """检查 training_knowledge collection 是否存在且有数据。"""
    try:
        from pymilvus import MilvusClient
        from training_agents.rag.config import MILVUS_URI, COLLECTION_NAME

        client = MilvusClient(uri=MILVUS_URI)
        if not client.has_collection(COLLECTION_NAME):
            return False
        stats = client.get_collection_stats(COLLECTION_NAME)
        return stats.get("row_count", 0) > 0
    except Exception:
        return False


IS_MILVUS_READY = _milvus_ready()


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def retrieve_fn():
    """导入 retrieve 函数。"""
    from training_agents.rag.retrieval import retrieve
    return retrieve


# ── 测试用例 ──────────────────────────────────────────────────

@pytest.mark.skipif(not IS_MILVUS_READY, reason="Milvus 库未就绪，先运行 build_index")
class TestRecoveryRAG:
    """基于真实跑步书籍的 RAG 检索测试。"""

    # ── 关键词基线（三本书中常见的中文跑步/恢复术语） ────────
    RECOVERY_KEYWORDS = [
        "恢复", "训练", "心率", "跑步", "疲劳",
        "强度", "休息", "睡眠", "肌肉", "负荷",
    ]

    QUERIES = [
        # (查询, 至少命中的关键词列表)
        ("静息心率偏高如何调整", ["心率", "恢复"]),
        ("马拉松赛后恢复方法", ["恢复", "训练"]),
        ("过度训练的征兆有哪些", ["疲劳", "训练"]),
        ("如何判断身体是否恢复", ["恢复", "跑步"]),
        ("丹尼尔斯阈值跑怎么练", ["训练", "强度"]),
    ]

    @pytest.mark.parametrize("query,expected_keywords", QUERIES)
    def test_retrieve_returns_relevant_results(self, retrieve_fn, query, expected_keywords):
        """验证检索返回非空结果且内容相关。"""
        results = retrieve_fn(query, top_k=3)

        # 1. 非空
        assert len(results) > 0, f"查询 '{query}' 未返回结果"

        # 2. 每条结果长度合理
        for r in results:
            print(r)
            assert isinstance(r, str)
            assert len(r) > 20, f"结果过短 ({len(r)} 字): {r[:50]}"

        # 3. 至少一条结果包含预期关键词（宽松匹配）
        all_text = "".join(results)
        matched = [kw for kw in expected_keywords if kw in all_text]
        assert len(matched) > 0, (
            f"查询 '{query}' 结果未命中预期关键词 {expected_keywords}。"
            f"实际命中: {matched}，结果摘要: {all_text[:200]}"
        )

    def test_retrieve_top_k_respects_limit(self, retrieve_fn):
        """验证 top_k 参数生效。"""
        for k in [1, 3, 5]:
            results = retrieve_fn("跑步恢复方法", top_k=k)
            assert len(results) <= k

    def test_retrieve_results_diverse(self, retrieve_fn):
        """验证多条结果不完全重复。"""
        results = retrieve_fn("恢复训练建议", top_k=5)
        assert len(results) >= 3, "至少应有 3 条结果"
        # 结果不应完全相同
        unique = set(results)
        assert len(unique) >= 2, f"5 条结果中只有 {len(unique)} 条不重复"

    def test_retrieve_all_contain_chinese(self, retrieve_fn):
        """验证所有结果包含中文。"""
        results = retrieve_fn("跑步", top_k=5)
        for r in results:
            has_cjk = any("\u4e00" <= c <= "\u9fff" for c in r)
            assert has_cjk, f"结果不含中文: {r[:100]}"
