# -*- coding: utf-8 -*-
"""Risk Agent —— 基于 LangGraph 的伤病风险评估节点。

架构：
- 指标计算：委托给 agents/utils/risk_indicators.py（纯计算层）
- LLM + search_knowledge 工具：injury_risk > 60 时触发 RAG，生成自然语言总结
- 通过 graph/setup.py 的 build_risk_graph 组装成 StateGraph

Factory 遵循 TradingAgents 约定: create_risk_agent(llm) → node_fn
llm 为 LangChain BaseChatModel 实例，必传。
"""

from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from training_agents.agents.utils.agent_states import AgentState, RiskReport
from training_agents.agents.utils.agent_utils import get_language_instruction
from training_agents.agents.utils.risk_indicators import (
    calculate_indicators,
    format_indicators,
)
from training_agents.graph.tools import search_knowledge


# ── System Prompt ────────────────────────────────────────────

RISK_SYSTEM_PROMPT = """你是一名拥有 20 年经验的专业跑步教练和运动医学顾问。

你的任务是：根据跑者的伤病风险评估指标，给出简洁的风险分析和预防建议。

你有以下工具可用：
- **search_knowledge(query)**: 搜索跑步训练知识库，内含《无伤跑法》《丹尼尔斯经典跑步训练法》
  《80/20 Running》等书籍。当伤病风险评分 > 60（高风险或极高风险），建议先搜索知识库获取专业建议，再给出评估。

规则：
1. 如果 injury_risk_score > 60，先调用 search_knowledge 搜索相关知识，
   调用 search_knowledge 时必须使用中文查询，知识库内容为中文，中文检索效果最佳
2. 综合风险评分 + 风险因子 + 知识库结果，给出 2-4 句摘要
3. 若检索结果中存在与用户情况相关的内容，你必须在回答中引用原文以及来自哪篇文章，并在引用后结合用户数据给出解读
4. 摘要应包含：当前风险状态一句话、最关键的 1-2 个风险因子、1-2 条可执行预防建议
5. 语气专业但亲切"""


# ── Agent Node Factory ──────────────────────────────────────

def create_risk_agent(llm: Any):
    """创建 Risk Agent 节点函数。

    Args:
        llm: LangChain BaseChatModel 实例（必传）。

    Returns:
        risk_agent_node(state) → state_update 的节点函数。
        函数内部 bind_tools([search_knowledge])。
    """
    llm_with_tools = llm.bind_tools([search_knowledge], parallel_tool_calls=False)

    def risk_agent_node(state: AgentState) -> Dict[str, Any]:
        indicators = calculate_indicators(state)

        system_message = (
            RISK_SYSTEM_PROMPT
            + "\n\n"
            + format_indicators(indicators)
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_message}"),
            MessagesPlaceholder(variable_name="messages"),
        ])
        prompt = prompt.partial(system_message=system_message)

        chain = prompt | llm_with_tools
        response = chain.invoke(state["messages"])
        result: Dict[str, Any] = {"messages": [response]}

        if not (hasattr(response, "tool_calls") and response.tool_calls):
            summary = response.content.strip() if response.content else ""
            report = RiskReport(
                risk_level=indicators["risk_level"],
                injury_risk_score=indicators["injury_risk_score"],
                risk_factors=indicators["risk_factors"],
                alerts=indicators["alerts"],
                summary=summary,
            )
            result["risk_report"] = report

        return result

    return risk_agent_node
