# -*- coding: utf-8 -*-
"""Performance 指标计算工具 —— 纯计算层，无 LLM 依赖。

供 Performance Analyst 使用的硬编码指标计算函数。
包括：Efficiency Factor、Aerobic Efficiency、Pace-HR Decoupling、
心率区间分布、训练目标匹配度、跑步技术异常标记。
"""

from typing import Any, Dict, List, Optional


# ── 计算常量 ──────────────────────────────────────────────────

HISTORY_SESSIONS = 10         # 近 N 次训练用于效率趋势和区间分布
EF_TREND_SLOPE_THRESHOLD = 0.0005   # EF 斜率阈值
PHRD_GOOD = 5.0               # Pace-HR 解耦率 ≤ 5% 为 good
PHRD_MODERATE = 10.0          # 5%–10% 为 moderate，> 10% 为 poor
ZONE2_HR_MIN_RATIO = 0.60     # Zone2 心率下限比例（占 max_hr）
ZONE2_HR_MAX_RATIO = 0.70     # Zone2 心率上限比例（占 max_hr）

# 技术指标阈值
CADENCE_GOOD = 170            # spm
CADENCE_WARNING = 160
GCT_GOOD = 220                # ms
GCT_WARNING = 260
VO_GOOD = 8.0                 # cm
VO_WARNING = 10.0
VR_GOOD = 8.0                 # %
VR_WARNING = 10.0
LR_BALANCE_GOOD = 1.0         # 偏差 %
LR_BALANCE_WARNING = 2.0


# ── Efficiency Factor ────────────────────────────────────────

def calc_efficiency_factor(activity: dict) -> float:
    """计算单次训练的跑步效率因子 EF = 速度(m/s) / 平均心率(bpm)。"""
    total_distance = activity.get("total_distance", 0.0)
    total_duration = activity.get("total_duration", 0.0)
    avg_hr = activity.get("avg_hr", 0)

    if total_duration <= 0 or avg_hr <= 0:
        return 0.0

    pace_m_s = total_distance / total_duration
    return round(pace_m_s / avg_hr, 4)


