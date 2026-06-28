# -*- coding: utf-8 -*-
"""Data Agent —— 解析训练文件，产出 ParsedActivity + 预读历史数据。

不依赖 LLM，纯数据解析层。
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from training_agents.agents.utils.agent_states import (
    AgentState, ParsedActivity, UserProfile, TrackpointSeries, HistoryContext,
)
from training_agents.dataflows.tcx_parser import parse_tcx
from training_agents.dataflows.history_reader import HistoryReader


def _resolve_data_dir(activity_file: str) -> str:
    """从当前训练文件路径反推 data 根目录。"""
    # activity_file: ".../data/training/xxx.tcx" → data_dir: ".../data"
    return os.path.dirname(os.path.dirname(os.path.abspath(activity_file)))


def _resolve_max_hr(profile: UserProfile) -> int:
    """从用户画像中获取最大心率，若未设置则用 220-age 估算。"""
    max_hr = profile.get("max_hr")
    if max_hr is not None and max_hr > 0:
        return int(max_hr)
    age = profile.get("age", 30)
    return 220 - age


def _default_parsed() -> ParsedActivity:
    """返回空的 ParsedActivity。"""
    return ParsedActivity(
        sport="Unknown",
        start_time="",
        total_distance=0,
        total_duration=0,
        avg_pace="0:00/km",
        avg_hr=0,
        max_hr=0,
        hr_drift=0.0,
        total_ascent=0.0,
        total_descent=0.0,
        hr_zones={},
        laps=[],
        avg_cadence=None,
        avg_stride_length=None,
        avg_gct=None,
        avg_vo=None,
        lr_balance=None,
        avg_vertical_ratio=None,
        trackpoints=TrackpointSeries(
            time=[], distance_m=[], heart_rate=[], speed=[],
            cadence=[], altitude=[], gct=[], vo=[],
            lr_balance=[], vertical_ratio=[],
        ),
    )


def data_agent_node(state: AgentState) -> Dict[str, Any]:
    """Data Agent 节点函数。

    1. 解析当前训练文件 → ParsedActivity
    2. 通过 HistoryReader 预读历史 daily_checkin + training 数据
    3. 写入 state.parsed_activity 和 state.history
    """
    activity_file: str = state.get("activity_file", "")
    user_profile: Optional[UserProfile] = state.get("user_profile")
    date: str = state.get("date", "")

    if not activity_file:
        return {
            "parsed_activity": _default_parsed(),
            "history": HistoryContext(
                from_date="", to_date="",
                daily_checkins=[], training_sessions=[],
            ),
        }

    # 1. 解析当前训练文件
    max_hr = _resolve_max_hr(user_profile) if user_profile else None
    parsed = parse_tcx(activity_file, max_hr=max_hr)

    # 2. 获取实际训练日期（优先 state.date → parsed.start_time）
    current_date = date or parsed.get("start_time", "")[:10]
    if not current_date:
        current_date = datetime.now().strftime("%Y-%m-%d")

    # 3. HistoryReader 预读：从 data 根目录读取
    data_dir = _resolve_data_dir(activity_file)
    reader = HistoryReader(data_dir)

    # 窗口: 前 28 天（覆盖 Load Agent 的慢性负荷窗口）
    current_dt = datetime.strptime(current_date, "%Y-%m-%d")
    from_dt = current_dt - timedelta(days=28)
    from_date = from_dt.strftime("%Y-%m-%d")

    history_context = reader.read(from_date, current_date, max_hr=max_hr)

    return {
        "parsed_activity": parsed,
        "history": history_context,
    }


def create_data_agent():
    """Factory 函数 —— 返回 Data Agent 节点。

    遵循 TradingAgents 的 create_xxx(llm) -> node_fn 模式，
    Data Agent 不需要 LLM，因此无参数。
    """
    return data_agent_node