# -*- coding: utf-8 -*-
"""Recovery Agent 测试 —— 指标计算单元测试 + Graph LLM summary 集成测试。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from training_agents.agents.analysts.recovery_analyst import create_recovery_agent
from training_agents.agents.utils.recovery_indicators import (
    calc_resting_hr_baseline,
    calc_fatigue_trend,
    calc_recovery_debt,
    calc_recovery_debt_trend,
    interpret_status,
    calculate_indicators,
)
from training_agents.default_config import DEFAULT_CONFIG
from training_agents.llm_clients import create_llm_client


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def base_state():
    """模拟 2024-03-04 训练日的真实 state。"""
    return {
        "morning_hr": 57,
        "rpe": 5,
        "muscle_soreness": 2,
        "parsed_activity": {
            "hr_drift": 3.3,
            "avg_hr": 165,
            "max_hr": 193,
        },
        "history": {
            "daily_checkins": [
                {"date": "2024-02-26", "morning_hr": 58},
                {"date": "2024-02-27", "morning_hr": 57},
                {"date": "2024-02-28", "morning_hr": 59},
                {"date": "2024-02-29", "morning_hr": 58},
                {"date": "2024-03-01", "morning_hr": 56},
                {"date": "2024-03-02", "morning_hr": 57},
                {"date": "2024-03-03", "morning_hr": 58},
                {"date": "2024-03-04", "morning_hr": 57},
            ],
            "training_sessions": [],    # ← 没写具体跑步数据
        },
    }


# ── LLM fixtures ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def llm():
    """Create DeepSeek LLM client via DEFAULT_CONFIG (.env already loaded)."""
    client = create_llm_client(
        DEFAULT_CONFIG["llm_provider"],
        DEFAULT_CONFIG["deep_think_llm"],
    )
    return client.get_llm()


@pytest.fixture
def llm_agent(llm):
    """Recovery agent backed by DeepSeek LLM."""
    return create_recovery_agent(llm=llm)


# ── 单元函数测试 ──────────────────────────────────────────────


class TestRecoveryAgentNodeLLM:
    """LLM 驱动的 Recovery Agent Graph 测试。"""

    @pytest.fixture
    def recovery_graph(self, llm):
        from training_agents.graph.setup import build_recovery_graph
        agent_node = create_recovery_agent(llm=llm)
        return build_recovery_graph(llm, agent_node)

    @pytest.mark.llm
    def test_llm_summary_non_empty(self, recovery_graph, base_state):
        """验证 LLM summary 非空。"""
        result = recovery_graph.invoke(base_state)
        report = result["recovery_report"]
        assert len(report["summary"]) > 20

    @pytest.mark.llm
    def test_llm_summary_contains_chinese(self, recovery_graph, base_state):
        """验证 LLM summary 包含中文。"""
        result = recovery_graph.invoke(base_state)
        report = result["recovery_report"]
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in report['summary'])
        assert has_chinese, f"summary should contain Chinese text, got: {report['summary']}"

    @pytest.mark.llm
    def test_llm_summary_poor_recovery(self, recovery_graph):
        """低恢复状态 LLM summary 应触发 search_knowledge。"""
        state = {
            "morning_hr": 68,
            "rpe": 9,
            "muscle_soreness": 4,
            "parsed_activity": {"hr_drift": 8.0},
            "history": {
                "daily_checkins": [
                    {"date": f"d{i}", "morning_hr": 56}
                    for i in range(10)
                ],
                "training_sessions": [],
            },
        }
        result = recovery_graph.invoke(state)
        report = result["recovery_report"]
        assert len(report["summary"]) > 50


class TestRAGIntegration:
    """RAG 集成测试 —— 通过 LangGraph recovery agent 验证端到端 RAG 流程。

    LLM 自主决定是否 search_knowledge，不再 mock retrieve。
    """

    @pytest.mark.llm
    def test_graph_recovery_with_rag(self, base_state):
        """高心率偏离场景 —— graph 模式 LLM 应触发 search_knowledge。"""
        from training_agents.graph.setup import build_recovery_graph

        state = dict(base_state)
        state["morning_hr"] = 65  # baseline ~57.7, deviation ~7.3

        llm_client = create_llm_client(DEFAULT_CONFIG["llm_provider"], DEFAULT_CONFIG["deep_think_llm"])
        llm = llm_client.get_llm()
        agent_node = create_recovery_agent(llm=llm)
        graph = build_recovery_graph(llm, agent_node)

        result = graph.invoke(state)
        report = result["recovery_report"]

        assert report["recovery_score"] < 80
        assert len(report["summary"]) > 30
        assert any(kw in report["summary"] for kw in ["恢复", "训练", "心率", "建议"])

    @pytest.mark.llm
    def test_graph_recovery_low_score(self, base_state):
        """低恢复评分场景 —— graph 模式 LLM 应搜索恢复建议。"""
        from training_agents.graph.setup import build_recovery_graph

        state = {
            "morning_hr": 68,
            "rpe": 9,
            "muscle_soreness": 4,
            "parsed_activity": {"hr_drift": 8.0},
            "history": {
                "daily_checkins": [
                    {"date": f"d{i}", "morning_hr": 56}
                    for i in range(10)
                ],
                "training_sessions": [],
            },
        }

        llm_client = create_llm_client(DEFAULT_CONFIG["llm_provider"], DEFAULT_CONFIG["deep_think_llm"])
        llm = llm_client.get_llm()
        agent_node = create_recovery_agent(llm=llm)
        graph = build_recovery_graph(llm, agent_node)

        result = graph.invoke(state)
        report = result["recovery_report"]

        assert report["recovery_score"] < 50
        assert len(report["summary"]) > 30

    @pytest.mark.llm
    def test_graph_recovery_normal(self, base_state):
        """正常恢复状态 —— graph 模式 LLM 不需要搜索。"""
        from training_agents.graph.setup import build_recovery_graph

        llm_client = create_llm_client(DEFAULT_CONFIG["llm_provider"], DEFAULT_CONFIG["deep_think_llm"])
        llm = llm_client.get_llm()
        agent_node = create_recovery_agent(llm=llm)
        graph = build_recovery_graph(llm, agent_node)

        result = graph.invoke(base_state)
        report = result["recovery_report"]

        assert report["recovery_score"] >= 85
        assert len(report["summary"]) > 20

    @pytest.mark.llm
    def test_graph_recovery_searches_books(self, recovery_graph):
        """极低恢复状态验证 LLM 能从知识库搜索恢复建议。"""
        state = {
            "morning_hr": 70,
            "rpe": 8,
            "muscle_soreness": 3,
            "parsed_activity": {"hr_drift": 6.5},
            "history": {
                "daily_checkins": [
                    {"date": f"d{i}", "morning_hr": 55}
                    for i in range(10)
                ],
                "training_sessions": [],
            },
        }
        result = recovery_graph.invoke(state)
        report = result["recovery_report"]

        assert report["recovery_score"] < 60
        summary = report["summary"]
        assert len(summary) > 50
        # 验证 summary 包含运动恢复领域术语
        domain_terms = ["恢复", "训练", "心率", "疲劳", "睡眠", "营养", "休息", "负荷"]
        matched = [t for t in domain_terms if t in summary]
        assert len(matched) >= 3, (
            f"summary 应包含至少 3 个领域术语: {matched}\nsummary: {summary}"
        )