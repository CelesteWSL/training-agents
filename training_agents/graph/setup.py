# -*- coding: utf-8 -*-
"""共享 Graph 组装器 —— 提供 ToolNode 工厂和 recovery graph 构建。

后续新增 Agent（如 Load Agent）只需添加 build_xxx_graph(llm) 函数即可。
"""

from typing import Any, List

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from training_agents.graph.tools import search_knowledge

# ── 共享工具注册表 ──────────────────────────────────────────

SHARED_TOOLS = [search_knowledge]


def build_tool_node(tools: List = None) -> ToolNode:
    """创建共享 ToolNode。

    Args:
        tools: 工具列表，默认使用 SHARED_TOOLS。
    """
    return ToolNode(tools or SHARED_TOOLS)


# ── 条件路由 ────────────────────────────────────────────────

def _route_after_agent(state: dict) -> str:
    """检查 LLM 最后一条消息是否包含 tool_calls。"""
    messages = state.get("messages", [])
    if not messages:
        return END
    last_msg = messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tool_executor"
    return END


# ── Recovery Graph ──────────────────────────────────────────

def build_recovery_graph(llm: Any, agent_node_fn):
    """构建 recovery agent 的 LangGraph workflow。

    Args:
        llm: LangChain BaseChatModel 实例。
        agent_node_fn: recovery_agent_node 函数（已 bind_tools）。

    Returns:
        编译后的 CompiledStateGraph。
    """
    from training_agents.agents.utils.agent_states import AgentState

    tool_node = build_tool_node()

    workflow = StateGraph(AgentState)
    workflow.add_node("recovery_agent", agent_node_fn)
    workflow.add_node("tool_executor", tool_node)

    workflow.add_edge(START, "recovery_agent")
    workflow.add_conditional_edges(
        "recovery_agent",
        _route_after_agent,
        {
            "tool_executor": "tool_executor",
            END: END,
        },
    )
    workflow.add_edge("tool_executor", "recovery_agent")

    return workflow.compile()



# ── Load Graph ─────────────────────────────────────────────

def build_load_graph(llm: Any, agent_node_fn):
    """构建 training load agent 的 LangGraph workflow。

    Args:
        llm: LangChain BaseChatModel 实例。
        agent_node_fn: load_agent_node 函数（已 bind_tools）。

    Returns:
        编译后的 CompiledStateGraph。
    """
    from training_agents.agents.utils.agent_states import AgentState

    tool_node = build_tool_node()

    workflow = StateGraph(AgentState)
    workflow.add_node("load_agent", agent_node_fn)
    workflow.add_node("tool_executor", tool_node)

    workflow.add_edge(START, "load_agent")
    workflow.add_conditional_edges(
        "load_agent",
        _route_after_agent,
        {
            "tool_executor": "tool_executor",
            END: END,
        },
    )
    workflow.add_edge("tool_executor", "load_agent")

    return workflow.compile()
# ── Performance Graph ───────────────────────────────────────

def build_performance_graph(llm: Any, agent_node_fn):
    """构建 performance agent 的 LangGraph workflow。

    Args:
        llm: LangChain BaseChatModel 实例。
        agent_node_fn: performance_agent_node 函数（已 bind_tools）。

    Returns:
        编译后的 CompiledStateGraph。
    """
    from training_agents.agents.utils.agent_states import AgentState

    tool_node = build_tool_node()

    workflow = StateGraph(AgentState)
    workflow.add_node("performance_agent", agent_node_fn)
    workflow.add_node("tool_executor", tool_node)

    workflow.add_edge(START, "performance_agent")
    workflow.add_conditional_edges(
        "performance_agent",
        _route_after_agent,
        {
            "tool_executor": "tool_executor",
            END: END,
        },
    )
    workflow.add_edge("tool_executor", "performance_agent")

    return workflow.compile()
# ── Risk Graph ────────────────────────────────────────────

def build_risk_graph(llm: Any, agent_node_fn):
    """构建 risk agent 的 LangGraph workflow。

    Args:
        llm: LangChain BaseChatModel 实例。
        agent_node_fn: risk_agent_node 函数（已 bind_tools）。

    Returns:
        编译后的 CompiledStateGraph。
    """
    from training_agents.agents.utils.agent_states import AgentState

    tool_node = build_tool_node()

    workflow = StateGraph(AgentState)
    workflow.add_node("risk_agent", agent_node_fn)
    workflow.add_node("tool_executor", tool_node)

    workflow.add_edge(START, "risk_agent")
    workflow.add_conditional_edges(
        "risk_agent",
        _route_after_agent,
        {
            "tool_executor": "tool_executor",
            END: END,
        },
    )
    workflow.add_edge("tool_executor", "risk_agent")

    return workflow.compile()

# ── Main Graph ─────────────────────────────────────────────

def build_main_graph(llm: Any):
    """构建完整 Training Agents pipeline。

    Data Agent → [Recovery ‖ Load ‖ Performance] → Risk → Coach 引擎 → Report Generator

    Args:
        llm: LangChain BaseChatModel 实例，所有 Analyst 和 Report Generator 共用。

    Returns:
        编译后的 CompiledStateGraph。
    """
    from training_agents.agents.analysts.data_analyst import create_data_agent
    from training_agents.agents.analysts.load_analyst import create_load_agent
    from training_agents.agents.analysts.performance_analyst import create_performance_agent
    from training_agents.agents.analysts.recovery_analyst import create_recovery_agent
    from training_agents.agents.analysts.risk_analyst import create_risk_agent
    from training_agents.agents.engines.decision_engine import decision_node
    from training_agents.agents.engines.recognition_engine import sra_node
    from training_agents.agents.report.report_generator import create_report_agent
    from training_agents.agents.utils.agent_states import AgentState

    # ── 子图 ──
    recovery_graph = build_recovery_graph(llm, create_recovery_agent(llm))
    load_graph = build_load_graph(llm, create_load_agent(llm))
    performance_graph = build_performance_graph(llm, create_performance_agent(llm))
    risk_graph = build_risk_graph(llm, create_risk_agent(llm))
    data_agent_fn = create_data_agent()

    # ── 节点 ──
    workflow = StateGraph(AgentState)
    workflow.add_node("data_agent", data_agent_fn)
    workflow.add_node("recovery_agent", recovery_graph)
    workflow.add_node("load_agent", load_graph)
    workflow.add_node("performance_agent", performance_graph)
    workflow.add_node("risk_agent", risk_graph)
    workflow.add_node("recognition_engine", sra_node)
    workflow.add_node("decision_engine", decision_node)
    workflow.add_node("report_generator", create_report_agent(llm))

    # ── 边 ──
    # Data → 三个 Analyst 并行
    workflow.add_edge(START, "data_agent")
    workflow.add_edge("data_agent", "recovery_agent")
    workflow.add_edge("data_agent", "load_agent")
    workflow.add_edge("data_agent", "performance_agent")

    # 三个 Analyst → Risk（fan-in）
    workflow.add_edge("recovery_agent", "risk_agent")
    workflow.add_edge("load_agent", "risk_agent")
    workflow.add_edge("performance_agent", "risk_agent")

    # Risk → Coach 引擎 → Report Generator
    workflow.add_edge("risk_agent", "recognition_engine")
    workflow.add_edge("recognition_engine", "decision_engine")
    workflow.add_edge("decision_engine", "report_generator")
    workflow.add_edge("report_generator", END)

    return workflow.compile()