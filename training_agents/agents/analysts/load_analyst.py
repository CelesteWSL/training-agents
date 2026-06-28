# -*- coding: utf-8 -*-
"""Training Load Agent —— 基于 LangGraph 的训练负荷评估节点。

架构：
- 指标计算：委托给 agents/utils/load_indicators.py（纯计算层）
- LLM + search_knowledge 工具：自主决定是否搜索跑步知识库、生成自然语言总结
- 通过 graph/setup.py 的 build_load_graph 组装成 StateGraph

Factory 遵循 TradingAgents 约定: create_load_agent(llm) → node_fn
llm 为 LangChain BaseChatModel 实例，必传。
"""

from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from training_agents.agents.utils.agent_states import AgentState, LoadReport
from training_agents.agents.utils.agent_utils import get_language_instruction
from training_agents.agents.utils.load_indicators import (
    calculate_indicators,
    format_indicators,
)
from training_agents.graph.tools import search_knowledge


# ── System Prompt ────────────────────────────────────────────

LOAD_SYSTEM_PROMPT = """你是一名拥有 20 年经验的专业跑步教练和运动科学家。

你的任务是：根据跑者的训练负荷指标，给出简洁的负荷评估和训练调整建议。

你有以下工具可用：
- **search_knowledge(query)**: 搜索跑步训练知识库，内含《丹尼尔斯经典跑步训练法》《无伤跑法》
  《80/20 Running》等书籍。当 ACWR 偏离最佳区间（>1.5 过度训练、<0.8 训练不足）、
  Ramp Rate 偏高（>0.15，即周跑量增长超过 15%），建议先搜索知识库获取专业建议，再给出评估。

规则：
1. 如果指标异常（ACWR > 1.5 或 < 0.8，Ramp Rate > 0.15），先调用 search_knowledge 搜索相关知识，
   调用 search_knowledge 时必须使用中文查询，知识库内容为中文，中文检索效果最佳
2. 综合指标 + 知识库结果，给出 3-6 句摘要
3. 若检索结果中存在与用户情况相关的内容，你必须在回答中引用原文以及来自哪篇文章，并在引用后结合用户数据给出解读
4. 摘要应包含：当前负荷状态一句话、关键风险点、1-2 条可执行建议
5. 语气专业但亲切"""


# ── Agent Node Factory ──────────────────────────────────────

def create_load_agent(llm: Any):
    """创建 Training Load Agent 节点函数。

    Args:
        llm: LangChain BaseChatModel 实例（必传）。

    Returns:
        load_agent_node(state) → state_update 的节点函数。
        函数内部 bind_tools([search_knowledge])。
    """
    llm_with_tools = llm.bind_tools([search_knowledge], parallel_tool_calls=False)

    def load_agent_node(state: AgentState) -> Dict[str, Any]:
        indicators = calculate_indicators(state)

        system_message = (
            LOAD_SYSTEM_PROMPT
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
            report = LoadReport(
                status=indicators["status"],
                acute_load=indicators["acute_load"],
                chronic_load=indicators["chronic_load"],
                acwr=indicators["acwr"],
                weekly_volume_km=indicators["weekly_volume_km"],
                ramp_rate=indicators["ramp_rate"],
                acwr_interpretation=indicators["acwr_interpretation"],
                ramp_rate_interpretation=indicators["ramp_rate_interpretation"],
                summary=summary,
            )
            result["load_report"] = report

        return result

    return load_agent_node
