# -*- coding: utf-8 -*-
"""Risk 指标计算工具 —— 纯计算层，无 LLM 依赖。

供 Risk Analyst 使用的硬编码指标计算函数。
包括：Injury Risk Score（四维阈值打分）、Risk Level 映射、Alerts 生成。
"""

from typing import Any, Dict, List, Optional


# ── 评分常量 ──────────────────────────────────────────────────

SCORE_LOAD_MAX = 40
SCORE_RECOVERY_MAX = 25
SCORE_TECHNIQUE_MAX = 20
SCORE_PROFILE_MAX = 15
CROSS_INTERACTION_BONUS = 5

# ACWR
ACWR_CRITICAL = 1.5
ACWR_WARNING = 1.3
ACWR_UNDER = 0.8

# Ramp Rate
RAMP_CRITICAL = 0.20
RAMP_WARNING = 0.15

# Recovery Score
RECOVERY_CRITICAL = 40
RECOVERY_WARNING = 60
RECOVERY_MODERATE = 80

# Age
AGE_ELEVATED = 50
AGE_WARNING = 40

# Technique: critical 最多 2 条，warning 最多 3 条
TECH_CRITICAL_MAX = 2
TECH_CRITICAL_PTS = 8
TECH_WARNING_MAX = 3
TECH_WARNING_PTS = 4

# 跨因子交互：旧伤关键词 → 关联技术指标
INJURY_TECH_MAP: Dict[str, List[str]] = {
    "膝盖": ["cadence", "gct", "lr_balance"],
    "跟腱": ["cadence", "gct"],
    "足底": ["cadence", "lr_balance"],
    "足底筋膜": ["cadence", "lr_balance"],
    "髋": ["cadence", "lr_balance"],
    "髋关节": ["cadence", "lr_balance"],
    "胫骨": ["gct", "vo", "vertical_ratio"],
    "应力": ["gct", "vo", "vertical_ratio"],
}


# ── Injury Risk Score ────────────────────────────────────────

