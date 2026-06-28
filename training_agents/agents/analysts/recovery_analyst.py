# -*- coding: utf-8 -*-
"""Recovery Agent —— 基于 LangGraph 的恢复评估节点。

架构：
- 指标计算：委托给 agents/utils/recovery_indicators.py（纯计算层）
- LLM + search_knowledge 工具：自主决定是否搜索跑步知识库、生成自然语言总结
- 通过 graph/setup.py 的 build_recovery_graph 组装成 StateGraph

Factory 遵循 TradingAgents 约定: create_recovery_agent(llm) → node_fn
llm 为 LangChain BaseChatModel 实例，必传。
"""

from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from training_agents.agents.utils.agent_states import (
    AgentState, RecoveryReport,
)
from training_agents.agents.utils.agent_utils import get_language_instruction
from training_agents.agents.utils.recovery_indicators import (
    calculate_indicators,
    format_indicators,
)
from training_agents.graph.tools import search_knowledge


# ── System Prompt ────────────────────────────────────────────

RECOVERY_SYSTEM_PROMPT = """你是一名拥有 20 年经验的专业跑步教练和运动科学家。

你的任务是：根据跑者的当日恢复指标，给出简洁的恢复评估和训练建议。

你有以下工具可用：
- **search_knowledge(query)**: 搜索跑步训练知识库，内含《科学跑步》《丹尼尔斯经典跑步训练法》
  《马拉松终极训练指南》等书籍。当恢复指标出现异常（静息心率偏离较大、恢复评分偏低、
  疲劳趋势为 accumulating、心率漂移明显、恢复负债持续上升），建议先搜索知识库获取专业建议，再给出评估。

规则：
1. 如果指标异常，先调用 search_knowledge 搜索相关知识，调用 search_knowledge 时必须使用中文查询，知识库内容为中文，中文检索效果最佳
2. 综合指标 + 知识库结果，给出 2-4 句摘要
3. 若检索结果中存在与用户情况相关的内容，你必须在回答中引用原文以及来自哪篇文章，并在引用后结合用户数据给出解读
4. 摘要应包含：当前状态一句话、关键风险点、1-2 条可执行建议、如果在训练知识库中找到
5. 语气专业但亲切"""


# ── Agent Node Factory ──────────────────────────────────────

def create_recovery_agent(llm: Any):
    """创建 Recovery Agent 节点函数。

    Args:
        llm: LangChain BaseChatModel 实例（必传）。

    Returns:
        recovery_agent_node(state) → state_update 的节点函数。
        函数内部 bind_tools([search_knowledge])。
    """
    llm_with_tools = llm.bind_tools([search_knowledge], parallel_tool_calls=False)

    def recovery_agent_node(state: AgentState) -> Dict[str, Any]:
        indicators = calculate_indicators(state)

        system_message = (
            RECOVERY_SYSTEM_PROMPT
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
            report = RecoveryReport(
                status=indicators["status"],
                recovery_score=indicators["recovery_score"],
                fatigue_trend=indicators["fatigue_trend"],
                resting_hr_deviation=indicators["resting_hr_deviation"],
                hr_drift=indicators["hr_drift"],
                recovery_debt=indicators["recovery_debt"],
                recovery_debt_trend=indicators["recovery_debt_trend"],
                consecutive_hard_days=indicators.get("consecutive_hard_days", 0),
                summary=summary,
            )
            result["recovery_report"] = report

        return result

    return recovery_agent_node
