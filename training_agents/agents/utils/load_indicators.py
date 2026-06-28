# -*- coding: utf-8 -*-
"""Training Load 指标计算工具 —— 纯计算层，无 LLM 依赖。

供 Load Analyst 使用的硬编码指标计算函数。
包括：Edwards TRIMP、Acute/Chronic Load、ACWR、Weekly Volume、Ramp Rate。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List


# ── 计算常量 ──────────────────────────────────────────────────

ACUTE_WINDOW = 7
CHRONIC_WINDOW = 28

# ACWR 判定阈值（Gabbett 2016）
ACWR_UNDERTRAINING = 0.8
ACWR_OPTIMAL = 1.3
ACWR_BORDERLINE = 1.5

# Ramp Rate 判定阈值（Nielsen 2014, 10% 法则）
RAMP_SAFE = 0.10
RAMP_MODERATE = 0.15
RAMP_CAUTION = 0.20


# ── Session TRIMP ────────────────────────────────────────────

def calc_session_trimp(activity: dict) -> float:
    """计算单次训练的 Edwards'' TRIMP（训练冲量）。

    Edwards, S. (1993). The Heart Rate Monitor Book.
    TRIMP = total_duration_min × Σ(zone_N_percentage × N)

    Args:
        activity: ParsedActivity，需包含 hr_zones 和 total_duration。

    Returns:
        TRIMP 值（任意单位 AU）。
    """
    hr_zones = activity.get("hr_zones", {})
    total_duration_s = activity.get("total_duration", 0)
    if total_duration_s <= 0 or not hr_zones:
        return 0.0

    total_duration_min = total_duration_s / 60.0
    weighted_sum = sum(
        hr_zones.get(f"zone{i}", 0.0) * i
        for i in range(1, 6)
    )
    return round(total_duration_min * weighted_sum, 1)


# ── 按天 TRIMP 映射 ──────────────────────────────────────────

def _build_daily_trimp_map(
    training_sessions: List[dict],
    from_date: str,
    to_date: str,
) -> Dict[str, float]:
    """构建日期 → 当日 TRIMP 总和的映射（含休息日=0）。

    Args:
        training_sessions: [{date, activity: ParsedActivity}, ...]
        from_date: 起始日期（含），"YYYY-MM-DD"
        to_date: 结束日期（含），"YYYY-MM-DD"
    """
    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    to_dt = datetime.strptime(to_date, "%Y-%m-%d")

    daily: Dict[str, float] = {}
    cursor = from_dt
    while cursor <= to_dt:
        daily[cursor.strftime("%Y-%m-%d")] = 0.0
        cursor += timedelta(days=1)

    for session in training_sessions:
        date_str = session.get("date", "")
        trimp = calc_session_trimp(session.get("activity", {}))
        if date_str in daily:
            daily[date_str] += trimp

    return daily


def _get_window_average(
    daily_trimp: Dict[str, float],
) -> float:
    """计算日均 TRIMP。"""
    if not daily_trimp:
        return 0.0
    values = list(daily_trimp.values())
    return round(sum(values) / len(values), 1)


# ── Acute / Chronic Load ─────────────────────────────────────

def calc_acute_load(
    training_sessions: List[dict],
    today: str,
    window: int = ACUTE_WINDOW,
) -> float:
    """急性负荷：近 window 天每日 TRIMP 均值（含休息日=0）。"""
    from_dt = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=window - 1)
    daily = _build_daily_trimp_map(
        training_sessions,
        from_dt.strftime("%Y-%m-%d"),
        today,
    )
    return _get_window_average(daily)


def calc_chronic_load(
    training_sessions: List[dict],
    today: str,
    window: int = CHRONIC_WINDOW,
) -> float:
    """慢性负荷：近 window 天每日 TRIMP 均值（含休息日=0）。"""
    from_dt = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=window - 1)
    daily = _build_daily_trimp_map(
        training_sessions,
        from_dt.strftime("%Y-%m-%d"),
        today,
    )
    return _get_window_average(daily)


# ── ACWR ─────────────────────────────────────────────────────

def calc_acwr(acute_load: float, chronic_load: float) -> float:
    """急慢性负荷比。chronic_load=0 时返回 0.0。"""
    if chronic_load <= 0:
        return 0.0
    return round(acute_load / chronic_load, 2)


# ── Weekly Volume ────────────────────────────────────────────

def calc_weekly_volume(
    training_sessions: List[dict],
    today: str,
    window: int = 7,
) -> float:
    """近 window 天累计跑量（公里）。"""
    from_dt = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=window - 1)
    from_str = from_dt.strftime("%Y-%m-%d")

    total_distance_m = 0.0
    for session in training_sessions:
        date_str = session.get("date", "")
        if from_str <= date_str <= today:
            total_distance_m += session.get("activity", {}).get("total_distance", 0.0)

    return round(total_distance_m / 1000.0, 1)


# ── Ramp Rate ────────────────────────────────────────────────

def calc_ramp_rate(
    training_sessions: List[dict],
    today: str,
) -> float:
    """周跑量增长率： (本周跑量 - 上周跑量) / 上周跑量。"""
    current_week = calc_weekly_volume(training_sessions, today, window=7)

    end_prev = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=7)
    start_prev = end_prev - timedelta(days=6)
    prev_week = calc_weekly_volume(
        training_sessions,
        end_prev.strftime("%Y-%m-%d"),
        window=7,
    )

    if prev_week <= 0:
        return 0.0

    return round((current_week - prev_week) / prev_week, 2)


# ── 解读函数 ─────────────────────────────────────────────────

def interpret_acwr(acwr: float) -> str:
    """ACWR 解读说明。"""
    if acwr == 0.0:
        return "历史数据不足，无法计算 ACWR"
    if acwr < ACWR_UNDERTRAINING:
        return "训练负荷偏低（undertraining），可适当增加训练量"
    if acwr <= ACWR_OPTIMAL:
        return "训练负荷处于最佳区间（optimal），当前负荷合理"
    if acwr <= ACWR_BORDERLINE:
        return "训练负荷偏高（borderline），建议关注恢复情况"
    return "训练负荷过高（overreaching），损伤风险显著上升，建议减量"


def interpret_ramp_rate(ramp_rate: float) -> str:
    """Ramp Rate 解读说明。"""
    if ramp_rate == 0.0:
        return "无上周对比数据"
    if ramp_rate <= RAMP_SAFE:
        return "周跑量增长在安全范围内（safe）"
    if ramp_rate <= RAMP_MODERATE:
        return "周跑量增长偏快，需关注恢复（moderate）"
    if ramp_rate <= RAMP_CAUTION:
        return "周跑量增长较快，中等风险（caution）"
    return "周跑量增长过快，高风险（aggressive），建议控制增幅"


def interpret_status(acwr: float, ramp_rate: float) -> str:
    """综合判断负荷状态，取 ACWR 与 Ramp Rate 中最差的结果。

    Returns:
        "good" / "moderate" / "warning" / "critical"
    """
    _order = {"good": 0, "moderate": 1, "warning": 2, "critical": 3}

    # ACWR → status
    if acwr == 0.0:
        acwr_status = "moderate"
    elif acwr < ACWR_UNDERTRAINING:
        acwr_status = "warning"
    elif acwr <= ACWR_OPTIMAL:
        acwr_status = "good"
    elif acwr <= ACWR_BORDERLINE:
        acwr_status = "warning"
    else:
        acwr_status = "critical"

    # Ramp Rate → status
    if ramp_rate == 0.0:
        ramp_status = "moderate"
    elif ramp_rate <= RAMP_SAFE:
        ramp_status = "good"
    elif ramp_rate <= RAMP_MODERATE:
        ramp_status = "warning"
    elif ramp_rate <= RAMP_CAUTION:
        ramp_status = "warning"
    else:
        ramp_status = "critical"

    if _order[acwr_status] >= _order[ramp_status]:
        return acwr_status
    return ramp_status


# ── 综合指标计算 ──────────────────────────────────────────────

def calculate_indicators(state: Dict[str, Any]) -> Dict[str, Any]:
    """从 state 中计算所有训练负荷指标。

    Args:
        state: AgentState，需包含 date 和 history.training_sessions。

    Returns:
        包含 acute_load, chronic_load, acwr, weekly_volume_km, ramp_rate,
        acwr_interpretation, ramp_rate_interpretation, status 的 dict。
    """
    history = state.get("history", {})
    training_sessions = history.get("training_sessions", [])
    today = state.get("date", "")

    if not today:
        return {
            "acute_load": 0.0,
            "chronic_load": 0.0,
            "acwr": 0.0,
            "weekly_volume_km": 0.0,
            "ramp_rate": 0.0,
            "status": "moderate",
            "acwr_interpretation": "缺少日期信息",
            "ramp_rate_interpretation": "缺少日期信息",
        }

    acute_load = calc_acute_load(training_sessions, today)
    chronic_load = calc_chronic_load(training_sessions, today)
    acwr = calc_acwr(acute_load, chronic_load)
    weekly_volume_km = calc_weekly_volume(training_sessions, today)
    ramp_rate = calc_ramp_rate(training_sessions, today)

    status = interpret_status(acwr, ramp_rate)
    acwr_interp = interpret_acwr(acwr)
    ramp_interp = interpret_ramp_rate(ramp_rate)

    return {
        "acute_load": acute_load,
        "chronic_load": chronic_load,
        "acwr": acwr,
        "weekly_volume_km": weekly_volume_km,
        "ramp_rate": ramp_rate,
        "status": status,
        "acwr_interpretation": acwr_interp,
        "ramp_rate_interpretation": ramp_interp,
    }


def format_indicators(indicators: Dict[str, Any]) -> str:
    """将负荷指标格式化为 prompt 文本。"""
    return (
        f"请评估以下跑者的训练负荷状态：\n\n"
        f"- ACWR（急慢性负荷比）: {indicators['acwr']:.2f}"
        f"  （急性 {indicators['acute_load']:.1f} / 慢性 {indicators['chronic_load']:.1f}）\n"
        f"- ACWR 解读: {indicators['acwr_interpretation']}\n"
        f"- 周跑量: {indicators['weekly_volume_km']:.1f} km\n"
        f"- 周跑量增长率: {indicators['ramp_rate']:+.0%}\n"
        f"- Ramp Rate 解读: {indicators['ramp_rate_interpretation']}\n"
        f"- 综合状态: {indicators['status']}"
    )
