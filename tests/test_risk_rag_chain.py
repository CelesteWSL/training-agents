# -*- coding: utf-8 -*-
"""可见调用链测试 —— 打印 risk agent RAG 全流程每一步输出。

用法: python tests/test_risk_rag_chain.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from training_agents.default_config import DEFAULT_CONFIG
from training_agents.llm_clients import create_llm_client
from training_agents.agents.analysts.risk_analyst import create_risk_agent
from training_agents.agents.utils.risk_indicators import calculate_indicators
from training_agents.graph.setup import build_risk_graph


# ── 辅助：构造 technique_flag ────────────────────────────────

def _flag(metric, current, severity="warning"):
    return {"metric": metric, "current": current, "benchmark": 0, "direction": "low", "severity": severity}


# ── 构造高风险状态（injury_risk > 60，触发 RAG）──────────────

state = {
    "load_report": {
        "acwr": 1.6,
        "ramp_rate": 0.25,
    },
    "recovery_report": {
        "recovery_score": 25.0,
        "fatigue_trend": "accumulating",
        "recovery_debt_trend": "worsening",
        "consecutive_hard_days": 5,
    },
    "performance_report": {
        "technique_flags": [
            _flag("cadence", 155, "critical"),
            _flag("gct", 280, "critical"),
            _flag("lr_balance", 47.0, "warning"),
        ],
    },
    "user_profile": {
        "injury_history": ["膝盖", "跟腱"],
        "age": 55,
        "max_hr": 165,
        "goal": "marathon",
        "training_level": "进阶",
        "gender": "男",
        "height_cm": 175.0,
        "weight_kg": 70.0,
        "personal_bests": {},
    },
}

# 步骤 1: 硬编码计算风险指标
indicators = calculate_indicators(state)
print("=" * 60)
print("步骤 1: 硬编码计算伤病风险指标")
print("=" * 60)
print(f"  伤病风险评分: {indicators['injury_risk_score']:.0f}/100")
print(f"  风险等级: {indicators['risk_level']}")
print(f"  风险因子 ({len(indicators['risk_factors'])} 条):")
for rf in indicators["risk_factors"]:
    print(f"    [{rf['source']:12s}] {rf['factor']:20s} = {str(rf['value']):10s} ({rf['status']})")
print(f"  预警 ({len(indicators['alerts'])} 条):")
for a in indicators["alerts"]:
    print(f"    ⚠  {a}")

# 步骤 2: 构建 Graph
llm_client = create_llm_client(
    DEFAULT_CONFIG["llm_provider"],
    DEFAULT_CONFIG["deep_think_llm"],
)
llm = llm_client.get_llm()
agent_node = create_risk_agent(llm=llm)
graph = build_risk_graph(llm, agent_node)

# 步骤 3: 执行（injury_risk > 60 → 触发 RAG 搜索知识库）
print()
print("=" * 60)
print("步骤 2: Graph 执行（LLM 决策 → 搜书 → 生成总结）")
print("          injury_risk > 60 → 应触发 search_knowledge")
print("=" * 60)

result = graph.invoke(state)
report = result["risk_report"]

# 打印最终报告
print()
print("=" * 60)
print("最终 RiskReport")
print("=" * 60)
print(f"  risk_level:        {report['risk_level']}")
print(f"  injury_risk_score: {report['injury_risk_score']:.0f}")
print(f"  alerts:            {report['alerts']}")
print(f"  --- LLM 总结 ---")
print(report["summary"])
