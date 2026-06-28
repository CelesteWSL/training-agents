# -*- coding: utf-8 -*-
"""Decision Engine —— 纯规则引擎，基于上游 Analyst 输出做训练决策。

包含 State Modifier（SRA 状态 → Gate 阈值调整）+ Waterfall Gate 评估
+ Technique Modifier。不调用 LLM。

节点函数：decision_node(state: AgentState) → Dict
"""

from typing import Any, Dict, List, Optional

from training_agents.agents.utils.agent_states import AgentState


# ── Gate 默认阈值 ──────────────────────────────────────────

GATE_DEFAULTS = {
    "recovery_score_low": 40,
    "consecutive_hard_days_limit": 3,
    "hr_drift_high": 10,
    "acwr_high": 1.5,
    "acwr_moderate_low": 1.3,
    "ramp_rate_high": 0.2,
    "recovery_debt_high": 20,
}


# ── 阈值字段可读名映射 ────────────────────────────────────

_THRESHOLD_LABELS = {
    "recovery_score_low": "recovery_score",
    "consecutive_hard_days_limit": "consecutive_hard_days",
    "hr_drift_high": "hr_drift",
    "acwr_high": "acwr",
    "acwr_moderate_low": "acwr",
    "ramp_rate_high": "ramp_rate",
    "recovery_debt_high": "recovery_debt",
}

# ── Severity Mapping ───────────────────────────────────────
# Primary State 按 severity 从高到低匹配后，查此表获取阈值调节规则。

SEVERITY_MAP: Dict[str, Dict[str, Any]] = {
    "injury_onset_pattern": {
        "severity": 100,
        "gate": "safety",
        "adjustments": {
            "_safety_add_rule": True,
        },
    },
    "non_functional_overreaching": {
        "severity": 90,
        "gate": "load",
        "adjustments": {
            "acwr_high": 1.2,
            "_action_override": "full_rest",
        },
    },
    "cns_fatigue": {
        "severity": 80,
        "gate": "recovery",
        "adjustments": {
            "recovery_score_low": 55,
            "consecutive_hard_days_limit": 2,
        },
    },
    "cardiovascular_strain": {
        "severity": 70,
        "gate": "recovery",
        "adjustments": {
            "hr_drift_high": 8,
        },
    },
    "muscular_fatigue": {
        "severity": 60,
        "gate": "load",
        "adjustments": {
            "_load_add_rule": True,
        },
    },
    "functional_overreaching": {
        "severity": 50,
        "gate": "recovery",
        "adjustments": {
            "recovery_score_low": 35,
            "acwr_high": 1.6,
        },
    },
}

# ── Action 映射 ────────────────────────────────────────────

ACTION_MAP = {
    "full_rest": {"status": "critical", "verdict": "建议完全休息"},
    "recovery_run": {"status": "warning", "verdict": "建议进行恢复跑"},
    "reduce_load": {"status": "warning", "verdict": "建议减量训练"},
    "quality_session": {"status": "good", "verdict": "可以执行高质量训练"},
    "normal_training": {"status": "good", "verdict": "按目标正常训练"},
}

# ── Technique Modifier 规则 ────────────────────────────────

TECHNIQUE_RULES = [
    {"key": "cadence_drill", "label": "步频练习", "metric": "cadence",
     "severity": "critical", "reason": "步频过低，需专项练习"},
    {"key": "gct_drill", "label": "触地时间练习", "metric": "gct",
     "severity_min": "warning", "reason": "触地时间过长"},
    {"key": "vo_drill", "label": "垂直振幅练习", "metric": "vo",
     "severity_min": "warning", "reason": "垂直振幅过大"},
    {"key": "lr_balance_drill", "label": "左右平衡练习", "metric": "lr_balance",
     "severity_min": "warning", "reason": "左右不平衡"},
]

SEVERITY_ORDER = {"low": 0, "warning": 1, "high": 2, "critical": 3}


# ── State Modifier ─────────────────────────────────────────

