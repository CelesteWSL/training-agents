# Training Agents — 多智能体训练分析系统

## 一、自动输入（来自 TCX，后期扩展 FIT / GPX）

无需用户手动输入。

------

### 基础训练数据

- 时间
- 距离
- 时长
- 海拔
- 速度（瞬时 m/s，来自 trackpoint）

------

### 心率数据

- 平均心率
- 最大心率
- 心率曲线

------

### 跑步技术数据（设备支持时）

- 步频 Cadence
- 步幅 Stride Length
- 触地时间 GCT
- 垂直振幅 VO
- 左右平衡
- 垂直步幅比 Vertical Ratio

------

### 骑行数据（后期）

- 功率 Power
- FTP
- 踏频
- NP
- IF

------

## 二、用户轻量输入

建议只保留这几个。

------

### 每次训练

#### RPE（必须）

```text
1~10
```

主观疲劳感知。

------

#### Muscle Soreness（推荐）

```text
0~5
```

肌肉酸痛程度。

------

## 三、每日输入

------

### Morning Resting HR

```text
晨间静息心率
```

一个数字即可。

------

### Energy Level（可选）

```text
1~5
```

精神状态。

------

## 四、用户基础画像（首次填写）

只填一次。

------

### 基础信息

- 年龄
- 性别
- 身高
- 体重

------

### 运动目标

例如：

- 5km
- 10km
- half_marathon
- marathon

------

### 训练水平

例如：

- 新手
- 进阶
- 高级

------

### 历史 PB（推荐）

例如：

- 5km
- 10km
- 半马
- 全马

------

### 历史伤病位置

例如：

- 膝盖
- 跟腱
- 足底筋膜
- 髋关节
- 胫骨 / 应力

------

## 五、分析 Agent

### Data Agent

#### 职责边界

Data Agent 负责**解析 TCX 文件 → 结构化数据 + 读取历史数据**。

```
TCX File → parse_tcx() → ParsedActivity + HistoryContext
```

**做这些：**
- 解析 TCX 文件（当前版本；后续扩展 FIT/GPX）
- 提取所有设备数据：运动类型、时间、距离、心率、海拔、步频、速度
- 提取跑步动态数据（设备支持时）：触地时间、垂直振幅、左右平衡、垂直步幅比
- 计算可直接推导的指标：配速、步幅、心率分区、心率飘逸
- 通过 HistoryReader 读取往期训练数据 + 每日 checkin，注入 history 字段

**不做这些：**
- 教练建议、恢复分析、风险预测、趋势判断（属于其他 Agent）
- 用户画像处理、用户手动输入（属于 User Profile / User Input）

---

#### 输入

| 来源 | 内容 |
|------|------|
| `state.activity_file` | TCX 文件路径 |
| `state.user_profile` | 用户基础画像（age、max_hr 等） |
| `state.date` | 训练日期 |

---

#### 输出：ParsedActivity

与 `agent_states.py` 中 `ParsedActivity` TypedDict 完全对齐。

##### Activity 汇总

| 字段 | 类型 | 说明 |
|------|------|------|
| `sport` | str | 运动类型（Running / Cycling / Swimming） |
| `start_time` | str | ISO 8601 开始时间 |
| `total_distance` | float | 总距离（米） |
| `total_duration` | float | 总时长（秒） |
| `avg_pace` | str | 平均配速 `"m:ss/km"` |
| `avg_hr` | int | 平均心率（bpm） |
| `max_hr` | int | 最大心率（bpm） |
| `hr_drift` | float | 心率飘逸（%），前后半段心率变化 |
| `total_ascent` | float | 累计爬升（米） |
| `total_descent` | float | 累计下降（米） |

##### 心率分区

| 字段 | 类型 | 说明 |
|------|------|------|
| `hr_zones` | dict | `{"zone1": 0.11, "zone2": 0.15, ...}`，基于 trackpoint HR ÷ max_hr |
| `max_hr` 来源 | | 用户设置 → `max_hr` → `220 - age` 兜底 |

##### Lap 分段

`laps: List[LapSummary]`

| 字段 | 类型 | 说明 |
|------|------|------|
| `index` | int | Lap 序号 |
| `distance_m` | float | 距离（米） |
| `duration_s` | float | 时长（秒） |
| `avg_hr` | int | 平均心率 |
| `max_hr` | int | 最大心率 |
| `avg_pace` | str | 配速 |
| `avg_cadence` | float \| null | 步频 |

---

### Recovery Agent

#### 职责边界

Recovery Agent 负责评估训练后的**身体恢复状态**，回答「今天能练吗」。

核心指标：
- **Recovery Score**（恢复评分 0-100）
- **Resting HR Deviation**（晨间静息心率偏离基线）
- **Fatigue Trend**（疲劳趋势：dissipating / stable / accumulating）
- **Recovery Debt**（恢复负债）
- **HR Drift**（心率飘逸）
- **Consecutive Hard Days**（连续高强度天数）

