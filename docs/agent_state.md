# Agent State 设计

参考 TradingAgents `agent_states.py`，采用 **TypedDict + MessagesState 继承** 模式。
一个 shared state 贯穿整个 LangGraph pipeline，各 Agent 只写自己的命名空间字段。

---

## 整体分层

```
入口参数
  ├── user_id / user_profile / activity_file / date
  ├── rpe / muscle_soreness / morning_hr / energy_level

Data Agent 产出
  └── parsed_activity

四个专业 Agent 产出（并行）
  ├── recovery_report
  ├── load_report
  ├── performance_report
  └── risk_report

State Recognition Agent 产出
  └── state_recognition

Coach Agent 产出
  ├── ruling（纯硬编码裁决）
  └── final_report（裁决 + LLM section 正文）
```

---

## TypedDict 定义

### UserProfile 用户基础画像

首次填写，长期不变，Agent 只读不写。

| 字段 | 类型 | 说明 |
|------|------|------|
| `age` | `int` | 年龄 |
| `gender` | `str` | 性别 |
| `height_cm` | `float` | 身高（厘米） |
| `weight_kg` | `float` | 体重（公斤） |
| `goal` | `str` | 运动目标：`"5km"` / `"10km"` / `"half_marathon"` / `"marathon"` |
| `training_level` | `str` | 训练水平：`"新手"` / `"进阶"` / `"高级"` |
| `personal_bests` | `dict` | 历史 PB，如 `{"5km": "22:30", "10km": "48:00", "半马": "1:45:00", "全马": "3:50:00"}` |
| `injury_history` | `List[str]` | 历史伤病部位，如 `["膝盖", "跟腱", "足底筋膜"]` |
| `max_hr` | `Optional[int]` | 用户设定的最大心率；若为空则 Data Agent 用 `220-age` 默认公式 |

---

### ParsedActivity — Data Agent 产出

> 每个字段标注数据来源：
> 📄 = TCX 直接提取 | 🧮 = Data Agent 计算 | 📜 = HistoryReader 历史数据

#### 活动汇总

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `sport` | `str` | 📄 | 运动类型：`"Running"` / `"Cycling"` / `"Swimming"` |
| `start_time` | `str` | 📄 | 开始时间，ISO 8601 |
| `total_distance` | `float` | 📄 | 总距离（米），所有 Lap DistanceMeters 累加 |
| `total_duration` | `float` | 📄 | 总时长（秒），所有 Lap TotalTimeSeconds 累加 |
| `avg_pace` | `str` | 🧮 | 平均配速，`total_duration ÷ total_distance` → `"4:55/km"` |
| `avg_hr` | `int` | 📄 | 平均心率（bpm），所有 trackpoint HR 均值 |
| `max_hr` | `int` | 📄 | 最大心率（bpm），所有 trackpoint HR 最大值 |
| `hr_drift` | `float` | 🧮 | 心率飘逸（%），前后半段平均心率变化 |
| `total_ascent` | `float` | 📄 | 累计爬升（米），trackpoint 海拔正差累加 |
| `total_descent` | `float` | 📄 | 累计下降（米），trackpoint 海拔负差累加 |
| `hr_zones` | `dict` | 🧮 | 心率五区占比，基于 trackpoint HR ÷ `max_hr`（用户设置 → `220-age` 兜底） |

#### Lap 每公里切分信息

`laps: List[LapSummary]`，下表描述**单个 Lap 元素**的结构。

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `index` | `int` | 📄 | Lap 序号 |
| `distance_m` | `float` | 📄 | DistanceMeters |
| `duration_s` | `float` | 📄 | TotalTimeSeconds |
| `avg_hr` | `int` | 📄 | AverageHeartRateBpm |
| `max_hr` | `int` | 📄 | MaximumHeartRateBpm |
| `avg_pace` | `str` | 🧮 | `duration_s ÷ distance_m` 格式化 |
| `avg_cadence` | `Optional[float]` | 📄+🧮 | 步频（TCX ×2 修正） |
| `avg_stride_length` | `Optional[float]` | 🧮 | 距离 ÷ 步数推算 |

#### 跑步技术指标（设备支持时，否则 `null`）

| 字段 | 类型 | 来源 | 单位 | 说明 |
|------|------|------|------|------|
| `avg_cadence` | `Optional[float]` | 📄 | spm | 平均步频（TCX Cadence ×2） |
| `avg_stride_length` | `Optional[float]` | 🧮 | m | 平均步幅，速度 ÷ 步频推算 |
| `avg_gct` | `Optional[float]` | 📄 | ms | 触地时间，兼容 GroundContactTime / StanceTime |
| `avg_vo` | `Optional[float]` | 📄 | cm | 垂直振幅 VerticalOscillation |
| `lr_balance` | `Optional[float]` | 📄 | % | 左右平衡，50 为完美对称 |
| `avg_vertical_ratio` | `Optional[float]` | 🧮 | % | 垂直步幅比 VO ÷ 步幅 × 100 |