def _select_primary_state(
    physiological_states: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """选择 Primary State：confidence 过滤 → severity 排序 → 取最高。

    - 普通状态：confidence >= 0.5
    - functional_overreaching：confidence >= 0.7
    - 多个命中：按 severity 取最高
    - 无命中：返回 None
    """
    best: Optional[Dict[str, Any]] = None
    best_severity = -1

    for s in physiological_states:
        name = s.get("name", "")
        entry = SEVERITY_MAP.get(name)
        if not entry:
            continue

        confidence = float(s.get("confidence", 0.0))
        if name == "functional_overreaching":
            if confidence < 0.7:
                continue
        elif confidence < 0.5:
            continue

        severity = int(entry["severity"])
        if severity > best_severity:
            best_severity = severity
            best = s

    return best


def _describe_adjustment(adjustments: Dict[str, Any]) -> str:
    """生成 SRA 阈值调节文字描述。"""
    parts: List[str] = []
    for k, v in adjustments.items():
        if k.startswith("_"):
            continue
        default = GATE_DEFAULTS.get(k)
        if default is not None and default != v:
            label = _THRESHOLD_LABELS.get(k, k)
            parts.append(f"{label} 阈值 {default} → {v}")
    return ", ".join(parts)


def _get_sra_context(
    primary_state: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """构建 sra_context，无命中时返回 None。"""
    if not primary_state:
        return None

    name = primary_state["name"]
    entry = SEVERITY_MAP.get(name)
    if not entry:
        return None

    return {
        "primary_state": name,
        "confidence": primary_state.get("confidence", 0.0),
        "gate_affected": entry["gate"],
        "adjustment": _describe_adjustment(entry["adjustments"]),
    }


def _apply_sra_thresholds(
    primary_state: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """应用 SRA 阈值调整，以 GATE_DEFAULTS 为基值覆盖。"""
    thresholds = dict(GATE_DEFAULTS)
    if not primary_state:
        return thresholds

    name = primary_state["name"]
    entry = SEVERITY_MAP.get(name)
    if not entry:
        return thresholds

    for k, v in entry["adjustments"].items():
        if not k.startswith("_") and k in thresholds:
            thresholds[k] = v

    return thresholds


def _get_sra_special(
    primary_state: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """提取 SRA 特殊指令（新增规则、action 覆盖）。"""
    if not primary_state:
        return {"safety_add": False, "load_add": False, "action_override": None}

    name = primary_state["name"]
    entry = SEVERITY_MAP.get(name)
    if not entry:
        return {"safety_add": False, "load_add": False, "action_override": None}

    adj = entry["adjustments"]
    return {
        "safety_add": adj.get("_safety_add_rule", False),
        "load_add": adj.get("_load_add_rule", False),
        "action_override": adj.get("_action_override"),
    }


# ── Gate 评估 ──────────────────────────────────────────────

def _make_result(
    action: str, gate: str, rule: str,
    actual_value: Any, priority: int,
) -> Dict[str, Any]:
    """构建单个 gate 命中结果。"""
    info = ACTION_MAP[action]
    return {
        "status": info["status"],
        "action": action,
        "verdict": info["verdict"],
        "gate": gate,
        "rule": rule,
        "actual_value": actual_value,
        "priority": priority,
    }


def _eval_safety_gate(
    state: Dict[str, Any], sra_special: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Safety Gate (priority 1-4) + SRA 新增规则。"""
    risk = state.get("risk_report") or {}
    recovery = state.get("recovery_report") or {}

    # Priority 1
    if risk.get("risk_level") == "critical":
        return _make_result("full_rest", "safety",
                           "risk_level == 'critical'",
                           "critical", 1)

    # Priority 2
    irs = risk.get("injury_risk_score", 0)
    if irs >= 85:
        return _make_result("full_rest", "safety",
                           f"injury_risk_score >= 85",
                           irs, 2)

    # SRA 新增：injury_onset_pattern → risk_level == "high" → full_rest
    if sra_special["safety_add"] and risk.get("risk_level") == "high":
        return _make_result("full_rest", "safety",
                           "risk_level == 'high' (SRA: injury_onset_pattern)",
                           "high", 3)

    # Priority 3
    if risk.get("risk_level") == "high":
        rs = recovery.get("recovery_score", 100)
        if rs < 50:
            return _make_result("full_rest", "safety",
                               "risk_level == 'high' && recovery_score < 50",
                               rs, 3)

    # Priority 4
    if (recovery.get("recovery_status") == "critical"
            and recovery.get("fatigue_trend") == "accumulating"):
        return _make_result("full_rest", "safety",
                           "recovery_status == 'critical' && fatigue_trend == 'accumulating'",
                           recovery["recovery_status"], 4)

    return None


def _eval_recovery_gate(
    state: Dict[str, Any], thresholds: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Recovery Gate (priority 5-9)。"""
    recovery = state.get("recovery_report") or {}

    # Priority 5
    rs = recovery.get("recovery_score", 100)
    low = thresholds["recovery_score_low"]
    if rs < low:
        return _make_result("recovery_run", "recovery",
                           f"recovery_score < {low}", rs, 5)

    # Priority 6
    if recovery.get("recovery_status") == "warning":
        return _make_result("recovery_run", "recovery",
                           "recovery_status == 'warning'",
                           "warning", 6)

    # Priority 7
    rd = recovery.get("recovery_debt", 0)
    if rd > thresholds["recovery_debt_high"]:
        return _make_result("recovery_run", "recovery",
                           f"recovery_debt > {thresholds['recovery_debt_high']}",
                           rd, 7)

    # Priority 8
    if recovery.get("fatigue_trend") == "accumulating":
        return _make_result("recovery_run", "recovery",
                           "fatigue_trend == 'accumulating'",
                           "accumulating", 8)

    # Priority 9
    hd = recovery.get("hr_drift", 0)
    if hd > thresholds["hr_drift_high"]:
        return _make_result("recovery_run", "recovery",
                           f"hr_drift > {thresholds['hr_drift_high']}",
                           hd, 9)

    return None


def _eval_load_gate(
    state: Dict[str, Any], thresholds: Dict[str, Any],
    sra_special: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Load Gate (priority 10-12) + SRA 调节。"""
    load = state.get("load_report") or {}

    # SRA 新增：muscular_fatigue → reduce_load
    if sra_special["load_add"]:
        return _make_result("reduce_load", "load",
                           "SRA: muscular_fatigue → reduce_load",
                           "muscular_fatigue", 10)

    # Priority 10
    acwr = load.get("acwr", 0.0)
    if acwr >= thresholds["acwr_high"]:
        action = "reduce_load"
        if sra_special["action_override"]:
            action = sra_special["action_override"]
        return _make_result(action, "load",
                           f"acwr >= {thresholds['acwr_high']}",
                           acwr, 10)

    # Priority 11
    rr = load.get("ramp_rate", 0.0)
    if rr >= thresholds["ramp_rate_high"]:
        return _make_result("reduce_load", "load",
                           f"ramp_rate >= {thresholds['ramp_rate_high']}",
                           rr, 11)

    # Priority 12
    if thresholds["acwr_moderate_low"] <= acwr < thresholds["acwr_high"]:
        return _make_result("reduce_load", "load",
                           f"acwr in [{thresholds['acwr_moderate_low']}, "
                           f"{thresholds['acwr_high']})",
                           acwr, 12)

    return None


def _eval_performance_gate(
    state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Performance Gate (priority 13-14)。"""
    perf = state.get("performance_report") or {}

    # Priority 13
    if perf.get("efficiency_trend") == "improving":
        return _make_result("quality_session", "performance",
                           "efficiency_trend == 'improving'",
                           "improving", 13)

    # Priority 14
    if perf.get("decoupling_status") == "good":
        return _make_result("quality_session", "performance",
                           "decoupling_status == 'good'",
                           "good", 14)

    return None


# ── Technique Modifier ─────────────────────────────────────

def _eval_technique_modifiers(
    technique_flags: List[Dict[str, Any]], action: str,
) -> List[Dict[str, Any]]:
    """独立计算技术修饰器。full_rest 时不激活。"""
    if action == "full_rest":
        return []

    if not technique_flags:
        return []

    modifiers: List[Dict[str, Any]] = []
    has_critical = False

    for rule in TECHNIQUE_RULES:
        metric = rule["metric"]

        if "severity" in rule:
            # 精确 severity 匹配 (如 cadence_drill 要求 critical)
            match = next(
                (f for f in technique_flags
                 if f.get("metric") == metric and f.get("severity") == rule["severity"]),
                None,
            )
        else:
            # severity >= 阈值匹配
            min_val = SEVERITY_ORDER.get(rule.get("severity_min", "low"), 0)
            match = next(
                (f for f in technique_flags
                 if f.get("metric") == metric
                 and SEVERITY_ORDER.get(f.get("severity", "low"), 0) >= min_val),
                None,
            )

        if match:
            modifiers.append({
                "key": rule["key"],
                "label": rule["label"],
                "reason": rule["reason"],
            })
            if match.get("severity") == "critical":
                has_critical = True

    # technique_focus：>= 2 个 warning+ flag，且无 critical flag
    warning_count = sum(
        1 for f in technique_flags
        if SEVERITY_ORDER.get(f.get("severity", "low"), 0)
        >= SEVERITY_ORDER["warning"]
    )
    if warning_count >= 2 and not has_critical:
        modifiers.append({
            "key": "technique_focus",
            "label": "综合技术关注",
            "reason": "多项技术指标预警，综合关注",
        })

    return modifiers


# ── 节点入口 ────────────────────────────────────────────────

def decision_node(state: AgentState) -> Dict[str, Any]:
    """Decision Engine 节点函数。

    1. 从 state_recognition 提取 SRA 结果
    2. State Modifier：选 primary state → 调阈值
    3. Waterfall Gate：Safety → Recovery → Load → Performance → Default
    4. Technique Modifier：独立计算
    5. 构建 RulingResult
    """
    state_dict: Dict[str, Any] = dict(state) if not isinstance(state, dict) else state

    # ── Step 1: 提取 SRA ──
    sr = state_dict.get("state_recognition") or {}
    physiological_states = sr.get("physiological_states") or []

    # ── Step 2: State Modifier ──
    primary_state = _select_primary_state(physiological_states)
    sra_context = _get_sra_context(primary_state)
    thresholds = _apply_sra_thresholds(primary_state)
    sra_special = _get_sra_special(primary_state)

    # ── Step 3: Waterfall Gate ──
    result: Optional[Dict[str, Any]] = None

    result = _eval_safety_gate(state_dict, sra_special)
    if not result:
        result = _eval_recovery_gate(state_dict, thresholds)
    if not result:
        result = _eval_load_gate(state_dict, thresholds, sra_special)
    if not result:
        result = _eval_performance_gate(state_dict)
    if not result:
        result = _make_result("normal_training", "default",
                             "以上均未命中", "", 15)

    # ── Step 4: Technique Modifier ──
    perf = state_dict.get("performance_report") or {}
    technique_flags: List[Dict[str, Any]] = perf.get("technique_flags") or []
    modifiers = _eval_technique_modifiers(technique_flags, result["action"])

    # ── Step 5: 构建 RulingResult ──
    return {
        "ruling": {
            "status": result["status"],
            "action": result["action"],
            "verdict": result["verdict"],
            "sra_context": sra_context,
            "gate_hit": {
                "gate": result["gate"],
                "rule": result["rule"],
                "actual_value": result["actual_value"],
                "priority": result["priority"],
            },
            "modifiers": modifiers,
        }
    }