def calc_efficiency_trend(
    training_sessions: List[dict],
    n_sessions: int = HISTORY_SESSIONS,
) -> str:
    """基于近 N 次训练的 EF 线性回归斜率判断效率趋势。"""
    recent = training_sessions[-min(n_sessions, len(training_sessions)):]
    ef_values = [
        calc_efficiency_factor(s.get("activity", {}))
        for s in recent
    ]
    ef_values = [v for v in ef_values if v > 0]
    if len(ef_values) < 2:
        return "stable"

    n = len(ef_values)
    x_mean = (n - 1) / 2.0
    y_mean = sum(ef_values) / n
    num = sum((i - x_mean) * (ef_values[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den > 0 else 0.0

    if slope > EF_TREND_SLOPE_THRESHOLD:
        return "improving"
    elif slope < -EF_TREND_SLOPE_THRESHOLD:
        return "declining"
    return "stable"


def calc_efficiency_history(
    training_sessions: List[dict],
    n_sessions: int = HISTORY_SESSIONS,
) -> List[Dict[str, object]]:
    """返回近 N 次训练的 EF 历史列表。"""
    recent = training_sessions[-min(n_sessions, len(training_sessions)):]
    result = []
    for s in recent:
        ef = calc_efficiency_factor(s.get("activity", {}))
        if ef > 0:
            result.append({
                "date": s.get("date", ""),
                "value": ef,
            })
    return result


# ── Aerobic Efficiency ───────────────────────────────────────

def calc_aerobic_efficiency(activity: dict, max_hr: int) -> float:
    """计算有氧效率：Zone2 区间内的配速/心率。

    从 trackpoints 中找出 HR 在 Zone2（60%–70% max_hr）的数据点，
    计算这些点的平均配速 / 平均心率。
    """
    if max_hr <= 0:
        return 0.0

    zone2_low = max_hr * ZONE2_HR_MIN_RATIO
    zone2_high = max_hr * ZONE2_HR_MAX_RATIO

    trackpoints = activity.get("trackpoints", {})
    hr_list = trackpoints.get("heart_rate", [])
    speed_list = trackpoints.get("speed", [])

    if not hr_list or not speed_list or len(hr_list) != len(speed_list):
        return 0.0

    zone2_speeds = []
    zone2_hrs = []
    for hr, speed in zip(hr_list, speed_list):
        if zone2_low <= hr <= zone2_high and speed > 0:
            zone2_speeds.append(speed)
            zone2_hrs.append(hr)

    if not zone2_speeds or not zone2_hrs:
        return 0.0

    avg_zone2_speed = sum(zone2_speeds) / len(zone2_speeds)
    avg_zone2_hr = sum(zone2_hrs) / len(zone2_hrs)

    if avg_zone2_hr <= 0:
        return 0.0

    return round(avg_zone2_speed / avg_zone2_hr, 4)


def calc_aerobic_trend(
    training_sessions: List[dict],
    max_hr: int,
    n_sessions: int = HISTORY_SESSIONS,
) -> Dict[str, str]:
    """分析 Zone2 配速和心率的变化方向。

    Returns:
        {"zone2_pace_trend": "improving"/"stable"/"declining",
         "zone2_hr_trend": "improving"/"stable"/"declining"}
    """
    recent = training_sessions[-min(n_sessions, len(training_sessions)):]

    pace_values = []
    hr_values = []
    for s in recent:
        activity = s.get("activity", {})
        trackpoints = activity.get("trackpoints", {})
        hr_list = trackpoints.get("heart_rate", [])
        speed_list = trackpoints.get("speed", [])

        if not hr_list or not speed_list:
            continue

        zone2_low = max_hr * ZONE2_HR_MIN_RATIO
        zone2_high = max_hr * ZONE2_HR_MAX_RATIO
        zone2_speeds = []
        zone2_hrs = []
        for hr, speed in zip(hr_list, speed_list):
            if zone2_low <= hr <= zone2_high and speed > 0:
                zone2_speeds.append(speed)
                zone2_hrs.append(hr)

        if zone2_speeds and zone2_hrs:
            pace_values.append(sum(zone2_speeds) / len(zone2_speeds))
            hr_values.append(sum(zone2_hrs) / len(zone2_hrs))

    def _trend_of(values: List[float]) -> str:
        if len(values) < 2:
            return "stable"
        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den > 0 else 0.0
        # 对于配速，斜率越大越好；对于心率，斜率越小越好
        return slope

    pace_slope = _trend_of(pace_values) if pace_values else 0.0
    hr_slope = _trend_of(hr_values) if hr_values else 0.0

    # Zone2 配速趋势：斜率 > 0 表示配速在提高（越来越好）
    if pace_slope > 0.01:
        pace_trend = "improving"
    elif pace_slope < -0.01:
        pace_trend = "declining"
    else:
        pace_trend = "stable"

    # Zone2 心率趋势：斜率 < 0 表示心率在降低（越来越好）
    if hr_slope < -0.1:
        hr_trend = "improving"
    elif hr_slope > 0.1:
        hr_trend = "declining"
    else:
        hr_trend = "stable"

    return {
        "zone2_pace_trend": pace_trend,
        "zone2_hr_trend": hr_trend,
    }


# ── Pace-HR Decoupling ───────────────────────────────────────

def calc_pace_hr_decoupling(activity: dict) -> float:
    """计算配速-心率解耦率（PHRD）。

    将训练分为前后两半，比较两半的 pace/HR 比值变化。
    PHRD = (first_ratio - second_ratio) / first_ratio × 100
    正值表示后半段效率下降（心率升高但配速未相应提高）。
    """
    trackpoints = activity.get("trackpoints", {})
    hr_list = trackpoints.get("heart_rate", [])
    speed_list = trackpoints.get("speed", [])

    if not hr_list or not speed_list or len(hr_list) < 4:
        return 0.0

    mid = len(hr_list) // 2
    first_hrs = [h for h in hr_list[:mid] if h > 0]
    first_speeds = [s for s in speed_list[:mid] if s > 0]
    second_hrs = [h for h in hr_list[mid:] if h > 0]
    second_speeds = [s for s in speed_list[mid:] if s > 0]

    if not first_hrs or not second_hrs or not first_speeds or not second_speeds:
        return 0.0

    first_avg_hr = sum(first_hrs) / len(first_hrs)
    first_avg_speed = sum(first_speeds) / len(first_speeds)
    second_avg_hr = sum(second_hrs) / len(second_hrs)
    second_avg_speed = sum(second_speeds) / len(second_speeds)

    if first_avg_hr <= 0 or second_avg_hr <= 0:
        return 0.0

    first_ratio = first_avg_speed / first_avg_hr
    second_ratio = second_avg_speed / second_avg_hr

    if first_ratio <= 0:
        return 0.0

    phr_d = (first_ratio - second_ratio) / first_ratio * 100
    return round(max(0.0, phr_d), 1)


def interpret_decoupling(phrd: float) -> str:
    """解读 Pace-HR 解耦率。"""
    if phrd <= PHRD_GOOD:
        return "good"
    elif phrd <= PHRD_MODERATE:
        return "moderate"
    return "poor"


# ── Zone Distribution ────────────────────────────────────────

def calc_zone_distribution(
    training_sessions: List[dict],
    n_sessions: int = HISTORY_SESSIONS,
) -> Dict[str, float]:
    """计算近 N 次训练的平均心率区间分布。"""
    recent = training_sessions[-min(n_sessions, len(training_sessions)):]
    all_zones = {f"zone{i}": [] for i in range(1, 6)}

    for s in recent:
        activity = s.get("activity", {})
        hr_zones = activity.get("hr_zones", {})
        for zone_name in all_zones:
            val = hr_zones.get(zone_name, 0.0)
            all_zones[zone_name].append(val)

    result = {}
    for zone_name, values in all_zones.items():
        if values:
            result[zone_name] = round(sum(values) / len(values), 3)
        else:
            result[zone_name] = 0.0
    return result


# ── Target Alignment ─────────────────────────────────────────
def calc_target_alignment(
    zone_distribution: Dict[str, float],
    user_goal: str,
) -> str:
    """判断训练结构是否与用户目标匹配。

    Args:
        zone_distribution: 近 N 次心率区间分布。
        user_goal: 用户运动目标，如"5km"/"10km"/"half_marathon"/"marathon"
    """
    z1 = zone_distribution.get("zone1", 0.0)
    z2 = zone_distribution.get("zone2", 0.0)
    z3 = zone_distribution.get("zone3", 0.0)
    z4 = zone_distribution.get("zone4", 0.0)
    z5 = zone_distribution.get("zone5", 0.0)

    total = z1 + z2 + z3 + z4 + z5
    if total < 0.01:
        return "insufficient_data"

    goal_lower = user_goal.lower()

    if "5km" in goal_lower:
        # 5km 需要 Zone3-4 的速度/阈值训练
        if (z3 + z4) >= 0.35:
            return "on_track"
        elif (z3 + z4) >= 0.20:
            return "mismatch"
        return "mismatch"

    elif "10km" in goal_lower:
        # 10km 需要有氧基础 + 阈值混合
        if z2 >= 0.50:
            return "on_track"
        elif z2 >= 0.35:
            return "mismatch"
        return "mismatch"

    elif "half_marathon" in goal_lower or "half marathon" in goal_lower:
        # 半马侧重有氧耐力
        if z2 >= 0.55:
            return "on_track"
        elif z2 >= 0.40:
            return "mismatch"
        return "mismatch"

    elif "marathon" in goal_lower:
        # 马拉松侧重 Zone2 有氧基础
        if z2 >= 0.60:
            return "on_track"
        elif z2 >= 0.45:
            return "mismatch"
        return "mismatch"

    else:
        # 默认：Zone2 为主的有氧基础 + 适量强度
        if z2 >= 0.45:
            return "on_track"
        elif z2 >= 0.30:
            return "mismatch"
        return "insufficient_data"



# ── Technique Flags ──────────────────────────────────────────

def _flag_severity(value: float, good: float, warning: float,
                   direction: str) -> Optional[Dict[str, object]]:
    """通用技术指标判定。

    Args:
        value: 当前值
        good: info 阈值
        warning: warning 阈值（与 good 相比的更差边界）
        direction: "higher_better" 或 "lower_better"
    """
    if value is None:
        return None

    if direction == "higher_better":
        if value >= good:
            return None  # 正常，不标记
        elif value >= warning:
            return {"severity": "warning"}
        else:
            return {"severity": "critical"}
    else:  # lower_better
        if value <= good:
            return None
        elif value <= warning:
            return {"severity": "warning"}
        else:
            return {"severity": "critical"}


def calc_technique_flags(activity: dict) -> List[Dict[str, object]]:
    """检测跑步技术异常标记。

    检查项：步频、触地时间、垂直振幅、垂直步幅比、左右平衡。
    """
    flags = []

    avg_cadence = activity.get("avg_cadence")
    if avg_cadence is not None:
        sev = _flag_severity(avg_cadence, CADENCE_GOOD, CADENCE_WARNING, "higher_better")
        if sev:
            flags.append({
                "metric": "cadence",
                "current": avg_cadence,
                "benchmark": CADENCE_GOOD,
                "direction": "higher_better",
                "severity": sev["severity"],
            })

    avg_gct = activity.get("avg_gct")
    if avg_gct is not None:
        sev = _flag_severity(avg_gct, GCT_GOOD, GCT_WARNING, "lower_better")
        if sev:
            flags.append({
                "metric": "gct",
                "current": avg_gct,
                "benchmark": GCT_GOOD,
                "direction": "lower_better",
                "severity": sev["severity"],
            })

    avg_vo = activity.get("avg_vo")
    if avg_vo is not None:
        sev = _flag_severity(avg_vo, VO_GOOD, VO_WARNING, "lower_better")
        if sev:
            flags.append({
                "metric": "vertical_oscillation",
                "current": avg_vo,
                "benchmark": VO_GOOD,
                "direction": "lower_better",
                "severity": sev["severity"],
            })

    # vertical_ratio 从 trackpoints 取平均
    trackpoints = activity.get("trackpoints", {})
    vr_values = trackpoints.get("vertical_ratio", [])
    if vr_values:
        vr_valid = [v for v in vr_values if v is not None]
        if vr_valid:
            avg_vr = sum(vr_valid) / len(vr_valid)
            sev = _flag_severity(avg_vr, VR_GOOD, VR_WARNING, "lower_better")
            if sev:
                flags.append({
                    "metric": "vertical_ratio",
                    "current": round(avg_vr, 1),
                    "benchmark": VR_GOOD,
                    "direction": "lower_better",
                    "severity": sev["severity"],
                })

    lr_balance = activity.get("lr_balance")
    if lr_balance is not None:
        deviation = abs(lr_balance - 50.0)
        if deviation > LR_BALANCE_GOOD:
            sev = "warning" if deviation <= LR_BALANCE_WARNING else "critical"
            flags.append({
                "metric": "lr_balance",
                "current": lr_balance,
                "benchmark": 50.0,
                "direction": "centered",
                "severity": sev,
            })

    return flags


# ── Status 判定 ──────────────────────────────────────────────

def interpret_performance_status(
    efficiency_trend: str,
    decoupling_status: str,
    technique_flags: List[Dict[str, object]],
    target_alignment: str,
) -> str:
    """综合判断表现状态，取各维度中最差的结果。"""
    order = {"good": 0, "moderate": 1, "warning": 2, "critical": 3}

    # 效率趋势 → status
    trend_map = {"improving": "good", "stable": "moderate", "declining": "warning"}
    ef_status = trend_map.get(efficiency_trend, "moderate")

    # 解耦 → status
    dec_map = {"good": "good", "moderate": "moderate", "poor": "warning"}
    dec_status = dec_map.get(decoupling_status, "moderate")

    # 技术异常 → status
    if not technique_flags:
        tech_status = "good"
    else:
        has_critical = any(f.get("severity") == "critical" for f in technique_flags)
        has_warning = any(f.get("severity") == "warning" for f in technique_flags)
        if has_critical:
            tech_status = "critical"
        elif has_warning:
            tech_status = "warning"
        else:
            tech_status = "good"

    # 目标匹配 → status
    align_map = {"on_track": "good", "mismatch": "warning", "insufficient_data": "moderate"}
    align_status = align_map.get(target_alignment, "moderate")

    worst = max(
        order[ef_status],
        order[dec_status],
        order[tech_status],
        order[align_status],
    )
    for label, idx in order.items():
        if idx == worst:
            return label
    return "moderate"


# ── 综合指标计算 ──────────────────────────────────────────────

def calculate_indicators(state: Dict[str, Any]) -> Dict[str, Any]:
    """从 state 中计算所有表现指标。

    Args:
        state: AgentState，需包含 parsed_activity、user_profile、history。

    Returns:
        包含 efficiency_factor, efficiency_trend, efficiency_history,
        aerobic_efficiency, aerobic_trend, pace_hr_decoupling, decoupling_status,
        zone_distribution, target_alignment, technique_flags, status 的 dict。
    """
    parsed = state.get("parsed_activity", {})
    user_profile = state.get("user_profile", {})
    history = state.get("history", {})
    training_sessions = history.get("training_sessions", [])

    max_hr = user_profile.get("max_hr") or 200
    user_goal = user_profile.get("goal", "general")

    efficiency_factor = calc_efficiency_factor(parsed)
    efficiency_trend = calc_efficiency_trend(training_sessions)
    efficiency_history = calc_efficiency_history(training_sessions)
    aerobic_efficiency = calc_aerobic_efficiency(parsed, max_hr)
    aerobic_trend = calc_aerobic_trend(training_sessions, max_hr)
    pace_hr_decoupling = calc_pace_hr_decoupling(parsed)
    decoupling_status = interpret_decoupling(pace_hr_decoupling)
    zone_distribution = calc_zone_distribution(training_sessions)
    target_alignment = calc_target_alignment(zone_distribution, user_goal)
    technique_flags = calc_technique_flags(parsed)
    status = interpret_performance_status(
        efficiency_trend, decoupling_status, technique_flags, target_alignment
    )

    return {
        "efficiency_factor": efficiency_factor,
        "efficiency_trend": efficiency_trend,
        "efficiency_history": efficiency_history,
        "aerobic_efficiency": aerobic_efficiency,
        "aerobic_trend": aerobic_trend,
        "pace_hr_decoupling": pace_hr_decoupling,
        "decoupling_status": decoupling_status,
        "zone_distribution": zone_distribution,
        "target_alignment": target_alignment,
        "technique_flags": technique_flags,
        "status": status,
    }


def format_indicators(indicators: Dict[str, Any]) -> str:
    """将表现指标格式化为 prompt 文本。"""
    trend_cn = {
        "improving": "提升中",
        "stable": "稳定",
        "declining": "下降中",
    }
    dec_cn = {
        "good": "良好",
        "moderate": "一般",
        "poor": "较差",
    }
    align_cn = {
        "on_track": "匹配",
        "mismatch": "不匹配",
        "insufficient_data": "数据不足",
    }

    zones = indicators.get("zone_distribution", {})
    zone_str = ", ".join(
        f"Zone{i}: {zones.get(f'zone{i}', 0.0):.0%}"
        for i in range(1, 6)
    )

    tech_lines = ""
    flags = indicators.get("technique_flags", [])
    if flags:
        tech_lines = "\n技术异常标记：\n"
        for f in flags:
            tech_lines += (
                f"  - {f['metric']}: 当前 {f['current']} "
                f"（基准 {f['benchmark']}），严重度 {f['severity']}\n"
            )

    aerobic = indicators.get("aerobic_trend", {})
    return (
        f"请评估以下跑者的运动表现状态：\n\n"
        f"- 跑步效率因子 (EF): {indicators.get('efficiency_factor', 0):.4f}"
        f"  （趋势: {trend_cn.get(indicators.get('efficiency_trend', 'stable'), 'stable')}）\n"
        f"- 有氧效率: {indicators.get('aerobic_efficiency', 0):.4f}"
        f"  （Zone2 配速趋势: {trend_cn.get(aerobic.get('zone2_pace_trend', 'stable'), 'stable')}"
        f"，Zone2 心率趋势: {trend_cn.get(aerobic.get('zone2_hr_trend', 'stable'), 'stable')}）\n"
        f"- 配速-心率解耦率: {indicators.get('pace_hr_decoupling', 0):.1f}%"
        f"  （状态: {dec_cn.get(indicators.get('decoupling_status', 'good'), 'good')}）\n"
        f"- 近{HISTORY_SESSIONS}次心率区间分布: {zone_str}\n"
        f"- 训练目标匹配度: {align_cn.get(indicators.get('target_alignment', 'insufficient_data'), 'insufficient_data')}"
        f"{tech_lines}"
        f"- 综合状态: {indicators.get('status', 'moderate')}"
)
