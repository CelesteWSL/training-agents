# -*- coding: utf-8 -*-
"""Agent State 类型定义 —— 基于 TypedDict + MessagesState 继承模式。

参考 TradingAgents 的 agent_states.py，一个 shared state 贯穿整个 LangGraph pipeline。
各 Agent 只写自己的命名空间字段。

兼容性：langgraph 未安装时使用纯 TypedDict 基类，安装后自动继承 MessagesState。
"""

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict

# 尝试继承 MessagesState，若 langgraph 不可用则回退到纯 TypedDict
try:
    from langgraph.graph import MessagesState  # noqa: F401

    _BASE = MessagesState
except ImportError:
    _BASE = dict  # type: ignore[assignment]


# ?? LangGraph Reducer ????????????????????????????????????????

def _reduce_keep_first(current, update):
    """?????? reducer??????? None ?????????

    ?? AgentState ????????user_profile?activity_file ???
    ????????????????????????
    """
    if current is not None:
        return current
    return update



# ── 入口 / 基础画像 ──────────────────────────────────────────

class UserProfile(TypedDict):
    """用户基础画像 — 首次填写，长期不变，各 Agent 只读不写。"""
    age: int
    gender: str
    height_cm: float
    weight_kg: float
    goal: str                    # "5km" / "10km" / "half_marathon" / "marathon"
    training_level: str          # "新手" / "进阶" / "高级"
    personal_bests: Dict[str, str]
    injury_history: List[str]
    max_hr: Optional[int]        # 空则用 220-age 默认公式


# ── Data Agent 产出 ──────────────────────────────────────────

class LapSummary(TypedDict):
    """单圈汇总（1 km 分段）。"""
    index: int
    distance_m: float
    duration_s: float
    avg_hr: int
    max_hr: int
    avg_pace: str               # "m:ss/km"
    avg_cadence: Optional[float]
    avg_stride_length: Optional[float]



class TrackpointSeries(TypedDict):
    """时序数据（列式）— 各属性独立数组，等长对齐，直接用于绘图。
    
    所有数组长度相同，第 i 个元素对应同一秒的采样点。
    缺失值: heart_rate 填 0, cadence 填 null, speed/altitude 填 0.0,
            gct/vo/lr_balance 无设备时全为 null。
    """
    time: List[str]              # ISO 8601 时间戳列表
    distance_m: List[float]      # 累计距离（米）
    heart_rate: List[int]        # 瞬时心率 (bpm)
    speed: List[float]           # 瞬时速度 (m/s)
    cadence: List[Optional[float]]  # 步频（已修正）
    altitude: List[float]        # 海拔（米）
    gct: List[Optional[float]]   # 触地时间（毫秒），无设备则为 null
    vo: List[Optional[float]]    # 垂直振幅（厘米），无设备则为 null
    lr_balance: List[Optional[float]]  # 左右平衡，无设备则为 null
    vertical_ratio: List[Optional[float]]  # 垂直步幅比（%），传感器优先，无则计算

class ParsedActivity(TypedDict):
    """Data Agent 产出 — 原始训练文件解析后的结构化数据。"""
    sport: str                   # "Running" / "Cycling" / "Swimming"
    start_time: str              # ISO 8601
    total_distance: float        # 米
    total_duration: float        # 秒
    avg_pace: str                # "m:ss/km"
    avg_hr: int                  # bpm
    max_hr: int                  # bpm
    hr_drift: float              # 心率飘逸（%）
    total_ascent: float          # 累计爬升（米）
    total_descent: float         # 累计下降（米）
    hr_zones: Dict[str, float]   # {"zone1": 0.08, "zone2": 0.62, ...}
    laps: List[LapSummary]
    avg_cadence: Optional[float]
    avg_stride_length: Optional[float]
    avg_gct: Optional[float]     # 平均触地时间（毫秒）
    avg_vo: Optional[float]      # 平均垂直振幅（厘米）
    lr_balance: Optional[float]
    trackpoints: TrackpointSeries  # 秒级时序数据  # 左右平衡（50.0 = 完全均衡）


# ── Recovery Agent 产出 ──────────────────────────────────────

class RecoveryReport(TypedDict):
    """Recovery Agent 产出。"""
    status: str                  # "good" / "moderate" / "warning" / "critical"
    recovery_score: float        # 0-100
    fatigue_trend: str           # "stable" / "recovering" / "accumulating"
    resting_hr_deviation: float
    hr_drift: float
    recovery_debt: float
    recovery_debt_trend: str     # "improving" / "stable" / "worsening"
    consecutive_hard_days: int  # 0..N
    summary: str                 # LLM 自然语言总结


# ── Training Load Agent 产出 ─────────────────────────────────

class LoadReport(TypedDict):
    """Training Load Agent 产出。"""
    status: str                  # "good" / "moderate" / "warning" / "critical"
    acute_load: float
    chronic_load: float
    acwr: float
    weekly_volume_km: float
    ramp_rate: float
    acwr_interpretation: str
    ramp_rate_interpretation: str
    summary: str


# ── Performance Agent 产出 ───────────────────────────────────

class PerformanceReport(TypedDict):
    """Performance Agent 产出。"""
    status: str                  # "good" / "moderate" / "warning" / "critical"
    efficiency_factor: float
    efficiency_trend: str        # "improving" / "stable" / "declining"
    efficiency_history: List[Dict[str, object]]   # [{"date": str, "value": float}, ...]
    aerobic_efficiency: float
    aerobic_trend: Dict[str, str]  # {"zone2_pace_trend": str, "zone2_hr_trend": str}
    pace_hr_decoupling: float
    decoupling_status: str       # "good" / "moderate" / "poor"
    zone_distribution: Dict[str, float]  # {"zone1": 0.08, ...}
    target_alignment: str        # "on_track" / "mismatch" / "insufficient_data"
    technique_flags: List[Dict[str, object]]  # [{metric, current, benchmark, direction, severity}, ...]
    summary: str


