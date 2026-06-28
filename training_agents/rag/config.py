# -*- coding: utf-8 -*-
"""RAG 统一配置 —— Milvus Lite 连接、Collection Schema、Embedding / Reranker 模型。"""

import os
from dataclasses import dataclass, field
from typing import List

# ── 路径 ──────────────────────────────────────────────────────

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")
MILVUS_DB_PATH = os.path.join(DATA_DIR, "milvus.db")

# ── Milvus Lite 连接 ──────────────────────────────────────────

MILVUS_URI = MILVUS_DB_PATH  # Milvus Lite 本地文件路径
COLLECTION_NAME = "training_knowledge"

# ── Collection Schema 字段 ────────────────────────────────────

DENSE_DIM = 1024  # text-embedding-v3 维度 向量维度

# ── 索引参数 ──────────────────────────────────────────────────

DENSE_INDEX_PARAMS = {
    "index_type": "IVF_FLAT",
    "metric_type": "COSINE",
    "params": {"nlist": 32},
}
SPARSE_INDEX_PARAMS = {
    "index_type": "SPARSE_INVERTED_INDEX",
    "metric_type": "BM25",
}

# ── 模型名称 (HuggingFace) ───────────────────────────────────

EMBEDDING_MODEL_NAME = "text-embedding-v3"
RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"  # 暂不使用，数据量小时可跳�?

# ── 切片参数 ──────────────────────────────────────────────────

PARENT_CHUNK_SIZE = 512  # 父块 token �?
CHILD_CHUNK_SIZE = 256    # 子块 token �?
CHUNK_OVERLAP = 50

# ── 检索参�?──────────────────────────────────────────────────

RETRIEVAL_TOP_N = 10    # 小数据量下调 粗筛 Top-N
RERANK_TOP_K = 3        # 精排 Top-K

# ── 领域映射 ──────────────────────────────────────────────────

# Agent �?检�?domain 的映�?
DOMAIN_MAP = {
    "recovery": ["recovery"],
    "load": ["training_load"],
    "performance": ["performance"],
    "risk": ["recovery", "risk"],
}

# ── Milvus Collection Schema 定义 ─────────────────────────────

COLLECTION_SCHEMA_FIELDS = [
    {"name": "id", "dtype": "INT64", "is_primary": True, "auto_id": True},
    {"name": "text", "dtype": "VARCHAR", "max_length": 65535},
    {"name": "dense_vector", "dtype": "FLOAT_VECTOR", "dim": DENSE_DIM},
    {"name": "sparse_vector", "dtype": "SPARSE_FLOAT_VECTOR"},
    {"name": "domain", "dtype": "VARCHAR", "max_length": 64},
    {"name": "book", "dtype": "VARCHAR", "max_length": 256},
    {"name": "chapter", "dtype": "VARCHAR", "max_length": 512},
]
