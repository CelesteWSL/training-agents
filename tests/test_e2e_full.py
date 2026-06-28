import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage, SystemMessage

from training_agents.agents.analysts.data_analyst import data_agent_node
from training_agents.agents.engines.recognition_engine import sra_node
from training_agents.agents.engines.decision_engine import decision_node
from training_agents.agents.report.report_generator import report_node
from training_agents.agents.utils.recovery_indicators import calculate_indicators as rec_calc, format_indicators as rec_fmt
from training_agents.agents.utils.load_indicators import calculate_indicators as load_calc, format_indicators as load_fmt
from training_agents.agents.utils.performance_indicators import calculate_indicators as perf_calc, format_indicators as perf_fmt
from training_agents.agents.utils.risk_indicators import calculate_indicators as risk_calc, format_indicators as risk_fmt
from training_agents.agents.analysts.recovery_analyst import RECOVERY_SYSTEM_PROMPT
from training_agents.agents.analysts.load_analyst import LOAD_SYSTEM_PROMPT
from training_agents.agents.analysts.performance_analyst import PERFORMANCE_SYSTEM_PROMPT
from training_agents.agents.analysts.risk_analyst import RISK_SYSTEM_PROMPT
from training_agents.llm_clients.factory import create_llm_client
from training_agents.agents.utils.agent_utils import get_language_instruction

# ── 1. Data Agent ──
print("=" * 60)
print("Step 1: Data Agent")
state = {
    "activity_file": "../data/training/亚索80020240321210044.tcx",
    "user_profile": {
        "age": 24, "gender": "male", "height_cm": 181, "weight_kg": 78,
        "goal": "marathon", "training_level": "进阶",
        "personal_bests": {"5km": "26:00", "10km": "56:00"},
        "injury_history": [], "max_hr": 190,
    },
    "date": "2024-03-21",
    "morning_hr": 65, "rpe": 4, "muscle_soreness": 3,
}
print(f'  activity_file: {state["activity_file"]}')
r = data_agent_node(state)
state.update(r)
pa = state["parsed_activity"]
h = state["history"]
print(f"  sport={pa['sport']}  dist={pa['total_distance']:.0f}m  dur={pa['total_duration']:.0f}s  avg_hr={pa['avg_hr']}")
print(f"  hr_drift={pa['hr_drift']:.1f}%  cadence={pa['avg_cadence']}")
print(f"  history: {len(h['training_sessions'])} training sessions, {len(h['daily_checkins'])} checkins")

# ���� 2. LLM ����
print("\n" + "=" * 60)
print("Step 2: LLM Client")
llm = create_llm_client("deepseek", "deepseek-v4-flash").get_llm()
print("  model ready")

# ���� 3. Analysts ����
msg = HumanMessage(content="-----------summary---------")

for label, calc_fn, fmt_fn, prompt in [
    ("Recovery", rec_calc, rec_fmt, RECOVERY_SYSTEM_PROMPT),
    ("Load", load_calc, load_fmt, LOAD_SYSTEM_PROMPT),
    ("Performance", perf_calc, perf_fmt, PERFORMANCE_SYSTEM_PROMPT),
    ("Risk", risk_calc, risk_fmt, RISK_SYSTEM_PROMPT),
]:
    print(f"\n{'=' * 60}")
    print(f"Step: {label} Agent")
    indicators = calc_fn(state)
    sys_msg = SystemMessage(content=prompt + "\n\n" + fmt_fn(indicators) + get_language_instruction())
    resp = llm.invoke([sys_msg, msg])
    report = {**indicators, "summary": resp.content.strip()}
    state[f"{label.lower()}_report"] = report
    print(f"  {label} summary: {resp.content.strip()}")

# ---- 4. Coach Engines ----
print("\n" + "=" * 60)
print("Step: Coach Engines")
r = sra_node(state)
state.update(r)
n = len(state["state_recognition"]["physiological_states"])
print(f"  SRA: {n} physiological states detected")

r = decision_node(state)
state.update(r)
ruling = state["ruling"]
print(f"  Decision: {ruling['action']} -> {ruling['verdict']}")

# ---- 5. Report Generator ----
print("\n" + "=" * 60)
print("Step: Report Generator")
r = report_node(state, llm)
state.update(r)
markdown = state["final_report"]["markdown"]
print(markdown)

print("\n" + "=" * 60)
print("PIPELINE COMPLETE")
