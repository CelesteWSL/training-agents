# -*- coding: utf-8 -*-
"""State Recognition 指标计算 —— 纯规则引擎，State Library + Gatekeeper + 权重积分制。

融合 Recovery / Load / Performance / Risk 四个 Agent 的输出，
识别 6 种潜在生理状态（Hidden Physiological State）。
"""

from typing import Any, Dict, List, Optional, Tuple


# ── Match Strength 计算 ──────────────────────────────────────

def _linear_match(value: float, low: float, high: float, reverse: bool = False) -> float:
    """数值指标线性插值。

    Args:
        value: 实际值
        low: 起评分线（Match=0）
        high: 满分线（Match=1.0）
        reverse: True 表示值越低越好（如 recovery_score 在某些场景中）
    """
    if low == high:
        return 1.0 if value >= high else 0.0

    if reverse:
        # 低值 → 高分：如 recovery_score < 50 得满分
        if value <= high:
            return 1.0
        if value >= low:
            return 0.0
        return round((low - value) / (low - high), 2)
    else:
        # 高值 → 高分
        if value >= high:
            return 1.0
        if value <= low:
            return 0.0
        return round((value - low) / (high - low), 2)


def _interval_match(value: float, low: float, high: float) -> float:
    """区间匹配：值在 [low, high] 内得 1.0，外按距离线性衰减。"""
    if low <= value <= high:
        return 1.0
    if value < low:
        return max(0.0, round(value / low, 2)) if low > 0 else 0.0
    # value > high: 按超出比例衰减，最远到 high*2 处衰减到 0
    decay_range = high  # 超出 high 的部分相对 high 衰减
    return max(0.0, round(1.0 - (value - high) / decay_range, 2))


def _severity_match(severity: Optional[str], low: str = "warning", low_score: float = 0.6) -> float:
    """离散 severity 指标匹配。

    critical → 1.0, high → 0.8, warning → 0.6, low → 0.0, null → 0.0
    """
    if not severity:
        return 0.0
    map_table = {"critical": 1.0, "high": 0.8, "warning": 0.6, "low": 0.0}
    return map_table.get(severity, 0.0)


def _trend_match(trend: Optional[str], target: str) -> float:
    """趋势离散匹配。"""
    if not trend:
        return 0.0
    return 1.0 if trend == target else 0.0


def _risk_level_match(level: Optional[str]) -> float:
    """风险等级匹配。"""
    if not level:
        return 0.0
    return {"critical": 1.0, "high": 0.6, "moderate": 0.0, "low": 0.0}.get(level, 0.0)


# ── 从 state 中安全提取字段 ──────────────────────────────────

def _get(state: dict, path: str, default=None):
    """安全提取嵌套字段，如 _get(state, 'recovery_report.recovery_score')"""
    keys = path.split(".")
    val = state
    for k in keys:
        if val is None:
            return default
        if isinstance(val, dict):
            val = val.get(k, default)
        else:
            return default
    return val if val is not None else default


def _get_technique_severity(technique_flags: list, metric: str) -> Optional[str]:
    """从 technique_flags 中提取指定指标的 severity。"""
    if not technique_flags:
        return None
    for flag in technique_flags:
        if isinstance(flag, dict) and flag.get("metric") == metric:
            return flag.get("severity")
    return None


# ── 单状态评分函数 ────────────────────────────────────────────

def _score_injury_onset(state: dict) -> Tuple[bool, float, float, str, list]:
    """伤病前兆模式。Gatekeeper: risk_level >= high"""
    risk_level = _get(state, "risk_report.risk_level")
    if risk_level not in ("high", "critical"):
        return False, 0.0, 100.0, 55, "", []

    lr_sev = _get_technique_severity(_get(state, "performance_report.technique_flags", []), "lr_balance")
    recovery_score = _get(state, "recovery_report.recovery_score", 100.0)

    indicators = []
    # lr_balance: 权重40, 满分 critical, 起评 warning(0.5)
    lr_match = _severity_match(lr_sev, "warning", 0.5)
    indicators.append({"metric": "lr_balance", "value": lr_sev, "match": lr_match, "weight": 40, "contribution": round(40 * lr_match, 1)})

    # recovery_score: 权重35, 满分 <50, 起评 <65
    rec_match = _linear_match(recovery_score, 65, 50, reverse=True)
    indicators.append({"metric": "recovery_score", "value": recovery_score, "match": rec_match, "weight": 35, "contribution": round(35 * rec_match, 1)})

    # risk_level: 权重25, 满分 critical, 起评 high(0.6)
    rl_match = _risk_level_match(risk_level)
    indicators.append({"metric": "risk_level", "value": risk_level, "match": rl_match, "weight": 25, "contribution": round(25 * rl_match, 1)})

    total = sum(i["contribution"] for i in indicators)
    triggered = total >= 55
    explanation = (
        f"身体已经开始通过代偿机制维持运动表现——左右平衡偏差 {lr_sev or '无数据'}（{lr_sev or 'N/A'}）是代偿的典型标志，"
        f"恢复评分仅 {recovery_score}，伤病风险等级 {risk_level}。继续增加训练负荷时，急性伤病风险显著升高。"
    )
    return triggered, total, 100.0, 55, explanation, indicators


