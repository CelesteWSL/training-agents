# -*- coding: utf-8 -*-
"""State Recognition Agent 测试 —— 纯规则引擎，无 LLM 依赖。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from training_agents.agents.engines.recognition_engine import create_sra_agent, sra_node
from training_agents.agents.utils.state_recognition_indicators import (
    recognize_states,
    _linear_match,
    _interval_match,
    _severity_match,
)


# ── 辅助函数 ─────────────────────────────────────────────────

def _flag(metric, severity):
    return {"metric": metric, "current": 0, "benchmark": 0, "direction": "low", "severity": severity}


def _make_state(load=None, recovery=None, performance=None, risk=None):
    return {
        "load_report": load or {},
        "recovery_report": recovery or {},
        "performance_report": performance or {},
        "risk_report": risk or {},
    }


# ── Match Strength 单元测试 ──────────────────────────────────


class TestNodeFunction:

    def test_node_returns_state_recognition(self):
        state = {
            "load_report": {"acwr": 1.5},
            "recovery_report": {"recovery_score": 35.0, "fatigue_trend": "accumulating", "resting_hr_deviation": 0.0, "hr_drift": 0.0},
            "performance_report": {"efficiency_trend": "declining", "technique_flags": [], "pace_hr_decoupling": 0.0},
            "risk_report": {"risk_level": "low"},
        }

        result = sra_node(state)
        assert "state_recognition" in result
        sr = result["state_recognition"]

        print("\n========== StateRecognitionResult（完整输出） ==========")
        states = sr.get("physiological_states", []) if isinstance(sr, dict) else sr["physiological_states"]
        print(f"触发状态数: {len(states)}")
        for s in states:
            print(f"\n--- {s['name']} ---")
            print(f"  priority: {s.get('priority', 'N/A')}")
            print(f"  confidence: {s.get('confidence', 'N/A')}")
            print(f"  total_score: {s.get('total_score', 'N/A')}")
            print(f"  threshold: {s.get('threshold', 'N/A')}")
            print(f"  explanation: {s.get('explanation', 'N/A')}")
            print(f"  indicators:")
            for ind in s.get("indicators", []):
                print(f"    {ind['metric']}: value={ind['value']}, match={ind['match']}, weight={ind['weight']}, contribution={ind['contribution']}")
        if not states:
            print("(无异常状态触发)")
        print("======================================================\n")
    def test_factory(self):
        node = create_sra_agent()
        assert callable(node)
        assert node is sra_node

    def test_empty_state(self):
        result = sra_node({})
        sr = result["state_recognition"]
        states = sr.get("physiological_states", []) if isinstance(sr, dict) else sr["physiological_states"]
        assert states == []