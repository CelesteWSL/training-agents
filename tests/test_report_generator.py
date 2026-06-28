# -*- coding: utf-8 -*-
"""Report Generator 测试 —— 不调用真实 LLM。"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from training_agents.agents.report.report_generator import (
    _safe_summary,
    _build_recognition_text,
    _build_modifiers_text,
    create_report_agent,
)
from training_agents.agents.engines.decision_engine import decision_node


# ── 辅助函数 ─────────────────────────────────────────────────

def _mock_llm(response_text="mock report"):
    """创建一个返回固定文本的 mock LLM。"""
    llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = response_text
    llm.invoke.return_value = mock_response
    return llm


def _make_state(**kwargs):
    return kwargs


def _sra_state(name, confidence=0.8):
    return {
        "name": name, "confidence": confidence, "priority": 1,
        "total_score": 80, "threshold": 50, "explanation": f"{name} 检测到异常", "indicators": [],
    }


# ── 辅助函数测试 ─────────────────────────────────────────────


class TestCreateReportAgent:
    def test_factory_returns_callable(self):
        llm = _mock_llm()
        agent = create_report_agent(llm)
        assert callable(agent)

    def test_returns_final_report(self):
        llm = _mock_llm("## 报告内容")

        # 构造一个完整的 state
        ruling = decision_node({
            "risk_report": {"risk_level": "low", "injury_risk_score": 10},
            "recovery_report": {
                "recovery_score": 75, "recovery_status": "good",
                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 5,
                "summary": "恢复状态良好",
            },
            "load_report": {"acwr": 1.1, "ramp_rate": 0.05, "summary": "负荷适中"},
            "performance_report": {
                "efficiency_trend": "improving", "decoupling_status": "moderate",
                "technique_flags": [], "summary": "表现提升",
            },
            "risk_report": {"risk_level": "low", "summary": "风险低"},
            "state_recognition": {
                "physiological_states": [],
            },
        })

        state = {
            "date": "2026-06-08",
            "recovery_report": {"summary": "恢复状态良好"},
            "load_report": {"summary": "负荷适中"},
            "performance_report": {"summary": "表现提升"},
            "risk_report": {"summary": "风险低"},
            "state_recognition": {"physiological_states": []},
            "ruling": ruling["ruling"],
        }

        agent = create_report_agent(llm)
        result = agent(state)

        assert "final_report" in result
        assert result["final_report"]["date"] == "2026-06-08"
        assert result["final_report"]["markdown"] == "## 报告内容"
        assert result["final_report"]["special_event"] is None

    def test_llm_receives_correct_prompt(self):
        llm = _mock_llm()
        state = {
            "date": "",
            "recovery_report": {"summary": "R"},
            "load_report": {"summary": "L"},
            "performance_report": {"summary": "P"},
            "risk_report": {"summary": "RK"},
            "state_recognition": {"physiological_states": []},
            "ruling": {"verdict": "建议进行恢复跑", "action": "recovery_run", "modifiers": []},
        }

        agent = create_report_agent(llm)
        agent(state)

        # 验证 LLM 被调用且 prompt 包含关键内容
        call_args = llm.invoke.call_args
        assert call_args is not None
        messages = call_args[0][0]
        # SystemMessage + HumanMessage
        assert len(messages) == 2
        user_content = messages[1].content
        assert "Recovery Coach 报告" in user_content
        assert "R" in user_content
        assert "Decision Engine 裁决" in user_content
        assert "建议进行恢复跑" in user_content
    def test_md_example_output(self):
        """复现 MD 文档示例场景，输出完整 prompt 和 LLM 响应。"""
        import json

        state = {
            "date": "2026-06-08",
            "recovery_report": {
                "summary": "恢复评分下降至 52，静息心率偏离基线 7bpm，心率漂移达 9%，疲劳趋势为 accumulating，建议优先恢复。"
            },
            "load_report": {
                "summary": "ACWR 为 1.49，周负荷增长较快，已进入高风险区间，建议减量 20-30%。"
            },
            "performance_report": {
                "summary": "运动表现出现下降，跑步效率降低，步频 155spm 偏低。"
            },
            "risk_report": {
                "summary": "伤病风险中等偏高，需关注恢复状态和负荷管理。"
            },
            "state_recognition": {
                "physiological_states": [
                    {
                        "name": "cns_fatigue",
                        "confidence": 0.83,
                        "explanation": "交感神经持续激活，恢复能力下降——晨脉偏离基线 7bpm 反映自主神经失衡，运动中 HR 漂移 9% 反映中枢驱动力下降。训练质量难以维持。",
                    }
                ]
            },
            "ruling": {
                "verdict": "建议进行恢复跑",
                "action": "recovery_run",
                "modifiers": [
                    {"key": "cadence_drill", "label": "步频练习", "reason": "步频过低，需专项练习"}
                ],
            },
        }

        llm = _mock_llm("## 训练总结\\n\\n当前恢复状态较差，检测到明显中枢疲劳迹象。\\n\\n## 根因分析\\n\\nCNS Fatigue 检测确认。\\n\\n## 训练建议\\n\\nZone1 恢复跑 30-45 分钟，配合步频练习。")
        agent = create_report_agent(llm)
        result = agent(state)

        print("\n===== 发送给 LLM 的 User Prompt =====")
        messages = llm.invoke.call_args[0][0]
        print(messages[1].content)

        print("\n===== LLM 返回的 Markdown =====")
        print(result["final_report"]["markdown"])

        print("\n===== FinalReport 结构 =====")
        print(f"date: {result['final_report']['date']}")
        print(f"verdict: {result['final_report']['recommendation']['verdict']}")
        print(f"action: {result['final_report']['recommendation']['action']}")
        print(f"special_event: {result['final_report']['special_event']}")

        assert "cns_fatigue" in messages[1].content
        assert "83%" in messages[1].content
        assert result["final_report"]["date"] == "2026-06-08"


class TestReportGeneratorEdgeCases:
    def test_all_none_reports(self):
        """全部 report 为 None 时不崩溃。"""
        llm = _mock_llm()
        state = {
            "recovery_report": None,
            "load_report": None,
            "performance_report": None,
            "risk_report": None,
            "state_recognition": None,
            "ruling": None,
            "date": "",
        }
        agent = create_report_agent(llm)
        result = agent(state)
        assert "final_report" in result
        assert result["final_report"]["markdown"] == "mock report"

    def test_partial_reports(self):
        """部分 report 有值部分为 None。"""
        llm = _mock_llm()
        state = {
            "recovery_report": {"summary": "ok"},
            "load_report": None,
            "performance_report": {"summary": ""},
            "risk_report": {"summary": "ok"},
            "state_recognition": None,
            "ruling": {"verdict": "ok", "action": "ok", "modifiers": None},
            "date": "",
        }
        agent = create_report_agent(llm)
        result = agent(state)
        assert "final_report" in result

    def test_sra_context_in_prompt(self):
        """SRA 诊断信息出现在 prompt 中。"""
        llm = _mock_llm()
        state = {
            "recovery_report": {"summary": "R"},
            "load_report": {"summary": "L"},
            "performance_report": {"summary": "P"},
            "risk_report": {"summary": "RK"},
            "state_recognition": {
                "physiological_states": [
                    {"name": "cns_fatigue", "confidence": 0.9,
                     "explanation": "中枢疲劳——交感神经持续激活"},
                ]
            },
            "ruling": {"verdict": "建议进行恢复跑", "action": "recovery_run", "modifiers": [
                {"key": "cadence_drill", "label": "步频练习", "reason": "步频过低"}
            ]},
            "date": "",
        }
        agent = create_report_agent(llm)
        agent(state)

        messages = llm.invoke.call_args[0][0]
        user_content = messages[1].content
        assert "cns_fatigue" in user_content
        assert "90%" in user_content
        assert "中枢疲劳" in user_content
        assert "步频练习" in user_content
        assert "cadence_drill" in user_content
