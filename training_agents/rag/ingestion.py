# -*- coding: utf-8 -*-
"""RAG 文档入库 —— 知识文件解析、父子切片、Embedding、写入 Milvus Lite。"""
# ── milvus-lite Windows 兼容性 monkeypatch ──
import os as _os
_original_rename = _os.rename
def _safe_rename(src, dst):
    try:
        _original_rename(src, dst)
    except FileExistsError:
        _os.replace(src, dst)
_os.rename = _safe_rename


import os
from typing import List, Dict, Optional, Tuple

from pymilvus import MilvusClient, DataType

from training_agents.rag.config import (
    MILVUS_URI,
    COLLECTION_NAME,
    KNOWLEDGE_DIR,
    DENSE_DIM,
    PARENT_CHUNK_SIZE,
    CHUNK_OVERLAP,
    DENSE_INDEX_PARAMS,
    SPARSE_INDEX_PARAMS,
    COLLECTION_SCHEMA_FIELDS,
    EMBEDDING_MODEL_NAME,
)

# ── 懒加载模型 ────────────────────────────────────────────────



# ── milvus-lite Windows 兼容性 monkeypatch ────────────────────

import os as _os

def _embed_texts(texts: list) -> list:
    """调用 embedding 客户端批量向量化。"""
    from training_agents.rag.embedding import get_embedding_client
    return get_embedding_client().embed_documents(texts)


# ── 文本切片 ──────────────────────────────────────────────────


def _split_text(text: str, chunk_size: int = PARENT_CHUNK_SIZE,
                overlap: int = CHUNK_OVERLAP) -> List[str]:
    """将文本按 token 数切片，返回 chunk 列表。"""
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.schema import Document as LlamaDoc

    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    nodes = splitter.get_nodes_from_documents([LlamaDoc(text=text)])
    return [node.get_content() for node in nodes]


# ── 加载知识文件 ──────────────────────────────────────────────


def _load_knowledge_files() -> List[Dict[str, str]]:
    """遍历 data/knowledge/ 目录，返回文档列表。

    Returns:
        List of dicts with keys: text, domain, book, filepath
    """
    documents: List[Dict[str, str]] = []
    supported_exts = {".txt", ".md", ".pdf", ".epub"}

    if not os.path.isdir(KNOWLEDGE_DIR):
        return documents

    for filename in os.listdir(KNOWLEDGE_DIR):
        filepath = os.path.join(KNOWLEDGE_DIR, filename)
        if not os.path.isfile(filepath):
            continue

        _, ext = os.path.splitext(filename)
        if ext.lower() not in supported_exts:
            continue

        book_name = os.path.splitext(filename)[0]

        try:
            if ext.lower() == ".pdf":
                text = _parse_pdf(filepath)
            elif ext.lower() == ".epub":
                text = _parse_epub(filepath)
            else:
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()

            if text.strip():
                documents.append({
                    "text": text,
                    "domain": "general",
                    "book": book_name,
                    "filepath": filepath,
                })
        except Exception as e:
            print(f"  [WARN] 跳过 {filepath}: {e}")

    return documents


def _parse_pdf(filepath: str) -> str:
    """使用 unstructured 解析 PDF 文件，返回纯文本。"""
    from unstructured.partition.pdf import partition_pdf

    elements = partition_pdf(filename=filepath)
    return "\n\n".join(str(el) for el in elements)