---

#### 输入

| 来源 | 内容 |
|------|------|
| `state.parsed_activity` | 当日训练数据（hr_drift、total_duration） |
| `state.history` | HistoryReader 预读的 daily_checkins + training_sessions |
| `state.morning_hr` | 当日晨间静息心率 |
| `state.rpe` | 主观疲劳 1-10 |
| `state.muscle_soreness` | 肌肉酸痛 0-5 |

---

#### 输出：RecoveryReport

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | str | `good` / `warning` / `critical` |
| `recovery_score` | int | 恢复评分 0-100 |
| `fatigue_trend` | str | `dissipating` / `stable` / `accumulating` |
| `resting_hr_deviation` | int | 静息心率偏离基线值（bpm） |
| `hr_drift` | float | 当日心率飘逸（%） |
| `recovery_debt` | float | 恢复负债累计值 |
| `recovery_debt_trend` | str | 负债趋势 |
| `consecutive_hard_days` | int | 连续高强度天数 |
| `summary` | str | LLM 生成的 2-4 句恢复评估 |

---

#### 触发 RAG 条件

- 静息心率偏离基线 > 5bpm
- Recovery Score < 50

---

### Training Load Agent

#### 职责边界

Training Load Agent 负责评估**训练负荷是否合理**，回答「练得够不够、有没有过度」。

核心指标：
- **ACWR**（急慢性负荷比）
- **Ramp Rate**（周负荷变化率）
- **Monotony**（训练单调性）
- **Strain**（训练压力）

---

#### 输入

| 来源 | 内容 |
|------|------|
| `state.parsed_activity` | 当日训练数据（total_distance、total_duration） |
| `state.history` | HistoryReader 预读的 28 天训练数据 |
| `state.user_profile` | 训练水平（新手/进阶/高级） |

---

#### 输出：LoadReport

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | str | `optimal` / `warning` / `critical` |
| `acwr` | float | 急慢性负荷比 |
| `acwr_status` | str | ACWR 状态描述 |
| `ramp_rate` | float | 周负荷变化率 |
| `chronic_load` | float | 慢性负荷（4 周均值） |
| `acute_load` | float | 急性负荷（1 周） |
| `monotony` | float | 训练单调性 |
| `strain` | float | 训练压力 |
| `summary` | str | LLM 生成的 2-4 句负荷评估 |

---

#### 触发 RAG 条件

- ACWR > 1.5 或 < 0.8
- Ramp Rate > 0.15

---

### Performance Agent

#### 职责边界

Performance Agent 负责评估**训练效果和效率**，回答「练得有没有进步」。

核心指标：
- **Efficiency Factor**（效率因子：配速/心率比）
- **Aerobic Efficiency**（有氧效率）
- **Pace-HR Decoupling**（配速-心率解耦率）
- **Zone Distribution**（心率区间分布）
- **Target Alignment**（训练结构与目标匹配度）
- **Technique Flags**（技术问题标记）

---

#### 输入

| 来源 | 内容 |
|------|------|
| `state.parsed_activity` | 当日训练数据（avg_pace、avg_hr、hr_zones、hr_drift） |
| `state.history` | HistoryReader 预读的 10 天训练数据 |
| `state.user_profile` | 运动目标（goal） |

---

#### 输出：PerformanceReport

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | str | `improving` / `stable` / `declining` |
| `efficiency_factor` | float | 效率因子 |
| `efficiency_trend` | str | 效率趋势 |
| `efficiency_history` | list | 近 10 天效率因子历史 |
| `aerobic_efficiency` | float | 有氧效率 |
| `aerobic_trend` | str | 有氧效率趋势 |
| `pace_hr_decoupling` | float | 配速-心率解耦率（%） |
| `decoupling_status` | str | 解耦状态 |
| `zone_distribution` | dict | 心率五区分布 |
| `target_alignment` | str | 训练与目标匹配度：`on_track` / `mismatch` / `insufficient_data` |
| `technique_flags` | list | 技术问题列表 |
| `summary` | str | LLM 生成的 2-4 句表现评估 |

---

#### 触发 RAG 条件

- Pace-HR Decoupling > 10%
- Zone2 占比偏离目标

---

### Risk Agent

#### 职责边界

Risk Agent 负责评估**伤病风险**，回答「会不会受伤」。

核心指标：
- **Injury Risk Score**（伤病风险评分 0-100）
- **Risk Factors**（风险因子列表）
- **Alerts**（警报）

---

#### 输入

