# -*- coding: utf-8 -*-
"""RAG Ingestion 测试 —— 文档加载、切片、Milvus 写入。"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def temp_knowledge_dir():
    """创建临时知识目录，模拟 data/knowledge （扁平化）。"""
    tmp = tempfile.mkdtemp()

    text = """# 测试知识

## 静息心率
静息心率升高5bpm以上表明恢复不足。

## 恢复建议
恢复评分低于50时需要主动恢复。
"""
    with open(os.path.join(tmp, "test_book.md"), "w", encoding="utf-8") as f:
        f.write(text)

    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def patched_config(temp_knowledge_dir):
    """Mock RAG 配置指向临时目录。"""
    with patch(
        "training_agents.rag.ingestion.KNOWLEDGE_DIR", temp_knowledge_dir
    ), patch(
        "training_agents.rag.config.KNOWLEDGE_DIR", temp_knowledge_dir
    ), patch(
        "training_agents.rag.ingestion.MILVUS_URI",
        os.path.join(temp_knowledge_dir, "test_milvus.db"),
    ), patch(
        "training_agents.rag.config.MILVUS_URI",
        os.path.join(temp_knowledge_dir, "test_milvus.db"),
    ):
        yield


# ── Tests ─────────────────────────────────────────────────────


class TestIngestionUnit:
    """不依赖 Milvus 和模型的单元测试。"""

    def test_load_knowledge_files(self, patched_config, temp_knowledge_dir):
        """验证知识文件加载。"""
        from training_agents.rag.ingestion import _load_knowledge_files

        docs = _load_knowledge_files()
        assert len(docs) == 1
        assert docs[0]["domain"] == "general"
        assert docs[0]["book"] == "test_book"
        assert "静息心率" in docs[0]["text"]

    def test_split_text(self, patched_config):
        """验证文本切片。"""
        from training_agents.rag.ingestion import _split_text

        text = "第一句话。第二句话。第三句话。第四句话。第五句话。" * 20
        chunks = _split_text(text, chunk_size=128, overlap=20)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c) > 0

    def test_empty_knowledge_dir(self, patched_config, temp_knowledge_dir):
        """空知识目录不应报错。"""
        # 清空目录
        for f in os.listdir(temp_knowledge_dir):
            fp = os.path.join(temp_knowledge_dir, f)
            if os.path.isfile(fp):
                os.remove(fp)

        from training_agents.rag.ingestion import _load_knowledge_files
        docs = _load_knowledge_files()
        assert docs == []


class TestIngestionIntegration:
    """依赖 Milvus Lite 和 BGE-M3 的集成测试。"""

    @pytest.mark.slow
    def test_ingest_and_collection(self, patched_config, temp_knowledge_dir):
        """完整 ingestion 流程验证。"""
        from training_agents.rag.ingestion import ingest
        from pymilvus import MilvusClient

        count = ingest(rebuild=True)
        assert count > 0

        # 验证 Milvus 中有数据
        db_path = os.path.join(temp_knowledge_dir, "test_milvus.db")
        client = MilvusClient(uri=db_path)
        stats = client.get_collection_stats("training_knowledge")
        assert stats["row_count"] >= count

        # 验证元数据
        results = client.query(
            collection_name="training_knowledge",
            filter='domain == "recovery"',
            output_fields=["domain", "book", "text"],
            limit=1,
        )
        assert len(results) > 0
        assert results[0]["domain"] == "recovery"
        assert results[0]["book"] == "test_book"