def _score_non_functional_overreaching(state: dict) -> Tuple[bool, float, float, str, list]:
    """恶性超量训练。Gatekeeper: acwr > 1.3"""
    acwr = _get(state, "load_report.acwr", 0.0)
    if acwr <= 1.3:
        return False, 0.0, 100.0, 60, "", []

    recovery_score = _get(state, "recovery_report.recovery_score", 100.0)
    efficiency_trend = _get(state, "performance_report.efficiency_trend")
    fatigue_trend = _get(state, "recovery_report.fatigue_trend")

    indicators = []
    # recovery_score: 权重40, 满分 <40, 起评 <55
    rec_match = _linear_match(recovery_score, 55, 40, reverse=True)
    indicators.append({"metric": "recovery_score", "value": recovery_score, "match": rec_match, "weight": 40, "contribution": round(40 * rec_match, 1)})

    # efficiency_trend: 权重30, 满分 declining, 起评 stable(0.3)
    eff_match = 0.0
    if efficiency_trend == "declining":
        eff_match = 1.0
    elif efficiency_trend == "stable":
        eff_match = 0.3
    indicators.append({"metric": "efficiency_trend", "value": efficiency_trend, "match": eff_match, "weight": 30, "contribution": round(30 * eff_match, 1)})

    # fatigue_trend: 权重30, 满分 accumulating, 起评 stable(0.3)
    fat_match = 0.0
    if fatigue_trend == "accumulating":
        fat_match = 1.0
    elif fatigue_trend == "stable":
        fat_match = 0.3
    indicators.append({"metric": "fatigue_trend", "value": fatigue_trend, "match": fat_match, "weight": 30, "contribution": round(30 * fat_match, 1)})

    total = sum(i["contribution"] for i in indicators)
    triggered = total >= 60
    explanation = (
        f"身体无法完成训练刺激的有效适应——高负荷下恢复评分仅 {recovery_score}、"
        f"效率趋势 {efficiency_trend}、疲劳趋势 {fatigue_trend}，"
        f"多个信号同时出现说明已经越过可适应的边界。继续训练将导致表现持续退化和伤病风险上升。"
    )
    return triggered, total, 100.0, 60, explanation, indicators


def _score_cns_fatigue(state: dict) -> Tuple[bool, float, float, str, list]:
    """中枢神经疲劳。Gatekeeper: acwr > 1.2 或 fatigue_trend == accumulating"""
    acwr = _get(state, "load_report.acwr", 0.0)
    fatigue_trend = _get(state, "recovery_report.fatigue_trend")
    if not (acwr > 1.2 or fatigue_trend == "accumulating"):
        return False, 0.0, 100.0, 60, "", []

    resting_hr_deviation = _get(state, "recovery_report.resting_hr_deviation", 0.0)
    hr_drift = _get(state, "recovery_report.hr_drift", 0.0)
    recovery_score = _get(state, "recovery_report.recovery_score", 100.0)

    indicators = []
    # resting_hr_deviation: 权重40, 满分 >5, 起评 >2
    hrm_match = _linear_match(resting_hr_deviation, 2, 5)
    indicators.append({"metric": "resting_hr_deviation", "value": resting_hr_deviation, "match": hrm_match, "weight": 40, "contribution": round(40 * hrm_match, 1)})

    # hr_drift: 权重30, 满分 >8%, 起评 >3%
    hrd_match = _linear_match(hr_drift, 3, 8)
    indicators.append({"metric": "hr_drift", "value": hr_drift, "match": hrd_match, "weight": 30, "contribution": round(30 * hrd_match, 1)})

    # recovery_score: 权重30, 满分 <50, 起评 <65
    rec_match = _linear_match(recovery_score, 65, 50, reverse=True)
    indicators.append({"metric": "recovery_score", "value": recovery_score, "match": rec_match, "weight": 30, "contribution": round(30 * rec_match, 1)})

    total = sum(i["contribution"] for i in indicators)
    triggered = total >= 60
    explanation = (
        f"交感神经持续激活，恢复能力下降——晨脉偏离基线 {resting_hr_deviation}bpm 反映自主神经失衡，"
        f"运动中 HR 漂移 {hr_drift}% 反映中枢驱动力下降，恢复评分 {recovery_score} 进一步确认系统性恢复不足。"
        f"训练质量难以维持。"
    )
    return triggered, total, 100.0, 60, explanation, indicators