def _parse_epub(filepath: str) -> str:
    """使用 Pandoc 解析 EPUB 文件，返回纯文本。"""
    import subprocess
    import os as _os

    pandoc_bin = _os.path.join(
        _os.environ.get("LOCALAPPDATA", ""), "Pandoc", "pandoc.exe"
    )
    result = subprocess.run(
        [pandoc_bin, filepath, "-t", "plain", "--wrap=none"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    return result.stdout


# ── Milvus Collection 管理 ────────────────────────────────────


def _create_collection(client: MilvusClient) -> None:
    """创建 Milvus collection（如已存在则先删除重建）。"""
    if client.has_collection(COLLECTION_NAME):
        client.drop_collection(COLLECTION_NAME)

    # 构建 schema
    schema = client.create_schema(
        auto_id=True,
        enable_dynamic_field=False,
    )
    schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field("text", DataType.VARCHAR, max_length=65535)
    schema.add_field(
        "dense_vector", DataType.FLOAT_VECTOR, dim=DENSE_DIM
    )
    schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field("domain", DataType.VARCHAR, max_length=64)
    schema.add_field("book", DataType.VARCHAR, max_length=256)
    schema.add_field("chapter", DataType.VARCHAR, max_length=512)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
    )

    # 创建索引（dense + sparse 合并为一次调用，避免 milvus-lite Windows bug）
    idx_params = client.prepare_index_params()
    idx_params.add_index(
        field_name="dense_vector",
        index_type=DENSE_INDEX_PARAMS["index_type"],
        metric_type=DENSE_INDEX_PARAMS["metric_type"],
        params=DENSE_INDEX_PARAMS["params"],
    )
    idx_params.add_index(
        field_name="sparse_vector",
        index_type=SPARSE_INDEX_PARAMS["index_type"],
        metric_type=SPARSE_INDEX_PARAMS["metric_type"],
    )
    client.create_index(
        collection_name=COLLECTION_NAME,
        index_params=idx_params,
    )


# ── 核心入库流程 ──────────────────────────────────────────────


def ingest(rebuild: bool = True) -> int:
    """执行完整入库流程：加载知识文件 → 切片 → Embedding → 写入 Milvus。

    Args:
        rebuild: True 时删除已有 collection 重建；False 时追加。

    Returns:
        入库的总 chunk 数量。
    """
    # 加载文档
    docs = _load_knowledge_files()
    if not docs:
        print("[INFO] data/knowledge/ 目录下无知识文件，跳过入库。")
        return 0

    print(f"[INFO] 发现 {len(docs)} 个知识文件")

    # 切片
    chunks: List[Dict] = []
    for doc in docs:
        doc_chunks = _split_text(doc["text"])
        for chunk in doc_chunks:
            chunks.append({
                "text": chunk,
                "domain": doc["domain"],
                "book": doc["book"],
                "chapter": "",  # 后续可解析 Markdown 标题
            })
    print(f"[INFO] 切片完成，共 {len(chunks)} 个 chunk")

    if not chunks:
        return 0

    # 连接 Milvus
    client = MilvusClient(uri=MILVUS_URI)

    if rebuild:
        _create_collection(client)

    # 生成 Embedding（OpenAI API）
    texts = [c["text"] for c in chunks]
    print(f"[INFO] 正在生成 Embedding ({len(texts)} 条)...")

    dense_vectors = _embed_texts(texts)

    # 构造插入数据（sparse 填空字典）
    data = []
    for i, chunk in enumerate(chunks):
        data.append({
            "text": chunk["text"],
            "dense_vector": dense_vectors[i],
            "sparse_vector": {0: 0.0},  # 不使用 sparse，填占位
            "domain": chunk["domain"],
            "book": chunk["book"],
            "chapter": chunk["chapter"],
        })

    # 批量插入
    insert_result = client.insert(collection_name=COLLECTION_NAME, data=data)
    print(
        f"[INFO] 入库完成: {insert_result['insert_count']} 条 -> "
        f"collection '{COLLECTION_NAME}'"
    )

    # 打印统计
    stats = client.get_collection_stats(COLLECTION_NAME)
    print(f"[INFO] Collection 统计: {stats}")

    return insert_result["insert_count"]


# ── CLI 入口 ──────────────────────────────────────────────────

if __name__ == "__main__":
    count = ingest(rebuild=True)
    print(f"Done: {count} chunks ingested.")
