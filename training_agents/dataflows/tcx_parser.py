"""TCX 文件解析器 —— lxml + XPath 实现。

支持 Garmin TCX v2 格式，产出 ParsedActivity。
时序数据采用列式 TrackpointSeries。
跑步动态指标: gct / vo / lr_balance / vertical_ratio（传感器优先→计算回退）。
"""

from typing import List, Optional, Dict
from lxml import etree

from training_agents.agents.utils.agent_states import (
    LapSummary, ParsedActivity, TrackpointSeries,
)

TCX_NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
EXT_NS = "http://www.garmin.com/xmlschemas/ActivityExtension/v2"
NS = {"tcx": TCX_NS, "ext": EXT_NS}


def _xpath_text(el, xpath_expr, default=None):
    results = el.xpath(xpath_expr, namespaces=NS)
    if results:
        val = results[0]
        return val.text if hasattr(val, "text") else str(val)
    return default


def _xpath_num(el, xpath_expr, default=0.0):
    t = _xpath_text(el, xpath_expr)
    if t is not None:
        try: return float(t)
        except (ValueError, TypeError): pass
    return default


def _xpath_int(el, xpath_expr, default=0):
    t = _xpath_text(el, xpath_expr)
    if t is not None:
        try: return int(float(t))
        except (ValueError, TypeError): pass
    return default


def _format_pace(duration_s: float, distance_m: float) -> str:
    if distance_m <= 0:
        return "0:00/km"
    pace = duration_s / (distance_m / 1000.0)
    return f"{int(pace // 60)}:{int(pace % 60):02d}/km"


def _calc_hr_zones(hr_values: List[int], max_hr: int) -> Dict[str, float]:
    if not hr_values or max_hr <= 0:
        return {"zone1": 0, "zone2": 0, "zone3": 0, "zone4": 0, "zone5": 0}
    zones = {"zone1": 0, "zone2": 0, "zone3": 0, "zone4": 0, "zone5": 0}
    for hr in hr_values:
        pct = hr / max_hr
        if pct < 0.60: zones["zone1"] += 1
        elif pct < 0.70: zones["zone2"] += 1
        elif pct < 0.80: zones["zone3"] += 1
        elif pct < 0.90: zones["zone4"] += 1
        else: zones["zone5"] += 1
    total = len(hr_values)
    return {k: round(v / total, 4) for k, v in zones.items()}


def _calc_hr_drift(hr: List[int], sp: List[float]) -> float:
    if len(hr) < 10 or len(sp) < 10:
        return 0.0
    mid = len(hr) // 2
    a1 = sum(hr[:mid]) / mid
    a2 = sum(hr[mid:]) / (len(hr) - mid)
    return round((a2 - a1) / a1 * 100, 2) if a1 > 0 else 0.0


def _correct_cadence(raw: float, sport: str) -> float:
    return raw * 2.0 if sport in ("Running", "running") else raw


# ── 跑步动态提取 ──────────────────────────────────────────────

def _extract_running_dynamics(tp) -> dict:
    """从 trackpoint Extensions 提取跑步动态指标。

    返回 {"gct", "vo", "lr_balance", "vertical_ratio"}，全 Optional[float]。
    覆盖: GroundContactTime / StanceTime → gct
          VerticalOscillation → vo
          LeftRightBalance / GroundContactTimeBalance → lr_balance
          VerticalRatio → vertical_ratio
    """
    result = {"gct": None, "vo": None, "lr_balance": None, "vertical_ratio": None}

    # 路径组 (XPath, key)，按优先级排列
    queries = [
        # ── ext:TPX 子元素（最常见）──
        ("ext:TPX/ext:GroundContactTime", "gct"),
        ("ext:TPX/ext:StanceTime", "gct"),
        ("ext:TPX/ext:VerticalOscillation", "vo"),
        ("ext:TPX/ext:LeftRightBalance", "lr_balance"),
        ("ext:TPX/ext:GroundContactTimeBalance", "lr_balance"),
        ("ext:TPX/ext:VerticalRatio", "vertical_ratio"),
        # ── Extensions 直接子元素 ──
        ("tcx:Extensions/ext:GroundContactTime", "gct"),
        ("tcx:Extensions/ext:StanceTime", "gct"),
        ("tcx:Extensions/ext:VerticalOscillation", "vo"),
        ("tcx:Extensions/ext:LeftRightBalance", "lr_balance"),
        ("tcx:Extensions/ext:GroundContactTimeBalance", "lr_balance"),
        ("tcx:Extensions/ext:VerticalRatio", "vertical_ratio"),
        # ── local-name() 兜底（无命名空间前缀）──
        ("*[local-name()='Extensions']/*[local-name()='TPX']/*[local-name()='GroundContactTime']", "gct"),
        ("*[local-name()='Extensions']/*[local-name()='TPX']/*[local-name()='StanceTime']", "gct"),
        ("*[local-name()='Extensions']/*[local-name()='TPX']/*[local-name()='VerticalOscillation']", "vo"),
        ("*[local-name()='Extensions']/*[local-name()='TPX']/*[local-name()='LeftRightBalance']", "lr_balance"),
        ("*[local-name()='Extensions']/*[local-name()='TPX']/*[local-name()='GroundContactTimeBalance']", "lr_balance"),
        ("*[local-name()='Extensions']/*[local-name()='TPX']/*[local-name()='VerticalRatio']", "vertical_ratio"),
    ]

    for path, key in queries:
        if result[key] is not None:
            continue
        val = _xpath_num(tp, path)
        if val > 0:
            result[key] = val

    return result


