# -*- coding: utf-8 -*-
"""可见调用链测试 —— 打印 training load agent RAG 全流程每一步输出。

用法: python tests/test_load_rag_chain.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from training_agents.default_config import DEFAULT_CONFIG
from training_agents.llm_clients import create_llm_client
from training_agents.agents.analysts.load_analyst import create_load_agent
from training_agents.agents.utils.load_indicators import calculate_indicators
from training_agents.graph.setup import build_load_graph


# ── 辅助：构造训练 session ───────────────────────────────────

def _make_zones(z1=0.1, z2=0.5, z3=0.3, z4=0.08, z5=0.02):
    return {"zone1": z1, "zone2": z2, "zone3": z3, "zone4": z4, "zone5": z5}


def _make_session(date, hr_zones, duration_s=3600, distance_m=10000):
    return {
        "date": date,
        "activity": {
            "hr_zones": hr_zones,
            "total_duration": duration_s,
            "total_distance": distance_m,
        },
    }


# ── 构造高负荷状态 ──────────────────────────────────────────

# 前 21 天：正常训练（每天 10km, 1hr）
zones_normal = _make_zones()
sessions = [
    _make_session(f"2024-03-{d:02d}", zones_normal, 3600, 10000)
    for d in range(1, 22)
]

# 后 7 天：高负荷（每天 15km, 1.5hr, Zone4/5 占比翻倍）
zones_intense = _make_zones(z1=0.05, z2=0.35, z3=0.35, z4=0.18, z5=0.07)
for d in range(22, 29):
    sessions.append(_make_session(f"2024-03-{d:02d}", zones_intense, 5400, 15000))

state = {
    "date": "2024-03-28",
    "history": {
        "daily_checkins": [],
        "training_sessions": sessions,
    },
}

# 步骤 1: 计算指标
indicators = calculate_indicators(state)
print("=" * 60)
print("步骤 1: 硬编码计算训练负荷指标")
print("=" * 60)
for k, v in indicators.items():
    print(f"  {k}: {v}")

# 步骤 2: 构建 Graph
llm_client = create_llm_client(
    DEFAULT_CONFIG["llm_provider"],
    DEFAULT_CONFIG["deep_think_llm"],
)
llm = llm_client.get_llm()
agent_node = create_load_agent(llm=llm)
graph = build_load_graph(llm, agent_node)

# 步骤 3: 执行
print()
print("=" * 60)
print("步骤 2: Graph 执行（LLM 决策 → 搜书 → 生成总结）")
print("=" * 60)

result = graph.invoke(state)
report = result["load_report"]

# 打印最终报告
print()
print("=" * 60)
print("最终 LoadReport")
print("=" * 60)
for k, v in report.items():
    if k != "summary":
        print(f"  {k}: {v}")
print(f"  --- LLM 总结 ---")
print(report["summary"])
