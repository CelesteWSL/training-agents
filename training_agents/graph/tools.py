# -*- coding: utf-8 -*-
"""共享工具注册表 —— 所有 Agent 共用的 LangChain Tool 定义。

新增工具只需在这里注册，graph/setup.py 即可复用。
"""

import time

from langchain_core.tools import tool


@tool
def search_knowledge(query: str) -> str:
    """搜索跑步训练知识库，获取专业运动科学的恢复、训练方法等建议。

    知识库包含《科学跑步》《丹尼尔斯经典跑步训练法》《马拉松终极训练指南》
    等书籍内容，可用于回答静息心率、过度训练、恢复策略、配速规划等问题。

    Args:
        query: 中文自然语言查询，如"静息心率偏高如何调整训练强度"
    """
    from training_agents.rag.retrieval import retrieve

    # MilvusLite 不支持并发，加简单重试
    for attempt in range(3):
        try:
            results = retrieve(query, top_k=3)
            if not results:
                return "未在知识库中找到相关内容。"
            return "\n\n---\n".join(results)
        except Exception:
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
            else:
                return "知识库暂时不可用，请基于训练经验给出建议。"
    return "知识库暂时不可用。"
