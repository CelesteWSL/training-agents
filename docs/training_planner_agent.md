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
    goal_priority:        bool      # Goal Prioritizer writes this; Repair Engine reads, does NOT re-derive
    priority_level:       int       # 1-3, written by Goal Prioritizer
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
        plan      = GoalPrioritizer.assign(policy, input.current_plan, input.user_goal)
        draft     = PlanModifier.modify(policy, plan, input.analysis_context)
        check     = ConstraintChecker.check_all(draft, input.analysis_context)
        repair    = RepairEngine.repair(draft, check.violations, input.analysis_context)
        changes   = diff(input.current_plan, repair.plan)
        debts     = DebtManager.register(changes)
        return PlannerOutput(repair.plan, changes, repair, debts)
```

流水线：**Policy Generator → Goal Prioritizer → Plan Modifier → Constraint Checker → Repair Engine → Final Plan**

职责分工：
- Policy Generator：生成训练调整策略
- Goal Prioritizer：标注 GoalPriority Session
- Plan Modifier：按策略修改课表（执行层）
- Constraint Checker：校验修改结果是否合规（验收层）
- Repair Engine：修复违规，以最小代价使计划合规（优化层）

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

#### 2. Goal Prioritizer（目标优先级标注）

遍历所有 session，根据 `user_goal` 标注"与比赛目标直接相关的质量训练"，将结果直接写入 session 的 `goal_priority` 和 `priority_level` 字段。

**输入：**

```json
current_plan + plan_metadata.goal
```

**输出：** 更新每个 session 的以下字段，不返回新数据结构：

| 字段 | 类型 | 说明 |
|------|------|------|
| `goal_priority` | `bool` | 该 session 是否为 GoalPriority session |
| `priority_level` | `int` | 1（最高，GoalPriority） / 2（quality session） / 3（easy/rest） |

**标注规则（Goal Prioritizer 内部实现，不对外暴露为 `GOAL_SESSION_MAP`）：**

- `session_type` 与 `user_goal` 匹配 → `goal_priority=true, priority_level=1`
  - marathon → long_run
  - half_marathon → marathon_pace
  - 10km / 5km → intervals
- 其他 quality session（tempo, intervals, threshold, strides）→ `goal_priority=false, priority_level=2`
- easy_run / recovery_run / rest → `goal_priority=false, priority_level=3`

> **关键设计决策：GoalPriority 由 Goal Prioritizer 写入 session 字段，下游模块（Plan Modifier、Constraint Checker、Repair Engine、Debt Manager）只读取 `goal_priority` / `priority_level`，不重新推导。** 这避免了"GoalPriority 识别规则变更时，Repair Engine 忘记同步"的双份逻辑风险。

---

#### 3. Plan Modifier（计划修改器）

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
Sun   Long Run 24km     ← 保留但减量 20%（Goal Prioritizer）
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
        "reason": "Policy: reduce_volume_ratio 0.2, Goal Prioritizer: Long Run ≤ 35%"
    }
]
```

---

#### 4. Constraint Checker（约束校验器）

专业度的核心来源。位于 Plan Modifier 之后，作为验收层——验证修改后的计划是否满足约束，不负责修改课表。

**内部结构：**

```
Constraint Checker
├── RecoveryConstraint    # priority 3（最高）
├── VolumeConstraint      # priority 2
└── IntensityConstraint   # priority 1
```

每个子约束实现统一的 BaseConstraint 接口：

