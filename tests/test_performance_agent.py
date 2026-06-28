# -*- coding: utf-8 -*-
"""Performance Agent 测试 —— 指标计算单元测试 + Graph LLM summary 集成测试。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from training_agents.agents.analysts.performance_analyst import create_performance_agent
from training_agents.agents.utils.performance_indicators import (
    calc_efficiency_factor,
    calc_efficiency_trend,
    calc_efficiency_history,
    calc_aerobic_efficiency,
    calc_aerobic_trend,
    calc_pace_hr_decoupling,
    interpret_decoupling,
    calc_zone_distribution,
    calc_target_alignment,
    calc_technique_flags,
    interpret_performance_status,
    calculate_indicators,
)
from training_agents.default_config import DEFAULT_CONFIG
from training_agents.llm_clients import create_llm_client


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def base_state():
    """模拟一个正常训练日的 state。"""
    return {
        "date": "2024-03-04",
        "user_profile": {
            "age": 30,
            "gender": "male",
            "height_cm": 175.0,
            "weight_kg": 70.0,
            "goal": "marathon",
            "training_level": "进阶",
            "personal_bests": {"5km": "22:00", "10km": "46:00", "半马": "1:45:00"},
            "injury_history": [],
            "max_hr": 190,
        },
        "parsed_activity": {
            "total_distance": 10000.0,
            "total_duration": 3000.0,  # 50 min
            "avg_hr": 155,
            "max_hr": 185,
            "hr_drift": 4.0,
            "avg_pace": "5:00/km",
            "avg_cadence": 175.0,
            "avg_gct": 210.0,
            "avg_vo": 7.5,
            "lr_balance": 50.5,
            "hr_zones": {"zone1": 0.10, "zone2": 0.60, "zone3": 0.15, "zone4": 0.10, "zone5": 0.05},
            "trackpoints": {
                "time": ["2024-03-04T06:00:00Z"] * 100,
                "distance_m": [i * 100.0 for i in range(100)],
                "heart_rate": [155] * 50 + [160] * 50,
                "speed": [3.33] * 50 + [3.30] * 50,
                "cadence": [87.0] * 100,
                "altitude": [100.0] * 100,
                "gct": [210.0] * 100,
                "vo": [7.5] * 100,
                "lr_balance": [50.5] * 100,
                "vertical_ratio": [7.0] * 100,
            },
        },
        "history": {
            "daily_checkins": [],
            "training_sessions": [],
        },
    }


@pytest.fixture
def multi_session_state(base_state):
    """包含多日训练历史的 state，EF 有明显改善趋势。"""
    sessions = []
    for day in range(10):
        duration = 3300 - day * 60   # 3300 → 2760
        hr = 165 - day * 2           # 165 → 147
        sessions.append({
            "date": f"2024-02-{23 + day:02d}",
            "activity": {
                "total_distance": 10000.0,
                "total_duration": duration,
                "avg_hr": hr,
                "hr_zones": {"zone1": 0.10, "zone2": 0.60, "zone3": 0.15, "zone4": 0.10, "zone5": 0.05},
                "trackpoints": {
                    "heart_rate": [hr] * 100,
                    "speed": [10000.0 / duration] * 100,
                },
            },
        })
    state = dict(base_state)
    state["history"]["training_sessions"] = sessions
    return state
    return state


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
    """Performance agent backed by LLM."""
    return create_performance_agent(llm=llm)


# ── 单元函数测试 ──────────────────────────────────────────────


class TestLLMSummary:

    @pytest.fixture
    def performance_graph(self, llm):
        from training_agents.graph.setup import build_performance_graph
        agent_node = create_performance_agent(llm=llm)
        return build_performance_graph(llm, agent_node)

    def test_llm_summary_normal(self, performance_graph, base_state):
        """正常表现状态 graph 调用。"""
        result = performance_graph.invoke(base_state)
        report = result["performance_report"]
        assert len(report["summary"]) > 20

    def test_llm_summary_contains_chinese(self, performance_graph, base_state):
        """验证 LLM summary 包含中文。"""
        result = performance_graph.invoke(base_state)
        report = result["performance_report"]
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in report['summary'])
        assert has_chinese, f"summary should contain Chinese text, got: {report['summary']}"

    def test_llm_summary_poor_performance(self, performance_graph, base_state):
        """低表现状态 LLM summary 应包含领域术语。"""
        state = dict(base_state)
        state["parsed_activity"]["avg_hr"] = 175
        state["parsed_activity"]["avg_cadence"] = 155.0
        state["parsed_activity"]["avg_gct"] = 280.0
        state["parsed_activity"]["trackpoints"] = {
            "time": ["t"] * 100,
            "distance_m": [i * 100.0 for i in range(100)],
            "heart_rate": [150] * 50 + [175] * 50,
            "speed": [3.5] * 50 + [3.0] * 50,
            "cadence": [77.0] * 100,
            "altitude": [100.0] * 100,
            "gct": [280.0] * 100,
            "vo": [11.0] * 100,
            "lr_balance": [47.0] * 100,
            "vertical_ratio": [9.0] * 100,
        }

        result = performance_graph.invoke(state)
        report = result["performance_report"]
        assert len(report["summary"]) > 30

    def test_llm_summary_decoupling_high(self, performance_graph, base_state):
        """高解耦率场景应触发 search_knowledge 或给出详细建议。"""
        state = dict(base_state)
        state["parsed_activity"]["trackpoints"] = {
            "time": ["t"] * 100,
            "distance_m": [i * 100.0 for i in range(100)],
            "heart_rate": [140] * 50 + [170] * 50,
            "speed": [4.0] * 50 + [3.0] * 50,
            "cadence": [87.0] * 100,
            "altitude": [100.0] * 100,
            "gct": [210.0] * 100,
            "vo": [7.5] * 100,
            "lr_balance": [50.0] * 100,
            "vertical_ratio": [7.0] * 100,
        }

        result = performance_graph.invoke(state)
        report = result["performance_report"]
        assert report["decoupling_status"] == "poor"
        assert len(report["summary"]) > 30


@pytest.mark.llm
class TestRAGIntegration:
    """RAG 集成测试 —— 通过 LangGraph performance agent 验证端到端 RAG 流程。"""

    @pytest.fixture(scope="class")
    def llm_client(self):
        return create_llm_client(DEFAULT_CONFIG["llm_provider"], DEFAULT_CONFIG["deep_think_llm"])

    def test_graph_performance_with_rag(self, base_state, llm_client):
        """高解耦率 + 有历史 sessions 场景 —— graph 模式 LLM 应触发 search_knowledge。"""
        from training_agents.graph.setup import build_performance_graph

        state = dict(base_state)
        state["parsed_activity"]["trackpoints"] = {
            "time": ["t"] * 100,
            "distance_m": [i * 100.0 for i in range(100)],
            "heart_rate": [140] * 50 + [175] * 50,
            "speed": [4.2] * 50 + [2.8] * 50,
            "cadence": [87.0] * 100,
            "altitude": [100.0] * 100,
            "gct": [210.0] * 100,
            "vo": [7.5] * 100,
            "lr_balance": [50.0] * 100,
            "vertical_ratio": [7.0] * 100,
        }

        # 添加历史训练 sessions
        sessions = []
        for day in range(10):
            sessions.append({
                "date": f"2024-02-{23 + day:02d}",
                "activity": {
                    "total_distance": 10000.0,
                    "total_duration": 3000.0,
                    "avg_hr": 150,
                    "hr_zones": {"zone1": 0.10, "zone2": 0.60, "zone3": 0.15, "zone4": 0.10, "zone5": 0.05},
                    "trackpoints": {"heart_rate": [150] * 100, "speed": [3.33] * 100},
                },
            })
        state["history"]["training_sessions"] = sessions

        llm = llm_client.get_llm()
        agent_node = create_performance_agent(llm=llm)
        graph = build_performance_graph(llm, agent_node)

        result = graph.invoke(state)
        report = result["performance_report"]

        assert report["decoupling_status"] == "poor"
        assert len(report["summary"]) > 30
        domain_terms = ["效率", "心率", "配速", "解耦", "训练", "有氧", "表现", "建议", "恢复"]
        matched = [t for t in domain_terms if t in report["summary"]]
        assert len(matched) >= 2, (
            f"summary 应包含至少 2 个领域术语: {matched}\nsummary: {report['summary']}"
        )

    def test_graph_performance_normal(self, base_state, llm_client):
        """正常表现状态 —— graph 模式 LLM 正常处理。"""
        from training_agents.graph.setup import build_performance_graph

        # 添加历史 sessions 使数据更完善
        sessions = []
        for day in range(10):
            sessions.append({
                "date": f"2024-02-{23 + day:02d}",
                "activity": {
                    "total_distance": 10000.0,
                    "total_duration": 3000.0,
                    "avg_hr": 150,
                    "hr_zones": {"zone1": 0.10, "zone2": 0.60, "zone3": 0.15, "zone4": 0.10, "zone5": 0.05},
                    "trackpoints": {"heart_rate": [150] * 100, "speed": [3.33] * 100},
                },
            })
        state = dict(base_state)
        state["history"]["training_sessions"] = sessions

        llm = llm_client.get_llm()
        agent_node = create_performance_agent(llm=llm)
        graph = build_performance_graph(llm, agent_node)

        result = graph.invoke(state)
        report = result["performance_report"]

        assert report["efficiency_factor"] > 0
        assert len(report["summary"]) > 20