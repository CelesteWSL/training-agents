# -*- coding: utf-8 -*-
"""Training Agents CLI —— 训练分析命令行入口。

命令：
    training-agents init                       交互式创建用户画像
    training-agents checkin --date DATE ...    每日记录（晨间心率 + RPE + 肌肉酸痛）
    training-agents analyze --date DATE        分析指定日期的训练
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 确保包根目录在 sys.path 中
_pkg_root = Path(__file__).resolve().parent.parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from dotenv import load_dotenv
load_dotenv()

from training_agents.default_config import DEFAULT_CONFIG
from training_agents.dataflows.profile_manager import UserProfileManager
from training_agents.graph.setup import build_main_graph
from training_agents.llm_clients.factory import create_llm_client

# ── 路径 ─────────────────────────────────────────────────────

DATA_DIR = _pkg_root / "data"
CHECKIN_DIR = DATA_DIR / "daily_checkin"
TRAINING_DIR = DATA_DIR / "training"
REPORTS_DIR = _pkg_root / "reports"


# ── 辅助 ─────────────────────────────────────────────────────

def _find_tcx(date_str: str) -> str | None:
    """根据日期查找 TCX 文件。

    TCX 命名: {description}{YYYYMMDDHHmmss}.tcx
    匹配后 14 位中的前 8 位日期。
    """
    date_compact = date_str.replace("-", "")
    if not os.path.isdir(TRAINING_DIR):
        return None

    matches = []
    for fname in os.listdir(TRAINING_DIR):
        if not fname.lower().endswith(".tcx"):
            continue
        stem = fname[:-4]
        if len(stem) < 14:
            continue
        ts = stem[-14:]
        if ts[:8] == date_compact:
            matches.append(os.path.join(TRAINING_DIR, fname))

    if not matches:
        return None
    if len(matches) > 1:
        print(f"⚠ 找到 {len(matches)} 个匹配的 TCX 文件，使用第一个: {matches[0]}")
    return matches[0]


def _read_checkin(date_str: str) -> dict:
    """读取 daily_checkin/{date}.json，返回 {morning_hr, rpe, muscle_soreness}。"""
    filepath = CHECKIN_DIR / f"{date_str}.json"
    if not filepath.is_file():
        raise FileNotFoundError(
            f"未找到 {date_str} 的每日记录。请先运行: training-agents checkin --date {date_str} --morning-hr <心率>"
        )
    with open(filepath, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _get_llm():
    """根据 DEFAULT_CONFIG 创建 LLM 客户端。"""
    provider = DEFAULT_CONFIG.get("llm_provider", "openai")
    model = DEFAULT_CONFIG.get("quick_think_llm", DEFAULT_CONFIG.get("deep_think_llm", "gpt-5.4-mini"))
    backend_url = DEFAULT_CONFIG.get("backend_url")
    return create_llm_client(provider, model, base_url=backend_url).get_llm()


# ── 命令实现 ─────────────────────────────────────────────────

def cmd_init():
    """交互式创建用户画像。"""
    profile = UserProfileManager.create_interactive()
    mgr = UserProfileManager(str(DATA_DIR))
    mgr.save(profile)
    print(f"\n✅ 用户画像已保存到 {DATA_DIR / 'user_profile.json'}")


def cmd_checkin(args):
    """写入每日记录。增量合并，不覆盖已有字段。"""
    date_str = args.date
    filepath = CHECKIN_DIR / f"{date_str}.json"

    # 读取已有数据
    existing = {}
    if filepath.is_file():
        with open(filepath, "r", encoding="utf-8-sig") as f:
            existing = json.load(f)

    # 合并新数据
    existing["morning_hr"] = args.morning_hr
    if args.rpe is not None:
        existing["rpe"] = args.rpe
    if args.soreness is not None:
        existing["muscle_soreness"] = args.soreness

    # 确保目录存在
    CHECKIN_DIR.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False)

    print(f"✅ {date_str} 每日记录已保存: {existing}")


def cmd_analyze(args):
    """运行全链路训练分析。"""
    date_str = args.date

    # 1. 加载用户画像
    mgr = UserProfileManager(str(DATA_DIR))
    if not mgr.exists():
        print("❌ 未找到用户画像。请先运行: training-agents init")
        sys.exit(1)
    user_profile = mgr.load()

    # 2. 读取每日记录
    checkin = _read_checkin(date_str)

    # 3. 查找 TCX 文件
    tcx_path = _find_tcx(date_str)
    if not tcx_path:
        print(f"❌ 未找到 {date_str} 的 TCX 文件 ({TRAINING_DIR})")
        sys.exit(1)
    print(f"📂 TCX: {tcx_path}")

    # 4. 组装 AgentState
    state = {
        "user_profile": user_profile,
        "activity_file": tcx_path,
        "date": date_str,
        "morning_hr": checkin["morning_hr"],
        "rpe": checkin.get("rpe", 0),
        "muscle_soreness": checkin.get("muscle_soreness", 0),
    }

    # 5. 运行 pipeline
    print("🤖 正在运行分析 pipeline...")
    llm = _get_llm()
    graph = build_main_graph(llm)
    result = graph.invoke(state)

    # 6. 提取并保存报告
    final_report = result.get("final_report", {})
    ruling = result.get("ruling", {})
    markdown = final_report.get("markdown", "")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{date_str}_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    # 终端摘要
    print(f"\n{'=' * 50}")
    print(f"  训练分析完成 — {date_str}")
    print(f"{'=' * 50}")
    print(f"  裁决: {ruling.get('verdict', 'N/A')}")
    print(f"  动作: {ruling.get('action', 'N/A')}")
    print(f"  报告: {report_path}")
    print(f"{'=' * 50}")


# ── CLI 入口 ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="training-agents",
        description="Training Agents — 多智能体训练分析系统",
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # init
    sub.add_parser("init", help="交互式创建用户画像")

    # checkin
    p_checkin = sub.add_parser("checkin", help="每日记录（晨间心率 + RPE + 肌肉酸痛）")
    p_checkin.add_argument("--date", "-d", required=True, help="日期 (YYYY-MM-DD)")
    p_checkin.add_argument("--morning-hr", type=int, required=True, help="晨间静息心率 (bpm)")
    p_checkin.add_argument("--rpe", type=int, default=None, help="主观疲劳 1-10（可选）")
    p_checkin.add_argument("--soreness", type=int, default=None, help="肌肉酸痛 0-5（可选）")

    # analyze
    p_analyze = sub.add_parser("analyze", help="分析指定日期的训练")
    p_analyze.add_argument("--date", "-d", required=True, help="日期 (YYYY-MM-DD)")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init()
    elif args.command == "checkin":
        cmd_checkin(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
