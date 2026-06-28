# -*- coding: utf-8 -*-
"""Embedding 统一抽象 —— 提供 embed_documents / embed_query 接口。

当前实现：OpenAI text-embedding-3-small（API 调用）
后续更换：新增 LocalEmbeddingClient 实现，改 get_embedding_client 分发逻辑即可。
"""

from typing import List

from training_agents.rag.config import EMBEDDING_MODEL_NAME


class EmbeddingClient:
    """Embedding 客户端 —— 使用 DashScope OpenAI 兼容接口。"""

    def __init__(self, model: str = EMBEDDING_MODEL_NAME):
        import os
        from openai import OpenAI

        self._model_name = model
        self._client = OpenAI(
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量 embedding（DashScope 限制 batch_size <= 10），返回 List[List[float]]。"""
        BATCH_SIZE = 10
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            result = self._client.embeddings.create(
                model=self._model_name,
                input=batch,
            )
            all_embeddings.extend(d.embedding for d in result.data)
        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """单条查询 embedding，返回 List[float]。"""
        result = self._client.embeddings.create(
            model=self._model_name,
            input=text,
        )
        return result.data[0].embedding


# ── 工厂函数 ──

_client: EmbeddingClient = None


def get_embedding_client(model: str = None) -> EmbeddingClient:
    """获取全局单例 EmbeddingClient。

    Args:
        model: 模型名，默认用 config.EMBEDDING_MODEL_NAME。
               以 "text-embedding-" 开头走 OpenAI API；
               否则走本地模型（SentenceTransformer，后续扩展）。
    """
    global _client
    if _client is None:
        model = model or EMBEDDING_MODEL_NAME
        _client = EmbeddingClient(model=model)
    return _client