| 来源 | 内容 |
|------|------|
| `state.parsed_activity` | 当日训练数据 |
| `state.history` | HistoryReader 预读的 7 天训练 + checkin 数据 |
| `state.user_profile` | 历史伤病位置 |
| `state.rpe` | 主观疲劳 |
| `state.muscle_soreness` | 肌肉酸痛 |

---

#### 输出：RiskReport

| 字段 | 类型 | 说明 |
|------|------|------|
| `risk_level` | str | `low` / `moderate` / `high` / `critical` |
| `injury_risk_score` | int | 伤病风险评分 0-100 |
| `risk_factors` | List[str] | 激活的风险因子 |
| `alerts` | List[str] | 警报信息 |
| `summary` | str | LLM 生成的 2-4 句风险评估 |

---

#### 触发 RAG 条件

- Injury Risk > 60
- Recovery Debt 持续上升

---

### State Recognition Agent

#### 职责边界

State Recognition Agent 负责**识别隐藏的生理状态**，是纯规则引擎（不调用 LLM）。它综合四个 Analyst 的输出，匹配已知的生理状态模式。

识别状态：

| 状态 | severity | 含义 |
|------|----------|------|
| `injury_onset_pattern` | 100 | 伤病前兆模式 |
| `non_functional_overreaching` | 90 | 非功能性过度训练 |
| `cns_fatigue` | 80 | 中枢神经疲劳 |
| `cardiovascular_strain` | 70 | 心血管压力 |
| `muscular_fatigue` | 60 | 肌肉疲劳 |
| `functional_overreaching` | 50 | 功能性过度训练 |

---

#### 输入

| 来源 | 内容 |
|------|------|
| `state.recovery_report` | Recovery Agent 输出 |
| `state.load_report` | Load Agent 输出 |
| `state.performance_report` | Performance Agent 输出 |
| `state.risk_report` | Risk Agent 输出 |
| `state.rpe` | 主观疲劳 |
| `state.muscle_soreness` | 肌肉酸痛 |

---

#### 输出：StateRecognitionResult

| 字段 | 类型 | 说明 |
|------|------|------|
| `physiological_states` | list | 匹配到的生理状态列表 |
| `primary_state` | dict | 最高 severity 的状态（用于 Gate 调节） |

---

### Coach Agent（Decision Engine + Report Generator）

#### 职责边界

Coach Agent 是系统的**最终决策层**，分为两个子模块：

1. **Decision Engine**（纯规则引擎）：根据上游分析结果做训练裁决
2. **Report Generator**（LLM）：生成面向用户的完整训练报告

---

#### Decision Engine

##### Waterfall Gate 评估

按优先级串联评估，先触发的 Gate 决定最终裁决：

| 优先级 | Gate | 触发条件 | 动作 |
|--------|------|---------|------|
| 1 | Safety | 伤病风险 critical | full_rest |
| 2 | Recovery | Recovery Score < 40 或 HR Drift > 10% | recovery_run |
| 3 | Load | ACWR > 1.5 或 Ramp Rate > 0.2 | reduce_load |
| 4 | Quality | 所有指标良好 | quality_session |
| 5 | Default | — | normal_training |

##### State Modifier

State Recognition 识别到的生理状态会调节 Gate 阈值：

| 状态 | 调节 |
|------|------|
| cns_fatigue | recovery_score_low: 40→55, consecutive_hard_days_limit: 3→2 |
| cardiovascular_strain | hr_drift_high: 10→8 |
| non_functional_overreaching | acwr_high: 1.5→1.2, action_override: full_rest |

##### RulingResult 输出

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | `full_rest` / `recovery_run` / `reduce_load` / `quality_session` / `normal_training` |
| `status` | str | `critical` / `warning` / `good` |
| `verdict` | str | 人类可读裁决描述 |
| `modifiers` | list | 技术修饰器（如步频练习、触地时间练习） |

---

#### Report Generator

Decision Engine 裁决后，Report Generator 调用 LLM 生成最终报告。

**输入：** 四个 Analyst 报告 + State Recognition 结果 + Decision Engine 裁决

**输出：FinalReport**

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | str | 报告日期 |
| `recommendation` | RulingResult | Decision Engine 裁决结果 |
| `special_event` | Optional[SpecialEvent] | 特殊事件，无则为 null |
| `markdown` | str | LLM 直出的完整 Markdown 报告 |

**设计原则：**
- 报告只生成一次，不是四个 Agent 各自写各自的
- 教练裁决先行（硬编码确定框架），LLM 再填入具体分析
- 四个 Analyst 报告 + State Recognition 作为 LLM 的输入材料
- LLM 在 prompt 指导下合成一份结构完整、逻辑自洽的教练评语

---

## 六、RAG

### 概述

RAG 知识库为 Recovery Agent、Training Load Agent、Performance Agent、Risk Agent 提供专业运动科学知识支持。Data Agent 不使用 RAG（仅做数据解析）。

---

### 知识库

