# -*- coding: utf-8 -*-
"""Recovery 指标计算工具 —— 纯计算层，无 LLM 依赖。

供 Recovery Analyst 使用的硬编码指标计算函数。
包括：静息心率基线、疲劳趋势、恢复评分、恢复负债等。
"""

from typing import Any, Dict, List
from datetime import datetime, timedelta


# ── 计算常量 ──────────────────────────────────────────────────

HR_DEVIATION_PENALTY_PER_BPM = 5
RPE_PENALTY_PER_POINT = 4
SORENESS_PENALTY_PER_POINT = 3
CONSECUTIVE_HARD_PENALTY = 8
RPE_HIGH_THRESHOLD = 6
SORENESS_HIGH_THRESHOLD = 2
DRIFT_NORMAL = 3.0
DRIFT_MILD = 6.0
FATIGUE_SLOPE_THRESHOLD = 0.5

# recovery_debt 计算常量
DEBT_WINDOW_DAYS = 7
DEBT_TREND_DAYS = 3
DEBT_DRIFT_BASELINE = 3.0      # hr_drift 低于此值不计入消耗
DEBT_COST_MULTIPLIER = 10.0    # (drift - baseline) × hours × multiplier


# ── 基础计算函数 ──────────────────────────────────────────────

def calc_resting_hr_baseline(checkins: List[dict], window: int = 7) -> float:
    """计算近 window 天静息心率基线（均值）。"""
    if not checkins:
        return 0.0
    recent = checkins[-min(window, len(checkins)):]
    values = [c["morning_hr"] for c in recent if c.get("morning_hr", 0) > 0]
    return sum(values) / len(values) if values else 0.0


