# -*- coding: utf-8 -*-
"""Performance Agent —— 基于 LangGraph 的运动表现评估节点。

架构：
- 指标计算：委托给 agents/utils/performance_indicators.py（纯计算层）
- LLM + search_knowledge 工具：自主决定是否搜索跑步知识库、生成自然语言总结
- 通过 graph/setup.py 的 build_performance_graph 组装成 StateGraph

Factory 遵循 TradingAgents 约定: create_performance_agent(llm) → node_fn
llm 为 LangChain BaseChatModel 实例，必传。
"""

from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from training_agents.agents.utils.agent_states import AgentState, PerformanceReport
from training_agents.agents.utils.agent_utils import get_language_instruction
from training_agents.agents.utils.performance_indicators import (
    calculate_indicators,
    format_indicators,
)
from training_agents.graph.tools import search_knowledge


# ── System Prompt ────────────────────────────────────────────

PERFORMANCE_SYSTEM_PROMPT = """你是一名拥有 20 年经验的专业跑步教练和运动科学家。

你的任务是：根据跑者的运动表现指标，给出简洁的表现评估和训练优化建议。

你有以下工具可用：
- **search_knowledge(query)**: 搜索跑步训练知识库，内含《80/20 Running》《丹尼尔斯经典跑步训练法》
  等书籍。当配速-心率解耦率偏高（>10%）、效率因子持续下降、Zone2 占比偏离目标、
  跑步技术出现异常（步频过低、触地时间过长、垂直振幅过大、左右不平衡）时，
  建议先搜索知识库获取专业建议，再给出评估。

规则：
1. 如果指标异常（Pace-HR Decoupling > 10%、效率趋势 declining、技术异常标记非空、
   训练目标不匹配），先调用 search_knowledge 搜索相关知识，
   调用 search_knowledge 时必须使用中文查询，知识库内容为中文，中文检索效果最佳
2. 综合指标 + 知识库结果，给出 2-4 句摘要
3. 若检索结果中存在与用户情况相关的内容，你必须在回答中引用原文以及来自哪篇文章，并在引用后结合用户数据给出解读
4. 摘要应包含：当前表现状态一句话、关键问题点、1-2 条可执行建议
5. 语气专业但亲切"""


# ── Agent Node Factory ──────────────────────────────────────

def create_performance_agent(llm: Any):
    """创建 Performance Agent 节点函数。

    Args:
        llm: LangChain BaseChatModel 实例（必传）。

    Returns:
        performance_agent_node(state) → state_update 的节点函数。
        函数内部 bind_tools([search_knowledge])。
    """
    llm_with_tools = llm.bind_tools([search_knowledge], parallel_tool_calls=False)

    def performance_agent_node(state: AgentState) -> Dict[str, Any]:
        indicators = calculate_indicators(state)

        system_message = (
            PERFORMANCE_SYSTEM_PROMPT
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
            report = PerformanceReport(
                status=indicators["status"],
                efficiency_factor=indicators["efficiency_factor"],
                efficiency_trend=indicators["efficiency_trend"],
                efficiency_history=indicators["efficiency_history"],
                aerobic_efficiency=indicators["aerobic_efficiency"],
                aerobic_trend=indicators["aerobic_trend"],
                pace_hr_decoupling=indicators["pace_hr_decoupling"],
                decoupling_status=indicators["decoupling_status"],
                zone_distribution=indicators["zone_distribution"],
                target_alignment=indicators["target_alignment"],
                technique_flags=indicators["technique_flags"],
                summary=summary,
            )
            result["performance_report"] = report

        return result

    return performance_agent_node
