# -*- coding: utf-8 -*-
"""Recognition Engine —— 纯规则引擎，识别 Hidden Physiological State。

不依赖 LLM，直接读取 Recovery / Load / Performance / Risk 四个 Agent 的报告，
通过 Gatekeeper + 权重积分制匹配 6 种生理状态。

架构（参照 Data Agent）：
- 计算层：agents/utils/state_recognition_indicators.py（State Library + 积分引擎）
- 节点层：本文件（读 AgentState → 调 recognize_states → 写 state_recognition）
"""

from typing import Any, Dict, List

from training_agents.agents.utils.agent_states import (
    AgentState,
    PhysiologicalState,
    StateRecognitionResult,
)
from training_agents.agents.utils.state_recognition_indicators import recognize_states


def sra_node(state: AgentState) -> Dict[str, Any]:
    """Recognition Engine 节点函数。

    1. 从各 Agent 的 report 中提取关键指标
    2. 调用 recognize_states 运行 State Library
    3. 构建 StateRecognitionResult 写入 state
    """
    states = recognize_states(dict(state))

    physiological_states: List[PhysiologicalState] = [
        PhysiologicalState(
            name=s["name"],
            priority=s["priority"],
            confidence=s["confidence"],
            total_score=s.get("total_score", 0.0),
            threshold=s.get("threshold", 0),
            explanation=s.get("explanation", ""),
            indicators=s.get("indicators", []),
        )
        for s in states
    ]

    return {
        "state_recognition": StateRecognitionResult(
            physiological_states=physiological_states,
        )
    }


def create_sra_agent():
    """Factory 函数 —— 返回 SRA 节点函数，无参数（不依赖 LLM）。"""
    return sra_node