def calc_fatigue_trend(checkins: List[dict], days: int = 3) -> str:
    """基于近 days 天静息心率斜率判断疲劳趋势。"""
    if len(checkins) < days:
        return "stable"
    recent = checkins[-days:]
    hrs = [c["morning_hr"] for c in recent]
    if len(hrs) < days:
        return "stable"
    n = len(hrs)
    x_mean = (n - 1) / 2.0
    y_mean = sum(hrs) / n
    num = sum((i - x_mean) * (hrs[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den > 0 else 0.0

    if slope > FATIGUE_SLOPE_THRESHOLD:
        return "accumulating"
    elif slope < -FATIGUE_SLOPE_THRESHOLD:
        return "recovering"
    return "stable"


def interpret_status(score: float) -> str:
    """将恢复评分映射为状态标签。"""
    if score >= 80:
        return "good"
    elif score >= 60:
        return "moderate"
    elif score >= 40:
        return "warning"
    return "critical"



# ── consecutive_hard_days ─────────────────────────────────

HARD_DAY_ZONE45_PCT = 0.20  # zone4+zone5 占比 > 20% 算高强度


def calc_consecutive_hard_days(
    training_sessions: List[dict],
    today: str,
) -> int:
    """计算从 today 向前追溯的连续高强度天数。

    判定规则：当日有训练 session 且 hr_zones 中 zone4+zone5 占比 > 20%。

    Args:
        training_sessions: [{date, activity: ParsedActivity}, ...]
        today: 当前日期 "YYYY-MM-DD"

    Returns:
        连续高强度天数（含 today）。
    """
    from datetime import datetime, timedelta

    if not training_sessions or not today:
        return 0

    # 按日期建立 session 索引
    session_by_date: Dict[str, dict] = {}
    for session in training_sessions:
        date_str = session.get("date", "")
        if date_str:
            session_by_date[date_str] = session

    today_dt = datetime.strptime(today, "%Y-%m-%d")
    count = 0
    cursor = today_dt

    while count < 30:  # 安全上限
        date_str = cursor.strftime("%Y-%m-%d")
        session = session_by_date.get(date_str)
        if session is None:
            break  # 休息日，停止计数

        activity = session.get("activity", {})
        hr_zones = activity.get("hr_zones", {})
        zone45 = hr_zones.get("zone4", 0.0) + hr_zones.get("zone5", 0.0)

        if zone45 > HARD_DAY_ZONE45_PCT:
            count += 1
        else:
            break  # 非高强度，停止计数

        cursor -= timedelta(days=1)

    return count


# ── recovery_debt / trend ───────────────────────────────────

def calc_recovery_debt(
    training_sessions: List[dict],
    window_days: int = DEBT_WINDOW_DAYS,
) -> float:
    """基于近期训练消耗计算累积恢复赤字。

    training_sessions: [{"date": str, "activity": ParsedActivity}, ...]
    每个训练日消耗 = max(0, hr_drift - 3.0) × 训练时长(小时) × 10
    recovery_debt = 近 window_days 天消耗之和
    """
    if not training_sessions:
        return 0.0

    recent = training_sessions[-min(window_days, len(training_sessions)):]
    total_cost = 0.0
    for session in recent:
        activity = session.get("activity", {})
        hr_drift = activity.get("hr_drift", 0.0)
        duration_s = activity.get("total_duration", 0.0)
        if hr_drift > DEBT_DRIFT_BASELINE and duration_s > 0:
            hours = duration_s / 3600.0
            cost = (hr_drift - DEBT_DRIFT_BASELINE) * hours * DEBT_COST_MULTIPLIER
            total_cost += cost

    return round(total_cost, 1)


def calc_recovery_debt_trend(
    training_sessions: List[dict],
    window_days: int = DEBT_WINDOW_DAYS,
    trend_days: int = DEBT_TREND_DAYS,
) -> str:
    """基于近期每日消耗的斜率判断恢复负债趋势。"""
    if len(training_sessions) < trend_days:
        return "stable"

    recent = training_sessions[-min(window_days, len(training_sessions)):]
    daily_costs: List[float] = []
    for session in recent:
        activity = session.get("activity", {})
        hr_drift = activity.get("hr_drift", 0.0)
        duration_s = activity.get("total_duration", 0.0)
        if hr_drift > DEBT_DRIFT_BASELINE and duration_s > 0:
            hours = duration_s / 3600.0
            daily_costs.append((hr_drift - DEBT_DRIFT_BASELINE) * hours * DEBT_COST_MULTIPLIER)
        else:
            daily_costs.append(0.0)

    if len(daily_costs) < trend_days:
        return "stable"

    last_n = daily_costs[-trend_days:]
    n = len(last_n)
    x_mean = (n - 1) / 2.0
    y_mean = sum(last_n) / n
    num = sum((i - x_mean) * (last_n[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den > 0 else 0.0

    if slope > 0.1:
        return "worsening"
    elif slope < -0.1:
        return "improving"
    return "stable"


# ── 综合指标计算 ──────────────────────────────────────────────

def calculate_indicators(state: Dict[str, Any]) -> Dict[str, Any]:
    """从 state 中计算所有恢复指标。

    Args:
        state: AgentState 或 dict，需包含 morning_hr, rpe, muscle_soreness,
               parsed_activity, history 字段。

    Returns:
        包含 baseline, resting_hr_deviation, fatigue_trend, hr_drift,
        recovery_score, status, recovery_debt, recovery_debt_trend 的 dict。
    """
    morning_hr = state.get("morning_hr", 0)
    rpe = state.get("rpe", 0)
    muscle_soreness = state.get("muscle_soreness", 0)
    parsed = state.get("parsed_activity", {})
    hr_drift = parsed.get("hr_drift", 0.0)
    history = state.get("history", {})
    checkins = history.get("daily_checkins", [])
    training_sessions = history.get("training_sessions", [])

    baseline = calc_resting_hr_baseline(checkins)
    resting_hr_deviation = round(morning_hr - baseline, 1) if baseline > 0 else 0.0
    fatigue_trend = calc_fatigue_trend(checkins)

    penalty = 0.0
    if baseline > 0:
        penalty += abs(resting_hr_deviation) * HR_DEVIATION_PENALTY_PER_BPM

    if rpe >= RPE_HIGH_THRESHOLD:
        penalty += (rpe - RPE_HIGH_THRESHOLD + 1) * RPE_PENALTY_PER_POINT

    if muscle_soreness > SORENESS_HIGH_THRESHOLD:
        penalty += (muscle_soreness - SORENESS_HIGH_THRESHOLD) * SORENESS_PENALTY_PER_POINT

    if hr_drift > DRIFT_MILD:
        penalty += (hr_drift - DRIFT_MILD) * 2

    recovery_score = max(0.0, min(100.0, 100.0 - penalty))
    recovery_score = round(recovery_score, 1)
    status = interpret_status(recovery_score)

    # recovery_debt 基于训练历史
    recovery_debt = calc_recovery_debt(training_sessions)
    recovery_debt_trend = calc_recovery_debt_trend(training_sessions)
    consecutive_hard_days = calc_consecutive_hard_days(training_sessions, state.get("date", ""))

    return {
        "baseline": baseline,
        "resting_hr_deviation": resting_hr_deviation,
        "fatigue_trend": fatigue_trend,
        "hr_drift": hr_drift,
        "recovery_score": recovery_score,
        "status": status,
        "recovery_debt": recovery_debt,
        "recovery_debt_trend": recovery_debt_trend,
        "consecutive_hard_days": consecutive_hard_days,
    }


def format_indicators(indicators: Dict[str, Any]) -> str:
    """将恢复指标格式化为 prompt 文本。"""
    debt_trend_cn = {
        "worsening": "上升中（需关注）",
        "improving": "下降中（好转）",
        "stable": "持平",
    }
    return (
        f"请评估以下跑者的恢复状态：\n\n"
        f"- 恢复评分: {indicators['recovery_score']:.0f}/100 ({indicators['status']})\n"
        f"- 静息心率偏离: {indicators['resting_hr_deviation']:+.1f} bpm（基线 {indicators['baseline']:.0f}）\n"
        f"- 疲劳趋势: {indicators['fatigue_trend']}\n"
        f"- 心率漂移: {indicators['hr_drift']:.1f}%\n"
        f"- 恢复负债: {indicators['recovery_debt']:.1f}，趋势 {debt_trend_cn.get(indicators['recovery_debt_trend'], indicators['recovery_debt_trend'])}"
    )