# ── 主解析 ────────────────────────────────────────────────────

def parse_tcx(filepath: str, max_hr: Optional[int] = None) -> ParsedActivity:
    tree = etree.parse(filepath)
    root = tree.getroot()

    sport = _xpath_text(root, "//tcx:Activity/@Sport", "Unknown")
    start_time = _xpath_text(root, "(//tcx:Lap)[1]/@StartTime", "")

    lap_elements = root.xpath("//tcx:Lap", namespaces=NS)

    total_distance = 0.0
    total_duration = 0.0
    all_hr: List[int] = []
    all_speeds: List[float] = []
    all_cadences_raw: List[float] = []
    lap_summaries: List[LapSummary] = []
    max_observed_hr = 0
    total_ascent = 0.0
    total_descent = 0.0
    prev_alt: Optional[float] = None

    # 跑步动态累计
    all_gct: List[float] = []
    all_vo: List[float] = []
    all_lr: List[float] = []
    all_vratio: List[float] = []

    # 列式 trackpoint
    tp_times: List[str] = []
    tp_distances: List[float] = []
    tp_heart_rates: List[int] = []
    tp_speeds: List[float] = []
    tp_cadences: List[Optional[float]] = []
    tp_altitudes: List[float] = []
    tp_gct: List[Optional[float]] = []
    tp_vo: List[Optional[float]] = []
    tp_lr: List[Optional[float]] = []
    tp_vratio: List[Optional[float]] = []

    for lap_idx, lap in enumerate(lap_elements):
        lap_duration = _xpath_num(lap, "tcx:TotalTimeSeconds")
        lap_distance = _xpath_num(lap, "tcx:DistanceMeters")
        lap_avg_hr = _xpath_int(lap, "tcx:AverageHeartRateBpm/tcx:Value")
        lap_max_hr = _xpath_int(lap, "tcx:MaximumHeartRateBpm/tcx:Value")

        total_duration += lap_duration
        total_distance += lap_distance

        lap_cadences_raw: List[float] = []

        trackpoints = lap.xpath("tcx:Track/tcx:Trackpoint", namespaces=NS)
        for tp in trackpoints:
            tp_time = _xpath_text(tp, "tcx:Time", "")
            tp_dist = _xpath_num(tp, "tcx:DistanceMeters")

            hr = _xpath_int(tp, "tcx:HeartRateBpm/tcx:Value")
            if hr > 0:
                all_hr.append(hr)
                max_observed_hr = max(max_observed_hr, hr)

            cad = _xpath_num(tp, "tcx:Cadence")

            speed = _xpath_num(tp, "tcx:Extensions/tcx:Speed")
            if speed <= 0:
                speed = _xpath_num(tp, "*[local-name()='Extensions']/*[local-name()='Speed']")
                if speed <= 0:
                    speed = _xpath_num(tp, "tcx:Extensions/ext:TPX/ext:Speed")
            if speed > 0:
                all_speeds.append(speed)

            alt = _xpath_num(tp, "tcx:AltitudeMeters")

            # 跑步动态
            dyn = _extract_running_dynamics(tp)
            if dyn["gct"] is not None: all_gct.append(dyn["gct"])
            if dyn["vo"] is not None: all_vo.append(dyn["vo"])
            if dyn["lr_balance"] is not None: all_lr.append(dyn["lr_balance"])
            if dyn["vertical_ratio"] is not None: all_vratio.append(dyn["vertical_ratio"])

            # ── 列式收集 ──
            tp_times.append(tp_time)
            tp_distances.append(tp_dist)
            tp_heart_rates.append(hr)
            tp_speeds.append(speed if speed > 0 else 0.0)
            tp_cadences.append(_correct_cadence(cad, sport) if cad > 0 else None)
            tp_altitudes.append(alt)
            tp_gct.append(dyn["gct"])
            tp_vo.append(dyn["vo"])
            tp_lr.append(dyn["lr_balance"])
            tp_vratio.append(dyn["vertical_ratio"])

            if cad > 0:
                all_cadences_raw.append(cad)
                lap_cadences_raw.append(cad)
            if alt > 0 and prev_alt is not None:
                diff = alt - prev_alt
                if diff > 0: total_ascent += diff
                else: total_descent += abs(diff)
            if alt > 0:
                prev_alt = alt

        # Lap 汇总
        lap_corrected = [_correct_cadence(c, sport) for c in lap_cadences_raw]
        lap_avg_cad = (round(sum(lap_corrected) / len(lap_corrected), 1) if lap_corrected else None)
        lap_avg_stride = None
        if lap_avg_cad and lap_distance > 0:
            steps = (lap_avg_cad * lap_duration) / 60.0
            if steps > 0:
                lap_avg_stride = round(lap_distance / steps, 2)

        lap_summaries.append(LapSummary(
            index=lap_idx, distance_m=lap_distance, duration_s=lap_duration,
            avg_hr=lap_avg_hr, max_hr=lap_max_hr,
            avg_pace=_format_pace(lap_duration, lap_distance),
            avg_cadence=lap_avg_cad, avg_stride_length=lap_avg_stride,
        ))

    # ── 汇总 ──
    avg_hr = round(sum(all_hr) / len(all_hr)) if all_hr else 0
    actual_max_hr = max_observed_hr
    avg_pace = _format_pace(total_duration, total_distance)
    user_max_hr = max_hr if max_hr else 220
    hr_zones = _calc_hr_zones(all_hr, user_max_hr)
    hr_drift = _calc_hr_drift(all_hr, all_speeds)

    corrected = [_correct_cadence(c, sport) for c in all_cadences_raw]
    avg_cadence = (round(sum(corrected) / len(corrected), 1) if corrected else None)
    avg_stride_length = None
    if avg_cadence and total_distance > 0 and total_duration > 0:
        steps = (avg_cadence * total_duration) / 60.0
        if steps > 0:
            avg_stride_length = round(total_distance / steps, 2)

    # 跑步动态汇总
    avg_gct = round(sum(all_gct) / len(all_gct), 1) if all_gct else None
    avg_vo = round(sum(all_vo) / len(all_vo), 1) if all_vo else None
    avg_lr = round(sum(all_lr) / len(all_lr), 1) if all_lr else None

    # 垂直步幅比: 传感器优先 → 计算回退
    if all_vratio:
        avg_vertical_ratio = round(sum(all_vratio) / len(all_vratio), 1)
    elif avg_vo and avg_stride_length and avg_stride_length > 0:
        avg_vertical_ratio = round(avg_vo / (avg_stride_length * 100.0) * 100, 1)
    else:
        avg_vertical_ratio = None

    # trackpoint 级别 vertical_ratio 列: 传感器值优先，无则逐点计算回退
    if all_vratio:
        # 传感器给了逐点值，直接用
        pass  # tp_vratio already populated
    else:
        # 计算回退: vo / stride_length * 100
        for i in range(len(tp_times)):
            vo_i = tp_vo[i]
            stride_i = None
            cad_i = tp_cadences[i]
            speed_i = tp_speeds[i]
            if cad_i and cad_i > 0 and speed_i > 0:
                # stride = speed(m/s) / (cadence(spm) / 60)
                stride_i = speed_i / (cad_i / 60.0)
            if vo_i and stride_i and stride_i > 0:
                tp_vratio[i] = round(vo_i / (stride_i * 100.0) * 100, 1)

    return ParsedActivity(
        sport=sport, start_time=start_time,
        total_distance=round(total_distance, 1),
        total_duration=round(total_duration, 1),
        avg_pace=avg_pace, avg_hr=avg_hr, max_hr=actual_max_hr,
        hr_drift=hr_drift,
        total_ascent=round(total_ascent, 1),
        total_descent=round(total_descent, 1),
        hr_zones=hr_zones, laps=lap_summaries,
        avg_cadence=avg_cadence, avg_stride_length=avg_stride_length,
        avg_gct=avg_gct, avg_vo=avg_vo, lr_balance=avg_lr,
        avg_vertical_ratio=avg_vertical_ratio,
        trackpoints=TrackpointSeries(
            time=tp_times, distance_m=tp_distances,
            heart_rate=tp_heart_rates, speed=tp_speeds,
            cadence=tp_cadences, altitude=tp_altitudes,
            gct=tp_gct, vo=tp_vo, lr_balance=tp_lr,
            vertical_ratio=tp_vratio,
        ),
    )
