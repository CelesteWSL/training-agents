# -*- coding: utf-8 -*-
"""Report Generator —— 将上游分析结论转化为面向跑者的自然语言报告。

不分析、不诊断、不决策，只做一件事：把上游所有专家结论讲成一个完整故事。
Coach Agent 中唯一调用 LLM 的节点。

输入：AgentState（4 路 Analyst summary + Recognition Engine + Decision Engine）
输出：FinalReport.markdown
"""

import json
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from training_agents.agents.utils.agent_states import AgentState
from training_agents.agents.utils.agent_utils import get_language_instruction


# ── System Prompt ────────────────────────────────────────────

SYSTEM_PROMPT = """你是一名拥有 20 年经验的专业耐力运动教练（Chief Coach）。

你的团队已经完成了今天的训练数据分析，分为两个层级：

**分析层（专家意见）：**
- Recovery Coach：恢复状态评估
- Load Coach：训练负荷评估
- Performance Coach：运动表现评估
- Risk Coach：伤病风险评估

**诊断与裁决层（综合结论，具有最高权威）：**
- Recognition Engine：跨维度根因诊断 —— 你的团队对各专家意见交叉验证后的最终诊断
- Decision Engine：训练动作裁决 —— 基于诊断结果做出的最终训练决策

你的任务是以分析层的专家意见为参考，但以诊断与裁决层的结论为准绳，生成一份面向跑者的最终训练报告。

请严格按照以下结构组织报告：

## 📌 训练总结 / Training Summary
概括 Recognition Engine 的诊断结论 + Decision Engine 的裁决建议。

## 🏃 当前状态 / Current Status
整合 Recovery / Load / Performance 专家的分析意见，描述运动员当前整体状态。以 Recognition Engine 的诊断方向为线索组织内容，而非简单罗列各 Agent 结论。

## 🔍 根因分析 / Root Cause Analysis
以 Recognition Engine 的诊断结果为核心，解释问题产生的根本原因。引用分析层专家的证据支撑诊断结论，展示指标之间如何互相印证。

## ⚠️ 风险评估 / Risk Assessment
基于 Risk Coach 的分析 + Recognition Engine 识别的状态，说明继续训练可能带来的后果。若 Recognition Engine 检测到 Injury Onset Pattern 或 Non-Functional Overreaching，必须重点警告。

## 📋 训练建议 / Training Recommendations
以 Decision Engine 的裁决为核心，结合 Recognition Engine 的根因，给出具体可执行的训练调整建议。解释为什么做出这个裁决，而非其他选择。

要求：
- 诊断与裁决层的结论必须作为报告的核心主线，分析层意见用于提供细节和证据
- 不要重复罗列原始指标，重点解释指标背后的意义
- 所有结论必须能追溯到上游分析结果
- 语言专业但易懂，根据用户画像调整语气"""


# ── 辅助 ─────────────────────────────────────────────────────

def _safe_summary(report: Any) -> str:
    """安全提取 summary，None / 空 dict 降级为占位文本。"""
    if not report or not isinstance(report, dict):
        return "暂无数据"
    return report.get("summary") or "暂无数据"


def _build_recognition_text(state: Dict[str, Any]) -> str:
    """将 Recognition Engine 输出内联为自然语言文本。"""
    sr = state.get("state_recognition") or {}
    states = sr.get("physiological_states") or []
    if states:
        return "\n".join(
            f"● {s['name']}（confidence={s['confidence']:.0%}）：{s['explanation']}"
            for s in states
        )
    return "未检测到异常生理状态"


def _build_modifiers_text(ruling: Dict[str, Any]) -> str:
    """将技术修饰器格式化为文本。"""
    modifiers = ruling.get("modifiers") or []
    if modifiers:
        return json.dumps(modifiers, ensure_ascii=False)
    return "无"


# ── 节点函数 ─────────────────────────────────────────────────

def report_node(state: AgentState, llm: Any) -> Dict[str, Any]:
    """Report Generator 节点函数。

    1. 从 AgentState 提取 6 路输出
    2. 拼接 System Prompt + 上下文
    3. 调用 LLM 生成 Markdown
    4. 写入 final_report
    """
    state_dict: Dict[str, Any] = dict(state) if not isinstance(state, dict) else state

    # ── 提取上游结论 ──
    recovery_text = _safe_summary(state_dict.get("recovery_report"))
    load_text = _safe_summary(state_dict.get("load_report"))
    performance_text = _safe_summary(state_dict.get("performance_report"))
    risk_text = _safe_summary(state_dict.get("risk_report"))
    recognition_text = _build_recognition_text(state_dict)

    ruling = state_dict.get("ruling") or {}
    verdict = ruling.get("verdict", "暂无裁决")
    action = ruling.get("action", "")
    modifiers_text = _build_modifiers_text(ruling)

    # ── 拼接 Prompt ──
    user_prompt = f"""
=== Recovery Coach 报告 ===
{recovery_text}

=== Load Coach 报告 ===
{load_text}

=== Performance Coach 报告 ===
{performance_text}

=== Risk Coach 报告 ===
{risk_text}

=== Recognition Engine 诊断 ===
{recognition_text}

=== Decision Engine 裁决 ===
裁决：{verdict}
动作：{action}
技术修饰：{modifiers_text}
"""

    # ── 调用 LLM ──
    messages = [
        SystemMessage(content=SYSTEM_PROMPT + get_language_instruction()),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)

    return {
        "final_report": {
            "date": state_dict.get("date", ""),
            "recommendation": ruling,
            "special_event": None,
            "markdown": response.content,
        }
    }


def create_report_agent(llm: Any):
    """Factory 函数 —— 返回绑定了 LLM 的 report_node。

    Args:
        llm: LangChain BaseChatModel 实例。

    Returns:
        callable: report_node(state) → Dict
    """
    def _node(state: AgentState) -> Dict[str, Any]:
        return report_node(state, llm)

    return _node