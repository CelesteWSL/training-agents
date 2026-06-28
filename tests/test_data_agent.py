# -*- coding: utf-8 -*-
"""Data Agent 节点测试。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from training_agents.agents.analysts.data_analyst import data_agent_node


@pytest.fixture
def state():
    """构造 Data Agent 输入 state。"""
    return {
        "activity_file": str(Path(__file__).resolve().parent.parent / "data" / "training" / "武汉市_跑步20240304215126.tcx"),
        "user_profile": {
            "age": 30,
            "gender": "male",
            "height_cm": 175,
            "weight_kg": 70,
            "goal": "marathon",
            "training_level": "中级",
            "personal_bests": {"5km": "22:00", "10km": "46:00"},
            "injury_history": [],
            "max_hr": 190,
        },
        "date": "2024-03-04",
    }



class TestDataAgentNode:

    def test_returns_parsed_activity(self, state):
        """详细打印 parsed_activity 各字段（不含 history）。"""
        print("\n=== Input State ===")
        print(f"  activity_file: {state['activity_file']}")
        up = state['user_profile']
        print(f"  user_profile:   age={up['age']} goal={up['goal']} level={up['training_level']} max_hr={up['max_hr']}")

        result = data_agent_node(state)

        print("\n=== Output: parsed_activity ===")
        pa = result["parsed_activity"]
        print(f"  sport:             {pa['sport']}")
        print(f"  start_time:        {pa['start_time']}")
        print(f"  total_distance:    {pa['total_distance']} m")
        print(f"  total_duration:    {pa['total_duration']} s")
        print(f"  avg_pace:          {pa['avg_pace']}")
        print(f"  avg_hr / max_hr:   {pa['avg_hr']} / {pa['max_hr']} bpm")
        print(f"  hr_drift:          {pa['hr_drift']} %")
        print(f"  ascent / descent:  {pa['total_ascent']} / {pa['total_descent']} m")
        print(f"  avg_cadence:       {pa['avg_cadence']} spm")
        print(f"  avg_stride_length: {pa['avg_stride_length']} m")
        print(f"  hr_zones:          {pa['hr_zones']}")
        ts = pa['trackpoints']
        print(f"  trackpoints:       {len(ts['time'])} points")
        print(f"  laps ({len(pa['laps'])}):")
        for lap in pa['laps']:
            print(f"    lap[{lap['index']}]: {lap['distance_m']}m {lap['duration_s']}s "
                  f"pace={lap['avg_pace']} cad={lap['avg_cadence']} stride={lap['avg_stride_length']} "
                  f"HR={lap['avg_hr']}/{lap['max_hr']}")

        print("\n  --- first 5 trackpoints ---")
        for i in range(min(5, len(ts["time"]))):
            print(f"    {ts['time'][i]}  dist={ts['distance_m'][i]}m  "
                  f"HR={ts['heart_rate'][i]}  speed={ts['speed'][i]}m/s  "
                  f"cad={ts['cadence'][i]}  alt={ts['altitude'][i]}m")
        print()

        assert "parsed_activity" in result
        assert pa["sport"] == "Running"
        assert pa["total_distance"] > 0
    def test_returns_parsed_activity_and_history(self, state):
        """data_agent_node 应同时返回 parsed_activity 和 history。"""
        result = data_agent_node(state)

        assert "parsed_activity" in result
        assert "history" in result

        pa = result["parsed_activity"]
        assert pa["sport"] == "Running"
        assert pa["total_distance"] > 0

        h = result["history"]
        assert "daily_checkins" in h
        assert "training_sessions" in h
        assert len(h["daily_checkins"]) > 0
        assert len(h["training_sessions"]) > 0

    def test_history_window_is_28_days(self, state):
        """历史窗口应为前28天（含当天）。"""
        result = data_agent_node(state)
        h = result["history"]
        assert h["from_date"] == "2024-02-05"  # 03-04 minus 28 = 02-05
        assert h["to_date"] == "2024-03-04"

    def test_history_contains_current_day(self, state):
        """当天训练应出现在 training_sessions 中。"""
        result = data_agent_node(state)
        dates = [s["date"] for s in result["history"]["training_sessions"]]
        assert "2024-03-04" in dates

    def test_empty_file_returns_default(self):
        result = data_agent_node({"activity_file": "", "user_profile": None, "date": ""})
        pa = result["parsed_activity"]
        assert pa["sport"] == "Unknown"
        assert pa["total_distance"] == 0
        h = result["history"]
        assert len(h["daily_checkins"]) == 0
        assert len(h["training_sessions"]) == 0

    def test_uses_user_max_hr(self, state):
        state["user_profile"]["max_hr"] = 200
        z1 = data_agent_node(state)["parsed_activity"]["hr_zones"]
        state["user_profile"]["max_hr"] = 180
        z2 = data_agent_node(state)["parsed_activity"]["hr_zones"]
        assert z1 != z2