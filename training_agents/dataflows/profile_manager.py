# -*- coding: utf-8 -*-
"""UserProfileManager — 用户画像的创建、持久化和加载。"""

import json
import os
from typing import Optional

from training_agents.agents.utils.agent_states import UserProfile

VALID_GOALS = ["5km", "10km", "half_marathon", "marathon"]
VALID_LEVELS = ["新手", "进阶", "高级"]
VALID_INJURIES = ["膝盖", "跟腱", "足底筋膜", "髋关节", "胫骨/应力"]
VALID_PB_DISTANCES = ["5km", "10km", "半马", "全马"]
VALID_GENDERS = ["male", "female", "other"]

def _validate_profile(profile):
    errors = []
    age = profile.get("age")
    if not isinstance(age, int) or not (10 <= age <= 120):
        errors.append(f"age 需为 10-120 的整数, 当前: {age}")
    gender = profile.get("gender", "")
    if gender not in VALID_GENDERS:
        errors.append(f"gender 需为 {VALID_GENDERS}, 当前: {gender}")
    height = profile.get("height_cm")
    if not isinstance(height, (int, float)) or not (100 <= height <= 250):
        errors.append(f"height_cm 需为 100-250, 当前: {height}")
    weight = profile.get("weight_kg")
    if not isinstance(weight, (int, float)) or not (30 <= weight <= 250):
        errors.append(f"weight_kg 需为 30-250, 当前: {weight}")
    goal = profile.get("goal", "")
    if goal not in VALID_GOALS:
        errors.append(f"goal 需为 {VALID_GOALS}, 当前: {goal}")
    level = profile.get("training_level", "")
    if level not in VALID_LEVELS:
        errors.append(f"training_level 需为 {VALID_LEVELS}, 当前: {level}")
    pbs = profile.get("personal_bests", {})
    if not isinstance(pbs, dict):
        errors.append("personal_bests 需为 dict")
    else:
        for k in pbs:
            if k not in VALID_PB_DISTANCES:
                errors.append(f"personal_bests key 需为 {VALID_PB_DISTANCES}, 当前: {k}")
    injuries = profile.get("injury_history", [])
    if not isinstance(injuries, list):
        errors.append("injury_history 需为 list")
    else:
        for item in injuries:
            if item not in VALID_INJURIES:
                errors.append(f"injury_history 每项需为 {VALID_INJURIES}, 当前: {item}")
    max_hr = profile.get("max_hr")
    if max_hr is not None:
        if not isinstance(max_hr, int) or not (100 <= max_hr <= 220):
            errors.append(f"max_hr 需为 100-220 或 null, 当前: {max_hr}")
    return errors