def calc_injury_risk_score(
    acwr: float,
    ramp_rate: float,
    recovery_score: float,
    fatigue_trend: str,
    recovery_debt_trend: str,
    consecutive_hard_days: int,
    technique_flags: List[Dict[str, Any]],
    injury_history: List[str],
    age: int,
) -> Dict[str, Any]:
    """四维阈值打分，返回总分 + risk_factors。"""

    risk_factors: List[Dict[str, Any]] = []

    # ── 1. Load Risk (0-40) ──
    load_score = 0.0
    if acwr > ACWR_CRITICAL:
        load_score += 30
        risk_factors.append({"factor": "acwr", "value": acwr, "status": "critical", "source": "load"})
    elif acwr >= ACWR_WARNING:
        load_score += 15
        risk_factors.append({"factor": "acwr", "value": acwr, "status": "high", "source": "load"})
    elif 0 < acwr < ACWR_UNDER:
        load_score += 5
        risk_factors.append({"factor": "acwr", "value": acwr, "status": "elevated", "source": "load"})

    if ramp_rate > RAMP_CRITICAL:
        load_score += 10
        risk_factors.append({"factor": "ramp_rate", "value": round(ramp_rate, 2), "status": "critical", "source": "load"})
    elif ramp_rate >= RAMP_WARNING:
        load_score += 5
        risk_factors.append({"factor": "ramp_rate", "value": round(ramp_rate, 2), "status": "high", "source": "load"})

    load_score = min(load_score, SCORE_LOAD_MAX)

    # ── 2. Recovery Risk (0-25) ──
    rec_score = 0.0
    if recovery_score < RECOVERY_CRITICAL:
        rec_score += 25
        risk_factors.append({"factor": "recovery_score", "value": recovery_score, "status": "critical", "source": "recovery"})
    elif recovery_score < RECOVERY_WARNING:
        rec_score += 15
        risk_factors.append({"factor": "recovery_score", "value": recovery_score, "status": "high", "source": "recovery"})
    elif recovery_score < RECOVERY_MODERATE:
        rec_score += 5
        risk_factors.append({"factor": "recovery_score", "value": recovery_score, "status": "elevated", "source": "recovery"})

    if fatigue_trend == "accumulating":
        rec_score += 5
        risk_factors.append({"factor": "fatigue_trend", "value": "accumulating", "status": "elevated", "source": "recovery"})

    if recovery_debt_trend == "worsening":
        risk_factors.append({"factor": "recovery_debt_trend", "value": "worsening", "status": "elevated", "source": "recovery"})

    if consecutive_hard_days >= 6:
        rec_score += 5
        risk_factors.append({"factor": "consecutive_hard_days", "value": consecutive_hard_days, "status": "critical", "source": "recovery"})
    elif consecutive_hard_days >= 4:
        rec_score += 3
        risk_factors.append({"factor": "consecutive_hard_days", "value": consecutive_hard_days, "status": "high", "source": "recovery"})
    elif consecutive_hard_days >= 3:
        rec_score += 2
        risk_factors.append({"factor": "consecutive_hard_days", "value": consecutive_hard_days, "status": "elevated", "source": "recovery"})

    rec_score = min(rec_score, SCORE_RECOVERY_MAX)

    # ── 3. Technique Risk (0-20) ──
    tech_score = 0.0
    critical_count = 0
    warning_count = 0
    tech_metrics: List[str] = []  # 记录 metric 名，供跨因子交互使用

    for flag in technique_flags or []:
        severity = flag.get("severity", "")
        metric = flag.get("metric", "")
        current = flag.get("current")
        if severity == "critical":
            if critical_count < TECH_CRITICAL_MAX:
                tech_score += TECH_CRITICAL_PTS
                critical_count += 1
            risk_factors.append({"factor": metric, "value": current, "status": "critical", "source": "technique"})
            tech_metrics.append(metric)
        elif severity == "warning":
            if warning_count < TECH_WARNING_MAX:
                tech_score += TECH_WARNING_PTS
                warning_count += 1
            risk_factors.append({"factor": metric, "value": current, "status": "high", "source": "technique"})
            tech_metrics.append(metric)

    tech_score = min(tech_score, SCORE_TECHNIQUE_MAX)

    # ── 4. User Profile Risk (0-15) ──
    profile_score = 0.0
    for injury in (injury_history or []):
        risk_factors.append({"factor": "injury_history", "value": injury, "status": "elevated", "source": "user_profile"})

    if injury_history:
        profile_score += 10

    if age > AGE_ELEVATED:
        profile_score += 8
        risk_factors.append({"factor": "age", "value": age, "status": "high", "source": "user_profile"})
    elif age > AGE_WARNING:
        profile_score += 5
        risk_factors.append({"factor": "age", "value": age, "status": "elevated", "source": "user_profile"})

    profile_score = min(profile_score, SCORE_PROFILE_MAX)

    # ── 5. Cross-Interaction Bonus (+5) ──
    cross = 0.0
    if injury_history and tech_metrics:
        for injury_kw in injury_history:
            for map_kw, linked_metrics in INJURY_TECH_MAP.items():
                if map_kw in injury_kw:
                    if any(m in linked_metrics for m in tech_metrics):
                        cross = CROSS_INTERACTION_BONUS
                        break
            if cross > 0:
                break

    total = round(load_score + rec_score + tech_score + profile_score + cross, 1)
    total = max(0.0, min(100.0, total))

    return {
        "injury_risk_score": total,
        "breakdown": {
            "load": load_score,
            "recovery": rec_score,
            "technique": tech_score,
            "profile": profile_score,
            "cross_interaction": cross,
        },
        "risk_factors": risk_factors,
    }


# ── Risk Level ───────────────────────────────────────────────

def map_risk_level(score: float) -> str:
    """分值 → 风险等级。"""
    if score >= 81:
        return "critical"
    elif score >= 61:
        return "high"
    elif score >= 31:
        return "moderate"
    return "low"


# ── Alerts ───────────────────────────────────────────────────

ALERT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "acwr": {
        "critical": "急性负荷过高，ACWR {value}，远超安全上限 1.5，损伤风险显著上升",
        "high": "ACWR 偏高（{value}），处于临界区间，建议关注恢复",
        "elevated": "ACWR 偏低（{value}），训练负荷不足，可能影响体能维持",
    },
    "ramp_rate": {
        "critical": "周跑量增长过快（{value:+.0%}），远超 10% 安全线，建议立即回调",
        "high": "周跑量增长偏快（{value:+.0%}），超过 15%，需控制增幅",
    },
    "recovery_score": {
        "critical": "恢复评分严重偏低（{value:.0f}/100），身体处于过度疲劳状态，建议立即休息",
        "high": "恢复评分偏低（{value:.0f}/100），需加强恢复",
        "elevated": "恢复评分略低（{value:.0f}/100），注意保证充足休息",
    },
    "cadence": {
        "critical": "步频过低（{value} spm），跨步过度，膝盖和髋关节冲击风险显著上升",
        "high": "步频偏低（{value} spm），建议提升至 170+ 以减少着地冲击",
    },
    "gct": {
        "critical": "触地时间偏长（{value}ms），落地冲击力增大，胫骨和膝盖负荷升高",
        "high": "触地时间偏长（{value}ms），落地冲击力增大，胫骨和膝盖负荷升高",
    },
    "vo": {
        "critical": "垂直振幅偏大（{value}cm），落地冲击力增加，应力性骨折风险上升",
        "high": "垂直振幅偏大（{value}cm），落地冲击力增加，应力性骨折风险上升",
    },
    "vertical_ratio": {
        "critical": "垂直步幅比偏高（{value}%），跑步经济性下降，冲击力增大",
        "high": "垂直步幅比偏高（{value}%），跑步经济性下降，冲击力增大",
    },
    "lr_balance": {
        "critical": "左右严重失衡（{value}%），单侧代偿，单侧过劳损伤风险高",
        "high": "左右平衡偏差（{value}%），建议加强弱侧力量训练",
    },
    "consecutive_hard_days": {
        "critical": "连续高强度训练 {value} 天，建议立即安排恢复日",
        "high": "连续高强度训练 {value} 天，建议安排恢复日",
        "elevated": "连续高强度训练 {value} 天，建议明天安排恢复日",
    },
    "fatigue_trend": {
        "elevated": "疲劳正在累积中，需关注恢复，避免训练债滚雪球",
    },
    "recovery_debt_trend": {
        "elevated": "恢复负债持续上升，存在过度训练风险",
    },
}


