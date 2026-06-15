## Training Table Generator

Training Table Generator 是训练计划系统的初始生成层，负责在用户初始化时生成完整的周期化训练表。它输出 TrainingTable，供 Training Planner Agent 后续动态调整。

### 与 Training Planner Agent 的关系

Training Table Generator 回答——初始计划是什么——，Training Planner Agent 回答——执行中如何调整——。

Training Table Generator 的输入是 UserProfile（goal + training_level），输出是完整的 12-16 周周期化训练表。采用三层模板系统生成，跑量按 Goal×Level 二维配置表计算，不设乘法因子。

### Schema

#### TrainingTable
```python
class TrainingTable(TypedDict):
    generated_date:       str       # "2026-06-15"
    start_date:           str       # "2026-06-15"
    end_date:             str       # "2026-10-04"
    plan_metadata:        PlanMetadata
    weekly_blocks:        List[WeeklyBlock]
```

#### PlanMetadata
```python
class PlanMetadata(TypedDict):
    goal:                 str       # "half_marathon"
    training_level:       str       # "进阶"
    plan_duration_weeks:  int       # 12
    weekly_frequency:     int       # 4（活跃训练日数）
```

#### WeeklyBlock
```python
class WeeklyBlock(TypedDict):
    week_number:          int       # 1-16
    start_date:           str       # "2026-06-15"
    end_date:             str       # "2026-06-21"
    phase:                str       # "base"
    phase_label:          str       # "基础期"
    planned_volume_km:    float
    status:               str       # "planned" / "active" / "completed" / "adjusted"
    sessions:             List[DailySession]
    notes:                str
```

#### DailySession
```python
class DailySession(TypedDict):
    session_id:           str       # "w03_tue_tempo"
    date:                 str       # "2026-06-15"
    day_of_week:          str       # "周一"
    session_type:         str       # rest / easy_run / long_run / tempo / intervals / strides / recovery_run / marathon_pace
    duration_min:         int
    target_distance_km:   Optional[float]
    intensity:            str       # "rest" / "easy" / "moderate" / "hard"
    hr_zone:              str       # "rest" / "zone1" / "zone2" / "zone3" / "zone4"
    description:          str
    technique_focus:      List[str]
```

---

### 三层模板系统

#### Layer 1 — Goal 周骨架（7 天 slot）

Slot 类型：`rest`, `easy`, `primary_quality`, `secondary_quality`, `long_run`

```python
WEEK_TEMPLATE = {
    "5km":            ["rest","primary_quality","easy","secondary_quality","easy","easy","long_run"],
    "10km":           ["rest","easy","primary_quality","easy","secondary_quality","easy","long_run"],
    "half_marathon":  ["rest","easy","primary_quality","easy","rest","easy","long_run"],
    "marathon":       ["rest","easy","primary_quality","easy","rest","easy","long_run"],
}
```

#### Layer 2 — Goal×Phase 解析 quality slot

```python
QUALITY_RESOLVER = {
    "5km": {
        "base":   ("easy_run", "easy_run"),
        "build":  ("tempo", "tempo"),
        "peak":   ("intervals", "tempo"),
        "taper":  ("tempo", "easy_run"),
    },
    "10km": {
        "base":   ("easy_run", "easy_run"),
        "build":  ("tempo", "tempo"),
        "peak":   ("tempo", "intervals"),
        "taper":  ("tempo", "easy_run"),
    },
    "half_marathon": {
        "base":   ("easy_run", "easy_run"),
        "build":  ("tempo", "tempo"),
        "peak":   ("marathon_pace", "tempo"),
        "taper":  ("tempo", "easy_run"),
    },
    "marathon": {
        "base":   ("easy_run", "easy_run"),
        "build":  ("tempo", "marathon_pace"),
        "peak":   ("marathon_pace", "tempo"),
        "taper":  ("tempo", "easy_run"),
    },
}
```

#### Layer 3 — Level 激活 slot

| Level | 规则 | 活跃日数 |
|-------|------|---------|
| 新手 | secondary_quality → rest | 3-4 |
| 进阶 | 全部保留 | 4-5 |
| 高级 | 最后一个 rest → easy | 5-6 |

