# -*- coding: utf-8 -*-
"""Risk Agent 测试 —— Graph LLM summary 集成测试 + RAG 触发验证。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from training_agents.agents.analysts.risk_analyst import create_risk_agent
from training_agents.default_config import DEFAULT_CONFIG
from training_agents.llm_clients import create_llm_client


# ── 辅助函数 ──────────────────────────────────────────────────

def _flag(metric, current, severity="warning"):
    return {"metric": metric, "current": current, "benchmark": 0, "direction": "low", "severity": severity}


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def low_risk_state():
    """低风险：一切正常。"""
    return {
        "load_report": {"acwr": 1.0, "ramp_rate": 0.05},
        "recovery_report": {
            "recovery_score": 90.0, "fatigue_trend": "recovering",
            "recovery_debt_trend": "stable", "consecutive_hard_days": 0,
        },
        "performance_report": {"technique_flags": []},
        "user_profile": {"injury_history": [], "age": 25, "max_hr": 190},
    }


@pytest.fixture
def moderate_risk_state():
    """中等风险：ACWR 偏高 + 步频偏低。"""
    return {
        "load_report": {"acwr": 1.35, "ramp_rate": 0.12},
        "recovery_report": {
            "recovery_score": 65.0, "fatigue_trend": "stable",
            "recovery_debt_trend": "stable", "consecutive_hard_days": 2,
        },
        "performance_report": {
            "technique_flags": [_flag("cadence", 158, "warning")]
        },
        "user_profile": {"injury_history": [], "age": 32, "max_hr": 188},
    }


@pytest.fixture
def high_risk_state():
    """高风险：触发 RAG 检索（injury_risk > 60）。"""
    return {
        "load_report": {"acwr": 1.6, "ramp_rate": 0.25},
        "recovery_report": {
            "recovery_score": 25.0, "fatigue_trend": "accumulating",
            "recovery_debt_trend": "worsening", "consecutive_hard_days": 5,
        },
        "performance_report": {
            "technique_flags": [
                _flag("cadence", 155, "critical"),
                _flag("gct", 280, "critical"),
            ]
        },
        "user_profile": {"injury_history": ["膝盖"], "age": 55, "max_hr": 165},
    }


# ── LLM fixtures ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def llm():
    """Create LLM client via DEFAULT_CONFIG."""
    client = create_llm_client(
        DEFAULT_CONFIG["llm_provider"],
        DEFAULT_CONFIG["deep_think_llm"],
    )
    return client.get_llm()


@pytest.fixture
def risk_agent_node(llm):
    """Risk agent node function (LLM + tools bound)."""
    return create_risk_agent(llm=llm)


@pytest.fixture(scope="session")
def risk_graph():
    """Risk agent graph (session-level, LLM loaded once)."""
    from training_agents.graph.setup import build_risk_graph

    llm_client = create_llm_client(
        DEFAULT_CONFIG["llm_provider"],
        DEFAULT_CONFIG["deep_think_llm"],
    )
    llm = llm_client.get_llm()
    agent_node = create_risk_agent(llm=llm)
    return build_risk_graph(llm, agent_node)


# ── 集成测试 ──────────────────────────────────────────────────

class TestRiskAgentSummary:

    @pytest.mark.llm
    def test_node_low_risk(self, risk_agent_node, low_risk_state):
        """低风险场景：LLM 应生成简短 summary，不触发 RAG。"""
        result = risk_agent_node(low_risk_state)
        report = result["risk_report"]

        assert report["risk_level"] == "low"
        assert report["injury_risk_score"] == 0.0
        assert report["alerts"] == []
        assert len(report["summary"]) > 20

    @pytest.mark.llm
    def test_node_moderate_risk(self, risk_agent_node, moderate_risk_state):
        """中等风险场景：LLM 应生成有效中文 summary。"""
        result = risk_agent_node(moderate_risk_state)
        report = result["risk_report"]

        assert report["risk_level"] == "low"
        assert 20 <= report["injury_risk_score"] <= 30
        assert len(report["risk_factors"]) >= 1
        assert len(report["alerts"]) >= 1
        assert len(report["summary"]) > 30
        # 验证包含领域术语
        assert any(kw in report["summary"] for kw in ["风险", "伤病", "训练", "恢复"])

    @pytest.mark.llm
    def test_node_high_risk_triggers_rag(self, risk_agent_node, high_risk_state):
        """高风险场景（injury_risk > 60）：验证 RAG 被触发。"""
        result = risk_agent_node(high_risk_state)
        report = result["risk_report"]

        assert report["risk_level"] == "critical"
        assert report["injury_risk_score"] >= 95
        assert len(report["risk_factors"]) >= 5
        assert len(report["alerts"]) >= 3
        assert len(report["summary"]) > 30

    @pytest.mark.llm
    def test_graph_low_risk(self, risk_graph, low_risk_state):
        """Graph 模式：低风险正常产出。"""
        result = risk_graph.invoke(low_risk_state)
        report = result["risk_report"]

        assert report["risk_level"] == "low"
        assert report["injury_risk_score"] == 0.0
        assert len(report["summary"]) > 20

    @pytest.mark.llm
    def test_graph_high_risk_rag(self, risk_graph, high_risk_state):
        """Graph 模式：高风险触发 RAG 搜索知识库。"""
        result = risk_graph.invoke(high_risk_state)
        report = result["risk_report"]

        assert report["risk_level"] == "critical"
        assert report["injury_risk_score"] >= 95
        summary = report["summary"]
        assert len(summary) > 50
        # 验证 summary 包含运动伤病领域术语
        domain_terms = ["风险", "伤病", "训练", "恢复", "负荷", "休息", "建议", "膝盖", "步频"]
        matched = [t for t in domain_terms if t in summary]
        assert len(matched) >= 3, (
            f"summary 应包含至少 3 个领域术语: {matched}\nsummary: {summary}"
        )

    @pytest.mark.llm
    def test_graph_empty_reports_handled(self, risk_graph, llm):
        """空报告输入应正常处理。"""
        from training_agents.agents.analysts.risk_analyst import create_risk_agent
        from training_agents.graph.setup import build_risk_graph

        agent_node = create_risk_agent(llm=llm)
        graph = build_risk_graph(llm, agent_node)

        state = {
            "load_report": None,
            "recovery_report": None,
            "performance_report": None,
            "user_profile": {"injury_history": [], "age": 25},
        }
        result = graph.invoke(state)
        report = result["risk_report"]

        assert report["risk_level"] == "low"
        assert report["injury_risk_score"] == 0.0
        assert report["alerts"] == []
        assert len(report["summary"]) > 10