```python
class BaseConstraint:
    def check(self, plan, context) -> ConstraintResult:
        """只发现问题，不修改计划。"""
        ...
class RecoveryConstraint(BaseConstraint):   ...
class VolumeConstraint(BaseConstraint):     ...
class IntensityConstraint(BaseConstraint):  ...

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
```json
{
    "passed": false,
    "score": 78,
    "violations": [
        {
            "constraint": "volume",
            "rule": "long_run_ratio",
            "severity": "warning",
            "repair": {"action": "reduce", "target": "long_run"},
            "target": {"week": 5, "session_id": "w05_sun_long_run"},
            "actual": 18.0,
            "limit": 14.0,
            "message": "Long Run 18km 占周跑量 45%，超出 35% 上限"
        },
        {
            "constraint": "recovery",
            "rule": "consecutive_hard_days",
            "severity": "critical",
            "repair": {"action": "downgrade", "target": "session"},
            "target": {"week": 5, "session_id": "w05_wed_tempo"},
            "actual": 2,
            "limit": 1,
            "message": "连续 Hard 天数 2，超出上限 1"
        }
    ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `passed` | bool | 所有子约束都通过才为 true |
| `score` | int | 计划健康度 0-100，从 100 开始按 violation 扣分：critical=-30, warning=-10, info=-2 |
| `violations` | list | 违规列表，按 (severity, constraint_priority) 降序排列 |
| `details` | dict | 分组保留各子约束结果（recovery/volume/intensity） |

**Violation 字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `constraint` | str | 所属约束：recovery / volume / intensity |
| `rule` | str | 违规规则标识 |
| `severity` | str | critical > warning > info，Repair Engine 按此排序处理 |
| `repair` | dict | 修复指令：`{"action": "downgrade", "target": "session"}` 等 |
| `target` | dict | 定位信息：week + session_id，Repair Engine 据此精确修改 |
| `actual` | float | 实际值 |
| `limit` | float | 阈值上限 |
| `message` | str | 人类可读描述 |

**repair action 集合：**

| action | target | 含义 |
|--------|--------|------|
| `downgrade` | `session` | 将当前 session 降级（hard→moderate, moderate→easy） |
| `reduce` | `long_run` | 缩减 Long Run 距离 |
| `reduce` | `volume` | 等比例缩减 easy run 距离 |
| `move` | `session` | 将 session 移到其他日期 |
| `remove` | `secondary_quality` | 删除 secondary_quality slot |

```python
repair = violation["repair"]
handler = REPAIR_HANDLERS[repair["action"]]
handler(plan, violation["target"], repair)
```

---

**score 计算与用途：**

```python
SEVERITY_SCORE = {"critical": -30, "warning": -10, "info": -2}

score = 100 + sum(SEVERITY_SCORE[v["severity"]] for v in violations)
score = max(0, score)
```

用途：
1. **Report Generator**：`Training Plan Quality: 78/100`，一眼看出计划质量
2. **Repair Engine early stop**：`if score >= 95: return` 跳过微调
3. **V2 趋势图**：连续多日 score 可绘制训练计划健康度曲线

**汇总逻辑：**

```python
def check_all(plan, context) -> ConstraintCheckerResult:
    details = {
        "recovery":  recovery_constraint.check(plan, context),
        "volume":    volume_constraint.check(plan, context),
        "intensity": intensity_constraint.check(plan, context),
    }
    violations = sorted(
        [v for r in details.values() for v in r.violations],
        key=lambda v: (SEVERITY_ORDER[v["severity"]], CONSTRAINT_PRIORITY[v["constraint"]]),
        reverse=True,
    )
    score = 100 + sum(SEVERITY_SCORE[v["severity"]] for v in violations)
    score = max(0, score)

    return ConstraintCheckerResult(
        passed=all(r.passed for r in details.values()),
        score=score,
        violations=violations,
        details=details,
    )
```

- `passed`：所有子约束都通过才为 true
- `score`：从 100 递减，按 violation severity 扣分
- `violations`：合并排序后的违规列表
- `details`：分组保留各子约束结果，后续 Report Generator 和 Repair Engine 均可复用

---

**子约束优先级：**

```python
SEVERITY_ORDER = {"critical": 3, "warning": 2, "info": 1}

CONSTRAINT_PRIORITY = {
    "recovery": 3,
    "volume": 2,
    "intensity": 1,
}
```

Recovery 优先级最高（恢复永远第一），Intensity 最低。


---


##### RecoveryConstraint（恢复约束）

| 规则 | 阈值 | severity | repair |
|------|------|----------|-------------|
| 连续 Hard 天数 | ≤ `max_consecutive_hard`（默认 1） | critical | `downgrade_session` |
| 3 日滚动负荷 | ≤ `rolling_3day_load_max`（默认 6） | warning | `downgrade_session` |

```python
LOAD_SCORE = {"rest": 0, "easy": 1, "moderate": 2, "hard": 3}

RECOVERY_POLICY = {
    "max_consecutive_hard": 1,
    "rolling_3day_load_max": 6,
}
```

`is_hard(session)` 统一使用 `session.intensity` 判定——不依赖 `session_type`。

- `intensity == "hard"` → LOAD_SCORE 3
- `intensity == "moderate"` → LOAD_SCORE 2
- `intensity == "easy"` → LOAD_SCORE 1
- `intensity == "rest"` → LOAD_SCORE 0

Long Run 默认 easy，但若含 MP/Tempo 段则 `intensity` 按实际判定。

**rolling_3day_load 规则**：任意连续 3 天的 LOAD_SCORE 总和超过阈值即违例。解决 `hard → moderate → hard` 模式漏检问题（moderate 本身有训练负荷，隔在中间不代表充分恢复）。

- `hard(3) + rest(0) + hard(3) = 6` → 通过
- `hard(3) + easy(1) + hard(3) = 7` → **违例**
- `hard(3) + moderate(2) + hard(3) = 8` → **违例**

两项阈值均可由 SRA 动态调节。例如 `cns_fatigue` 时 `max_consecutive_hard = 0`、`rolling_3day_load_max = 4`。

违例输出：

```json
{
  "rule": "consecutive_hard_days",
  "actual": 2,
  "limit": 1,
  "repair": {"action": "downgrade", "target": "session"}
}
```

```json
{
  "rule": "rolling_3day_load",
  "actual": 8,
  "limit": 6,
  "repair": {"action": "downgrade", "target": "session"}
}
```


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

按 **训练时长（training_minutes）** 统计，而非训练天数。阈值随训练阶段（phase）动态调整：

```python
INTENSITY_POLICY = {
    "base": {
        "low_min": 0.80,
        "moderate_max": 0.10,
        "high_max": 0.10,
    },
    "build": {
        "low_min": 0.75,
        "moderate_max": 0.15,
        "high_max": 0.10,
    },
    "peak": {
        "low_min": 0.80,
        "moderate_max": 0.18,
        "high_max": 0.05,
    },
    "taper": {
        "low_min": 0.85,
        "moderate_max": 0.10,
        "high_max": 0.05,
    },
}
```

校验时根据 `context.training_phase` 动态读取对应 phase 的阈值，而非固定 80/20。

强度判定规则（统一使用 `session.intensity`，不依赖 `session_type`）：

| session_type | intensity | 说明 |
| rest / recovery_run / easy_run | rest / easy | 恢复和基础有氧 |
| long_run（纯 Zone2） | easy | 默认长距离有氧 |
| long_run（含 MP / Tempo 段） | moderate | 按实际配速段判定 |
| tempo | moderate | 节奏跑 |
| marathon_pace | moderate | Zone3 专项配速跑 |
| intervals / strides / vo2max | hard | 高强度间歇 |
| intervals / strides / vo2max | High | 高强度间歇 |

> **V2**：改为基于实际心率数据的精确统计——使用 ParsedActivity.hr_zones（Zone1~5 占比）计算极化分布和 Zone3 陷阱（Zone3 占比 ≤ 10%）。受控的 marathon_pace 不计入 Zone3 Trap：仅 goal=marathon 且 MP Session ≤1 次/周时豁免。替代当前的课型定性映射。

#### 5. Repair Engine（修复引擎）

职责：

> 根据 Constraint Checker 的违规结果，以最小代价（Minimal Change）修复训练计划，同时最大程度保留 GoalPriority Session。

位于 Constraint Checker 之后，作为优化层。是整个 Planning System 的核心壁垒——前面的模块都在"看懂"和"修改"，只有 Repair Engine 在"优化"。

**核心设计原则：**

> **Repair Engine 永远追求 Minimal Change（最小改动原则），而不是把违规计划修成一个全新的计划。**

这是专业训练软件（TrainingPeaks、Final Surge、Runna 等）的核心思想——用户昨天刚安排好的课表，今天 AI 一修整个星期都变了，体验会很差。

---

##### 内部结构

```
Repair Engine
├── Violation Grouper     → 聚合违规，识别共享根因
├── Action Generator     → 生成候选修复动作
├── Action Evaluator     → Dry Run 模拟 + 打分，选最优
├── Plan Applier         → 执行修复
└── Validation Loop      → 重新校验并迭代
```

##### 输入

```json
draft_plan + violations + analysis_context
```

> Repair Engine 不需要 `user_goal`——Goal Prioritizer 已将目标编码为 `session.goal_priority` 和 `session.priority_level`。Repair Engine 只读取这些字段，不关心"marathon"或"5km"等业务概念。

##### 输出

```json
{
  "repaired": true,
  "attempts": 2,
  "final_score": 95,
  "remaining_violations": [],
  "changes": [
    {
      "action": "move_session",
      "session_id": "w03_thu_tempo",
      "from": "thu",
      "to": "fri",
      "reason": "Hard gap violation",
      "cost": 1
    },
    {
      "action": "reduce_distance",
      "session_id": "w03_sun_long_run",
      "from": 20,
      "to": 18,
      "reason": "Long run ratio",
      "cost": 1
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `repaired` | `bool` | 是否完成修复（可能仍有 remaining_violations） |
| `attempts` | `int` | 实际修复迭代次数 |
| `final_score` | `int` | 修复后的 Constraint Checker 健康度评分（0-100） |
| `remaining_violations` | `list` | 修复后仍存在的违规（为空才说明完全修复） |
| `changes` | `List[RepairChange]` | 每次修复的详细记录，含 action / cost |

---

##### Violation Resolver（违规排序器）

负责决定先修什么，后修什么。

输入 violations，按以下优先级排序（从高到低）：

```text
severity（critical > warning > info）
    ↓
constraint_priority（recovery > volume > intensity）
    ↓
goal_priority（GoalPriority session 的违规降序处理，尽量不碰）
```

例如：

```text
critical recovery 违规 → 最先修
warning volume 违规   → 其次
warning intensity 违规 → 最后
```

其中 GoalPriority session 的违规在同等 severity 下排到最后——这保证了 Repair Engine 优先修改非关键的 session。

```python
SEVERITY_ORDER = {"critical": 3, "warning": 2, "info": 1}

CONSTRAINT_PRIORITY = {
    "recovery": 3,
    "volume": 2,
    "intensity": 1,
}
```

---

##### Action Generator（动作生成器）

根据 violation 生成候选修复动作。核心思想：**同一违规有多种修法，按 cost 择优——这是专业度的来源。**

**统一接口：**

```python
class BaseRepairAction:
    def simulate(self, plan, violation, context) -> dict | None:
        """模拟修复，返回 {"plan": candidate_plan, "cost": int}。失败返回 None。不修改原 plan。"""
        ...

    def apply(self, plan) -> dict:
        """将 simulate 产出的 candidate_plan 写入原 plan。永不失败（simulate 已验证通过）。"""
        ...

**5 种具体修复动作：**

| Action | Cost | 含义 |
|--------|------|------|
| `MoveSessionAction` | 1 | 将 session 移到邻近空闲 slot，不顺延后续 session |
| `ReduceDistanceAction` | 1 | 缩减距离 |
| `DowngradeSessionAction` | 2 | 降级强度（hard→moderate, moderate→easy, easy→rest） |
| `InsertRestAction` | 3 | 在两个 session 之间插入 rest day |
| `RemoveSessionAction` | 5 | 删除非核心 session |

**REPAIR_POLICY（约束类别 → 候选修复动作）：**

不与具体 rule 耦合。新增 rule 只需归属到对应 constraint 类别，自动继承该类的修复动作列表。

```python
REPAIR_POLICY = {
    "recovery": [
        MoveSessionAction(),
        DowngradeSessionAction(),
        InsertRestAction(),
        RemoveSessionAction(),
    ],
    "volume": [
        ReduceDistanceAction(),
    ],
    "intensity": [
        DowngradeSessionAction(),
    ],
}
```

Action Generator 按 violation 的 `constraint` 字段查找：

```python
candidates = REPAIR_POLICY[violation.constraint]
```

##### Action Evaluator（动作评估器）与 Dry Run

不直接 apply。先对所有候选动作做 Dry Run（`simulate`），逐个打分，再 apply 最优：

```text
Violation
    ↓
MoveSession     → simulate → score=96
    ↓
DowngradeSession → simulate → score=92
    ↓
InsertRest      → simulate → score=88
    ↓
RemoveSession   → simulate → score=85
    ↓
Action Evaluator 选最高分
    ↓
Apply MoveSession（唯一一次真实写入）
```

```python
score = (
    constraint_score      # Constraint Checker 评估 candidate_plan
    - repair_cost         # 动作自身 cost
    - goal_penalty        # GOAL_PENALTY[priority_level]
)
```

| 候选动作 | constraint_score | cost | goal_penalty | **总分** |
|----------|:---:|:---:|:---:|:---:|
| MoveSession | 96 | -1 | 0 | **95** |
| DowngradeSession | 95 | -2 | 0 | 93 |
| InsertRest | 93 | -3 | 0 | 90 |

选出总分最高的 MoveSession → `apply()`。

> Dry Run 是专业训练软件和业余脚本的分水岭——不是在纸上猜测哪个动作好，而是真的跑一遍 constraint check 看结果。

例如新增 `zone3_trap` 规则，归属 `intensity` 类别，自动获得 `DowngradeSessionAction`，无需修改任何 registry：

```python
# Constraint Checker 侧：
{
    "constraint": "intensity",
    "rule": "zone3_trap",
    ...
}

# Repair Engine 侧：零改动，自动通过 REPAIR_POLICY["intensity"] 拿到 DowngradeSessionAction
```

所有候选动作均做 simulate → score → 选最高分 → apply，而非按序取第一个成功。这确保改动最小且效果最好。

**设计示例——连续 Hard 违规的多种修法：**

原计划：

```
Mon easy  |  Tue intervals  |  Wed tempo  |  Thu rest   |  Fri long_run
```

违规：Tue intervals + Wed tempo 连续 Hard。

| 方案 | 动作 | 结果 | Cost | Score |
|------|------|------|------|:---:|
| **方案1（推荐）** | MoveSession | Wed tempo → Thu（空闲 slot），不触动其他 session | 1 | **95** |
| 方案2 | DowngradeSession | Wed tempo → easy | 2 | 93 |
| 方案3 | InsertRest | Wed 插入 rest，后续顺延 | 3 | 90 |

Action Generator 自动选择方案1。

---

##### Goal Priority Penalty（目标优先级惩罚）

GoalPriority session 由 **Goal Prioritizer 预先标注**：解析时直接读取 session 的 `goal_priority` 字段，**不重新推导**。

```python
GOAL_PENALTY = {
    1: 100,   # primary: marathon→long_run, 5km→intervals 等
    2: 50,    # secondary: 其他 quality session (tempo, intervals, threshold, strides)
    3: 0,     # normal: easy_run, recovery_run, rest
}
```

代价计算：

```python
cost += GOAL_PENALTY[session.priority_level]
```

例如：
- 删除 easy_run（priority_level=3）→ cost = 5 + 0 = 5
- 删除 tempo（priority_level=2）→ cost = 5 + 50 = 55
- 删除 long_run（priority_level=1）→ cost = 5 + 100 = 105


##### GoalPriority Override（目标优先级覆盖）

不需 `OVERRIDE_POLICY` 等显式规则。Action Evaluator 通过 **自然降级（Natural Fallthrough）** 处理：

```text
Move session       → simulate → 可行 ✓ (score 最高)
    ↓ 若 simulate 返回 None
Downgrade session  → simulate → 可行 ✓
    ↓ 若 simulate 返回 None
Insert rest        → simulate → 可行 ✓
    ↓ 若 simulate 返回 None
Remove non-goal_priority session → simulate → 可行 ✓
    ↓ 若所有候选均不可行
Remove goal_priority session → GOAL_PENALTY=100, 但仍可能是唯一解
```

核心机制：

- `GOAL_PENALTY[priority_level]` 让修改 GoalPriority session 的 score 大幅降低
- Action Evaluator 自然选最高分 → 低 cost 动作天然优先
- 只有当所有低 cost 方案的 `simulate()` 均返回 `None`（无法执行）时，高 penalty 方案才成为默认赢家

> 不把 `full_rest` 写死为触发条件，也不把 `critical` severity 作为开关。**是否触碰 GoalPriority，由 simulate → score 的结果决定，而非预先声明的规则。**
> **为何不在 Repair Engine 内重复 GoalPriority 推导：** GoalPriority 的识别逻辑可能随时间变化（如 marathon 将来引入 `marathon_pace` 作为并列 GoalPriority），若 Repair Engine 独立维护一份映射表，极易在升级时遗漏同步，产生 bug。正确的做法是 Goal Prioritizer 一次性写入 `goal_priority`，Repair Engine 仅读取。

---

##### Plan Applier（计划应用器）

对 Action Evaluator 选出的最优动作（附带 simulate 产出的 `candidate_plan`），修改对应的 `DailySession`：

| 动作 | 修改内容 |
|------|----------|
| MoveSessionAction | 改 `date` / `day_of_week` / `session_id`，仅改目标 session，不顺延 |
| DowngradeSessionAction | 改 `session_type` / `intensity` / `hr_zone` / `description` |
| ReduceDistanceAction | 改 `target_distance_km` / `duration_min` |
| InsertRestAction | 插入 Rest session（`session_type="rest", intensity="rest"`），后续顺延 |
| RemoveSessionAction | 从 `sessions` 列表中移除 |

Applier 不负责跨周操作——只修改 violation.target 所指向的 `WeeklyBlock`。

---

##### Violation Grouping（违规聚合）

单次循环修一条 violation 太保守，会产生大量重复计算。多个违规往往共享同一根因——同一个 session 可能同时触发 `consecutive_hard_days` 和 `rolling_3day_load`。

先按 `group_key` 聚合：

```python
def group_violations(violations: List[Violation]) -> Dict[str, List[Violation]]:
    groups = {}
    for v in violations:
        # group_key = 违规指向的 session + 周
        key = f"{v.target.week}_{v.target.session_id}"
        groups.setdefault(key, []).append(v)
    return groups
```

示例：

```
Mon intervals → consecutive_hard_days (warning)
Tue tempo      → consecutive_hard_days (warning)
Wed intervals  → consecutive_hard_days (critical)
               + rolling_3day_load    (warning)
```

聚合后：

| group_key | sessions | violations | top_severity |
|-----------|----------|------------|-------------|
| `w03_mon_intervals` | 1 | `consecutive_hard_days` | warning |
| `w03_tue_tempo` | 1 | `consecutive_hard_days` | warning |
| `w03_wed_intervals` | 1 | `consecutive_hard_days, rolling_3day_load` | **critical** |

按 `top_severity` 排序，先修 `w03_wed_intervals`。一次 move/downgrade 同时解决两个违规。

---

##### Validation Loop（验证闭环）

每次迭代修复**一个 group**（而非一条 violation），修完重新校验，形成闭环：

```text
Constraint Checker
    ↓
Violation Grouping（聚合违规）
    ↓
Repair Engine (修复最高优先级 group)
    ↓
Constraint Checker（重新校验）
    ↓
仍有违规且 attempts < max_attempts？
    ↓ YES → 重新 Grouping，再修一组
    ↓ NO  → 返回结果
```

停止条件（满足任一即停止）：

```python
check.passed == True       # 无违规
score >= 95                # 健康度达标，跳过微调
attempts >= max_attempts   # 达到上限（默认 3）
```

```python
MAX_ATTEMPTS = 3
```

**典型场景——一次修一组：**

```
原计划违约：Mon intervals + Tue tempo + Wed intervals
    → consecutive_hard_days (Mon, Tue, Wed 各一条)
    → rolling_3day_load  (Mon-Wed 一条)
    ↓
Grouping: w03_wed_intervals = [consecutive_hard_days(critical), rolling_3day_load(warning)]
    ↓
修复：move Wed intervals → Thu（一次动作同时消两条违规）
    ↓
重新校验：consecutive_hard_days 全部清除
    ↓
通过 ✓
```

---
##### Repair Engine 主入口

```python
class RepairEngine:
    @staticmethod
    def repair(
        draft_plan: dict,
        violations: List[dict],
        context: dict,
        max_attempts: int = 3,
    ) -> RepairResult:
        """修复训练计划中的约束违规。

        1. Violation Grouper  → 聚合违规，按 group 排序
        2. 逐组修复（Validation Loop）：
           a. Action Generator → 生成候选动作
           b. Action Evaluator → Dry Run 模拟 + 打分，选最优
           c. Plan Applier → 执行最优动作
           d. Constraint Checker → 重新校验
        3. 返回 RepairResult
        """
        ...

class RepairResult(TypedDict):
    repaired: bool
    attempts: int
    final_score: int
    changes: List[RepairChange]
    remaining_violations: List[dict]

class RepairChange(TypedDict):
    action: str              # "move_session" / "downgrade_session" / ...
    session_id: str          # 被修改的 session
    from: Any                # 修改前的值
    to: Any                  # 修改后的值
    reason: str              # 修复原因
    cost: int                # 修复代价
```

---

#### 6. Debt Manager（债务管理器 V2）
#### 6. Debt Manager（债务管理器 V2）
#### 6. Debt Manager（债务管理器 V2）

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

#### 7. Forecast Engine（V3 预留）

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

#### 8. Performance Limitation Analysis（V2）

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
