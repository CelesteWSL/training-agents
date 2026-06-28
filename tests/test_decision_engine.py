# -*- coding: utf-8 -*-
"""Decision Engine 测试 —— State Modifier + Waterfall Gate + Technique Modifier。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from training_agents.agents.engines.decision_engine import (
    _select_primary_state,
    _apply_sra_thresholds,
    _get_sra_context,
    _get_sra_special,
    _eval_safety_gate,
    _eval_recovery_gate,
    _eval_load_gate,
    _eval_performance_gate,
    _eval_technique_modifiers,
    _make_result,
    decision_node,
    GATE_DEFAULTS,
    ACTION_MAP,
)


# ── 辅助函数 ─────────────────────────────────────────────────

def _state(**kwargs):
    return kwargs


def _sra_state(name, confidence=0.8):
    return {
        "name": name, "confidence": confidence, "priority": 1,
        "total_score": 80, "threshold": 50, "explanation": "", "indicators": [],
    }


def _tf(metric, severity):
    return {"metric": metric, "current": 0, "benchmark": 0, "direction": "low", "severity": severity}


# ── State Modifier ──────────────────────────────────────────

class TestSelectPrimaryState:
    def test_empty_returns_none(self):
        assert _select_primary_state([]) is None

    def test_single_state(self):
        states = [_sra_state("cns_fatigue", 0.83)]
        result = _select_primary_state(states)
        assert result["name"] == "cns_fatigue"

    def test_low_confidence_filtered(self):
        states = [_sra_state("cns_fatigue", 0.3)]
        assert _select_primary_state(states) is None

    def test_functional_overreaching_needs_07(self):
        states = [_sra_state("functional_overreaching", 0.6)]
        assert _select_primary_state(states) is None

    def test_functional_overreaching_passes_07(self):
        states = [_sra_state("functional_overreaching", 0.75)]
        result = _select_primary_state(states)
        assert result["name"] == "functional_overreaching"

    def test_highest_severity_wins(self):
        states = [
            _sra_state("cns_fatigue", 0.8),          # severity 80
            _sra_state("cardiovascular_strain", 0.8), # severity 70
        ]
        result = _select_primary_state(states)
        assert result["name"] == "cns_fatigue"

    def test_injury_onset_beats_all(self):
        states = [
            _sra_state("cns_fatigue", 0.9),              # severity 80
            _sra_state("injury_onset_pattern", 0.6),     # severity 100
            _sra_state("non_functional_overreaching", 0.8),  # severity 90
        ]
        result = _select_primary_state(states)
        assert result["name"] == "injury_onset_pattern"

    def test_unknown_state_ignored(self):
        states = [_sra_state("unknown_state", 0.9)]
        assert _select_primary_state(states) is None


class TestApplySRAThresholds:
    def test_no_state_returns_defaults(self):
        result = _apply_sra_thresholds(None)
        assert result == GATE_DEFAULTS

    def test_cns_fatigue_adjusts(self):
        state = _sra_state("cns_fatigue", 0.83)
        result = _apply_sra_thresholds(state)
        assert result["recovery_score_low"] == 55
        assert result["consecutive_hard_days_limit"] == 2
        assert result["hr_drift_high"] == GATE_DEFAULTS["hr_drift_high"]  # unchanged

    def test_non_functional_overreaching_adjusts(self):
        state = _sra_state("non_functional_overreaching", 0.8)
        result = _apply_sra_thresholds(state)
        assert result["acwr_high"] == 1.2

    def test_functional_overreaching_relaxes(self):
        state = _sra_state("functional_overreaching", 0.75)
        result = _apply_sra_thresholds(state)
        assert result["recovery_score_low"] == 35
        assert result["acwr_high"] == 1.6

    def test_cardiovascular_strain_adjusts(self):
        state = _sra_state("cardiovascular_strain", 0.7)
        result = _apply_sra_thresholds(state)
        assert result["hr_drift_high"] == 8


class TestGetSRAContext:
    def test_none_returns_none(self):
        assert _get_sra_context(None) is None

    def test_cns_fatigue_context(self):
        state = _sra_state("cns_fatigue", 0.83)
        ctx = _get_sra_context(state)
        assert ctx["primary_state"] == "cns_fatigue"
        assert ctx["confidence"] == 0.83
        assert ctx["gate_affected"] == "recovery"
        assert "40 → 55" in ctx["adjustment"]

    def test_injury_onset_context(self):
        state = _sra_state("injury_onset_pattern", 0.6)
        ctx = _get_sra_context(state)
        assert ctx["gate_affected"] == "safety"
        assert ctx["adjustment"] == ""


class TestGetSRASpecial:
    def test_none(self):
        result = _get_sra_special(None)
        assert result == {"safety_add": False, "load_add": False, "action_override": None}

    def test_safety_add_rule(self):
        state = _sra_state("injury_onset_pattern", 0.6)
        result = _get_sra_special(state)
        assert result["safety_add"] is True
        assert result["load_add"] is False
        assert result["action_override"] is None

    def test_action_override(self):
        state = _sra_state("non_functional_overreaching", 0.8)
        result = _get_sra_special(state)
        assert result["action_override"] == "full_rest"

    def test_load_add_rule(self):
        state = _sra_state("muscular_fatigue", 0.6)
        result = _get_sra_special(state)
        assert result["load_add"] is True


# ── Safety Gate ─────────────────────────────────────────────

class TestSafetyGate:
    def test_critical_risk(self):
        result = _eval_safety_gate(
            _state(risk_report={"risk_level": "critical"}),
            _get_sra_special(None),
        )
        assert result["action"] == "full_rest"
        assert result["priority"] == 1

    def test_injury_score_high(self):
        result = _eval_safety_gate(
            _state(risk_report={"risk_level": "moderate", "injury_risk_score": 90}),
            _get_sra_special(None),
        )
        assert result["action"] == "full_rest"
        assert result["priority"] == 2

    def test_risk_high_low_recovery(self):
        result = _eval_safety_gate(
            _state(
                risk_report={"risk_level": "high", "injury_risk_score": 50},
                recovery_report={"recovery_score": 30},
            ),
            _get_sra_special(None),
        )
        assert result["action"] == "full_rest"
        assert result["priority"] == 3

    def test_critical_recovery_accumulating(self):
        result = _eval_safety_gate(
            _state(
                risk_report={"risk_level": "moderate", "injury_risk_score": 50},
                recovery_report={"recovery_status": "critical", "fatigue_trend": "accumulating"},
            ),
            _get_sra_special(None),
        )
        assert result["action"] == "full_rest"
        assert result["priority"] == 4

    def test_sra_injury_onset_adds_rule(self):
        state = _sra_state("injury_onset_pattern", 0.6)
        result = _eval_safety_gate(
            _state(
                risk_report={"risk_level": "high", "injury_risk_score": 40},
                recovery_report={"recovery_score": 80},
            ),
            _get_sra_special(state),
        )
        assert result["action"] == "full_rest"
        assert "SRA" in result["rule"]

    def test_safety_pass(self):
        result = _eval_safety_gate(
            _state(
                risk_report={"risk_level": "low", "injury_risk_score": 10},
                recovery_report={"recovery_status": "good", "fatigue_trend": "stable", "recovery_score": 80},
            ),
            _get_sra_special(None),
        )
        assert result is None


# ── Recovery Gate ───────────────────────────────────────────

class TestRecoveryGate:
    def test_low_recovery_score(self):
        result = _eval_recovery_gate(
            _state(recovery_report={"recovery_score": 30}),
            GATE_DEFAULTS,
        )
        assert result["action"] == "recovery_run"
        assert result["priority"] == 5

    def test_recovery_warning(self):
        result = _eval_recovery_gate(
            _state(recovery_report={"recovery_score": 80, "recovery_status": "warning"}),
            GATE_DEFAULTS,
        )
        assert result["action"] == "recovery_run"
        assert result["priority"] == 6

    def test_recovery_debt_high(self):
        result = _eval_recovery_gate(
            _state(recovery_report={
                "recovery_score": 80, "recovery_status": "good",
                "recovery_debt": 30, "fatigue_trend": "stable", "hr_drift": 5,
            }),
            GATE_DEFAULTS,
        )
        assert result["action"] == "recovery_run"
        assert result["priority"] == 7

    def test_fatigue_accumulating(self):
        result = _eval_recovery_gate(
            _state(recovery_report={
                "recovery_score": 80, "recovery_status": "good",
                "recovery_debt": 5, "fatigue_trend": "accumulating", "hr_drift": 5,
            }),
            GATE_DEFAULTS,
        )
        assert result["action"] == "recovery_run"
        assert result["priority"] == 8

    def test_hr_drift_high(self):
        result = _eval_recovery_gate(
            _state(recovery_report={
                "recovery_score": 80, "recovery_status": "good",
                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 15,
            }),
            GATE_DEFAULTS,
        )
        assert result["action"] == "recovery_run"
        assert result["priority"] == 9

    def test_recovery_pass(self):
        result = _eval_recovery_gate(
            _state(recovery_report={
                "recovery_score": 80, "recovery_status": "good",
                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 5,
            }),
            GATE_DEFAULTS,
        )
        assert result is None

    def test_sra_cns_fatigue_catches_52(self):
        state = _sra_state("cns_fatigue", 0.83)
        thresholds = _apply_sra_thresholds(state)
        result = _eval_recovery_gate(
            _state(recovery_report={"recovery_score": 52}),
            thresholds,
        )
        assert result is not None
        assert result["action"] == "recovery_run"

    def test_sra_cardiovascular_strain_catches_hr9(self):
        state = _sra_state("cardiovascular_strain", 0.7)
        thresholds = _apply_sra_thresholds(state)
        result = _eval_recovery_gate(
            _state(recovery_report={
                "recovery_score": 80, "recovery_status": "good",
                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 9,
            }),
            thresholds,
        )
        assert result is not None
        assert result["action"] == "recovery_run"


# ── Load Gate ───────────────────────────────────────────────

class TestLoadGate:
    def test_acwr_high(self):
        result = _eval_load_gate(
            _state(load_report={"acwr": 1.8}),
            GATE_DEFAULTS,
            _get_sra_special(None),
        )
        assert result["action"] == "reduce_load"
        assert result["priority"] == 10

    def test_ramp_rate_high(self):
        result = _eval_load_gate(
            _state(load_report={"acwr": 1.0, "ramp_rate": 0.3}),
            GATE_DEFAULTS,
            _get_sra_special(None),
        )
        assert result["action"] == "reduce_load"
        assert result["priority"] == 11

    def test_acwr_moderate(self):
        result = _eval_load_gate(
            _state(load_report={"acwr": 1.4, "ramp_rate": 0.05}),
            GATE_DEFAULTS,
            _get_sra_special(None),
        )
        assert result["action"] == "reduce_load"
        assert result["priority"] == 12

    def test_load_pass(self):
        result = _eval_load_gate(
            _state(load_report={"acwr": 1.0, "ramp_rate": 0.05}),
            GATE_DEFAULTS,
            _get_sra_special(None),
        )
        assert result is None

    def test_sra_nfor_action_upgrade(self):
        state = _sra_state("non_functional_overreaching", 0.8)
        thresholds = _apply_sra_thresholds(state)
        sra_special = _get_sra_special(state)
        result = _eval_load_gate(
            _state(load_report={"acwr": 1.3}),
            thresholds,
            sra_special,
        )
        assert result["action"] == "full_rest"

    def test_sra_muscular_fatigue_adds_rule(self):
        state = _sra_state("muscular_fatigue", 0.6)
        sra_special = _get_sra_special(state)
        result = _eval_load_gate(
            _state(load_report={"acwr": 1.0, "ramp_rate": 0.05}),
            GATE_DEFAULTS,
            sra_special,
        )
        assert result["action"] == "reduce_load"
        assert "muscular_fatigue" in result["rule"]


# ── Performance Gate ────────────────────────────────────────

class TestPerformanceGate:
    def test_efficiency_improving(self):
        result = _eval_performance_gate(
            _state(performance_report={"efficiency_trend": "improving"}),
        )
        assert result["action"] == "quality_session"
        assert result["priority"] == 13

    def test_decoupling_good(self):
        result = _eval_performance_gate(
            _state(performance_report={
                "efficiency_trend": "stable",
                "decoupling_status": "good",
            }),
        )
        assert result["action"] == "quality_session"
        assert result["priority"] == 14

    def test_performance_pass(self):
        result = _eval_performance_gate(
            _state(performance_report={
                "efficiency_trend": "stable",
                "decoupling_status": "moderate",
            }),
        )
        assert result is None


# ── Technique Modifier ──────────────────────────────────────

class TestTechniqueModifier:
    def test_full_rest_suppresses(self):
        result = _eval_technique_modifiers(
            [_tf("cadence", "critical")], "full_rest",
        )
        assert result == []

    def test_cadence_critical(self):
        result = _eval_technique_modifiers(
            [_tf("cadence", "critical")], "normal_training",
        )
        assert any(m["key"] == "cadence_drill" for m in result)

    def test_gct_warning(self):
        result = _eval_technique_modifiers(
            [_tf("gct", "warning")], "quality_session",
        )
        assert any(m["key"] == "gct_drill" for m in result)

    def test_vo_warning(self):
        result = _eval_technique_modifiers(
            [_tf("vo", "warning")], "recovery_run",
        )
        assert any(m["key"] == "vo_drill" for m in result)

    def test_lr_balance_high(self):
        result = _eval_technique_modifiers(
            [_tf("lr_balance", "high")], "quality_session",
        )
        assert any(m["key"] == "lr_balance_drill" for m in result)

    def test_cadence_warning_not_enough_for_drill(self):
        result = _eval_technique_modifiers(
            [_tf("cadence", "warning")], "normal_training",
        )
        assert not any(m["key"] == "cadence_drill" for m in result)

    def test_technique_focus(self):
        result = _eval_technique_modifiers(
            [_tf("gct", "warning"), _tf("vo", "warning")], "normal_training",
        )
        assert any(m["key"] == "technique_focus" for m in result)

    def test_technique_focus_blocked_by_critical(self):
        result = _eval_technique_modifiers(
            [_tf("cadence", "critical"), _tf("gct", "warning"),
             _tf("vo", "warning")], "normal_training",
        )
        assert any(m["key"] == "cadence_drill" for m in result)
        assert not any(m["key"] == "technique_focus" for m in result)

    def test_empty_flags(self):
        result = _eval_technique_modifiers([], "normal_training")
        assert result == []


# ── decision_node 端到端 ────────────────────────────────────

class TestDecisionNode:
    def test_empty_state_defaults(self):
        result = decision_node({})
        ruling = result["ruling"]
        assert ruling["action"] == "normal_training"
        assert ruling["sra_context"] is None
        assert ruling["gate_hit"]["gate"] == "default"
        assert ruling["modifiers"] == []

    def test_critical_returns_full_rest(self):
        result = decision_node({"risk_report": {"risk_level": "critical"}})
        assert result["ruling"]["action"] == "full_rest"
        assert result["ruling"]["status"] == "critical"

    def test_sra_cns_fatigue_shifts_threshold(self):
        result = decision_node({
            "risk_report": {"risk_level": "low", "injury_risk_score": 10},
            "recovery_report": {
                "recovery_score": 52, "recovery_status": "good",
                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 5,
            },
            "state_recognition": {
                "physiological_states": [_sra_state("cns_fatigue", 0.83)],
            },
        })
        ruling = result["ruling"]
        assert ruling["action"] == "recovery_run"
        assert ruling["sra_context"] is not None
        assert ruling["sra_context"]["primary_state"] == "cns_fatigue"
        assert "55" in ruling["gate_hit"]["rule"]

    def test_none_reports_handled(self):
        result = decision_node({
            "risk_report": None,
            "recovery_report": None,
            "load_report": None,
            "performance_report": None,
        })
        assert result["ruling"]["action"] == "normal_training"

    def test_waterfall_priority(self):
        """Safety beats Recovery: both conditions met → Safety wins."""
        result = decision_node({
            "risk_report": {"risk_level": "critical", "injury_risk_score": 95},
            "recovery_report": {"recovery_score": 20},
        })
        assert result["ruling"]["action"] == "full_rest"
        assert result["ruling"]["gate_hit"]["gate"] == "safety"


# ── Action Map ──────────────────────────────────────────────

class TestActionMap:
    def test_all_actions_defined(self):
        assert len(ACTION_MAP) == 5
        for action in ["full_rest", "recovery_run", "reduce_load", "quality_session", "normal_training"]:
            assert action in ACTION_MAP
            assert "status" in ACTION_MAP[action]
            assert "verdict" in ACTION_MAP[action]


# ── Make Result ─────────────────────────────────────────────

class TestMakeResult:
    def test_returns_correct_structure(self):
        result = _make_result("recovery_run", "recovery", "test_rule", 42, 5)
        assert result["action"] == "recovery_run"
        assert result["gate"] == "recovery"
        assert result["rule"] == "test_rule"
        assert result["actual_value"] == 42
        assert result["priority"] == 5
        assert result["status"] == "warning"
        assert result["verdict"] == "建议进行恢复跑"
# ── decision_node 端到端输出验证 ────────────────────────────

class TestDecisionNodeFullOutput:
    """验证 decision_node 在不同场景下的完整输出结构。"""

    def _base_state(self):
        return {
            "risk_report": {"risk_level": "low", "injury_risk_score": 10},
            "recovery_report": {"recovery_score": 75, "recovery_status": "good",
                                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 5},
            "load_report": {"acwr": 1.1, "ramp_rate": 0.05},
            "performance_report": {"efficiency_trend": "stable", "decoupling_status": "moderate",
                                   "technique_flags": []},
        }

    def test_normal_training_output(self):
        """正常训练：所有 Gate 通过 → normal_training。"""
        result = decision_node(self._base_state())
        ruling = result["ruling"]
        assert ruling["action"] == "normal_training"
        assert ruling["status"] == "good"
        assert ruling["verdict"] == "按目标正常训练"
        assert ruling["sra_context"] is None
        assert ruling["gate_hit"]["gate"] == "default"
        assert ruling["gate_hit"]["priority"] == 15
        assert ruling["modifiers"] == []

    def test_full_rest_output(self):
        """完整休息：Safety Gate 命中 → full_rest，modifier 抑制。"""
        result = decision_node({
            "risk_report": {"risk_level": "critical", "injury_risk_score": 90},
            "performance_report": {
                "technique_flags": [
                    _tf("cadence", "critical"),
                    _tf("gct", "warning"),
                ],
            },
        })
        ruling = result["ruling"]
        assert ruling["action"] == "full_rest"
        assert ruling["status"] == "critical"
        assert ruling["verdict"] == "建议完全休息"
        assert ruling["gate_hit"]["gate"] == "safety"
        assert ruling["gate_hit"]["rule"] == "risk_level == 'critical'"
        assert ruling["gate_hit"]["actual_value"] == "critical"
        assert ruling["gate_hit"]["priority"] == 1
        assert ruling["modifiers"] == []
        assert ruling["sra_context"] is None

    def test_recovery_run_with_sra_output(self):
        """恢复跑 + SRA 介入：cns_fatigue 调整阈值 → recovery_run。"""
        result = decision_node({
            "risk_report": {"risk_level": "low", "injury_risk_score": 10},
            "recovery_report": {"recovery_score": 52, "recovery_status": "good",
                                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 5},
            "state_recognition": {
                "physiological_states": [
                    _sra_state("cns_fatigue", 0.83),
                ],
            },
        })
        ruling = result["ruling"]
        assert ruling["action"] == "recovery_run"
        assert ruling["status"] == "warning"
        assert ruling["verdict"] == "建议进行恢复跑"
        assert ruling["gate_hit"]["gate"] == "recovery"
        assert ruling["gate_hit"]["actual_value"] == 52
        assert ruling["sra_context"]["primary_state"] == "cns_fatigue"
        assert ruling["sra_context"]["confidence"] == 0.83
        assert ruling["sra_context"]["gate_affected"] == "recovery"
        assert "40 → 55" in ruling["sra_context"]["adjustment"]

    def test_reduce_load_with_sra_action_upgrade(self):
        """减量 → SRA NFOR 升级为 full_rest。"""
        result = decision_node({
            "risk_report": {"risk_level": "low", "injury_risk_score": 10},
            "recovery_report": {"recovery_score": 75, "recovery_status": "good",
                                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 5},
            "load_report": {"acwr": 1.3, "ramp_rate": 0.05},
            "state_recognition": {
                "physiological_states": [
                    _sra_state("non_functional_overreaching", 0.85),
                ],
            },
        })
        ruling = result["ruling"]
        assert ruling["action"] == "full_rest"
        assert ruling["status"] == "critical"
        assert ruling["verdict"] == "建议完全休息"
        assert ruling["gate_hit"]["gate"] == "load"
        assert "1.2" in ruling["gate_hit"]["rule"]
        assert ruling["sra_context"]["primary_state"] == "non_functional_overreaching"

    def test_quality_with_technique_modifiers(self):
        """质量训练 + 多项 technique flag → modifier 输出。"""
        result = decision_node({
            "risk_report": {"risk_level": "low", "injury_risk_score": 10},
            "recovery_report": {"recovery_score": 75, "recovery_status": "good",
                                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 5},
            "load_report": {"acwr": 1.1, "ramp_rate": 0.05},
            "performance_report": {
                "efficiency_trend": "improving",
                "decoupling_status": "moderate",
                "technique_flags": [
                    _tf("cadence", "critical"),
                    _tf("gct", "warning"),
                    _tf("lr_balance", "high"),
                ],
            },
        })
        ruling = result["ruling"]
        assert ruling["action"] == "quality_session"
        assert ruling["status"] == "good"
        assert ruling["verdict"] == "可以执行高质量训练"
        assert ruling["gate_hit"]["gate"] == "performance"
        assert ruling["gate_hit"]["rule"] == "efficiency_trend == 'improving'"
        modifier_keys = [m["key"] for m in ruling["modifiers"]]
        assert "cadence_drill" in modifier_keys
        assert "gct_drill" in modifier_keys
        assert "lr_balance_drill" in modifier_keys

    def test_waterfall_safety_beats_recovery(self):
        """Safety 命中时不进入 Recovery：即使 recovery_score 极低。"""
        result = decision_node({
            "risk_report": {"risk_level": "high", "injury_risk_score": 30},
            "recovery_report": {"recovery_score": 25, "recovery_status": "good",
                                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 5},
        })
        ruling = result["ruling"]
        assert ruling["action"] == "full_rest"
        assert ruling["gate_hit"]["gate"] == "safety"

    def test_waterfall_recovery_beats_load(self):
        """Recovery 命中时不进入 Load：即使 acwr 极高。"""
        result = decision_node({
            "risk_report": {"risk_level": "low", "injury_risk_score": 10},
            "recovery_report": {"recovery_score": 25, "recovery_status": "good",
                                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 5},
            "load_report": {"acwr": 2.0, "ramp_rate": 0.5},
        })
        ruling = result["ruling"]
        assert ruling["action"] == "recovery_run"
        assert ruling["gate_hit"]["gate"] == "recovery"

    def test_sra_safety_add_rule_catches_high_no_low_recovery(self):
        """SRA injury_onset: risk_level=high 且 recovery_score=80（正常）
        仍触发 full_rest，因为 SRA 新增条件不需要 recovery_score<50。"""
        result = decision_node({
            "risk_report": {"risk_level": "high", "injury_risk_score": 40},
            "recovery_report": {"recovery_score": 80, "recovery_status": "good",
                                "recovery_debt": 5, "fatigue_trend": "stable", "hr_drift": 5},
            "state_recognition": {
                "physiological_states": [
                    _sra_state("injury_onset_pattern", 0.65),
                ],
            },
        })
        ruling = result["ruling"]
        assert ruling["action"] == "full_rest"
        assert ruling["gate_hit"]["gate"] == "safety"
        assert "SRA" in ruling["gate_hit"]["rule"]
        assert ruling["sra_context"]["primary_state"] == "injury_onset_pattern"

    def test_return_keys_exist(self):
        """验证 decision_node 返回的所有顶层 key。"""
        result = decision_node(self._base_state())
        assert "ruling" in result
        ruling_keys = {"status", "action", "verdict", "sra_context",
                       "gate_hit", "modifiers"}
        assert set(result["ruling"].keys()) == ruling_keys
class TestDecisionNodeMDOutput:
    """对照 training-agent.md 输出示例，输出完整 ruling 结构。"""

    def test_md_example_output(self):
        """复现 MD 文档中的示例场景并输出。

        SRA: cns_fatigue (confidence 0.83)
        → State Modifier: recovery_score 阈值 40 → 55
        → Recovery Gate: recovery_score 52 < 55 命中
        → Technique: cadence critical → cadence_drill
        """
        import json

        result = decision_node({
            "risk_report": {"risk_level": "low", "injury_risk_score": 10},
            "recovery_report": {
                "recovery_score": 52,
                "recovery_status": "good",
                "recovery_debt": 5,
                "fatigue_trend": "stable",
                "hr_drift": 5,
            },
            "state_recognition": {
                "physiological_states": [
                    _sra_state("cns_fatigue", 0.83),
                ],
            },
            "performance_report": {
                "technique_flags": [
                    _tf("cadence", "critical"),
                ],
            },
        })

        ruling = result["ruling"]

        # ── 格式要求：原始指标值 → SRA 识别状态（含 confidence）
        #    → State Modifier 调整 → 阈值比对 → 命中 Gate
        #    → 最终 Action + Modifiers

        print("\n===== Decision Engine 输出 =====")
        print(f"原始指标: recovery_score=52, hr_drift=5, recovery_debt=5")
        print(f"SRA 识别: cns_fatigue confidence=0.83")
        print(f"State Modifier: recovery_score 阈值 40 → 55")
        print(f"阈值比对: recovery_score 52 < 55 → 命中 Recovery Gate")
        print(f"最终 Action: {ruling['action']} ({ruling['verdict']})")
        print()

        print(json.dumps(ruling, ensure_ascii=False, indent=2))

        # ── 字段验证 ──
        assert ruling["status"] == "warning"
        assert ruling["action"] == "recovery_run"
        assert ruling["verdict"] == "建议进行恢复跑"

        assert ruling["sra_context"]["primary_state"] == "cns_fatigue"
        assert ruling["sra_context"]["confidence"] == 0.83
        assert ruling["sra_context"]["gate_affected"] == "recovery"
        assert "40 → 55" in ruling["sra_context"]["adjustment"]

        assert ruling["gate_hit"]["gate"] == "recovery"
        assert "recovery_score < 55" in ruling["gate_hit"]["rule"]
        assert ruling["gate_hit"]["actual_value"] == 52
        assert ruling["gate_hit"]["priority"] == 5

        modifier_keys = [m["key"] for m in ruling["modifiers"]]
        assert "cadence_drill" in modifier_keys