#### Trackpoint 逐点序列

`trackpoints: TrackpointSeries`，用于图表绘制和精细化分析。

| 字段 | 类型 | 说明 |
|------|------|------|
| `time` | `List[int]` | 时间戳序列（秒） |
| `distance_m` | `List[float]` | 累计距离序列（米） |
| `heart_rate` | `List[int]` | 心率序列（bpm） |
| `speed` | `List[float]` | 速度序列（m/s） |
| `cadence` | `List[float]` | 步频序列（spm） |
| `altitude` | `List[float]` | 海拔序列（米） |
| `gct` | `List[float]` | 触地时间序列（ms） |
| `vo` | `List[float]` | 垂直振幅序列（cm） |
| `lr_balance` | `List[float]` | 左右平衡序列（%） |
| `vertical_ratio` | `List[float]` | 垂直步幅比序列（%） |

---

### HistoryContext — Data Agent 预读的历史数据

| 字段 | 类型 | 说明 |
|------|------|------|
| `from_date` | `str` | 查询起始日期 |
| `to_date` | `str` | 查询截止日期 |
| `daily_checkins` | `List[DailyCheckin]` | 历史每日 checkin 记录 |
| `training_sessions` | `List[ParsedActivity]` | 历史训练记录（re-parse 后的结构化数据） |

---

### RecoveryReport — Recovery Agent 产出

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `str` | `"good"` / `"warning"` / `"critical"` |
| `recovery_score` | `int` | 恢复评分 0-100 |
| `fatigue_trend` | `str` | `"dissipating"` / `"stable"` / `"accumulating"` |
| `resting_hr_deviation` | `int` | 静息心率偏离基线值（bpm） |
| `hr_drift` | `float` | 当日心率飘逸（%） |
| `recovery_debt` | `float` | 恢复负债累计值 |
| `recovery_debt_trend` | `str` | 负债趋势：`"improving"` / `"stable"` / `"worsening"` |
| `consecutive_hard_days` | `int` | 连续高强度训练天数 |
| `summary` | `str` | LLM 生成的自然语言总结 |

---

### LoadReport — Training Load Agent 产出

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `str` | `"optimal"` / `"warning"` / `"critical"` |
| `acwr` | `float` | 急慢性负荷比 |
| `acwr_status` | `str` | ACWR 状态描述 |
| `ramp_rate` | `float` | 周负荷变化率 |
| `chronic_load` | `float` | 慢性负荷（4 周均值） |
| `acute_load` | `float` | 急性负荷（1 周） |
| `monotony` | `float` | 训练单调性 |
| `strain` | `float` | 训练压力 |
| `summary` | `str` | LLM 生成的自然语言总结 |

---

### PerformanceReport — Performance Agent 产出

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `str` | `"improving"` / `"stable"` / `"declining"` |
| `efficiency_factor` | `float` | 效率因子（配速/心率比） |
| `efficiency_trend` | `str` | 效率趋势 |
| `efficiency_history` | `List[float]` | 近 10 天效率因子历史 |
| `aerobic_efficiency` | `float` | 有氧效率 |
| `aerobic_trend` | `str` | 有氧效率趋势 |
| `pace_hr_decoupling` | `float` | 配速-心率解耦率（%） |
| `decoupling_status` | `str` | 解耦状态 |
| `zone_distribution` | `dict` | 心率五区分布 `{"zone1": 0.11, ...}` |
| `target_alignment` | `str` | `"on_track"` / `"mismatch"` / `"insufficient_data"` |
| `technique_flags` | `List[dict]` | 技术问题列表，含 `key` `label` `severity` |
| `summary` | `str` | LLM 生成的自然语言总结 |

---

### RiskReport — Risk Agent 产出

| 字段 | 类型 | 说明 |
|------|------|------|
| `risk_level` | `str` | `"low"` / `"moderate"` / `"high"` / `"critical"` |
| `injury_risk_score` | `int` | 伤病风险评分 0-100 |
| `risk_factors` | `List[str]` | 激活的风险因子列表 |
| `alerts` | `List[str]` | 警报信息列表 |
| `summary` | `str` | LLM 生成的自然语言总结 |

---

### StateRecognitionResult — State Recognition Agent 产出

| 字段 | 类型 | 说明 |
|------|------|------|
| `physiological_states` | `List[dict]` | 匹配到的生理状态列表，每个含 `name` `confidence` `evidence` |
| `primary_state` | `dict` or `null` | 最高 severity 的状态，用于 Gate 阈值调节 |

生理状态枚举：

| name | severity | 含义 |
|------|----------|------|
| `injury_onset_pattern` | 100 | 伤病前兆模式 |
| `non_functional_overreaching` | 90 | 非功能性过度训练 |
| `cns_fatigue` | 80 | 中枢神经疲劳 |
| `cardiovascular_strain` | 70 | 心血管压力 |
| `muscular_fatigue` | 60 | 肌肉疲劳 |
| `functional_overreaching` | 50 | 功能性过度训练 |