| 书籍 | 知识域 | 对应 Agent | 语言 |
|------|--------|-----------|------|
| 《丹尼尔斯经典跑步训练法》Jack Daniels | `training_load` | Training Load Agent | 英文/中文 |
| 《无伤跑法》戴剑松 | `recovery`、`risk` | Recovery Agent、Risk Agent | 中文 |
| 《80/20 Running》Matt Fitzgerald | `performance` | Performance Agent | 英文 |

每条入库数据附带元数据标记 `book`、`chapter`、`domain`，供检索时过滤。

---

### 技术栈

| 组件 | 用途 |
|------|------|
| **Unstructured** | PDF 解析，按标题层级自动切片，保留文档结构 |
| **LlamaIndex** | 子切片编排、索引管理、查询引擎 |
| **Milvus** | 混合向量库（稠密语义向量 + 稀疏 BM25 关键词向量） |
| **BGE-M3** | Embedding 模型，中英文通吃，1024 维，本地部署 |
| **BGE-Reranker-v2-m3** | 检索后二次排序，Top-20 → Top-5 |

---

### 核心策略

#### 1. 层级切片（Parent-Child Chunking）

```
父块 (Parent, 1024 tokens)  保证上下文完整
  ├── 子块 1 (256 tokens)   用于向量检索
  ├── 子块 2 (256 tokens)   用于向量检索
  ├── 子块 3 (256 tokens)   用于向量检索
  └── 子块 4 (256 tokens)   用于向量检索
```

检索命中子块 → 返回对应父块 → Agent 拿到完整上下文。

#### 2. 混合检索（语义 + 关键词）

| 检索方式 | 解决问题 |
|----------|----------|
| 稠密向量（语义） | 「跑步后心率恢复慢怎么办」→ 匹配到恢复相关段落 |
| 稀疏向量（BM25 关键词） | 「ACWR」→ 精确命中含此术语的段落 |

Milvus 2.4+ 原生支持混合检索，一次查询同时走两条通路。

#### 3. 元数据过滤

每个 Agent 查询时只搜自己域，砍掉 75% 无关数据。

| Agent | 检索 domain |
|-------|------------|
| Recovery Agent | `recovery` |
| Training Load Agent | `training_load` |
| Performance Agent | `performance` |
| Risk Agent | `recovery`、`risk` |

#### 4. Rerank 二次排序

粗筛 20 条 → BGE-Reranker 精排 → 返回 Top-5 条，足够 Agent 做判断，不撑爆上下文窗口。

---

### Agent 触发 RAG 的场景

| Agent | 触发条件 | 检索目标 |
|-------|----------|----------|
| **Recovery** | 静息心率偏离基线 > 5bpm | 静息心率升高与恢复不足的关联 |
| | Recovery Score < 50 | 低恢复评分下的训练调整建议 |
| **Training Load** | ACWR > 1.5 或 < 0.8 | ACWR 偏离最优区间的风险 |
| | Ramp Rate > 0.15 | 周负荷增长的安全上限 |
| **Performance** | Pace-HR Decoupling > 10% | 高解耦率的原因与改进方法 |
| | Zone2 占比偏离目标 | Zone2 训练的科学分配原则 |
| **Risk** | Injury Risk > 60 | 高伤病风险下的训练调整策略 |
| | Recovery Debt 持续上升 | 恢复负债与过度使用损伤的关联 |

**原则**：不在每个 agent 调用时都 RAG，仅在指标异常、需要专业解释和建议时才触发。

---

### 检索链路总览

```
Agent 检测到指标异常
    ↓
构造自然语言 query + domain filter
    ↓
Milvus 混合检索（语义 + BM25 + 元数据过滤）粗筛 Top-20
    ↓
BGE-Reranker 精排 Top-5
    ↓
注入 Agent prompt 作为上下文 + 引用来源
    ↓
Agent 将 RAG 检索结果注入 prompt，LLM 生成 summary（RAG 内容融入总结，不单独暴露）
```

---

## 七、Pipeline 总览

```
Data Agent（解析 TCX）
    ↓
┌───────────────────────────────────────┐
│ Recovery │ Load │ Performance │ Risk  │  （并行分析）
└───────────────────────────────────────┘
    ↓
State Recognition Agent（识别生理状态）
    ↓
Coach Agent
  ├── Decision Engine（纯规则裁决）
  └── Report Generator（LLM 生成报告）
    ↓
Training Planner Agent（调整训练计划，V1）
```

---

## 八、CLI 命令

| 命令 | 说明 |
|------|------|
| `training-agents init` | 交互式创建用户画像 |
| `training-agents checkin --date 2024-06-15 --morning-hr 56 --rpe 4 --soreness 2` | 每日记录 |
| `training-agents analyze --date 2024-06-15` | 运行全链路分析 |
