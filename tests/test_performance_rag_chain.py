# -*- coding: utf-8 -*-
"""可见调用链测试 —— 打印 performance agent RAG 全流程每一步输出。

用法: python tests/test_performance_rag_chain.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from training_agents.default_config import DEFAULT_CONFIG
from training_agents.llm_clients import create_llm_client
from training_agents.agents.analysts.performance_analyst import create_performance_agent
from training_agents.agents.utils.performance_indicators import calculate_indicators
from training_agents.graph.setup import build_performance_graph

# 构造差表现状态 —— 高解耦 + 技术异常 + 效率下降 + 目标不匹配
state = {
    "date": "2024-03-10",
    "user_profile": {
        "age": 35,
        "gender": "male",
        "height_cm": 175.0,
        "weight_kg": 72.0,
        "goal": "marathon",
        "training_level": "进阶",
        "personal_bests": {"5km": "23:00", "10km": "48:00", "半马": "1:50:00"},
        "injury_history": [],
        "max_hr": 185,
    },
    "parsed_activity": {
        "total_distance": 12000.0,
        "total_duration": 3600.0,    # 6:00/km pace
        "avg_hr": 165,
        "max_hr": 185,
        "hr_drift": 7.5,
        "avg_pace": "5:00/km",
        "avg_cadence": 158.0,        # 步频偏低
        "avg_gct": 250.0,            # 触地时间偏高
        "avg_vo": 9.5,               # 垂直振幅偏高
        "lr_balance": 47.5,          # 左右不平衡
        "hr_zones": {"zone1": 0.05, "zone2": 0.30, "zone3": 0.35, "zone4": 0.20, "zone5": 0.10},
        "trackpoints": {
            "time": [f"2024-03-10T06:{i:02d}:00Z" for i in range(100)],
            "distance_m": [i * 120.0 for i in range(100)],
            # 前半段低心率高配速，后半段高心率低配速 → 高解耦
            "heart_rate": [145] * 50 + [175] * 50,
            "speed": [3.8] * 50 + [2.9] * 50,
            "cadence": [79.0] * 100,
            "altitude": [100.0] * 100,
            "gct": [250.0] * 100,
            "vo": [9.5] * 100,
            "lr_balance": [47.5] * 100,
            "vertical_ratio": [9.5] * 100,
        },
    },
    "history": {
        "daily_checkins": [],
        "training_sessions": [
            # 近 10 次训练 —— EF 逐渐下降、Zone2 占比偏低
            {"date": "2024-03-01", "activity": {
                "total_distance": 10000, "total_duration": 3200, "avg_hr": 150,
                "hr_zones": {"zone1": 0.10, "zone2": 0.55, "zone3": 0.20, "zone4": 0.10, "zone5": 0.05},
                "trackpoints": {"heart_rate": [150]*50, "speed": [3.13]*50},
            }},
            {"date": "2024-03-02", "activity": {
                "total_distance": 10000, "total_duration": 3250, "avg_hr": 152,
                "hr_zones": {"zone1": 0.10, "zone2": 0.50, "zone3": 0.25, "zone4": 0.10, "zone5": 0.05},
                "trackpoints": {"heart_rate": [152]*50, "speed": [3.08]*50},
            }},
            {"date": "2024-03-03", "activity": {
                "total_distance": 10000, "total_duration": 3300, "avg_hr": 153,
                "hr_zones": {"zone1": 0.10, "zone2": 0.48, "zone3": 0.25, "zone4": 0.12, "zone5": 0.05},
                "trackpoints": {"heart_rate": [153]*50, "speed": [3.03]*50},
            }},
            {"date": "2024-03-04", "activity": {
                "total_distance": 10000, "total_duration": 3350, "avg_hr": 155,
                "hr_zones": {"zone1": 0.05, "zone2": 0.45, "zone3": 0.30, "zone4": 0.15, "zone5": 0.05},
                "trackpoints": {"heart_rate": [155]*50, "speed": [2.99]*50},
            }},
            {"date": "2024-03-05", "activity": {
                "total_distance": 8000, "total_duration": 2700, "avg_hr": 156,
                "hr_zones": {"zone1": 0.05, "zone2": 0.42, "zone3": 0.30, "zone4": 0.18, "zone5": 0.05},
                "trackpoints": {"heart_rate": [156]*50, "speed": [2.96]*50},
            }},
            {"date": "2024-03-06", "activity": {
                "total_distance": 10000, "total_duration": 3400, "avg_hr": 158,
                "hr_zones": {"zone1": 0.05, "zone2": 0.38, "zone3": 0.32, "zone4": 0.18, "zone5": 0.07},
                "trackpoints": {"heart_rate": [158]*50, "speed": [2.94]*50},
            }},
            {"date": "2024-03-07", "activity": {
                "total_distance": 8000, "total_duration": 2750, "avg_hr": 159,
                "hr_zones": {"zone1": 0.05, "zone2": 0.35, "zone3": 0.33, "zone4": 0.20, "zone5": 0.07},
                "trackpoints": {"heart_rate": [159]*50, "speed": [2.91]*50},
            }},
            {"date": "2024-03-08", "activity": {
                "total_distance": 10000, "total_duration": 3450, "avg_hr": 160,
                "hr_zones": {"zone1": 0.05, "zone2": 0.32, "zone3": 0.35, "zone4": 0.20, "zone5": 0.08},
                "trackpoints": {"heart_rate": [160]*50, "speed": [2.90]*50},
            }},
            {"date": "2024-03-09", "activity": {
                "total_distance": 9000, "total_duration": 3100, "avg_hr": 162,
                "hr_zones": {"zone1": 0.05, "zone2": 0.30, "zone3": 0.35, "zone4": 0.22, "zone5": 0.08},
                "trackpoints": {"heart_rate": [162]*50, "speed": [2.90]*50},
            }},
        ],
    },
}

# 步骤 1: 计算指标
indicators = calculate_indicators(state)
print("=" * 60)
print("步骤 1: 硬编码计算表现指标")
print("=" * 60)
for k, v in indicators.items():
    if k == "technique_flags":
        print(f"  {k}:")
        for flag in v:
            print(f"    - {flag}")
    elif k == "zone_distribution":
        print(f"  {k}: {v}")
    elif k == "aerobic_trend":
        print(f"  {k}: {v}")
    elif k == "efficiency_history":
        print(f"  {k}: ({len(v)} entries)")
    else:
        print(f"  {k}: {v}")

# 步骤 2: 构建 Graph
llm_client = create_llm_client(
    DEFAULT_CONFIG["llm_provider"],
    DEFAULT_CONFIG["deep_think_llm"],
)
llm = llm_client.get_llm()
agent_node = create_performance_agent(llm=llm)
graph = build_performance_graph(llm, agent_node)

# 步骤 3: 执行
print()
print("=" * 60)
print("步骤 2: Graph 执行（LLM 决策 → 搜书 → 生成总结）")
print("=" * 60)

result = graph.invoke(state)
report = result["performance_report"]

# 打印最终报告
print()
print("=" * 60)
print("最终 PerformanceReport")
print("=" * 60)
for k, v in report.items():
    if k == "technique_flags":
        print(f"  {k}:")
        for flag in v:
            print(f"    - {flag}")
    elif k == "zone_distribution":
        print(f"  {k}: {v}")
    elif k == "aerobic_trend":
        print(f"  {k}: {v}")
    elif k == "efficiency_history":
        print(f"  {k}: ({len(v)} entries)")
    elif k == "summary":
        continue
    else:
        print(f"  {k}: {v}")
print(f"  --- LLM 总结 ---")
print(report["summary"])