def generate_alerts(
    risk_factors: List[Dict[str, Any]],
    consecutive_hard_days: int,
) -> List[str]:
    """基于 risk_factors 生成中文预警列表。"""
    alerts: List[str] = []
    seen: set = set()

    for rf in risk_factors:
        factor = rf["factor"]
        status = rf["status"]
        value = rf["value"]

        # 跳过无预警模板的因子
        if factor == "age":
            continue
        if factor == "injury_history":
            continue

        templates = ALERT_TEMPLATES.get(factor, {})
        template = templates.get(status)

        if template and factor not in seen:
            try:
                # ramp_rate 需要百分比格式化
                if factor == "ramp_rate" and isinstance(value, (int, float)):
                    alert = template.format(value=float(value))
                else:
                    alert = template.format(value=value)
                alerts.append(alert)
                seen.add(factor)
            except (ValueError, KeyError, AttributeError):
                pass  # 模板格式化失败，跳过

    return alerts


# ── 综合指标计算 ──────────────────────────────────────────────

def calculate_indicators(state: Dict[str, Any]) -> Dict[str, Any]:
    """从 state 中提取各 Agent 产出，计算 Risk 指标。

    Args:
        state: AgentState，需包含 load_report、recovery_report、
               performance_report、user_profile。

    Returns:
        包含 injury_risk_score, risk_level, risk_factors, alerts 的 dict。
    """
    load = state.get("load_report", {}) or {}
    recovery = state.get("recovery_report", {}) or {}
    perf = state.get("performance_report", {}) or {}
    profile = state.get("user_profile", {}) or {}

    acwr = load.get("acwr", 0.0)
    ramp_rate = load.get("ramp_rate", 0.0)
    recovery_score = recovery.get("recovery_score", 100.0)
    fatigue_trend = recovery.get("fatigue_trend", "stable")
    recovery_debt_trend = recovery.get("recovery_debt_trend", "stable")
    consecutive_hard_days = recovery.get("consecutive_hard_days", 0)
    technique_flags = perf.get("technique_flags", [])
    injury_history = profile.get("injury_history", [])
    age = profile.get("age", 0)

    result = calc_injury_risk_score(
        acwr=acwr,
        ramp_rate=ramp_rate,
        recovery_score=recovery_score,
        fatigue_trend=fatigue_trend,
        recovery_debt_trend=recovery_debt_trend,
        consecutive_hard_days=consecutive_hard_days,
        technique_flags=technique_flags,
        injury_history=injury_history,
        age=age,
    )

    risk_level = map_risk_level(result["injury_risk_score"])
    alerts = generate_alerts(result["risk_factors"], consecutive_hard_days)

    return {
        "injury_risk_score": result["injury_risk_score"],
        "risk_level": risk_level,
        "risk_factors": result["risk_factors"],
        "alerts": alerts,
    }


def format_indicators(indicators: Dict[str, Any]) -> str:
    """将风险指标格式化为 prompt 文本。"""
    score = indicators.get("injury_risk_score", 0.0)
    level = indicators.get("risk_level", "low")
    level_cn = {"low": "低", "moderate": "中等", "high": "高", "critical": "极高"}

    factor_lines = ""
    for rf in indicators.get("risk_factors", []):
        factor_lines += (
            f"  - {rf['factor']}: {rf['value']}"
            f"  ({rf['status']}, 来源: {rf['source']})\n"
        )

    alert_lines = ""
    for a in indicators.get("alerts", []):
        alert_lines += f"  - {a}\n"

    return (
        f"请评估以下跑者的伤病风险状态：\n\n"
        f"- 伤病风险评分: {score:.0f}/100（{level_cn.get(level, level)}风险）\n"
        f"- 风险因子:\n{factor_lines}"
        f"- 预警:\n{alert_lines}"
    )
