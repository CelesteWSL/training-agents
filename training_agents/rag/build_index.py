# -*- coding: utf-8 -*-
"""RAG 向量索引构建 CLI 入口 —— 一键构建/重建向量索引。

用法:
    python -m training_agents.rag.build_index          # 重建索引
    python -m training_agents.rag.build_index --append  # 追加模式
"""


import argparse

from training_agents.rag.ingestion import ingest


def main():
    parser = argparse.ArgumentParser(
        description="构建/重建 RAG 向量索引"
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="追加模式（不删除已有 collection）",
    )
    args = parser.parse_args()

    rebuild = not args.append
    count = ingest(rebuild=rebuild)
    if count == 0:
        print(
            "\n[INFO] 未入库任何数据。"
            "请先在 data/knowledge/{domain}/ 下放置知识文件（.txt/.md/.pdf/.epub）。"
        )


if __name__ == "__main__":
    main()
