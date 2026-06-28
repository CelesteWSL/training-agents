# -*- coding: utf-8 -*-
"""可见调用链测试 —— 打印 recovery agent RAG 全流程每一步输出。

用法: python tests/test_recovery_rag_chain.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from training_agents.default_config import DEFAULT_CONFIG
from training_agents.llm_clients import create_llm_client
from training_agents.agents.analysts.recovery_analyst import create_recovery_agent
from training_agents.agents.utils.recovery_indicators import calculate_indicators
from training_agents.graph.setup import build_recovery_graph

# 构造差恢复状态（含训练历史）
state = {
    "morning_hr": 68,
    "rpe": 8,
    "muscle_soreness": 3,
    "parsed_activity": {"hr_drift": 6.5},
    "history": {
        "daily_checkins": [
            {"date": f"2024-03-0{d}", "morning_hr": 56}
            for d in range(1, 9)
        ],
        "training_sessions": [
            {"date": "2024-03-01", "activity": {"hr_drift": 4.5, "total_duration": 3000}},
            {"date": "2024-03-02", "activity": {"hr_drift": 5.2, "total_duration": 3600}},
            {"date": "2024-03-03", "activity": {"hr_drift": 3.0, "total_duration": 2700}},
            {"date": "2024-03-04", "activity": {"hr_drift": 6.0, "total_duration": 4200}},
            {"date": "2024-03-05", "activity": {"hr_drift": 7.0, "total_duration": 3600}},
            {"date": "2024-03-06", "activity": {"hr_drift": 5.5, "total_duration": 3300}},
            {"date": "2024-03-07", "activity": {"hr_drift": 6.5, "total_duration": 3800}},
        ],
    },
}

# 步骤 1: 计算指标
indicators = calculate_indicators(state)
print("=" * 60)
print("步骤 1: 硬编码计算恢复指标")
print("=" * 60)
for k, v in indicators.items():
    print(f"  {k}: {v}")

# 步骤 2: 构建 Graph
llm_client = create_llm_client(
    DEFAULT_CONFIG["llm_provider"],
    DEFAULT_CONFIG["deep_think_llm"],
)
llm = llm_client.get_llm()
agent_node = create_recovery_agent(llm=llm)
graph = build_recovery_graph(llm, agent_node)

# 步骤 3: 执行
print()
print("=" * 60)
print("步骤 2: Graph 执行（LLM 决策 → 搜书 → 生成总结）")
print("=" * 60)

result = graph.invoke(state)
report = result["recovery_report"]

# 打印最终报告
print()
print("=" * 60)
print("最终 RecoveryReport")
print("=" * 60)
for k, v in report.items():
    if k != "summary":
        print(f"  {k}: {v}")
print(f"  --- LLM 总结 ---")
print(report["summary"])