---

### Phase 配置

```python
PHASE_CONFIG = {
    "5km":            {"base": 3, "build": 5, "peak": 2, "taper": 2},   # 12 周
    "10km":           {"base": 4, "build": 4, "peak": 2, "taper": 2},   # 12 周
    "half_marathon":  {"base": 4, "build": 4, "peak": 2, "taper": 2},   # 12 周
    "marathon":       {"base": 6, "build": 6, "peak": 2, "taper": 2},   # 16 周
}

PHASE_LABELS = {
    "base":   "基础期",
    "build":  "进展期",
    "peak":   "巅峰期",
    "taper":  "减量期",
}
```

---

### 跑量配置

#### 二维跑量表 BASE_VOLUME[goal][level]（km/w 基准）

```python
BASE_VOLUME = {
    "5km":            {"新手": 15, "进阶": 25, "高级": 40},
    "10km":           {"新手": 20, "进阶": 35, "高级": 50},
    "half_marathon":  {"新手": 25, "进阶": 40, "高级": 60},
    "marathon":       {"新手": 35, "进阶": 55, "高级": 80},
}
```

#### 跑量递进规则

- 基础周跑量 = `BASE_VOLUME[goal][level]`
- Build 期逐周递增 5-10%，Peak 期到达峰值
- Taper 期递减至峰值的 60-70%
- 每 3-4 周安排一次减量周（-15% ~ -20%）

---

### Session 类型

| session_type | 中文名 | 心率区间 | 配速参考 |
|-------------|--------|---------|---------|
| rest | 休息 | rest | — |
| recovery_run | 恢复跑 | Zone1 | 非常轻松 |
| easy_run | 轻松跑 | Zone2 | 舒适可对话 |
| long_run | 长距离 | Zone2 | 轻松跑配速 |
| tempo | 节奏跑 | Zone3-4 | 5:00-5:30/km |
| intervals | 间歇跑 | Zone4-5 | 3:45-4:15/km |
| strides | 跨步跑 | Zone4 | 短冲刺 |
| marathon_pace | 比赛配速跑 | Zone3 | 5:15-5:45/km |

---

### 自动调节 Gate（防震荡）

#### FATIGUE_POLICY 配置

```python
FATIGUE_POLICY = {
    "rpe_threshold": 7,
    "soreness_threshold": 3,
    "fatigue_days": 3,
}
```

#### should_adjust 逻辑

```python
def should_adjust(recent_analyses: List[RulingResult]) -> bool:
    critical_count = sum(1 for r in recent_analyses if r.severity == "critical")
    warning_count = sum(1 for r in recent_analyses if r.severity == "warning")
    fatigue_streak = compute_fatigue_streak(recent_analyses)

    if critical_count >= 1:
        return True
    if warning_count >= 2:
        return True
    if fatigue_streak >= FATIGUE_POLICY["fatigue_days"]:
        return True
    return False
```

触发阈值：
- 1 次 critical → 立即调整
- 连续 2 天 warning → 调整
- 连续 3 天疲劳信号（RPE≥7 或 soreness≥3）→ 调整

#### 调节动作

| 触发条件 | 调节动作 |
|---------|---------|
| full_rest | 当日 + 次日全休，Long Run 减量 50% |
| recovery_run | 高强度 → Easy，跑量缩减 50% |
| reduce_load | 高强度 → Easy，跑量缩减 30%，保留 Long Run |
| quality_session | 按原计划执行质量训练 |
| normal_training | 不调整 |

---

### ruling_log.json

固定窗口记录，避免无限增长。

```python
MAX_RULING_HISTORY = 30
```

#### 追加逻辑

```python
def append_ruling(entry: dict):
    history = load_ruling_log()
    history.append(entry)
    history = history[-MAX_RULING_HISTORY:]
    save_ruling_log(history)
```

---

### CLI

#### init 集成

初始化 UserProfile 时自动触发 Training Table Generator，生成首个 12-16 周计划。

```
training-agents init
  → UserProfile 录入
  → TrainingTable 自动生成
  → 保存至 data/training_plan.json
```

#### analyze 集成