def _score_cardiovascular_strain(state: dict) -> Tuple[bool, float, float, str, list]:
    """心血管系统压力。Gatekeeper: hr_drift > 8"""
    hr_drift = _get(state, "recovery_report.hr_drift", 0.0)
    if hr_drift <= 8:
        return False, 0.0, 100.0, 50, "", []

    pace_hr_decoupling = _get(state, "performance_report.pace_hr_decoupling", 0.0)

    indicators = []
    # hr_drift: 权重55, 满分 >12%, 起评 >8%
    hrd_match = _linear_match(hr_drift, 8, 12)
    indicators.append({"metric": "hr_drift", "value": hr_drift, "match": hrd_match, "weight": 55, "contribution": round(55 * hrd_match, 1)})

    # pace_hr_decoupling: 权重45, 满分 >15%, 起评 >8%
    phd_match = _linear_match(pace_hr_decoupling, 8, 15)
    indicators.append({"metric": "pace_hr_decoupling", "value": pace_hr_decoupling, "match": phd_match, "weight": 45, "contribution": round(45 * phd_match, 1)})

    total = sum(i["contribution"] for i in indicators)
    triggered = total >= 50
    explanation = (
        f"心血管系统出现明显疲劳特征——HR 漂移 {hr_drift}% 表明维持同样输出需要更高的心率驱动，"
        f"Pace-HR 解耦率 {pace_hr_decoupling}% 进一步确认这不是暂时的环境因素，而是系统性的心血管效率下降。"
    )
    return triggered, total, 100.0, 50, explanation, indicators


def _score_muscular_fatigue(state: dict) -> Tuple[bool, float, float, str, list]:
    """局部肌肉疲劳。Gatekeeper: cadence severity >= warning 或 gct severity >= warning"""
    technique_flags = _get(state, "performance_report.technique_flags", [])
    cadence_sev = _get_technique_severity(technique_flags, "cadence")
    gct_sev = _get_technique_severity(technique_flags, "gct")

    if cadence_sev not in ("warning", "critical") and gct_sev not in ("warning", "critical"):
        return False, 0.0, 100.0, 50, "", []

    recovery_score = _get(state, "recovery_report.recovery_score", 0.0)

    indicators = []
    # cadence: 权重35, 满分 critical, 起评 warning(0.6)
    cad_match = _severity_match(cadence_sev, "warning", 0.6)
    indicators.append({"metric": "cadence", "value": cadence_sev, "match": cad_match, "weight": 35, "contribution": round(35 * cad_match, 1)})

    # gct: 权重35, 满分 critical, 起评 warning(0.6)
    gct_match = _severity_match(gct_sev, "warning", 0.6)
    indicators.append({"metric": "gct", "value": gct_sev, "match": gct_match, "weight": 35, "contribution": round(35 * gct_match, 1)})

    # recovery_score: 权重30, 满分 >85, 起评 >70（反向：高分=确认局部性疲劳）
    rec_match = _linear_match(recovery_score, 70, 85)
    indicators.append({"metric": "recovery_score", "value": recovery_score, "match": rec_match, "weight": 30, "contribution": round(30 * rec_match, 1)})

    total = sum(i["contribution"] for i in indicators)
    triggered = total >= 50
    explanation = (
        f"疲劳主要集中于局部肌群——步频 {cadence_sev or '正常'}、触地时间 {gct_sev or '正常'} 是局部肌肉疲劳的典型跑姿表现，"
        f"但恢复评分 {recovery_score}（>70）说明自主神经系统和整体代谢恢复良好，尚未发展为系统性疲劳。"
    )
    return triggered, total, 100.0, 50, explanation, indicators


