# -*- coding: utf-8 -*-
"""RAG 运行时检索 —— 混合检索（语义 + 关键词）+ BGE-Reranker 精排。"""

import threading
from typing import List, Optional

from pymilvus import MilvusClient

from training_agents.rag.config import (
    MILVUS_URI,
    COLLECTION_NAME,
    DENSE_DIM,
    RETRIEVAL_TOP_N,
    RERANK_TOP_K,
    EMBEDDING_MODEL_NAME,
    RERANKER_MODEL_NAME,
    DOMAIN_MAP,
)

# 懒加载模型

def _embed_query(text: str) -> list:
    from training_agents.rag.embedding import get_embedding_client
    return get_embedding_client().embed_query(text)


# MilvusClient 单例 + 线程锁（ToolNode 多线程并发保护）

_milvus_client: Optional[MilvusClient] = None
_collection_loaded: bool = False
_lock = threading.Lock()


def _get_milvus_client() -> MilvusClient:
    global _milvus_client, _collection_loaded
    with _lock:
        if _milvus_client is None:
            _milvus_client = MilvusClient(uri=MILVUS_URI)
        if not _collection_loaded and _milvus_client.has_collection(COLLECTION_NAME):
            _milvus_client.load_collection(COLLECTION_NAME)
            _collection_loaded = True
        return _milvus_client


def close_client() -> None:
    global _milvus_client, _collection_loaded
    with _lock:
        if _milvus_client is not None:
            try:
                _milvus_client.close()
            except Exception:
                pass
            _milvus_client = None
            _collection_loaded = False


import atexit as _atexit
_atexit.register(close_client)


# 核心检索

def retrieve(
    query: str,
    domain: str = None,
    top_k: int = RERANK_TOP_K,
) -> List[str]:
    client = _get_milvus_client()

    if not client.has_collection(COLLECTION_NAME):
        return []

    filter_expr = None
    if domain:
        domains = DOMAIN_MAP.get(domain, [domain])
        filter_expr = " or ".join(
            f'domain == "{d}"' for d in domains
        )

    query_dense = _embed_query(query)

    search_kwargs = {
        "collection_name": COLLECTION_NAME,
        "data": [query_dense],
        "anns_field": "dense_vector",
        "limit": RETRIEVAL_TOP_N,
        "output_fields": ["text"],
        "search_params": {"metric_type": "COSINE", "params": {"nprobe": 16}},
    }
    if filter_expr:
        search_kwargs["expr"] = filter_expr

    with _lock:
        dense_results = client.search(**search_kwargs)[0]
    hybrid_results = dense_results

    candidate_texts = [hit["entity"]["text"] for hit in hybrid_results]
    if not candidate_texts:
        return []

    return candidate_texts[:top_k]


# CLI 调试入口

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python retrieval.py <domain> <query>")
        print("Example: python retrieval.py recovery 静息心率偏高如何恢复")
        sys.exit(1)

    domain = sys.argv[1]
    query = " ".join(sys.argv[2:])
    results = retrieve(query, domain, top_k=3)

    print(f"\n--- 检索结果 (domain={domain}) ---")
    for i, text in enumerate(results, 1):
        print(f"\n[{i}] {text[:300]}...")