每次 `training-agents analyze` 后评估是否需要调整计划，自动定位当前周并通过 Gate 判断。

```
training-agents analyze
  → 各 Agent 分析
  → Coach Agent 裁决
  → (if Gate passes) Training Planner 调整计划
```

---

### 核心函数

```python
def generate_training_table(profile: UserProfile) -> TrainingTable:
    """基于 UserProfile 生成完整周期化训练表。"""
    ...

def build_week(week_num: int, phase: str, goal: str, level: str) -> WeeklyBlock:
    """按三层模板生成单周课表。"""
    ...

def calculate_volume(goal: str, level: str, phase: str, week_num: int) -> float:
    """根据 BASE_VOLUME 和递进规则计算当周跑量。"""
    ...
```

#### 内部辅助

```python
def resolve_slot(slot: str, goal: str, phase: str, level: str) -> DailySession:
    """将 slot（primary_quality 等）解析为具体 DailySession。"""
    ...

def apply_level_activation(slots: List[str], level: str) -> List[str]:
    """Level 3 规则：新手/进阶/高级激活 slot。"""
    ...
```

---

## Training Planner Agent

### 职责边界

Training Planner Agent 负责**动态调整已有训练计划**，不负责初始生成。它接收 Coach Agent 的裁决，在已有 TrainingTable 基础上修改未来的训练安排。

Coach Agent 回答"发生了什么"，Training Planner Agent 回答"未来怎么办"——两者配合构成完整的训练教练系统。

### 输入

