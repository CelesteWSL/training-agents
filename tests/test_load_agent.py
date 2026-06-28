# -*- coding: utf-8 -*-
"""Training Load Agent 测试 —— 指标计算单元测试 + Graph LLM summary 集成测试。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from training_agents.agents.analysts.load_analyst import create_load_agent
from training_agents.agents.utils.load_indicators import (
    calc_session_trimp,
    calc_acute_load,
    calc_chronic_load,
    calc_acwr,
    calc_weekly_volume,
    calc_ramp_rate,
    interpret_acwr,
    interpret_ramp_rate,
    interpret_status,
    calculate_indicators,
)
from training_agents.default_config import DEFAULT_CONFIG
from training_agents.llm_clients import create_llm_client


# ── 辅助函数 ──────────────────────────────────────────────────

def _make_session(date: str, hr_zones: dict, total_duration_s: float = 3600.0,
                  total_distance_m: float = 10000.0) -> dict:
    """快速构造训练 session。"""
    return {
        "date": date,
        "activity": {
            "hr_zones": hr_zones,
            "total_duration": total_duration_s,
            "total_distance": total_distance_m,
        },
    }


def _make_zones(z1=0.1, z2=0.5, z3=0.3, z4=0.08, z5=0.02):
    """快速构造 hr_zones dict。"""
    return {"zone1": z1, "zone2": z2, "zone3": z3, "zone4": z4, "zone5": z5}


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def base_state():
    """模拟有 28 天训练历史的 state。"""
    zones_normal = _make_zones()
    sessions = [
        _make_session(f"2024-03-{d:02d}", zones_normal, 3600, 10000)
        for d in range(1, 29)
    ]
    return {
        "date": "2024-03-28",
        "history": {
            "daily_checkins": [],
            "training_sessions": sessions,
        },
    }


@pytest.fixture
def empty_state():
    """无训练历史的 state。"""
    return {
        "date": "2024-03-28",
        "history": {
            "daily_checkins": [],
            "training_sessions": [],
        },
    }


@pytest.fixture
def high_load_state():
    """高负荷状态：近 7 天每天双倍训练量。"""
    zones = _make_zones()
    sessions = [
        _make_session(f"2024-03-{d:02d}", zones, 3600, 10000)
        for d in range(1, 22)  # d1-d21: 正常
    ]
    # d22-d28: 双倍训练量（一天两练）
    for d in range(22, 29):
        sessions.append(_make_session(f"2024-03-{d:02d}", zones, 3600, 10000))
        sessions.append(_make_session(f"2024-03-{d:02d}", zones, 3600, 10000))

    return {
        "date": "2024-03-28",
        "history": {
            "daily_checkins": [],
            "training_sessions": sessions,
        },
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
def llm_agent(llm):
    """Load agent backed by LLM."""
    return create_load_agent(llm=llm)


# ══════════════════════════════════════════════════════════════
#  单元测试：calc_session_trimp
# ══════════════════════════════════════════════════════════════


class TestLoadAgentLLM:

    @pytest.fixture
    def load_graph(self, llm):
        from training_agents.graph.setup import build_load_graph
        agent_node = create_load_agent(llm=llm)
        return build_load_graph(llm, agent_node)

    def test_llm_summary_normal(self, load_graph, base_state):
        """正常负荷状态 —— LLM 应直接生成 summary。"""
        from langchain_core.messages import HumanMessage

        state = dict(base_state)
        state["messages"] = [HumanMessage(content="评估训练负荷")]

        result = load_graph.invoke(state)
        report = result["load_report"]

        assert report["status"] in ("good", "moderate")
        assert len(report["summary"]) > 20

    def test_llm_summary_chinese(self, load_graph, base_state):
        """验证 LLM summary 包含中文。"""
        from langchain_core.messages import HumanMessage

        state = dict(base_state)
        state["messages"] = [HumanMessage(content="评估训练负荷")]

        result = load_graph.invoke(state)
        report = result["load_report"]
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in report['summary'])
        assert has_chinese, f"summary should contain Chinese text, got: {report['summary']}"

    def test_llm_summary_high_acwr(self, load_graph, high_load_state):
        """高 ACWR 状态 —— LLM 应触发 search_knowledge。"""
        from langchain_core.messages import HumanMessage

        state = dict(high_load_state)
        state["messages"] = [HumanMessage(content="评估训练负荷")]

        result = load_graph.invoke(state)
        report = result["load_report"]

        assert report["acwr"] > 1.3
        assert len(report["summary"]) > 30
        assert any(kw in report["summary"] for kw in ["负荷", "训练", "恢复", "建议"])

    def test_llm_summary_empty(self, load_graph, empty_state):
        """无训练数据 —— LLM 应生成合适的提示。"""
        from langchain_core.messages import HumanMessage

        state = dict(empty_state)
        state["messages"] = [HumanMessage(content="评估训练负荷")]

        result = load_graph.invoke(state)
        report = result["load_report"]

        assert report["acwr"] == 0.0
        assert len(report["summary"]) > 10