---

### RulingResult — Decision Engine 产出

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | `str` | `"full_rest"` / `"recovery_run"` / `"reduce_load"` / `"quality_session"` / `"normal_training"` |
| `status` | `str` | `"critical"` / `"warning"` / `"good"` |
| `verdict` | `str` | 人类可读裁决描述（中文） |
| `modifiers` | `List[dict]` | 技术修饰器列表，每个含 `key` `label` `reason` |

---

### FinalReport — Coach Agent 最终产出

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | `str` | 报告日期 |
| `recommendation` | `RulingResult` | Decision Engine 裁决结果 |
| `special_event` | `Optional[SpecialEvent]` | 特殊事件，无则为 `null` |
| `markdown` | `str` | LLM 直出的完整 Markdown 报告 |

---

## 顶层 AgentState

继承 `MessagesState`，所有节点读/写同一 state，字段逐步累积。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | `str` | 用户唯一标识，用于查询历史训练记录和基线数据 |
| `user_profile` | `UserProfile` | 用户基础画像，各 Agent 只读不写 |
| `activity_file` | `str` | 本次训练原始文件路径（TCX/FIT/GPX） |
| `date` | `str` | 训练日期，ISO 8601 格式 |
| `rpe` | `int` | 主观疲劳感知 1~10 |
| `muscle_soreness` | `int` | 肌肉酸痛程度 0~5 |
| `morning_hr` | `int` | 晨间静息心率（bpm） |
| `energy_level` | `Optional[int]` | 当日精神状态 1~5，可选 |
| `parsed_activity` | `ParsedActivity` | Data Agent 产出，原始文件解析后的结构化训练数据 |
| `history` | `HistoryContext` | Data Agent 预读的历史数据（日常 checkin + 训练记录） |
| `recovery_report` | `RecoveryReport` | Recovery Agent 产出 |
| `load_report` | `LoadReport` | Training Load Agent 产出 |
| `performance_report` | `PerformanceReport` | Performance Agent 产出 |
| `risk_report` | `RiskReport` | Risk Agent 产出 |
| `ruling` | `RulingResult` | Coach Agent 裁决结果（Decision Engine 输出） |
| `state_recognition` | `StateRecognitionResult` | State Recognition Agent 输出，识别到的生理状态列表 |
| `final_report` | `FinalReport` | Coach Agent 最终训练报告 |

---

## 数据存储约定

### 文件结构

```
data/
├── daily_checkin/                  # 每日输入（有无训练都记录）
│   ├── 2024-10-18.json             # { morning_hr: 56, energy: 4 }
│   ├── 2024-10-19.json             # { morning_hr: 58, energy: 3 }
│   ├── 2024-10-20.json             # { morning_hr: 60, energy: 3 }
│   └── ...

└── training/                       # 训练日原始文件（仅训练日有），历史查询时 re-parse
    ├── 2024-10-18/
    │   └── input.tcx
    ├── 2024-10-20/
    │   └── input.tcx
    └── ...
```

### 数据对齐原则

| 约定 | 说明 |
|------|------|
| **训练日才跑 pipeline** | 每次上传一个 TCX 触发一次完整 multi-agent 流程 |
| **state 只放当天** | `rpe`、`morning_hr`、`muscle_soreness`、`energy_level` 只存本次训练日的值 |
| **历史由 Data Agent 预读** | Agent 需要的历史数据由 Data Agent 通过 `HistoryReader` 统一预读，注入 `AgentState.history`（顶层字段，与 `parsed_activity` 平级），下游 Agent 直接读取，无需自己访问文件系统 |
| **每日输入独立存储** | `daily_checkin/` 按天存，无论当天是否有训练，保证 Recovery Agent 能读到连续的晨间心率 |
| **训练文件独立存储** | `training/` 按天存 TCX，不存计算结果。各 Agent 需要历史指标时通过 HistoryReader 自动 re-parse 提取 |

### Agent 的历史查询范围

> 历史数据读取统一通过 `HistoryReader`，`training/` 下只存 TCX，指标由 HistoryReader 内部 `parse_tcx` 提取。

| Agent | 数据源 | 查询 ParsedActivity 字段 | 窗口（天） |
|-------|--------|--------------------------|-----------|
| **Data Agent** | 本次 TCX 文件 | — | 无历史查询 |
| **Recovery Agent** | `state.history.daily_checkins` + `state.history.training_sessions` | `morning_hr`（晨间心率基线偏离/趋势）、`hr_drift` + `total_duration`（恢复负债计算） | 7 天 |
| **Load Agent** | `training/` | `total_distance`、`total_duration` | 28 天 |
| **Performance Agent** | `training/` | `avg_hr`、`avg_pace`、`hr_zones`、`hr_drift`、`total_duration` | 10 天 |
| **Risk Agent** | `training/` + `daily_checkin/` | `avg_hr`、`hr_drift`、`total_distance` | 7 天 |
| **Coach Agent** | 仅读 state 中四个 Agent report | — | 无历史查询 |