class UserProfileManager:
    FILENAME = "user_profile.json"
    def __init__(self, data_dir):
        self._filepath = os.path.join(data_dir, self.FILENAME)
    def exists(self):
        return os.path.isfile(self._filepath)
    def load(self):
        if not self.exists():
            raise FileNotFoundError(f"Profile 文件不存在: {self._filepath}")
        with open(self._filepath, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        errors = _validate_profile(data)
        if errors:
            raise ValueError("Profile 校验失败:\n" + "\n".join(f"  - {e}" for e in errors))
        return UserProfile(
            age=data["age"], gender=data["gender"],
            height_cm=float(data["height_cm"]), weight_kg=float(data["weight_kg"]),
            goal=data["goal"], training_level=data["training_level"],
            personal_bests=data.get("personal_bests", {}),
            injury_history=data.get("injury_history", []),
            max_hr=data.get("max_hr"),
        )
    def save(self, profile):
        profile_dict = dict(profile)
        errors = _validate_profile(profile_dict)
        if errors:
            raise ValueError("保存前校验失败:\n" + "\n".join(f"  - {e}" for e in errors))
        os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(profile_dict, f, ensure_ascii=False, indent=2)
    @staticmethod
    def create_default():
        return UserProfile(
            age=28, gender="male", height_cm=175.0, weight_kg=70.0,
            goal="half_marathon", training_level="进阶",
            personal_bests={"5km": "25:00", "10km": "52:00", "半马": "1:55:00"},
            injury_history=[], max_hr=192,
        )
    @staticmethod
    def create_interactive():
        print("=" * 50)
        print("  跑者基础画像录入")
        print("=" * 50)
        while True:
            raw = input("年龄 (10-120): ").strip()
            try:
                age = int(raw)
                if 10 <= age <= 120:
                    break
            except ValueError:
                pass
            print("  请输入 10-120 之间的整数")
        print("\n性别: " + ", ".join(VALID_GENDERS))
        while True:
            raw = input("性别: ").strip().lower()
            if raw in VALID_GENDERS:
                gender = raw
                break
            print("  请输入 " + ", ".join(VALID_GENDERS) + " 之一")
        while True:
            raw = input("身高/cm (100-250): ").strip()
            try:
                height_cm = float(raw)
                if 100 <= height_cm <= 250:
                    break
            except ValueError:
                pass
            print("  请输入 100-250 之间的数字")
        while True:
            raw = input("体重/kg (30-250): ").strip()
            try:
                weight_kg = float(raw)
                if 30 <= weight_kg <= 250:
                    break
            except ValueError:
                pass
            print("  请输入 30-250 之间的数字")
        print("\n训练目标:")
        for i, g in enumerate(VALID_GOALS):
            print(f"  [{i+1}] {g}")
        while True:
            raw = input("选择 (1-5): ").strip()
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(VALID_GOALS):
                    goal = VALID_GOALS[idx]
                    break
            except ValueError:
                pass
            print("  请输入 1-" + str(len(VALID_GOALS)))
        print("\n训练水平:")
        for i, lv in enumerate(VALID_LEVELS):
            print(f"  [{i+1}] {lv}")
        while True:
            raw = input("选择 (1-3): ").strip()
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(VALID_LEVELS):
                    training_level = VALID_LEVELS[idx]
                    break
            except ValueError:
                pass
            print("  请输入 1-3")
        print("\n历史 PB (可选, 直接回车跳过):")
        personal_bests = {}
        for dist in VALID_PB_DISTANCES:
            raw = input(f"  {dist} 成绩 (mm:ss): ").strip()
            if raw:
                personal_bests[dist] = raw
        print("\n历史伤病位置 (可选, 多选用逗号分隔):")
        for i, inj in enumerate(VALID_INJURIES):
            print(f"  [{i+1}] {inj}")
        raw = input("选择 (如 1,2,3): ").strip()
        injury_history = []
        if raw:
            seen = set()
            for part in raw.split(","):
                try:
                    idx = int(part.strip()) - 1
                    if 0 <= idx < len(VALID_INJURIES):
                        inj = VALID_INJURIES[idx]
                        if inj not in seen:
                            injury_history.append(inj)
                            seen.add(inj)
                except ValueError:
                    pass
        default_hr = 220 - age
        print(f"\n最大心率 (直接回车 = {default_hr}):")
        raw = input("最大心率 (100-220): ").strip()
        max_hr = None
        if raw:
            try:
                val = int(raw)
                if 100 <= val <= 220:
                    max_hr = val
            except ValueError:
                pass
        if max_hr is None:
            max_hr = default_hr
            print(f"  使用: {max_hr}")
        print()
        print("-" * 50)
        print("录入完成!")
        print(f"  年龄:{age}  性别:{gender}  身高:{height_cm}cm  体重:{weight_kg}kg")
        print(f"  目标:{goal}  水平:{training_level}  最大心率:{max_hr}")
        if personal_bests:
            print(f"  PB: {personal_bests}")
        if injury_history:
            print(f"  伤病史: {injury_history}")
        print("-" * 50)
        return UserProfile(
            age=age, gender=gender, height_cm=height_cm, weight_kg=weight_kg,
            goal=goal, training_level=training_level,
            personal_bests=personal_bests, injury_history=injury_history, max_hr=max_hr,
        )