# ── Risk Agent 产出 ──────────────────────────────────────────


# ── State Recognition Agent 产出 ────────────────────────────

class StateIndicator(TypedDict):
    """单条指标贡献明细。"""
    metric: str                  # 指标名称
    value: Any                   # 实际值
    match: float                 # Match_Strength 0~1
    weight: int                  # 指标权重
    contribution: float          # weight × match

class PhysiologicalState(TypedDict):
    """State Recognition Agent 识别到的单条生理状态。"""
    name: str                    # "cns_fatigue" / "non_functional_overreaching" / ...
    priority: int                # 响应优先级 1~3
    confidence: float            # Rule Match Score，0.0 ~ 1.0
    total_score: float           # 原始加权总分
    threshold: int               # 触发阈值
    explanation: str             # 生理学解释（模板+变量替换）
    indicators: List[StateIndicator]  # 各指标贡献明细

class StateRecognitionResult(TypedDict):
    """State Recognition Agent 产出。"""
    physiological_states: List[PhysiologicalState]  # 识别到的生理状态列表（空列表 = 无异常）
class RiskFactor(TypedDict):
    """触发风险的单个因子。"""
    factor: str                  # "acwr" / "recovery_score" / "cadence" / "injury_history" / ...
    value: object                # 实际值
    status: str                  # "normal" / "elevated" / "high" / "critical"
    source: str                  # "load" / "recovery" / "technique" / "user_profile"


class RiskReport(TypedDict):
    """Risk Agent 产出。"""
    risk_level: str              # "low" / "moderate" / "high" / "critical"
    injury_risk_score: float     # 0-100
    risk_factors: List[RiskFactor]
    alerts: List[str]
    summary: str



# ── History Context ──────────────────────────────────────

class HistoryCheckin(TypedDict):
    """单日晨间检查数据。"""
    date: str
    morning_hr: int


class HistoryTrainingSession(TypedDict):
    """单次训练历史记录（解析后的 ParsedActivity + 日期）。"""
    date: str
    activity: ParsedActivity


class HistoryContext(TypedDict):
    """HistoryReader 产出，注入 AgentState，下游 Agent 直接读取。"""
    from_date: str
    to_date: str
    daily_checkins: List[HistoryCheckin]
    training_sessions: List[HistoryTrainingSession]
# ── Coach Agent 产出 ─────────────────────────────────────────

class SRAConext(TypedDict):
    """SRA State Modifier 对 Gate 的影响记录。"""
    primary_state: str           # 触发调节的生理状态名
    confidence: float            # SRA 识别置信度
    gate_affected: str           # 受影响的主 Gate
    adjustment: str              # 调节描述，如 "recovery_score 阈值 40 → 55"


class GateHit(TypedDict):
    """Waterfall Gate 命中记录。"""
    gate: str                    # "safety" / "recovery" / "load" / "performance" / "default"
    rule: str                    # 命中规则描述
    actual_value: Any            # 触发时的实际值
    priority: int                # 规则优先级


class TechniqueModifier(TypedDict):
    """技术修饰器条目。"""
    key: str                     # "cadence_drill" / "gct_drill" / ...
    label: str                   # 中文标签
    reason: str                  # 触发原因


class RulingResult(TypedDict):
    """Coach Agent 裁决结果（Decision Engine 输出）。

    status / action / verdict / gate_hit 由硬编码规则决定；
    headline / message / next_steps 由 LLM Report Generator 填充。
    """
    status: str                  # "good" / "moderate" / "warning" / "critical"
    action: str                  # "full_rest" / "recovery_run" / "reduce_load" / "quality_session" / "normal_training"
    verdict: str                 # "建议完全休息" / "建议进行恢复跑" / ...
    sra_context: Optional[SRAConext]  # SRA 调节上下文，无命中时为 None
    gate_hit: GateHit            # Waterfall Gate 命中记录
    modifiers: List[TechniqueModifier]  # 技术修饰器列表


class SpecialEvent(TypedDict):
    """特殊事件标记。"""
    event_type: str              # "PB" / "best_week" / "recovery_day" / "milestone" / "high_risk"
    priority: int                # 1 (最高) ~ 5
    title: str
    message: str
    icon: str                    # emoji


class FinalReport(TypedDict):
    """Coach Agent 最终训练报告。"""
    date: str
    recommendation: RulingResult
    special_event: Optional[SpecialEvent]
    markdown: str                # LLM 直出的完整 Markdown 报告


# ── 顶层 AgentState ──────────────────────────────────────────

class AgentState(_BASE):  # type: ignore[valid-type]
    """顶层 state，langgraph 可用时自动继承 MessagesState。

    所有节点读/写同一个 state，字段逐步累积。
    """
    user_profile: Annotated[UserProfile, _reduce_keep_first]
    activity_file: Annotated[str, _reduce_keep_first]
    date: Annotated[str, _reduce_keep_first]
    rpe: Annotated[int, _reduce_keep_first]
    muscle_soreness: Annotated[int, _reduce_keep_first]
    morning_hr: Annotated[int, _reduce_keep_first]

    parsed_activity: Annotated[ParsedActivity, _reduce_keep_first]

    recovery_report: RecoveryReport
    load_report: LoadReport
    performance_report: PerformanceReport
    risk_report: RiskReport

    history: Annotated[HistoryContext, _reduce_keep_first]

    ruling: RulingResult
    final_report: FinalReport