```json
{
    "action": "reduce_load",
    "modifiers": [{"key": "cadence_drill", "label": "步频练习", "reason": "步频过低"}],
    "user_goal": "marathon",
    "current_plan": "<TrainingTable>",
    "analysis_context": {
        "date": "2026-06-15",
        "physiological_states": ["cns_fatigue"],
        "ruling_history": [...]
    }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | `str` | Decision Engine 裁决：`full_rest` / `recovery_run` / `reduce_load` / `quality_session` / `normal_training` |
| `modifiers` | `List[TechniqueModifier]` | 技术修饰器列表（可空），含 `key` `label` `reason` |
| `user_goal` | `str` | 用户训练目标：`5km` / `10km` / `half_marathon` / `marathon` |
| `current_plan` | `TrainingTable` | 当前生效的训练计划 |
| `analysis_context` | `dict` | 当日分析上下文（生理状态、裁决历史等） |

### 输出

```json
{
    "plan_updated": true,
    "updated_plan": "<TrainingTable>",
    "changes": [
        {
            "date": "2026-06-18",
            "original": "Interval 8×400m",
            "updated": "Easy 8km",
            "reason": "Policy: remove_high_intensity",
            "debt_created": "debt_20260618_interval"
        }
    ],
    "constraint_check": {
        "passed": true,
        "violations": []
    },
    "repair_log": null
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `plan_updated` | `bool` | 计划是否有变更 |
| `updated_plan` | `TrainingTable` | 修改后的完整计划 |
| `changes` | `List[Adjustment]` | 逐条修改记录 |
| `constraint_check` | `ConstraintCheckerResult` | 约束校验结果 |
| `repair_log` | `dict` or `null` | 修复引擎日志 |

### 核心设计原则

#### 修改计划，而非生成计划

与 Training Table Generator 严格分工。Planner 永远基于已有计划做增量修改——只调整受影响的周和 Session，不重新生成整表。这保证了训练计划的连续性和可追溯性。

---

### 内部架构

```python
class TrainingPlannerAgent:
    def adjust(self, input: PlannerInput) -> PlannerOutput:
        policy    = PolicyGenerator.generate(input.action, input.modifiers, input.user_goal)
        draft     = PlanModifier.modify(policy, input.current_plan, input.analysis_context)
        check     = ConstraintChecker.check_all(draft, input.analysis_context)
        if not check.passed:
            draft = RepairEngine.repair(draft, check.violations)
            check = ConstraintChecker.check_all(draft, input.analysis_context)
        changes   = diff(input.current_plan, draft)
        debts     = DebtManager.register(changes)
        return PlannerOutput(draft, changes, check, debts)
```

流水线：**Policy Generator → Plan Modifier → Constraint Checker → Repair Engine → Final Plan**

注意：Constraint 的职责是验收（Validation），不是指导修改（Modification）。Repair Engine 才是修复的执行者。

---

### 模块详解

#### 1. Policy Generator（策略生成器）

最上层策略模块，不关心具体课表，只产生产品级训练调整策略。

**输入：**

```json
{
    "action": "reduce_load",
    "modifiers": [{"key": "cadence_drill", "label": "步频练习", "reason": "步频过低"}],
    "user_goal": "marathon"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | `str` | Decision Engine 裁决：`full_rest` / `recovery_run` / `reduce_load` / `quality_session` / `normal_training` |
| `modifiers` | `List[TechniqueModifier]` | 技术修饰器列表（可空），含 `key` `label` `reason` |
| `user_goal` | `str` | 用户训练目标：`5km` / `10km` / `half_marathon` / `marathon` |

**输出：**

```json
{
    "downgrade_high_intensity": true,
    "reduce_volume_ratio": 0.3,
    "protect_long_run": true,
    "apply_technique_modifiers": true
}
```

| 策略字段 | 类型 | 说明 |
|----------|------|------|
| `downgrade_high_intensity` | `bool` | 是否将 Interval / Tempo / VO2Max / Long Run 降级为 Easy Run |
| `reduce_volume_ratio` | `float` | 训练量缩减比例（0.0 ~ 1.0），作用于所有非 Rest 课 |
| `protect_long_run` | `bool` | 是否保留长距离训练（不减量、不降级） |
| `apply_technique_modifiers` | `bool` | 是否将 `modifiers` 中的技术练习叠加到当日训练 |

**action → Policy 映射规则（硬编码）：**

| action | downgrade_high_intensity | reduce_volume_ratio | protect_long_run | apply_technique_modifiers |
|---|---|---|---|---|
| `full_rest` | true | 1.0 | false | false |
| `recovery_run` | true | 0.5 | false | true |
| `reduce_load` | true | 0.3 | true | true |
| `quality_session` | false | 0.0 | true | true |
| `normal_training` | false | 0.0 | true | false |

> **降级映射表**由 Plan Modifier 负责：Interval/VO2Max → Easy(70%时长)、Tempo/Threshold → Easy(等时长)、Long Run → Easy(60%距离)。Policy Generator 只决定"是否降级"，不决定"降到什么程度"。

---

#### 2. Plan Modifier（计划修改器）

根据 Policy Generator 的策略修改课表，产出修改后的计划草案。

**输入：**

```json
policy + constraints + debts + current_plan
```

**输出：**

```json
updated_plan
```

**示例：**

原计划（一周）：

```
Mon   Rest
Tue   Interval 8×400m
Wed   Easy 10km
Thu   Tempo 8km
Fri   Easy 8km
Sat   Easy 10km
Sun   Long Run 30km
```

Policy（`protect_recovery`）→ 调整后：

```
Mon   Rest
Tue   Easy 8km          ← Interval → Easy（降强度）
Wed   Easy 10km
Thu   Easy 8km          ← Tempo → Easy（降强度）
Fri   Easy 8km
Sat   Easy 10km
Sun   Long Run 24km     ← 保留但减量 20%（GoalConstraint）
```

**Adjustment Log（changes 字段）：**

```json
[
    {
        "date": "2024-06-04",
        "original": "Interval 8×400m",
        "updated": "Easy 8km",
        "reason": "Policy: remove_high_intensity",
        "debt_created": "debt_20240604_interval"
    },
    {
        "date": "2024-06-06",
        "original": "Tempo 8km",
        "updated": "Easy 8km",
        "reason": "Policy: remove_high_intensity"
    },
    {
        "date": "2024-06-09",
        "original": "Long Run 30km",
        "updated": "Long Run 24km",
        "reason": "Policy: reduce_volume_ratio 0.2, GoalConstraint: Long Run ≤ 35%"
    }
]
```

---

#### 3. Constraint Checker（约束校验器）

专业度的核心来源。位于 Plan Modifier 之后，作为验收层——验证修改后的计划是否满足约束，不负责修改课表。

**内部结构：**

```
Constraint Checker
├── GoalConstraint
├── RecoveryConstraint
├── VolumeConstraint
└── IntensityConstraint
```

每个子约束实现统一的 BaseConstraint 接口：

```python
class BaseConstraint:
    def check(self, plan, context) -> ConstraintResult:
        """只发现问题，不修改计划。"""
        ...

class GoalConstraint(BaseConstraint):       ...
class RecoveryConstraint(BaseConstraint):   ...
class VolumeConstraint(BaseConstraint):     ...
class IntensityConstraint(BaseConstraint):  ...
```

子约束返回 ConstraintResult：

```json
{
    "name": "volume",
    "passed": false,
    "violations": [...]
}
```

顶层 ConstraintChecker.check_all() 汇总为 ConstraintCheckerResult：

```json
{
    "passed": false,
    "violations": [
        {
            "constraint": "volume",
            "rule": "long_run_ratio",
            "severity": "warning",
            "target": {"week": 5, "session_id": "w05_sun_long_run"},
            "actual": 18.0,
            "limit": 14.0,
            "message": "Long Run 18km 占周跑量 45%，超出 35% 上限"
        },
        {
            "constraint": "recovery",
            "rule": "hard_gap",
            "severity": "critical",
            "target": {"week": 5, "session_id": "w05_wed_tempo"},
            "actual": 1,
            "limit": 2,
            "message": "Hard session 间隔不足（需 ≥ 2 天）"
        }
    ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| constraint | str | 所属约束：goal / recovery / volume / intensity |
| rule | str | 违规规则标识 |
| severity | str | critical > warning > info，Repair Engine 按此排序处理 |
| target | dict | 定位信息：week + session_id，Repair Engine 据此精确修改 |
| actual | float | 实际值 |
| limit | float | 阈值上限 |
| message | str | 人类可读描述 |

最终由 Constraint Checker 汇总所有子结果：

```python
def check_all(plan, context) -> ConstraintCheckerResult:
    details = {
        "goal":      goal_constraint.check(plan, context),
        "recovery":  recovery_constraint.check(plan, context),
        "volume":    volume_constraint.check(plan, context),
        "intensity": intensity_constraint.check(plan, context),
    }
    return ConstraintCheckerResult(
        passed=all(r.passed for r in details.values()),
        violations=[v for r in details.values() for v in r.violations],
        details=details,
    )
```

- `passed`：所有子约束都通过才为 true
- `violations`：合并所有子约束的违规列表（保留 `details` 便于 Debug）
- `details`：分组保留各子约束结果，后续 Report Generator 和 Repair Engine 均可复用

##### GoalConstraint（目标约束）

根据用户目标，标记 GoalPriority Session（优先保留，仅在 critical / full_rest 时可调整）：

| 目标 | GoalPriority Slot | 原因 |
|------|-----------------|------|
| `marathon` | Long Run | 全马成绩依赖长距离耐力 |
| `5km` | Interval / VO2Max | 5km 依赖速度耐力 |
| `10km` | Tempo / Interval | 10km 依赖阈值能力 |
| `half_marathon` | Long Run / Tempo | 半马依赖耐力+速度 |

```python
GOAL_PRIORITY = {
    "marathon":       ["long_run"],
    "half_marathon":  ["long_run", "primary_quality"],
    "10km":           ["primary_quality", "secondary_quality"],
    "5km":            ["primary_quality"],
}
```

**降级链（减量时从先到后）：**

```
easy → secondary_quality → primary_quality → long_run（slot 级别，由 Resolver 解析为具体课型）
```

##### RecoveryConstraint（恢复约束）

| 规则 | 阈值 | severity |
|------|------|----------|
| Hard Session 间隔 | ≥ 1 天（hard_gap_days=1） | critical |
| 禁止连续 2 天 Hard | — | critical |

```python
HARD_SESSIONS = {
    "intervals",
    "vo2max",
    "threshold",
}

MODERATE_SESSIONS = {
    "tempo",
    "marathon_pace",
}
```

`is_hard(session)` 统一判定。Long Run 默认 Low，但若含 MP/Tempo 段则按实际强度判定。

##### VolumeConstraint（负荷约束）

| 规则 | 阈值 | severity |
|------|------|----------|
| 周跑量变化率 | 新手 ≤10% / 进阶 ≤15% / 高级 ≤20% | warning |
| Long Run 占比 | 5km≤25% / 10km≤30% / 半马≤35% / 全马≤40% | warning |

```python
VOLUME_POLICY = {
    "新手": 0.10,
    "进阶": 0.15,
    "高级": 0.20,
}

LONG_RUN_POLICY = {
    "5km":            0.25,
    "10km":           0.30,
    "half_marathon":  0.35,
    "marathon":       0.40,
}
```

##### IntensityConstraint（强度分布约束）

按 **训练时长（training_minutes）** 统计，而非训练天数。

| 规则 | 阈值 | severity |
|------|------|----------|
| Low 占比 | ≥ 80% 训练时长 | info |
| Moderate 占比 | ≤ 10% 训练时长 | warning |
| High 占比 | ≤ 10% 训练时长 | warning |

```python
INTENSITY_POLICY = {
    "low_min": 0.80,       # ≥ 80%
    "moderate_max": 0.10,  # ≤ 10%
    "high_max": 0.10,      # ≤ 10%
}
```

强度判定规则：

| session_type | intensity | 说明 |
|-------------|-----------|------|
| rest / recovery_run / easy_run | Low | 恢复和基础有氧 |
| long_run（纯 Zone2） | Low | 默认长距离有氧 |
| tempo | Moderate | 节奏跑 |
| marathon_pace | Moderate | Zone3 专项配速跑 |
| intervals / strides / vo2max | High | 高强度间歇 |

与业界 80/20 极化训练原则一致，和 V2 基于心率数据的精确统计自然衔接。

> **V2**：改为基于实际心率数据的精确统计——使用 ParsedActivity.hr_zones（Zone1~5 占比）计算 80/20 极化分布和 Zone3 陷阱（Zone3 占比 ≤ 10%）。受控的 marathon_pace 不计入 Zone3 Trap：仅 goal=marathon 且 MP Session ≤1 次/周时豁免。替代当前的课型定性映射。

---

#### 4. Repair Engine（修复引擎）

接收 Constraint Checker 的违规列表，按 severity 排序后逐条修复。

**输入：**

```json
draft_plan + violations
```

**输出：**

```json
{
    "repaired": true,
    "attempts": 2,
    "changes": [
        {"session": "w03_thu_tempo", "from": "tempo", "to": "easy_run", "reason": "Hard 间隔不足"}
    ]
}
```

修复优先级：
1. critical → 立即修复
2. warning → 按序修复
3. info → 记录但不强制修复

修复策略：
- Hard 间隔不足 → 将相邻 Hard session 降级为 Easy
- Long Run 占比过高 → 缩减 Long Run 距离
- 周跑量增幅过大 → 等比例缩减 Easy run 距离
- 强度分布不达标 → 降级部分 Moderate/High session

---

#### 5. Debt Manager（债务管理器 V2）

记录未完成的关键训练，恢复后找机会补回。使系统具有**长期记忆**，而非每次分析完就结束。

**TrainingDebt 结构：**

```json
{
    "debt_id": "debt_20240601_threshold",
    "type": "threshold",
    "original_date": "2024-06-01",
    "missed_reason": "state_cns_fatigue",
    "priority": 2,
    "status": "pending",
    "expiry_date": "2024-06-08"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `debt_id` | `str` | 唯一标识 |
| `type` | `str` | 训练类型：`threshold` / `interval` / `long_run` / `tempo` |
| `original_date` | `str` | 原定日期 |
| `missed_reason` | `str` | 跳过的原因（Coach coaching_action 或 physiological_states） |
| `priority` | `int` | 1（最高）~ 3（最低） |
| `status` | `str` | `pending` / `scheduled` / `cleared` / `expired` |
| `expiry_date` | `str` | 债务有效期，过期自动 clear（避免无限期追债） |

**生命周期：**

```
训练被策略取消
    ↓
debt 登记 (status = pending)
    ↓
恢复后 Constraint Checker 放行
    ↓
Plan Modifier 安排 (status = scheduled)
    ↓
完成训练 → status = cleared
超时未还 → status = expired
```

**优先级规则：**

| priority | 条件 | 示例 |
|----------|------|------|
| 1 | 与比赛目标直接相关的 GoalPriority Session | marathon → Long Run |
| 2 | 重要的质量训练 | Threshold / Interval |
| 3 | 一般的质量训练 | Tempo / Strides |

---

#### 6. Forecast Engine（V3 预留）

基于更新后的训练计划，预测比赛成绩，分析目标可达性。

**输入：**

```json
updated_plan + user_goal + historical_data
```

**输出：**

```json
{
    "race_predictions": {
        "5km": "21:30",
        "10km": "45:00",
        "half_marathon": "1:42:00",
        "marathon": "3:45:00"
    },
    "goal_feasibility": {
        "target": "marathon_3:30",
        "feasible": false,
        "gap": "-15min",
        "advice": "当前训练负荷不足以支撑目标，建议周跑量从 45km 提升至 60km+"
    },
    "confidence": 0.72
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `race_predictions` | `dict` | 基于当前计划的各项比赛预测成绩 |
| `goal_feasibility` | `dict` | 目标可达性分析（能否达成 / 差距 / 建议） |
| `confidence` | `float` | 预测置信度（0.0 ~ 1.0），数据越多越高 |

**典型场景：**

```
用户目标：全马 3:30
当前计划周跑量：45km
预测全马：3:45

↓

差距：-15 分钟
建议：周跑量提升至 60km+，加入更多阈值训练
```

```
用户目标：半马 1:30
当前计划：周跑量 65km，含高质量 Interval + Tempo
预测半马：1:28

↓

目标可达 ✓
建议：保持当前节奏，赛前 2 周 taper
```

**预测逻辑参考：**

> 实际实现时可基于经典耐力运动公式（如 Riegel Formula、Daniels VDOT）结合用户历史 PB 和近期训练数据（配速、心率、跑量趋势）做加权推算，纯硬编码或轻量 ML 均可。V3 阶段优先保证可解释性（告诉用户为什么预测这个时间），而非追求模型精度。

---

#### Performance Limitation Analysis（V2）

负责识别和解决运动员的中长期能力短板，回答"为什么成绩上不去"：

- **Aerobic Base Deficiency**（有氧基础不足）
- **Threshold Limitation**（阈值能力限制）
- **Running Economy Limitation**（跑步经济性限制）
- **Technique Limitation**（跑姿技术限制）
- **Speed Reserve Limitation**（速度储备限制）

> 这些 Limitation 属于 Training Planner 的规划维度（未来 4~8 周），与 State Recognition Agent 识别的 Hidden Physiological State（当日状态根因）和 Decision Engine 的裁决（今日训练建议）天然分离：
>
> - **State Recognition** → 识别今天身体处于什么状态
> - **Decision Engine** → 决定今天怎么练
> - **Training Planner** → 规划未来 4~8 周怎么改进能力短板
>
> 三者可以同时为真、互不冲突，最终在同一份报告中呈现。

### 版本路线

| 版本 | 模块 | 目标 |
|------|------|------|
| **V1** | Policy Generator + Plan Modifier + Constraint Checker + Repair Engine | 核心链路跑通：Coach 裁决 → 策略 → 修改 → 约束校验 → 修复 → 课表更新 |
| **V2** | + Debt Manager | 加入长期训练记忆，实现债务生命周期管理 |
| **V3** | + Forecast Engine | 比赛成绩预测 + 目标可达性分析，从"训练分析器"升级为接近真实耐力运动教练系统 |

---

### 与现有 Agent 的关系

Training Planner Agent 在整个系统中的位置：

```
Data Agent
    ↓
Recovery Agent  ─┐
Load Agent      ─┤
Performance Agent ─┤  （Observation 观察层）
Risk Agent      ─┘
    ↓
Coach Agent     ───┘
    ↓
Training Planner Agent  ← （Intervention 干预层）
```

Coach Agent 回答"发生了什么"，Training Planner Agent 回答"未来怎么办"——两者配合构成完整的训练教练系统。