def _score_functional_overreaching(state: dict) -> Tuple[bool, float, float, str, list]:
    """良性超量恢复。Gatekeeper: acwr > 1.2"""
    acwr = _get(state, "load_report.acwr", 0.0)
    if acwr <= 1.2:
        return False, 0.0, 100.0, 60, "", []

    recovery_score = _get(state, "recovery_report.recovery_score", 100.0)
    efficiency_trend = _get(state, "performance_report.efficiency_trend")
    risk_level = _get(state, "risk_report.risk_level")

    indicators = []
    # recovery_score: 权重45, 满分 [50, 70] 区间
    rec_match = _interval_match(recovery_score, 50, 70)
    indicators.append({"metric": "recovery_score", "value": recovery_score, "match": rec_match, "weight": 45, "contribution": round(45 * rec_match, 1)})

    # efficiency_trend: 权重30, 满分 improving, 起评 stable(0.7)
    eff_match = 0.0
    if efficiency_trend == "improving":
        eff_match = 1.0
    elif efficiency_trend == "stable":
        eff_match = 0.7
    indicators.append({"metric": "efficiency_trend", "value": efficiency_trend, "match": eff_match, "weight": 30, "contribution": round(30 * eff_match, 1)})

    # risk_level: 权重25, 满分 low, 起评 moderate(0.7)
    rl_match = 0.0
    if risk_level == "low":
        rl_match = 1.0
    elif risk_level == "moderate":
        rl_match = 0.7
    indicators.append({"metric": "risk_level", "value": risk_level, "match": rl_match, "weight": 25, "contribution": round(25 * rl_match, 1)})

    total = sum(i["contribution"] for i in indicators)
    triggered = total >= 60
    explanation = (
        f"身体正在完成训练适应——恢复评分 {recovery_score}（在 [50,70] 区间）、"
        f"效率趋势 {efficiency_trend}、风险等级 {risk_level}，"
        f"是超量恢复（Supercompensation）的理想前置条件。适当恢复后运动表现可能提升。"
    )
    return triggered, total, 100.0, 60, explanation, indicators


# ── 状态注册表 ───────────────────────────────────────────────

STATE_REGISTRY = [
    ("injury_onset_pattern", _score_injury_onset, 1),
    ("non_functional_overreaching", _score_non_functional_overreaching, 1),
    ("cns_fatigue", _score_cns_fatigue, 1),
    ("cardiovascular_strain", _score_cardiovascular_strain, 2),
    ("muscular_fatigue", _score_muscular_fatigue, 3),
    ("functional_overreaching", _score_functional_overreaching, 3),
]

# 抑制 FOR 的状态名集合
_FOR_SUPPRESSORS = {
    "injury_onset_pattern",
    "non_functional_overreaching",
    "cns_fatigue",
    "cardiovascular_strain",
}


# ── 公开接口 ─────────────────────────────────────────────────

def recognize_states(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """识别所有触发的生理状态。

    Args:
        state: AgentState dict，需包含 recovery_report / load_report / performance_report / risk_report。

    Returns:
        触发的 PhysiologicalState 列表，按 priority 排序。
    """
    triggered_states: List[Dict[str, Any]] = []
    triggered_names: set = set()

    for name, score_fn, priority in STATE_REGISTRY:
        triggered, total_score, max_score, threshold, explanation, indicators = score_fn(state)

        if not triggered:
            continue

        # FOR 抑制规则
        if name == "functional_overreaching":
            if triggered_names & _FOR_SUPPRESSORS:
                continue

        confidence = min(1.0, round(total_score / max_score, 2))

        triggered_states.append({
            "name": name,
            "priority": priority,
            "confidence": confidence,
            "total_score": round(total_score, 1),
            "threshold": threshold,
            "explanation": explanation,
            "indicators": indicators,
        })
        triggered_names.add(name)

    # 按 priority 升序
    triggered_states.sort(key=lambda s: s["priority"])
    return triggered_states
