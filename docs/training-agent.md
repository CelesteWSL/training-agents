# Training Agents — 多智能体协作的 AI 跑步训练分析系统

> **Training Agents** 是一个多智能体协作的 AI 跑步训练分析系统：你跑完步上传一条 Garmin / Coros 训练数据（TCX），系统自动产出一份教练级分析报告。
>
> 类比真实的教练团队——体能教练看负荷、康复师看恢复、技术教练看表现、队医看伤病风险，最后主教练综合拍板。五个 Agent 各司其职，纯 Python 指标计算 + LLM 叙事生成，裁决层硬编码保证确定性，报告层发挥 LLM 的自然语言能力。
>
> **快速开始：** `training-agents init` 创建画像 → `training-agents checkin` 记录晨间心率 → 跑完步 `training-agents analyze --date YYYY-MM-DD` 获取完整报告。

> 💡 项目中已内置部分示例训练数据，可直接运行体验。如需使用个人数据，删除 data/training/ 下的文件并放入自己的 TCX 数据 + 删除 daily_checkin 重新调用命令行 即可。

## 快速开始

### 环境要求

- Python >= 3.10
- pip（推荐使用虚拟环境）

### 安装

```bash
# 克隆仓库
git clone https://github.com/your-org/training-agents.git
cd training-agents

# 安装依赖
pip install -e .
```

### 配置 LLM

系统通过环境变量配置大模型。支持 OpenAI、DeepSeek、通义千问、Anthropic Claude、Google Gemini 等。

**.env 文件示例：**

```env
# 必填：至少配置一个 Provider 的 API Key
OPENAI_API_KEY=sk-xxx
# 或
DEEPSEEK_API_KEY=sk-xxx

# 可选：指定使用的 Provider 和模型
LLM_PROVIDER=deepseek
DEEP_THINK_LLM=deepseek-v4-pro
QUICK_THINK_LLM=deepseek-v4-flash

# 可选：自定义 API 地址
LLM_BACKEND_URL=https://your-proxy.com/v1

# 可选：报告语言（Chinese / English）
OUTPUT_LANGUAGE=Chinese
```

> **支持的 Provider：** openai / deepseek / anthropic / google / azure / qwen / glm / minimax / ollama / openrouter

### 准备训练数据

1. 从 Garmin Connect / Coros / Strava 导出训练记录为 **TCX 文件**
2. 将 TCX 文件放入 `data/training/` 目录
3. 文件命名格式：`{描述}{YYYYMMDDHHmmss}.tcx`（如 `武汉市_跑步20240317220508.tcx`）

### 三步上手

**Step 1：创建用户画像**

```bash
training-agents init
```

> ⚠️ 当前交互提示为中文。英文用户可跳过此步骤，直接手动创建 `data/user_profile.json`（字段说明见下方）。

交互式录入，仅需执行一次。各字段的约束与可选值：

| 字段 | 约束 | 可选值 / 说明 |
|------|------|---------------|
| 年龄 | 10 ~ 120 | 整数 |
| 性别 | `male` / `female` / `other` | 三选一 |
| 身高 | 100 ~ 250 cm | 浮点数 |
| 体重 | 30 ~ 250 kg | 浮点数 |
| 训练目标 | `5km` / `10km` / `half_marathon` / `marathon` | 五选一（含未列出的"其他"） |
| 训练水平 | `新手` / `进阶` / `高级` | 三选一 |
| 历史 PB | 可选，直接回车跳过 | 格式 `mm:ss`，支持的项：`5km` `10km` `半马` `全马` |
| 伤病历史 | 可选，多选用逗号分隔 | 可选：`膝盖` `跟腱` `足底筋膜` `髋关节` `胫骨/应力` |
| 最大心率 | 可选，100 ~ 220 | 留空则默认 `220 - 年龄` |

**英文用户手动创建画像：**

```json
// data/user_profile.json
{
    "age": 30,
    "gender": "male",
    "height_cm": 175.0,
    "weight_kg": 70.0,
    "goal": "half_marathon",
    "training_level": "进阶",
    "personal_bests": {"10km": "45:00", "半马": "1:45:00"},
    "injury_history": ["膝盖"],
    "max_hr": 190
}
```

**Step 2：每日晨间打卡**

```bash
training-agents checkin --date 2024-03-17 --morning-hr 55 --rpe 4 --soreness 2
```

- `--morning-hr`：晨间静息心率（bpm），**必填**
- `--rpe`：主观疲劳 1~10，可选
- `--soreness`：肌肉酸痛 0~5，可选

即使当天不训练也建议打卡，系统需要连续的晨间心率数据来判断恢复趋势。

**Step 3：跑完步，获取分析报告**

```bash
training-agents analyze --date 2024-03-17
```

系统自动：
1. 解析 TCX 文件 → 提取配速、心率、步频、触地时间等十几维指标
2. 四路 Agent 并行分析恢复/负荷/表现/风险
3. 跨维度交叉验证识别隐藏生理状态
4. 规则引擎做确定性裁决
5. LLM 生成自然语言教练级报告 → 输出到 `reports/` 目录

### 查看报告

```bash
# 报告保存在 reports/ 目录
cat reports/2024-03-17_report.md
```

报告包含：训练数据摘要 → 恢复/负荷/表现/风险逐项分析 → 状态识别结论 → 训练建议。


## 系统架构

```
TCX File → [Data Agent] → ┬→ Recovery Agent ──────┐
                           ├→ Load Agent ───────────┤
                           ├→ Performance Agent ────┤
                           └→ Risk Agent ───────────┘
                                     ↓
                           State Recognition Engine
                                     ↓
                           Decision Engine
                                     ↓
                           Report Generator
                                     ↓
                              最终训练报告
```


# 一、自动输入（来自 TCX，后期扩展 FIT / GPX）

无需用户手动输入。

------

## 基础训练数据

- 时间
- 距离
- 时长
- 海拔
- 速度（瞬时 m/s，来自 trackpoint）

------

## 心率数据

- 平均心率
- 最大心率
- 心率曲线

------

## 跑步技术数据（设备支持时）

- 步频 Cadence
- 步幅 Stride Length
- 触地时间 GCT
- 垂直振幅 VO
- 左右平衡
- 垂直步幅比 Vertical Ratio

------

## 骑行数据 🚧（计划中，当前版本未实现）

- 功率 Power
- FTP
- 踏频
- NP
- IF

------

# 二、用户轻量输入

建议只保留这几个。

------

## 每次训练后

### RPE（必须）

```text
1~10
```

主观疲劳。

------

### Muscle Soreness（推荐）

```text
0~5
```

肌肉酸痛。

------

# 三、每日输入

------

## Morning Resting HR

```text
晨间静息心率
```

一个数字即可。

------

## Energy Level（可选）

```text
1~5
```

精神状态。

------

# 四、用户基础画像（首次填写）

只填一次。

------

## 基础信息

- 年龄
- 性别
- 身高
- 体重

------

## 运动目标

例如：

- 5km
- 10km
- half_marathon
- marathon

------

## 训练水平

例如：

- 新手
- 进阶
- 高级

------

## 历史PB（推荐）

例如：

- 5km
- 10km
- 半马
- 全马

------

## 历史伤病位置

例如：

- 膝盖
- 跟腱
- 足底筋膜
- 髋 / 髋关节
- 胫骨 / 应力

# 分析agent

## Data Agent

### 职责边界

Data Agent 负责：**解析 TCX 文件 → 结构化数据 + 读取历史数据**

```
TCX File → parse_tcx() → ParsedActivity + HistoryContext
```

✅ **做这些：**
- 解析 TCX 文件（当前版本；后续扩展 FIT/GPX）
- 提取所有设备数据：运动类型、时间、距离、心率、海拔、步频、速度
- 提取跑步动态数据（设备支持时）：触地时间、垂直振幅、左右平衡、垂直步幅比
- 计算可直接推导的指标：配速、步幅、心率分区、心率飘逸
- 通过 HistoryReader 读取往期训练数据 + 每日 checkin，注入 history 字段

❌ **不做这些：**
- 教练建议、恢复分析、风险预测、趋势判断（属于其他 Agent）
- 用户画像处理、用户手动输入（属于 User Profile / User Input）

---

### 输入

| 来源 | 内容 |
|------|------|
| `state.activity_file` | TCX 文件路径 |
| `state.user_profile` | 用户基础画像（age、max_hr 等） |
| `state.date` | 训练日期 |

---

### 输出：ParsedActivity

与 `agent_states.py` 中 `ParsedActivity` TypedDict 完全对齐。

#### Activity 汇总

| 字段 | 类型 | 说明 |
|------|------|------|
| `sport` | str | 运动类型（Running / Cycling / Swimming） |
| `start_time` | str | ISO 8601 开始时间 |
| `total_distance` | float | 总距离（米） |
| `total_duration` | float | 总时长（秒） |
| `avg_pace` | str | 平均配速 `"m:ss/km"` |
| `avg_hr` | int | 平均心率（bpm） |
| `max_hr` | int | 最大心率（bpm） |
| `hr_drift` | float | 心率飘逸（%），前后半段心率变化率 |
| `total_ascent` | float | 累计爬升（米） |
| `total_descent` | float | 累计下降（米） |

#### 心率分区

| 字段 | 类型 | 说明 |
|------|------|------|
| `hr_zones` | dict | `{"zone1": 0.11, "zone2": 0.15, ...}`，基于 trackpoint HR ÷ max_hr |
| `max_hr` 来源 | — | 用户设置的 `max_hr` → `220 - age` → 兜底 220 |

#### Lap 分段

`laps: List[LapSummary]`

| 字段 | 类型 | 说明 |
|------|------|------|
| `index` | int | Lap 序号 |
| `distance_m` | float | 距离（米） |
| `duration_s` | float | 时长（秒） |
| `avg_hr` | int | 平均心率 |
| `max_hr` | int | 最大心率 |
| `avg_pace` | str | 配速 |
| `avg_cadence` | float \| null | 步频（已修正 ×2） |
| `avg_stride_length` | float \| null | 步幅（米） |

#### 跑步技术指标（设备支持时）

| 字段 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `avg_cadence` | float \| null | spm | 平均步频，TCX 原生值 ×2 修正 |
| `avg_stride_length` | float \| null | m | 步幅，速度 ÷ 步频推算 |
| `avg_gct` | float \| null | ms | 触地时间，需传感器 |
| `avg_vo` | float \| null | cm | 垂直振幅，需传感器 |
| `lr_balance` | float \| null | % | 左右平衡（50.0 = 均衡），需传感器 |
| `avg_vertical_ratio` | float \| null | % | 垂直步幅比，传感器优先 → VO ÷ 步幅回退 |

> 设备不支持时字段为 `null`。Parser 内部兼容 GroundContactTime / StanceTime、LeftRightBalance / GroundContactTimeBalance 等多厂商别名。

#### 时间序列（TrackpointSeries — 列式）

`trackpoints: TrackpointSeries`，各属性独立等长数组，第 i 个元素对应同一秒采样。

| 列 | 类型 | 说明 |
|------|------|------|
| `time` | List[str] | ISO 8601 时间戳 |
| `distance_m` | List[float] | 累计距离（米） |
| `heart_rate` | List[int] | 瞬时心率（bpm），缺则 0 |
| `speed` | List[float] | 瞬时速度（m/s），缺则 0.0 |
| `cadence` | List[float\|null] | 步频（已修正），缺则 null |
| `altitude` | List[float] | 海拔（米） |
| `gct` | List[float\|null] | 触地时间 |
| `vo` | List[float\|null] | 垂直振幅 |
| `lr_balance` | List[float\|null] | 左右平衡 |
| `vertical_ratio` | List[float\|null] | 垂直步幅比 |

> 全量透传，不做降采样。各列永远等长对齐，缺失值用 0 / null 占位。可直接用于 `plt.plot(ts["time"], ts["heart_rate"])`。

#### 历史上下文（HistoryContext）

Data Agent 通过 `HistoryReader` 读取往期数据，注入 `parsed_activity.history`，下游 Agent 无需再读文件。

| 数据源                      | 解析路径                | 时间范围 | 用途                                                         |
| :-------------------------- | :---------------------- | :------- | :----------------------------------------------------------- |
| `history.daily_checkins`    | `daily_checkin/`        | 近 7 天  | 计算静息心率基线/偏离/趋势                                   |
| `history.training_sessions` | `training/` (re-parse) | 近 7 天  | 一次性读取近 28 天（≈10 次）的完整训练记录，下游 Agent 各取所需窗口 |

---

## Recovery Agent

### 职责边界

Recovery Agent 负责：**综合分析恢复状态，输出恢复评分与建议**

✅ **做这些：**
- 8 项指标全部硬编码计算：
  - **status** — good / moderate / warning / critical
  - **recovery_score** — 0-100
  - **fatigue_trend** — stable / recovering / accumulating
  - **resting_hr_deviation** — 晨间心率偏离 7 天基线的幅度（bpm）
  - **hr_drift** — 心率漂移百分比
  - **hr_drift_interpretation** — <3% 正常 / 3-6% 轻微 / >6% 明显
  - **recovery_debt** — Σ max(0, hr_drift-3.0) × 训练时长(h) × 10（近 7 天）
  - **recovery_debt_trend** — improving / stable / worsening
  - **summary** — LLM 自然语言总结（含 RAG 检索到的专业知识）
- 基于 RAG 知识库提供专业恢复建议
- 识别恢复不足的风险信号

❌ **不做这些：**
- 解析原始运动文件（由 Data Agent 负责）
- 计算训练负荷指标（由 Training Load Agent 负责）
- 运动表现分析（由 Performance Agent 负责）

---

### 输入

#### 来自 ParsedActivity（当前训练 + history 预读）

| 字段 | 用途 |
|------|------|
| `avg_hr` | 本次训练强度基准 |
| `max_hr` | 峰值压力大小 |
| `hr_drift` | 本次训练中疲劳累积程度 |
| `hr_zones` | 高强度占比 → 恢复需求评估 |
| `total_duration` | 时长 × 强度交互 → 总恢复需求 |
| `trackpoints.heart_rate` + `trackpoints.time` | HR 恢复速率（峰值后下降斜率） |
| `history.morning_hr_series` | 近 7 天晨间静息心率 → 基线偏离 |
| `history.hr_drift_series` | 近 10 次 hr_drift → 疲劳趋势 |

#### 来自 User Input

- `morning_hr` — 当日晨间静息心率
- `rpe` — 主观疲劳 1~10
- `muscle_soreness` — 肌肉酸痛 0~5

#### 来自 User Profile

- `age` — 年龄越大恢复越慢
- `training_level` — 新手/进阶/高级
---

### 自身计算

#### Recovery Score（恢复评分）

```json
{
  "recovery_score": 72,
  "level": "moderate",
  "factors": {
    "hrv_trend": "stable",
    "resting_hr_trend": "stable",
    "recent_load": "moderate",
    "sleep_quality": "unknown"
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `recovery_score` | number | 恢复评分（0-100，越高越好） |
| `level` | string | 恢复等级：`excellent` / `good` / `moderate` / `poor` |
| `factors` | object | 影响恢复的各项因子 |

评分综合考虑：
- Morning Resting HR 相对基线的偏移
- 近期训练负荷（来自 Training Load Agent，或暂由自身估算）
- RPE / Muscle Soreness 趋势

#### Fatigue Trend（疲劳趋势）

```json
{
  "fatigue_trend": "accumulating",
  "trend_score": -3.2,
  "consecutive_hard_days": 3,
  "warning": true
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `fatigue_trend` | string | 趋势方向：`decreasing` / `stable` / `accumulating` |
| `trend_score` | number | 趋势量化值（正=恢复中，负=累积中） |
| `consecutive_hard_days` | number | 连续高强度天数 |
| `warning` | boolean | 是否触发疲劳预警 |

#### Resting Trend（静息心率趋势）

```json
{
  "resting_hr_current": 58,
  "resting_hr_baseline": 54,
  "resting_hr_deviation": 4,
  "resting_trend": "elevated"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `resting_hr_current` | number | 当前静息心率（最近 3 天均值） |
| `resting_hr_baseline` | number | 基线静息心率（14 天均值） |
| `resting_hr_deviation` | number | 偏离值（正值=偏高，需关注） |
| `resting_trend` | string | 趋势：`stable` / `elevated` / `decreasing` |

偏离超过基线 5bpm 以上触发关注。

---

### 输出

| 字段                      | 类型   | 说明                                                   |
| ------------------------- | ------ | ------------------------------------------------------ |
| `status`                  | string | 恢复状态：`good` / `moderate` / `warning` / `critical` |
| `recovery_score`          | float  | 恢复评分 0-100                                         |
| `fatigue_trend`           | string | 疲劳趋势：`stable` / `recovering` / `accumulating`     |
| `resting_hr_deviation`    | float  | 晨间静息心率偏离基线的幅度（bpm），正数=偏高           |
| `hr_drift`                | float  | 心率飘逸（%）                                          |
| `hr_drift_interpretation` | string | 心率飘逸的解读说明                                     |
| `recovery_debt`           | float  | 恢复负债                                               |
| `recovery_debt_trend`     | string | 恢复负债趋势：`improving` / `stable` / `worsening`     |
| `summary`                 | string | Agent 对恢复指标的自然语言总结（调 LLM 生成）          |

```json
{
  status: critical
  recovery_score: 29.0
  fatigue_trend: stable
  resting_hr_deviation: 12.0
  hr_drift: 6.5
  hr_drift_interpretation: 明显疲劳，心率持续上升，恢复需求较高
  recovery_debt: 0.0
  recovery_debt_trend: stable

  summary: "..."
}

// 下面是整个summary部分，LLM 100% 自动生成，不是代码里硬编码的
## 📊 恢复数据评估

// 这部分是根据我们human_prompt对应的回答
| 指标 | 当前值 | 状态 | 解读 |
|------|--------|------|------|
| **恢复评分** | 29/100 | 🔴 临界 (Critical) | 身体恢复严重不足，已进入预警区间，需立即关注 |
| **静息心率偏离** | +12.0 bpm（基线 56 → 今日 ≈68） | 🔴 显著异常 | 偏离幅度较大，提示自主神经系统疲劳或潜在过度训练 |
| **疲劳趋势** | Stable（稳定） | 🟡 需关注 | 疲劳未进一步累积，但当前疲劳水平仍偏高 |
| **心率漂移** | 6.5% | 🔴 明显疲劳 | 运动中维持心率困难，心血管系统承受较大压力，恢复需求较高 |

> **核心判断**：静息心率偏离 +12 bpm 与恢复评分 29（临界）互为印证，结合心率漂移 6.5%，表明身体正处于**较明显的恢复不足状态**，需 要立即调整训练负荷，而非继续「硬扛」。

---

// 这部分是prompt里面的恢复评估和训练建议
## 📚 专业建议（结合知识库）

### 1️⃣ 立即安排休息或主动恢复日

根据《科学跑步》中的明确指导：*"如果醒来时的心率远远高于你平时测量的结果，你可能就需要休息一下或者做个体检了。"* 当前静息心率偏离 +12 bpm 已属于「远高于平时」的范畴。建议：

- **今明两天暂停所有高强度训练**，可安排 20-30 分钟极低强度的散步或拉伸。
- 若想进行恢复性跑步，应控制在**最大心率的 50%-60%**（即轻松跑的最低区间），以促进血液循环而非施加训练刺激。

### 2️⃣ 持续监控心率，必要时就医排查

如《心率训练》一书所述：*"当疲劳、过度训练、生病、感冒或发烧时，你的心率都会有变化，这样一来就可以据此修改训练计划。"*

- **连续 3 天**监测晨起静息心率，若持续高于基线 5 bpm 以上，建议暂停跑步 3-5 天。
- 若伴随睡眠质量下降、食欲减退、情绪低落等症状，需警惕**过度训练综合征**，应咨询运动医学医生。

### 3️⃣ 规划一次「计划中的休整」

长期来看，知识库中丹尼尔斯博士的建议是：*"我喜欢将休整看成训练的一部分……计划中的休整期定为 2~6 周。"* 考虑到你当前的恢复评分已触及界，建议：

- 在接下来 1-2 周内，将训练量降低至正常水平的 **50%-60%**。
- 可引入**交叉训练**（椭圆仪、游泳、单车），在不产生冲击力的情况下维持有氧能力，避免 VDOT 下降过多。

### 4️⃣ 心率漂移 6.5% 的应对策略

心率漂移（Cardiac Drift）是心血管疲劳的直接信号。在当前状态下，切忌按照「配速」来硬跑，而应**以心率区间为核心**来指导训练：       

- 如果目标是维持某个心率，就接受配速自然会变慢；反之，如果坚持既定配速，心率只会越来越高，进一步加剧疲劳。
- 在恢复期间，建议完全按照**心率而非配速**来跑步，上限不超过最大心率的 70%。

---

## ✅ 总结行动清单

| 优先级 | 行动 |
|--------|------|
| 🔴 立即 | 暂停高强度训练，安排主动恢复日 |
| 🔴 短期 | 连续监测晨起静息心率，若持续偏高→就医 |
| 🟡 本周 | 训练量降至 50%-60%，以心率而非配速指导 |
| 🟢 长期 | 规划 2-6 周休整期，加入交叉训练（游泳/椭圆仪/单车） |

---

> ⚠️ **重要提示**：以上建议旨在帮助你科学调整训练，不能替代专业医疗诊断。如果静息心率持续异常或出现胸痛、严重乏力等症状，请及时就 医。健康的身体永远是跑步的第一前提，适度退一步，才能更持久地跑下去。
---
```

## Training Load Agent

### 职责边界

Training Load Agent 负责：**计算训练负荷指标，为下游 agent 提供负荷数据**

✅ **做这些：**
- 计算 Acute Load、Chronic Load、ACWR
- 统计周训练量、负荷增长速率
- 提供结构化负荷数据供 Recovery / Risk / Performance Agent 使用

❌ **不做这些：**
- 恢复状态分析（由 Recovery Agent 负责）
- 风险判断（由 Risk Agent 负责）
- 训练建议（由 Decision Engine + Report Generator 负责）
- 用户输入处理
- RAG 检索

---

### 输入

来自 `history.training_sessions`（Data Agent 预读的近 28 天训练历史）

| 字段 | 用途 |
|------|------|
| `total_distance` | 跑量统计（米 → 公里） |
| `total_duration` | 训练时长（秒） |
| `hr_zones` | 心率五区时间占比 → TRIMP 加权 |

不需要 User Input、User Profile、RAG。

### 负荷计算方式

采用 **Edwards'' TRIMP（Training Impulse，训练冲量）**：

| 心率区间 | %HRmax | TRIMP 系数 |
|----------|--------|------------|
| Zone 1 | < 60% | ×1 |
| Zone 2 | 60–70% | ×2 |
| Zone 3 | 70–80% | ×3 |
| Zone 4 | 80–90% | ×4 |
| Zone 5 | 90–100% | ×5 |

```
单次训练 TRIMP = total_duration_min × Σ(zone_N百分比 × N)
```

> **为什么用 TRIMP？** 同等训练时长，高强度区间的生理负荷可达到低强度的 3-5 倍，TRIMP 通过心率区间加权准确反映真实生理负荷。
>
> **参考**：Edwards, S. (1993). *The Heart Rate Monitor Book*.

---

### 自身计算

#### Acute Load（急性负荷，近 7 天）

```
acute_load = 近 7 天每日 TRIMP 的均值（含休息日，计为 0）
```

#### Chronic Load（慢性负荷，近 28 天）

```
chronic_load = 近 28 天每日 TRIMP 的均值（含休息日，计为 0）
```

> 按天平均（而非按训练次数平均）是 ACWR 文献的标准做法，确保休息日的恢复效果被正确纳入计算。

#### ACWR（急慢性负荷比）

```
acwr = acute_load / chronic_load
```

| ACWR 范围 | 状态 |
|-----------|------|
| < 0.8 | undertraining |
| 0.8 ~ 1.3 | optimal |
| 1.3 ~ 1.5 | borderline |
| > 1.5 | overreaching |

> **参考**：Gabbett, T.J. (2016). "The training-injury prevention paradox." *British Journal of Sports Medicine*, 50(5).

#### Weekly Volume（周跑量）

```
weekly_volume_km = 近 7 天 total_distance 累计 / 1000
```

#### Ramp Rate（周跑量增长率）

```
ramp_rate = (本周跑量 - 上周跑量) / 上周跑量
```

| Ramp Rate | 状态 |
|-----------|------|
| ≤ 0.10 | safe（安全增长） |
| 0.10 ~ 0.15 | moderate（需关注） |
| 0.15 ~ 0.20 | caution（中风险） |
| > 0.20 | aggressive（高风险） |

> **参考**：Nielsen, R.O. et al. (2014). "Training errors and running related injuries." *JOSPT*.

#### TSS 🚧（计划中，当前版本未实现）

第一版不实现。基于功率或心率阈值计算训练压力评分。

---

### 输出

```json
{
    status: critical
    acute_load: 258.3
    chronic_load: 173.5
    acwr: 1.49
    weekly_volume_km: 105.0
    ramp_rate: 0.5
    acwr_interpretation: 训练负荷偏高（borderline），建议关注恢复情况
    ramp_rate_interpretation: 周跑量增长过快，高风险（aggressive），建议控制增幅
    summary: "..."
}

// 下面是整个summary部分，LLM 100% 自动生成，不是代码里硬编码的
**📊 当前负荷状态：**
你正处于 **"临界危险区"**。ACWR 1.49（急性 258.3 / 慢性 173.5）紧贴 1.5 的过度训练红线，而周跑量单周暴涨 **+50%**（直接拉到 105 km），这不是"加量"，这是"冲击身体的红线"。

---

**🔴 关键风险点：**

> 📖 知识库指出：*"为了避免过度训练……不过快地进入训练、设置现实的目标"*，以及 *"最好能够坚持 10% 的原则，即控制每周增加的跑量在 10% 以内"*（来源：《无伤跑法》/ 训练基本原则）。

你的周增幅是 **50%，是安全上限的 5 倍**。ACWR 1.49 意味着急性负荷几乎达到慢性负荷的 1.5 倍——身体来不及吸收这些负荷，骨骼、肌腱和关正在承受远超适应能力的冲击。跟腱炎、应力性骨折、髌腱炎等"增量型伤病"风险正处于爆发窗口。

---

**🩺 可执行调整建议：**

1. **立刻回调本周跑量**：将本周跑量降至约 **95 km 或以下**（以慢性负荷 173.5 km 为锚点，先回归 10% 增幅原则），并取消任何高强度训练（间歇、节奏跑），只保留轻松有氧慢跑。

2. **插入恢复周**：📖 知识库也强调：*"跑得太快就是最常出现的错误和最常见的受伤原因……放松的耐力训练是最高效的"*。接下来 7-10 天以恢复为核心，跑量控制在 70-80 km，配速比平常轻松跑再慢 15-20 秒/公里，同时优先保障睡眠和营养，让身体把之前的训练"吸收"进去，而不是继续透支。

---

**一句话总结：** 你在受伤的边缘，但还没掉下去——现在主动踩刹车，比被迫停跑要聪明得多。把"10% 原则"贴在你的训练日志上，下周开始严格执行。需要我帮你重新规划接下来 3-4 周的"安全降量"过渡方案吗？
```

纯数据结构，不包含解读或建议。下游 agent 按需使用。

---

## Performance Agent

### 职责边界

Performance Agent 负责：**追踪跑步效率变化，评估训练结构是否合理**

✅ **做这些：**
- 计算 Efficiency Factor、Aerobic Efficiency、Pace-HR Decoupling
- 分析心率区间分布趋势
- 判断训练结构是否与用户目标匹配

❌ **不做这些：**
- 恢复状态分析（由 Recovery Agent 负责）
- 负荷计算（由 Training Load Agent 负责）
- 风险预测（由 Risk Agent 负责）
- 训练计划制定 🚧（计划中）

---

### 输入

#### 来自训练数据

| 字段 | 用途 |
|------|------|
| `avg_pace` | 本次表现输出 |
| `avg_hr` | 本次生理成本（EF 分母） |
| `hr_drift` | 心率漂移 %（Data Agent 计算，≠ PHRD，见下方 Pace-HR Decoupling 公式） |
| `hr_zones` | 有氧/无氧分布 → 训练结构判断 |
| `total_ascent` + `total_descent` | 地形修正（供 LLM 参考，爬坡配速不能和平地比） |
| `avg_cadence` + `avg_stride_length` | 跑步形态 |
| `avg_gct` + `avg_vo` + `avg_vertical_ratio` | 跑步经济性指标 |
| `laps` | 每公里配速/心率对照 → 分段效率分析（供 LLM 参考） |
| `trackpoints.heart_rate` + `trackpoints.speed` | 逐秒 Pace-HR 对照 → 解耦计算 |
| `history.training_sessions` | 近 10 次完整训练记录（re-parse），每条含 `avg_hr`、`avg_pace`、`hr_zones`、`hr_drift`、`total_duration` → EF 趋势 / 区间分布 / PHRD 背景 |

#### 来自 User Profile

- `goal` — 目标赛事/训练类型 → 判断训练结构是否匹配
- `personal_bests` — 历史 PB → 表现基准对照

> 注意：Performance Agent 和 Load Agent 是并行运行的，不依赖 Load Agent 的输出。

### 自身计算

#### Efficiency Factor（跑步效率）

```json
{
  "efficiency_factor": 1.08,
  "efficiency_trend": "improving",
  "history": [
    { "date": "2024-10-14", "value": 1.02 },
    { "date": "2024-10-21", "value": 1.08 }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `efficiency_factor` | number | 当前跑步效率（配速 ÷ 心率），越高越好 |
| `efficiency_trend` | string | 趋势：`improving` / `stable` / `declining` |
| `history` | array | 近 4 周逐周变化 |

**计算方法**：

1. 从 `history.training_sessions`（近 10 次）逐次解析 `avg_pace` 为速度：
   - `avg_pace` 格式为 `"M:SS/km"`，解析为 `seconds_per_km = M×60 + SS`
   - `speed_m_per_min = 1000 / (seconds_per_km / 60)`
   - `EF_i = speed_m_per_min / avg_hr_i`

2. 对 EF 序列 `[EF₁, EF₂, ..., EF_N]` 做线性回归（同 Recovery Agent 的 fatigue_trend 方法），取斜率 β：
   - `β = Σ((i − ī)(EF_i − EF̄)) / Σ((i − ī)²)`

3. β 的单位是"每次训练 EF 变化量"，判定：

| β 范围 | 趋势 | 含义 |
|--------|------|------|
| β > +0.005 | improving | 同等心率下配速在提升 |
| −0.005 ≤ β ≤ +0.005 | stable | 效率持平 |
| β < −0.005 | declining | 效率下滑，可能是疲劳信号 |
| N < 3 | insufficient_data | 历史数据不足 |

> EF 值典型范围 1.0~1.5，斜率 0.005/次 × 10 次 = 0.05，约 3~5% 变化，足以排除随机波动。

#### Aerobic Efficiency（有氧效率）

```json
{
  "aerobic_efficiency": 0.95,
  "zone2_pace_trend": "faster",
  "zone2_hr_trend": "stable"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `aerobic_efficiency` | number | 有氧效率，Zone2 配速 ÷ Zone2 心率 |
| `zone2_pace_trend` | string | Zone2 配速变化：`faster` / `stable` / `slower` |
| `zone2_hr_trend` | string | Zone2 心率变化：`lower` / `stable` / `higher` |

仅在 Zone2 占比 > 30% 的训练中计算。同配速下心率下降，或同心率下配速提升，均为正向信号。

#### Pace-HR Decoupling（配速-心率解耦）

> **⚠️ 与 hr_drift 的区别**：hr_drift 只衡量心率单方面的前后半段变化率；PHRD 衡量的是**配速与心率之间的背离程度**。心率漂了但配速同步下降 → PHRD 可能接近 0（耐力尚可）；心率漂了但配速稳定 → PHRD 高（心血管在代偿）。

**计算公式**（Joe Friel / TrainingPeaks 标准）：

PHRD = [ (HR_second_half / HR_first_half) / (Pace_second_half / Pace_first_half) − 1 ] × 100%

其中：

+ HR_first_half  = 训练前 50% trackpoints 的平均心率
+ HR_second_half = 训练后 50% trackpoints 的平均心率
+ Pace_first_half  = 训练前 50% trackpoints 的平均速度 (m/s)
+ Pace_second_half = 训练后 50% trackpoints 的平均速度 (m/s)

简化近似（当 pace 变化不大时）：
PHRD ≈ hr_drift − pace_drift。其中 pace_drift = (Pace_second_half / Pace_first_half − 1) × 100%

```json
{
  pace_hr_decoupling: 3.5,
  "status": "good"
}
```

| 解耦率 | 状态 | 含义 |
|--------|------|------|
| < 5% | good | 有氧耐力优秀，配速与心率耦合良好 |
| 5% ~ 10% | moderate | 有氧耐力一般，后半段心率上升快于配速 |
| > 10% | poor | 有氧耐力不足，需加强低强度长距离训练 |

衡量长距离训练后半段**心率相对配速**的漂移程度。解耦率低 = 耐力好。与单纯的 hr_drift 不同，PHRD 同时考虑了配速变化，更能反映真实的生理效率。

#### Zone Distribution Trend（区间分布趋势）

```json
{
  "zone_distribution": {
    "zone1": 0.08,
    "zone2": 0.55,
    "zone3": 0.15,
    "zone4": 0.12,
    "zone5": 0.10
  },
  "target_alignment": "on_track"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `current_distribution` | object | 近 10 次训练按时长加权的 zone1~zone5 占比 |
| `target_alignment` | string | 与用户运动目标的匹配度：`on_track` / `mismatch` / `insufficient_data` |

> zone 边界同 Load Agent 的 Edwards TRIMP 模型：Zone1 < 60%、Zone2 60–70%、Zone3 70–80%、Zone4 80–90%、Zone5 90–100% HRmax。

**计算方法**：

1. **按时长加权汇总**（长训练权重更高，避免短间歇跑和长 LSD 同等对待）：
   ```
   total_time = Σ duration_i          （i = 1..N，N ≤ 10）
   aggregated_zone_k = Σ(zone_k_i × duration_i) / total_time   （k = 1..5）
   ```
   若 `total_time = 0` 或无 `hr_zones` 数据 → `target_alignment` 返回 `insufficient_data`。

2. **目标匹配判定**（`target_alignment`）：根据 `user_profile.goal`，将汇总后的 zone 分布与期望对比：

| 用户 goal | 期望分布 | mismatch 条件 |
|-----------|----------|---------------|
| 5km | zone3+4 ≥ 35% | zone4+5 < 20% |
| 10km | zone2 ≥ 50% | zone2 < 35% |
| half_marathon | zone2 ≥ 55% | zone2 < 40% |
| marathon | zone2 ≥ 60% | zone2 < 45% |
| 其他 / 默认 | 不判定 | 始终 `on_track` |

   若可用 session < 3 → `insufficient_data`。
> 例如：用户 goal = "half_marathon"，但加权汇总后 zone2 不够，则 `target_alignment = "mismatch"`。

#### Technique Flags（跑步技术指标）

从 `parsed_activity` 提取 Data Agent 已计算好的跑步技术指标，与行业基准做硬编码阈值对比，生成技术异常标记。

**输入**：`avg_cadence`、`avg_gct`、`avg_vo`、`avg_vertical_ratio`、`lr_balance`

**判定规则**：

| 指标 | info | warning | critical |
|------|------|---------|----------|
| cadence 步频 (spm) | ≥ 170 | 160–170 | < 160 |
| gct 触地时间 (ms) | < 220 | 220–260 | > 260 |
| vo 垂直振幅 (cm) | < 8 | 8–10 | > 10 |
| vertical_ratio 垂直步幅比 (%) | < 8 | 8–10 | > 10 |
| lr_balance 左右平衡 | 50/50 ±1% | ±1–2% | > ±2% |

设备不支持时对应字段为 `null`，不生成该条 flag。每条 flag 包含：`metric`（指标名）、`current`（当前值）、`benchmark`（基准值）、`direction`（偏离方向：`low`/`high`/`imbalance`）、`severity`（`info`/`warning`/`critical`）。

---

### 输出

```json
{
  status: critical
  efficiency_factor: 0.0202
  efficiency_trend: stable
  efficiency_history: (9 entries)
  aerobic_efficiency: 0.0
  aerobic_trend: {'zone2_pace_trend': 'stable', 'zone2_hr_trend': 'stable'}
  pace_hr_decoupling: 36.8
  decoupling_status: poor
  zone_distribution: {'zone1': 0.067, 'zone2': 0.417, 'zone3': 0.294, 'zone4': 0.161, 'zone5': 0.061}
  target_alignment: mismatch
  technique_flags:
    - {'metric': 'cadence', 'current': 158.0, 'benchmark': 170, 'direction': 'higher_better', 'severity': 'critical'}
    - {'metric': 'gct', 'current': 250.0, 'benchmark': 220, 'direction': 'lower_better', 'severity': 'warning'}
    - {'metric': 'vertical_oscillation', 'current': 9.5, 'benchmark': 8.0, 'direction': 'lower_better', 'severity': 'warning'}    
    - {'metric': 'vertical_ratio', 'current': 9.5, 'benchmark': 8.0, 'direction': 'lower_better', 'severity': 'warning'}
    - {'metric': 'lr_balance', 'current': 47.5, 'benchmark': 50.0, 'direction': 'centered', 'severity': 'critical'}
summary: "..."
}

// 下面是整个summary部分，LLM 100% 自动生成，不是代码里硬编码的
  --- LLM 总结 ---
# 跑者综合运动表现评估

## 📊 当前状态概览

你的各项指标亮起了**多盏红灯**，综合状态评定为 **critical（危急）**，说明当前的训练模式与身体输出之间存在系统性的偏差，需要立即调 整方向。

---

## 🔴 关键问题点

### 1. 有氧耐力基础严重不足
**配速-心率解耦率高达 36.8%**（正常应 <10%），这意味着即使配速不变，你的心率在训练后段会不受控制地持续飙升。知识库中指出：        

> “马拉松比赛时间超长，由于疲劳、大量出汗导致身体脱水、体温升高等因素，越到比赛后程，心率越高。这种现象又被称为‘心率漂移’……心脏拼 命跳动，但其实效率已经明显降低。”

你的解耦率远超警戒线，反映出**有氧引擎的“油箱”太小、效率太低**——这是长期缺乏扎实的基础期训练的直接后果。

### 2. 训练强度分布失衡，违背极化训练原则
近10次心率区间分布：**Zone2 仅占 42%，Zone3+4+5 合计高达 51%**。知识库明确指出：

> “一位竞技跑步运动员，90%～97% 的训练都是以低于无氧阈速度进行的。”

你当前的中高强度占比远超合理范围，属于典型的 **“灰区训练”陷阱**——既不够轻松来打造有氧基础，又不够高质来刺激专项能力，最终两头落空 。这也是“训练目标匹配度：不匹配”的根源所在。

### 3. 跑步技术存在连锁性缺陷
| 指标 | 当前值 | 基准值 | 严重度 |
|------|--------|--------|--------|
| 步频 (cadence) | 158 spm | 170 spm | **critical** |
| 触地时间 (gct) | 250 ms | 220 ms | warning |
| 垂直振幅 | 9.5 cm | 8.0 cm | warning |
| 左右平衡 | 47.5% | 50.0% | **critical** |

**步频过低**是这些技术问题的核心诱因。知识库强调：

> “一般推荐的步频应当达到 170～180 步/分，理想值为 180 步/分以上。即使速度慢，也需要步频达到 180 步/分……步幅过大实际上大大降低了跑的效率，步幅越大，身体的重心上下起伏也就越大，落地时地面冲击力也越大。”

你的低步频（158）导致步幅被迫拉大，继而引发**垂直振幅升高、触地时间延长、着地冲击增大**的连锁反应，大幅降低跑步经济性并显著增加受 伤风险。

**左右平衡 47.5%（偏离基准 2.5%）** 提示明显的肢体不对称，知识库建议：

> “强化你的臀部肌肉与大腿外侧肌肉的力量……几乎所有人都是一侧更好、更灵活，而另一侧僵硬。”

---

## ✅ 可执行建议

### 建议一：重塑有氧基础——立刻降速、降量
在接下来 **6-8 周**，将 **80% 以上** 的训练放在 Zone2（可轻松对话的强度），严格控制 Zone3+ 的时间不超过总训练量的 20%。这是解决心 率解耦率问题的根本途径。心率漂移的改善不会立竿见影，但持续的低强度堆积会让你重新“长”出有氧根基。

使用节拍器 App（设为 170-175 bpm），每周至少 2 次在轻松跑中刻意跟随节拍。初期会感到不适应、步幅“碎”，这是正常的。知识库中明确指出 ：

> “只要增加跑者的步频，就可以大大减少跑步对于膝关节和髋关节的冲击力。”

当步频提升至 170+ 后，垂直振幅和触地时间往往会**自然改善**。同时，加入单腿力量训练（单腿臀桥、保加利亚分腿蹲）来纠正左右不平衡问题。

---
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | string | 评估日期 |
| `status` | string | 表现状态：`good` / `moderate` / `warning` / `critical` |
| `efficiency_factor` | number | 跑步效率（配速 ÷ 心率） |
| `efficiency_trend` | string | 效率趋势：`improving` / `stable` / `declining` |
| `efficiency_history` | array | 近 4 周效率变化 |
| `aerobic_efficiency` | number | 有氧效率（Zone2 配速 ÷ Zone2 心率） |
| `aerobic_trend` | object | Zone2 配速和心率的变化方向 |
| `pace_hr_decoupling` | number | 配速-心率解耦率（%） |
| `decoupling_status` | string | 解耦状态：`good` / `moderate` / `poor` |
| `zone_distribution` | object | 近 10 次心率区间分布 |
| `target_alignment` | string | 与运动目标匹配度：`on_track` / `mismatch` |
| `technique_flags` | array | 跑步技术异常标记，包含 metric、current、benchmark、direction、severity |
| `summary` | string | Agent 对表现指标的自然语言总结（调 LLM 生成） |

`technique_flags` 判定规则：

| 指标 | info | warning | critical |
|------|------|---------|----------|
| cadence 步频 (spm) | ≥ 170 | 160–170 | < 160 |
| gct 触地时间 (ms) | < 220 | 220–260 | > 260 |
| vo 垂直振幅 (cm) | < 8 | 8–10 | > 10 |
| vertical_ratio 垂直步幅比 (%) | < 8 | 8–10 | > 10 |
| lr_balance 左右平衡 | 50/50 ±1% | ±1–2% | > ±2% |

设备不支持时字段为 `null`，不生成对应 flag。

**原则**：Performance Agent 先算指标再调 LLM 生成 summary。Decision Engine 可基于 summary 或原始指标做决策。

---

## Risk Agent

### 职责边界

Risk Agent 负责：**综合训练负荷与跑步技术，评估伤病风险，提前预警**

✅ **做这些：**
- 5 项指标全部硬编码计算：
  - **injury_risk_score** — 0-100 伤病风险综合评分
  - **risk_level** — low / moderate / high / critical
  - **risk_factors** — 触发的风险因子列表，每项含 factor、value、status、source
  - **alerts** — 中文预警文本列表
  - **summary** — LLM 自然语言总结（高风险时触发 RAG 知识库检索）
- 基于 RAG 知识库（injury_risk > 60 时触发）提供伤病预防建议
- 将技术异常映射到具体伤病机理

❌ **不做这些：**
- 恢复指标计算（由 Recovery Agent 负责）
- 负荷指标计算（由 Training Load Agent 负责）
- 跑步技术异常检测（由 Performance Agent 负责）
- 训练计划调整 🚧（计划中）

---

### 输入

Risk Agent 不直接读取 ParsedActivity 原始数据，所有输入均来自其他 Agent 的产出和 User Profile。

| 来源 | 字段 | 用途 |
|------|------|------|
| `load_report` | `acwr` | 急慢性负荷比 → 负荷维度风险 |
| `load_report` | `ramp_rate` | 周跑量增长率 → 负荷增长过快风险 |
| `recovery_report` | `recovery_score` | 恢复评分 → 恢复维度风险 |
| `recovery_report` | `fatigue_trend` | 疲劳趋势 → 疲劳累积风险 |
| `recovery_report` | `recovery_debt_trend` | 恢复负债趋势 → 持续恶化风险 |
| `recovery_report` | `consecutive_hard_days` | 连续高强度天数 → 过度训练风险 |
| `performance_report` | `technique_flags` | 技术异常标记（含 metric/current/benchmark/direction/severity） |
| `user_profile` | `injury_history` | 历史伤病部位 → 加重对应风险权重 |
| `user_profile` | `age` | 年龄 → 年龄越大组织耐受力越差 |

> `technique_flags` 由 Performance Agent 产出，每条结构：`{metric, current, benchmark, direction, severity}`，severity 为 `info` / `warning` / `critical`。设备不支持时对应 flag 不生成，Risk Agent 无需处理 null。

---

### 自身计算

#### Injury Risk Score（伤病风险综合评分）

四维阈值打分，总分 0-100，纯硬编码，不依赖 LLM。

```json
{
  "injury_risk_score": 55.0,
  "risk_level": "moderate",
  "breakdown": {
    "load": 15.0,
    "recovery": 5.0,
    "technique": 20.0,
    "profile": 15.0
  }
}
```

**训练负荷因子（上限 40 分）：**

| 因子 | 触发条件 | 得分 |
|------|----------|------|
| ACWR | > 1.5 | +30 |
| ACWR | 1.3 ~ 1.5 | +15 |
| ACWR | < 0.8 | +5 |
| Ramp Rate | > 0.20 | +10 |
| Ramp Rate | 0.15 ~ 0.20 | +5 |

**恢复因子（上限 25 分）：**

| 因子 | 触发条件 | 得分 |
|------|----------|------|
| Recovery Score | < 40 | +25 |
| Recovery Score | 40 ~ 59 | +15 |
| Recovery Score | 60 ~ 79 | +5 |
| Fatigue Trend | accumulating | +5 |
| Consecutive Hard Days | ≥ 6 | +5 |
| Consecutive Hard Days | 4 ~ 5 | +3 |
| Consecutive Hard Days | 3 | +2 |

**跑步技术因子（上限 20 分）：**

基于 Performance Agent 的 `technique_flags` 中 severity 判定：

| severity | 单条得分 | 计入上限 |
|----------|----------|----------|
| critical | +8 | 最多 2 条（16 分） |
| warning | +4 | 最多 3 条（12 分） |

> 多条 critical/warning 同时存在时叠加，但总分不超过 20。

每个计入得分的 technique_flag 同时生成一条 risk_factor，其 status 对应 severity。

**用户画像因子（上限 15 分）：**

| 因子 | 触发条件 | 得分 |
|------|----------|------|
| 历史伤病 | injury_history 非空 | +10 |
| 年龄 | > 50 岁 | +8 |
| 年龄 | 40 ~ 50 岁 | +5 |

> 年龄因子取最高档，不与低档叠加。

**跨因子交互（额外 +5）：** 当旧伤部位与当前技术异常存在叠加效应时额外加分。判定逻辑：

1. 提取 `technique_flags` 中 severity ≥ warning 的 metric 列表
2. 按下表匹配 `injury_history` 中的关键词：

| 旧伤关键词 | 关联的技术异常 | 逻辑 |
|-----------|---------------|------|
| 膝盖 | cadence, gct, lr_balance | 步频过低 → 跑者膝；GCT 过长 → 髌腱炎；左右失衡 → ITBS |
| 跟腱 | cadence, gct | 步频过低 → 跨步过度牵拉跟腱；GCT 过长 → 落地冲击传导 |
| 足底 / 足底筋膜 | cadence, lr_balance | 步频过低 → 刹车效应；左右失衡 → 单侧足底过载 |
| 髋 / 髋关节 | cadence, lr_balance | 步频过低 → 髋关节撞击；左右失衡 → 单侧髋负荷 |
| 胫骨 / 应力 | gct, vo, vertical_ratio | GCT 过长 → 胫骨应力；垂直振幅/步幅比大 → 应力性骨折 |
| 其他（未匹配） | 不触发 | 无明确对应关系，保守不加分 |

3. 若存在至少一对匹配 → **额外 +5 分**

此项为跨因子叠加，不受用户画像因子 15 分上限约束。

**总分 = min(load + recovery + technique + profile + cross_interaction, 100)**，下限 0。

---

#### Risk Level（风险等级映射）

| 风险等级 | 评分范围 | 含义 |
|----------|----------|------|
| `low` | 0 ~ 30 | 风险可控，正常训练 |
| `moderate` | 31 ~ 60 | 中等风险，需关注 |
| `high` | 61 ~ 80 | 高风险，建议减量或调整 |
| `critical` | 81 ~ 100 | 极高风险，建议暂停高强度训练 |

---

#### Alerts（预警生成）

每条得分的 risk_factor 对应一条硬编码中文预警。规则：

| 因子 | status | 预警模板 |
|------|--------|----------|
| acwr | critical | `急性负荷过高，ACWR {value}，远超安全上限 1.5，损伤风险显著上升` |
| acwr | high | `ACWR 偏高（{value}），处于临界区间，建议关注恢复` |
| ramp_rate | critical | `周跑量增长过快（{value:+.0%}），远超 10% 安全线，建议立即回调` |
| ramp_rate | high | `周跑量增长偏快（{value:+.0%}），超过 15%，需控制增幅` |
| recovery_score | critical | `恢复评分严重偏低（{value:.0f}/100），身体处于过度疲劳状态，建议立即休息` |
| recovery_score | high | `恢复评分偏低（{value:.0f}/100），需加强恢复` |
| cadence | critical | `步频过低（{value} spm），跨步过度，膝盖和髋关节冲击风险显著上升` |
| cadence | high | `步频偏低（{value} spm），建议提升至 170+ 以减少着地冲击` |
| gct | critical/high | `触地时间偏长（{value}ms），落地冲击力增大，胫骨和膝盖负荷升高` |
| vo | critical/high | `垂直振幅偏大（{value}cm），落地冲击力增加，应力性骨折风险上升` |
| vertical_ratio | critical/high | `垂直步幅比偏高（{value}%），跑步经济性下降，冲击力增大` |
| lr_balance | critical | `左右严重失衡（{value}%），单侧代偿，单侧过劳损伤风险高` |
| lr_balance | high | `左右平衡偏差（{value}%），建议加强弱侧力量训练` |
| consecutive_hard_days | critical/high | `连续高强度训练 {value} 天，建议立即安排恢复日` |
| fatigue_trend | elevated | `疲劳正在累积中，需关注恢复，避免训练债滚雪球` |
| recovery_debt_trend | elevated | `恢复负债持续上升，存在过度训练风险` |

---

### 输出

| 字段                | 类型     | 说明                                                       |
| ------------------- | -------- | ---------------------------------------------------------- |
| `risk_level`        | string   | 风险等级：`low` / `moderate` / `high` / `critical`         |
| `injury_risk_score` | float    | 伤病风险评分 0-100                                         |
| `risk_factors`      | array    | 触发的风险因子列表，每项含 factor、value、status、source   |
| `alerts`            | string[] | 硬编码中文预警列表，基于风险因子自动生成                   |
| `summary`           | string   | LLM 自然语言风险总结（injury_risk > 60 时含 RAG 检索结果） |

```json
// 这部分是风险因子，数据指标异常，对应的硬编码中文预警才写入alerts
  risk_factors 风险因子 (12 条):
    [load        ] acwr                 = 1.6        (critical)
    [load        ] ramp_rate            = 0.25       (critical)
    [recovery    ] recovery_score       = 25.0       (critical)
    [recovery    ] fatigue_trend        = accumulating (elevated)
    [recovery    ] recovery_debt_trend  = worsening  (elevated)
    [recovery    ] consecutive_hard_days = 5          (high)
    [technique   ] cadence              = 155        (critical)
    [technique   ] gct                  = 280        (critical)
    [technique   ] lr_balance           = 47.0       (high)
    [user_profile] injury_history       = 膝盖         (elevated)
    [user_profile] injury_history       = 跟腱         (elevated)
    [user_profile] age                  = 55         (high)

// 下面是agent的具体输出
{
  risk_level:critical
  injury_risk_score: 100
  alerts: [
    '急性负荷过高，ACWR 1.6，远超安全上限 1.5，损伤风险显著上升', 
    '周跑量增长过快（+25%），远超 10% 安全线，建议即回调', 
    '恢复评分严重偏低（25/100），身体处于过度疲劳状态，建议立即休息', 
    '疲劳正在累积中，需关注恢复，避免训练债滚雪球', 
    '恢复复债持续上升，存在过度训练风险', 
    '连续高强度训练 5 天，建议安排恢复日', 
    '步频过低（155 spm），跨步过度，膝盖和髋关节冲击风险显著上上', 
    '触地时间偏长（280ms），落地冲击力增大，胫骨和膝盖负荷升高', 
    '左右平衡偏差（47.0%），建议加强弱侧力量训练']
summary: "..."
}

// 下面是整个summary部分，LLM 100% 自动生成，不是代码里硬编码的

**🔴 极高风险 — 必须立即停跑，优先恢复！**

> 📊 当前状态：伤病风险评分 **100/100（极高风险）**，您正处于过度训练的边缘，身体多个系统已发出严重警告信号。

---

### ⚠️ 最关键的两个风险因子

1. **急性负荷严重超标**
   - ACWR 高达 **1.6**，远超安全上限 1.5；周跑量增幅 **+25%**，是推荐安全线（10%）的 2.5 倍。
   > 📚 知识库明确指出：*“最好能够坚持10%的原则，即控制每周增加的跑量在10%以内。”*
   > **解读：** 您当前的训练量增速过于激进，直接导致膝关节和跟腱损伤风险急剧升高。

2. **恢复系统全面崩溃**
   - 恢复评分仅 **25/100**（严重偏低），疲劳正在累积，恢复负债持续恶化，且已连续高强度训练 **5 天**。
   > 📚 知识库提示：*“过度训练的典型标志有：对训练产生反感，无力，容易感染、受伤，肌肉过度紧张，双腿沉重……”*
   > **解读：** 您的身体已无法及时修复训练带来的微损伤，继续训练只会让状况恶化。

---

### 🛠️ 可执行的预防建议

1. **立即停跑 ≥ 5–7 天**
   - 当前状态下继续跑步不仅无益，反而会显著增加膝关节和跟腱的损伤风险。请转为主动恢复（散步、游泳、拉伸），直到恢复评分回升至 70  以上。

2. **纠正步频与触地时间**
   - 步频 **155 spm**、触地时间 **280 ms** 均严重偏离理想区间。
   > 📚 知识库指出：*“一般推荐的步频应当达到 170～180 步/分，理想值为 180 步/分以上……只要增加跑者的步频，就可以大大减少跑步对于膝 关节和髋关节的冲击力。”*
   > **训练建议：** 使用节拍器 App 设置 180 bpm，先从短距离练习小步幅、快步频，逐步适应后，触地时间自然会缩短，膝盖和胫骨负荷将显 著降低。

3. **整合力量与恢复周期**
   - 左右平衡偏差 **47%**，有膝盖和跟腱伤病史，年龄 55 岁。
   > 📚 知识库建议：*“每周至少两次力量训练……设定每周 1～2 天跑步休息日……在每次跑步或所有训练前，需要进行热身准备运动至少 5 分钟。”*
   > **训练建议：** 每周加入单侧力量训练（单腿蹲、提踵），强化弱侧；严格遵循“跑一休一”或“跑二休一”原则，每周至少有一天完全休息。  

---

> **总结一句话：** 您当前的训练负荷已超过身体的恢复能力，请立即停跑、优先恢复，待身体警报解除后，再以 **≤10% 周增幅** 逐步重建跑量并同步改善步频和力量平衡。您的膝盖和跟腱会感谢您现在的“暂停”。
```

---

## 分析决策层

内部架构：两个纯规则节点接收上游四个 Analyst 的输出，完成根因诊断和动作裁决。

```
Recovery Agent ─┐
Load Agent      ─┤
Performance Agent ─┤  四个 Analyst 完成指标分析
Risk Agent      ─┘
        │
        ↓
┌─ 分析决策层（纯规则，不调 LLM）──────────────┐
│                                               │
│  Recognition Engine   Decision Engine   │
│  "为什么会这样"            "该怎么办"         │
│  规则 + Pattern Matching    规则引擎          │
│                                               │
└───────────────────────┬───────────────────────┘
                        │
                        ↓
┌─ 沟通层（唯一调用 LLM）──────────────────────┐
│                                               │
│  Report Generator                             │
│  "把结论讲成故事"                             │
│  Prompt Builder → LLM → Markdown             │
│                                               │
└───────────────────────────────────────────────┘
                        │
                        ↓
                  FinalReport
```

> **关键约束**：Recognition Engine 和 Decision Engine 不调 LLM，全部使用硬编码规则 + 模式匹配。
> Report Generator 是 Coach Agent 中**唯一调用 LLM 的节点**。

---


### State Recognition Engine

**节点函数**：`recognition_node(state: AgentState) → Dict`，纯规则引擎 + Pattern Matching，不调 LLM。

职责是**识别训练数据背后的潜在生理状态（Hidden Physiological State），解释当前恢复水平、训练表现和风险状态形成的原因。**

它通过融合 Recovery Agent、Load Agent、Performance Agent、Risk Agent 的输出，发现单个 Agent 无法独立识别的跨维度模式，并将其转换为可解释的训练状态。

---

#### 回答的问题

State Recognition Engine 主要回答：

- 为什么今天状态下降？
- 为什么恢复能力下降？
- 为什么训练效率下降？
- 为什么伤病风险上升？
- 当前身体处于什么训练适应阶段？

而不是：

- 为什么成绩长期无法提升？
- 当前最大的能力短板是什么？

这些问题属于 Performance Limitation Analysis 的职责范围 🚧（计划中，当前版本未实现）。

---

#### 架构

State Recognition Engine 是一个**纯规则引擎**，不依赖 LLM，不使用工具调用。它直接读取 AgentState 中各 Analyst 的结构化报告，通过硬编码规则匹配，输出识别到的生理状态列表。

```
Recovery Report ──┐
Load Report ──────┤
Performance Report ├──→ State Recognition Engine ──→ 生理状态列表
Risk Report ──────┘        （纯规则引擎）
```

---

#### 输入

从各 Agent Report 中提取关键指标进行交叉分析：

| 来源 | 关键字段 |
|------|----------|
| Recovery Agent | `recovery_score`, `resting_hr_deviation`, `fatigue_trend`, `hrv_status` |
| Load Agent | `acwr`, `training_debt` |
| Performance Agent | `efficiency_trend`, `hr_drift`, `pace_hr_decoupling`, `technique_flags` |
| Risk Agent | `risk_level` |

---

#### 输出：StateRecognitionResult

```json
{
  "physiological_states": [
    {
      "name": "cns_fatigue",
      "priority": 1,
      "confidence": 0.81,
      "total_score": 81,
      "threshold": 60,
      "explanation": "交感神经持续激活，恢复能力下降——晨脉偏离基线 7bpm 反映自主神经失衡，运动中 HR 漂移 9% 反映中枢驱动力下降。训练质量难以维持。",
      "indicators": [
        {"metric": "resting_hr_deviation", "value": 7.0, "match": 1.0, "weight": 40, "contribution": 40},
        {"metric": "hr_drift", "value": 9.0, "match": 0.5, "weight": 30, "contribution": 15},
        {"metric": "recovery_score", "value": 52.0, "match": 0.87, "weight": 30, "contribution": 26}
      ]
    }
  ]
}
```

允许同时识别多个生理状态（Multi-State Coexistence）。被抑制的状态（如 FOR 被 CNS Fatigue 抑制）不会出现在输出列表中——抑制是引擎内部行为，输出仅包含实际触发的状态。

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 状态标识符 |
| `priority` | `int` | 响应优先级，1（最高）~ 3（最低），Decision Engine 据此排序 |
| `confidence` | `float` | Rule Match Score（0.0 ~ 1.0），`total_score / max_score` |
| `total_score` | `float` | 原始加权总分 |
| `threshold` | `int` | 触发阈值 |
| `explanation` | `str` | 模板 + 变量替换生成（非 LLM），嵌入指标实际值后供 Report Generator 直接引用 |
| `indicators` | `list` | 各指标明细 |
| `indicators[].metric` | `str` | 指标名称 |
| `indicators[].value` | `float` | 实际值 |
| `indicators[].match` | `float` | Match_Strength（0~1） |
| `indicators[].weight` | `int` | 指标权重 |
| `indicators[].contribution` | `float` | `weight × match`，实际贡献分 |

### 状态优先级映射

| 状态 | priority | 说明 |
|------|----------|------|
| Injury Onset Pattern | 1 | 最高优先——急性伤病风险，需立即响应 |
| Non-Functional Overreaching | 1 | 最高优先——已进入恶性循环，需立即减量 |
| CNS Fatigue | 1 | 最高优先——系统性恢复崩溃前兆 |
| Cardiovascular Strain | 2 | 中等优先——心血管系统过载，需关注 |
| Muscular Fatigue | 3 | 较低优先——局部问题，可边练边调 |
| Functional Overreaching | 3 | 良性信号，无需干预 |

---
#### 核心机制：Gatekeeper + 权重积分制

每个生理状态的识别拆分为两部分：

- **Gatekeeper（准入条件）**：必须满足的底层大前提（1-2 个），代表该状态的核心驱动力。不满足则一票否决，得分直接归零。
- **Scoring Indicators（积分指标）**：多个辅助表现，每个指标根据偏离程度贡献不同的分数。

**触发与 Confidence 计算**：

```
Total_Score = sum(Weight_i × Match_Strength_i)

若 Total_Score >= Trigger_Threshold → 状态触发
Confidence = min(1.0, Total_Score / Max_Possible_Score)
```

Match_Strength 的取值规则：

- 数值指标：在起评分线到满分线之间线性插值，低于起评分线 = 0，达到满分线 = 1.0
  例：`recovery_score` 满分线 `< 50`，起评分线 `< 65`，实际值 55 → `(65-55)/(65-50) = 0.67`
- 分类指标（severity / trend）：按等级固定映射（如 `critical` = 1.0，`warning` = 0.6，`good` = 0）

> 这种机制解决了传统绝对 AND 的致命问题：**一分之差错失诊断**。recovery_score 61 vs 60 不再是"触发 vs 不触发"，而是匹配度从 0.27 降到 0.20，对总分的冲击被权重稀释——Gatekeeper 把关核心前提，积分指标平滑贡献，单个指标的微小波动不会造成系统颠簸。

---
### State Library（状态库）

---

> **Injury Onset Pattern（伤病前兆模式）**

出现明显代偿动作，并伴随较高伤病风险。

**Gatekeeper**：`risk_level >= high`

| 积分指标 | 权重 | 满分条件 | 起评分线 |
|----------|------|----------|----------|
| `lr_balance` severity | 40 | `critical` | `warning`（0.5） |
| `recovery_score` | 35 | `< 50` | `< 65` |
| `risk_level` | 25 | `critical` | `high`（0.6） |

- 触发阈值：**55** / 满分：**100**

> **生理学解释**：身体已经开始通过代偿机制维持运动表现——左右平衡偏差 {lr_balance_value}（{lr_balance_severity}）是代偿的典型标志，恢复评分仅 {recovery_score}，伤病风险等级 {risk_level}。继续增加训练负荷时，急性伤病风险显著升高。

---

> **Non-Functional Overreaching（恶性超量训练）**

训练刺激已经超过身体恢复能力，表现正在下降。

**Gatekeeper**：`acwr > 1.3`

| 积分指标 | 权重 | 满分条件 | 起评分线 |
|----------|------|----------|----------|
| `recovery_score` | 40 | `< 40` | `< 55` |
| `efficiency_trend` | 30 | `declining` | `stable`（0.3） |
| `fatigue_trend` | 30 | `accumulating` | `stable`（0.3） |

- 触发阈值：**60** / 满分：**100**

> **生理学解释**：身体无法完成训练刺激的有效适应——高负荷下恢复评分仅 {recovery_score}、效率趋势 {efficiency_trend}、疲劳趋势 {fatigue_trend}，四个信号同时出现说明已经越过可适应的边界。继续训练将导致表现持续退化和伤病风险上升。

---

> **CNS Fatigue（中枢神经疲劳）**

训练压力持续积累后，自主神经系统恢复不足。

**Gatekeeper**：`acwr > 1.2` 或 `fatigue_trend == accumulating`

| 积分指标 | 权重 | 满分条件 | 起评分线 |
|----------|------|----------|----------|
| `resting_hr_deviation` | 40 | `> 5` bpm | `> 2` bpm |
| `hr_drift` | 30 | `> 8`% | `> 3`% |
| `recovery_score` | 30 | `< 50` | `< 65` |

- 触发阈值：**60** / 满分：**100**

> **生理学解释**：交感神经持续激活，恢复能力下降——晨脉偏离基线 {resting_hr_deviation}bpm 反映自主神经失衡，运动中 HR 漂移 {hr_drift}% 反映中枢驱动力下降，恢复评分 {recovery_score} 进一步确认系统性恢复不足。训练质量难以维持。

---

> **Cardiovascular Strain（心血管系统压力）**

心肺系统疲劳导致维持同样配速需要更高心率。

**Gatekeeper**：`hr_drift > 8`

| 积分指标 | 权重 | 满分条件 | 起评分线 |
|----------|------|----------|----------|
| `hr_drift` | 55 | `> 12`% | `> 8`% |
| `pace_hr_decoupling` | 45 | `> 15`% | `> 8`% |

- 触发阈值：**50** / 满分：**100**

> **生理学解释**：心血管系统出现明显疲劳特征——HR 漂移 {hr_drift}% 表明维持同样输出需要更高的心率驱动，Pace-HR 解耦率 {pace_hr_decoupling}% 进一步确认这不是暂时的环境因素，而是系统性的心血管效率下降。

---

> **Muscular Fatigue（局部肌肉疲劳）**

局部肌肉疲劳已经开始影响跑步动作，但系统性恢复尚可。

**Gatekeeper**：`cadence` severity >= `warning` 或 `gct` severity >= `warning`

| 积分指标 | 权重 | 满分条件 | 起评分线 |
|----------|------|----------|----------|
| `cadence` severity | 35 | `critical` | `warning`（0.6） |
| `gct` severity | 35 | `critical` | `warning`（0.6） |
| `recovery_score` | 30 | `> 85` | `> 70` |

- 触发阈值：**50** / 满分：**100**

> **生理学解释**：疲劳主要集中于局部肌群——步频 {cadence_severity}、触地时间 {gct_severity} 是局部肌肉疲劳的典型跑姿表现，但恢复评分 {recovery_score}（>70）说明自主神经系统和整体代谢恢复良好，尚未发展为系统性疲劳。

---

> **Functional Overreaching（良性超量恢复）**

训练刺激较高，但身体仍处于可适应范围，可能出现超量恢复。

**Gatekeeper**：`acwr > 1.2`

| 积分指标 | 权重 | 满分条件 | 起评分线 |
|----------|------|----------|----------|
| `recovery_score` | 45 | `in [50, 70]` | 区间外按距离线性衰减 |
| `efficiency_trend` | 30 | `improving` | `stable`（0.7） |
| `risk_level` | 25 | `low` | `moderate`（0.7） |

- 触发阈值：**60** / 满分：**100**

> **生理学解释**：身体正在完成训练适应——恢复评分 {recovery_score}（在 [50,70] 区间）、效率趋势 {efficiency_trend}、风险等级 {risk_level}，是超量恢复（Supercompensation）的理想前置条件。适当恢复后运动表现可能提升。

> ⚠️ **抑制规则**：若以下任一异常状态被触发，Functional Overreaching 自动抑制（得分归零，不输出）：
> - Injury Onset Pattern
> - Non-Functional Overreaching
> - CNS Fatigue
> - Cardiovascular Strain
>
> 理由：这些状态表明身体处于系统性应激中，不可能同时处于"良性适应"阶段。Muscular Fatigue 不抑制 FOR——它是局部问题，与系统性良性适应可以共存。


---

### Decision Engine

**节点函数**：`decision_node(state: AgentState) → Dict`，纯硬编码规则引擎，不调 LLM。

#### 职责

Decision Engine 的职责是在安全边界内最大化训练收益。它接收四个 Analyst + State Recognition 的输出，通过 **State Modifier → Waterfall Gate → Technique Modifier** 三步裁决，输出统一的训练动作建议。

```
State Recognition → State Modifier（调阈值）
    ↓
Waterfall: Safety → Recovery → Load → Performance → Default
    ↓                                    ↓
Technique Modifier（并行）  ←───────────┘
    ↓
RulingResult（action + modifiers）
```

优先级原则：**Risk > Recovery > Load > Performance**，高优先级直接截断，不进入下层判断。

---

#### Step 1：State Modifier（SRA 阈值调节）

State Recognition Engine 识别到的生理状态会动态调节 Gate 阈值：

```python
GATE_DEFAULTS = {
    "recovery_score_low": 40,
    "consecutive_hard_days_limit": 3,
    "hr_drift_high": 10,
    "acwr_high": 1.5,
    "acwr_moderate_low": 1.3,
    "ramp_rate_high": 0.2,
    "recovery_debt_high": 20,
}
```

| 生理状态 | severity | 调节项 |
|---------|----------|--------|
| `injury_onset_pattern` | 100 | 新增 Safety 规则：risk_level=="high" → full_rest |
| `non_functional_overreaching` | 90 | acwr_high: 1.5→1.2, action_override: full_rest |
| `cns_fatigue` | 80 | recovery_score_low: 40→55, consecutive_hard_days_limit: 3→2 |
| `cardiovascular_strain` | 70 | hr_drift_high: 10→8 |
| `muscular_fatigue` | 60 | 新增 Load 规则 |
| `functional_overreaching` | 50 | recovery_score_low: 40→35, acwr_high: 1.5→1.6 |

SRA 调节后的阈值与额外规则进入 Waterfall Gate。

---

#### Step 2：Waterfall Gate（分层裁决）

全部基于明确阈值比对，纯硬编码规则，不依赖 LLM。按层级从上到下匹配，首次命中即返回。

---

**Level 1：Safety Gate（安全层）**

| Priority | 条件 | Action |
|----------|------|--------|
| 1 | `risk_level == "critical"` | `full_rest` |
| 2 | `injury_risk_score >= 85` | `full_rest` |
| 3 | `risk_level == "high"`（SRA: injury_onset_pattern） | `full_rest` |
| 4 | `risk_level == "high" && recovery_score < 50` | `full_rest` |

---

**Level 2：Recovery Gate（恢复层）**

| Priority | 条件 | Action |
|----------|------|--------|
| 5 | `recovery_score < 40`（SRA 可调） | `recovery_run` |
| 6 | `recovery_status == "warning"` | `recovery_run` |
| 7 | `recovery_debt > 20` | `recovery_run` |
| 8 | `fatigue_trend == "accumulating"` | `recovery_run` |
| 9 | `hr_drift > 10`（SRA 可调） | `recovery_run` |

---

**Level 3：Load Gate（负荷层）**

| Priority | 条件 | Action |
|----------|------|--------|
| 10 | `acwr >= 1.5`（SRA 可调） | `reduce_load` |
| 11 | `ramp_rate >= 0.2` | `reduce_load` |
| 12 | `acwr in [1.3, 1.5)` | `reduce_load` |

SRA 可追加额外 Load 规则（muscular_fatigue 时），可由 `_load_add_rule` 指令触发。

---

**Level 4：Performance Gate（表现层）**

| Priority | 条件 | Action |
|----------|------|--------|
| 13 | `efficiency_trend == "improving"` | `quality_session` |
| 14 | `decoupling_status == "good"` | `quality_session` |

---

**Level 5：Default（默认）**

| Priority | 条件 | Action |
|----------|------|--------|
| 15 | 以上均未命中 | `normal_training` |

---

#### Step 3：Technique Modifier（技术修饰器）

**独立于 Waterfall Gate 并行执行**。根据 `performance_report.technique_flags` 生成技术修饰建议，叠加到最终裁决上。`full_rest` 时不激活。

| 规则 | 条件 | 输出 |
|------|------|------|
| `cadence_drill` | cadence flag severity == critical | 步频练习 |
| `gct_drill` | gct flag severity >= warning | 触地时间练习 |
| `vo_drill` | vo flag severity >= warning | 垂直振幅练习 |
| `lr_balance_drill` | lr_balance flag severity >= warning | 左右平衡练习 |
| `technique_focus` | warning+ flags ≥ 2 且无 critical | 综合技术关注 |

---

#### Action 汇总

| Action | 含义 | status |
|--------|------|--------|
| `full_rest` | 建议完全休息 | `critical` |
| `recovery_run` | 建议进行恢复跑 | `warning` |
| `reduce_load` | 建议减量训练 | `warning` |
| `quality_session` | 可以执行高质量训练 | `good` |
| `normal_training` | 按目标正常训练 | `good` |

---

#### 输出：RulingResult

```json
{
  "status": "warning",
  "action": "reduce_load",
  "verdict": "建议减量训练",
  "sra_context": {
    "primary_state": "cns_fatigue",
    "confidence": 0.85,
    "gate_affected": "recovery",
    "adjustment": "recovery_score 阈值 40 → 55, consecutive_hard_days 阈值 3 → 2"
  },
  "gate_hit": {
    "gate": "load",
    "rule": "acwr >= 1.5",
    "actual_value": 1.62,
    "priority": 10
  },
  "modifiers": [
    {"key": "cadence_drill", "label": "步频练习", "reason": "步频过低，需专项练习"}
  ]
}
```

| 字段 | 说明 |
|------|------|
| `status` | `critical` / `warning` / `good` |
| `action` | 5 个训练动作之一 |
| `verdict` | 中文裁决描述 |
| `sra_context` | SRA 状态识别上下文（调节了哪些阈值），无命中时为 null |
| `gate_hit` | 命中的 Gate 规则详情（gate、rule、actual_value、priority） |
| `modifiers` | Technique Modifier 产出的技术修饰列表 |

> Decision Engine 仅输出 `status` / `action` / `verdict` / `sra_context` / `gate_hit` / `modifiers`。最终的自然语言报告由后续 LLM Report Generator 基于这些结构化数据生成。

## 沟通层

### Report Generator（`report_node`）

**节点函数**：`report_node(state: AgentState) → Dict`，Coach Agent 中**唯一调用 LLM 的节点**。

#### 模块定位

报告生成节点，负责将上游所有分析结论转化为面向跑者的自然语言报告。它不分析、不诊断、不决策，只做一件事——

> 把上游所有专家结论讲成一个完整故事。

所有分析工作已由上游四个 Analyst 和两个分析决策节点完成。report_node 读取这些结论，用 LLM 生成一份面向跑者的教练报告。

---

#### 整体流程

```
recovery_report ──┐
load_report ──────┤
performance_report ┤
risk_report ──────┤
state_recognition ─┤
ruling ───────────┘
        │
        ▼
  Prompt Builder
        │
        ▼
      LLM
        │
        ▼
  FinalReport.markdown
```
---

#### Prompt Builder

唯一核心。System Prompt + 4 段叙事策略 + 直接拼接 `AgentState` 中的 6 路输出。

**System Prompt：**

```text
你是一名拥有 20 年经验的专业耐力运动教练（Chief Coach）。

你的团队已经完成了今天的训练数据分析，分为两个层级：

**分析层（专家意见）：**
- Recovery Coach：恢复状态评估
- Load Coach：训练负荷评估
- Performance Coach：运动表现评估
- Risk Coach：伤病风险评估

**诊断与裁决层（综合结论，具有最高权威）：**
- Recognition Engine：跨维度根因诊断 —— 你的团队对各专家意见交叉验证后的最终诊断
- Decision Engine：训练动作裁决 —— 基于诊断结果做出的最终训练决策

你的任务是以分析层的专家意见为参考，但以诊断与裁决层的结论为准绳，生成一份面向跑者的最终训练报告。

请严格按照以下结构组织报告：

## 📌 训练总结
用 2-3 句概括 Recognition Engine 的诊断结论 + Decision Engine 的裁决建议。

## 🏃 当前状态
整合 Recovery / Load / Performance 专家的分析意见，描述运动员当前整体状态。以 Recognition Engine 的诊断方向为线索组织内容，而非简单罗列各 Agent 结论。

## 🔍 根因分析
以 Recognition Engine 的诊断结果为核心，解释问题产生的根本原因。引用分析层专家的证据支撑诊断结论，展示指标之间如何互相印证。

## ⚠️ 风险评估
基于 Risk Coach 的分析 + Recognition Engine 识别的状态，说明继续训练可能带来的后果。若 Recognition Engine 检测到 Injury Onset Pattern 或 Non-Functional Overreaching，必须重点警告。

## 📋 训练建议
以 Decision Engine 的裁决为核心，结合 Recognition Engine 的根因，给出具体可执行的训练调整建议。解释为什么做出这个裁决，而非其他选择。

要求：
- 诊断与裁决层的结论必须作为报告的核心主线，分析层意见用于提供细节和证据
- 不要重复罗列原始指标，重点解释指标背后的意义
- 所有结论必须能追溯到上游分析结果
- 语言专业但易懂，根据用户画像调整语气
```

**上下文拼接：**

```python
recovery_text = recovery_report.get("summary") or "暂无数据"
load_text = load_report.get("summary") or "暂无数据"
performance_text = performance_report.get("summary") or "暂无数据"
risk_text = risk_report.get("summary") or "暂无数据"
recognition_text = _build_recognition_text(state_dict)
modifiers_text = _build_modifiers_text(ruling)

user_prompt = f"""
=== Recovery Coach 报告 ===
{recovery_text}

=== Load Coach 报告 ===
{load_text}

=== Performance Coach 报告 ===
{performance_text}

=== Risk Coach 报告 ===
{risk_text}

=== Recognition Engine 诊断 ===
{recognition_text}

=== Decision Engine 裁决 ===
裁决：{ruling["verdict"]}
动作：{ruling["action"]}
技术修饰：{modifiers_text}
"""

messages = [
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=user_prompt),
]
response = llm.invoke(messages)
```

---

#### 输出

LLM 一次调用直接返回 Markdown，存入 `FinalReport.markdown`。

**示例输出：**

```markdown
# 今日训练报告

## 📌 训练总结

当前恢复状态较差，检测到明显中枢疲劳迹象。建议未来 2~3 天减量训练，优先安排恢复跑与充足睡眠。

## 🏃 当前状态

恢复评分下降至 48，ACWR 上升至 1.49，训练负荷已进入高风险区间。心率漂移达 11%，表明运动中心血管系统承受较大压力。运动表现出现明显下降。

## 🔍 根因分析

检测到 CNS Fatigue（中枢神经疲劳）。近期训练量增长过快，静息心率持续高于基线 6 bpm，恢复能力已低于训练刺激需求。自主神经系统处于恢复不足状态，运动时产生代偿性高心率。

## ⚠️ 风险评估

若继续维持当前负荷，未来一周伤病风险可能进一步增加。动作代偿风险上升，需密切关注左右平衡和步频变化。

## 📋 训练建议

建议未来 2~3 天减少训练量 20%~30%，暂停阈值跑和间歇训练。优先安排 Zone1 恢复跑 30-45 分钟，配合充足睡眠和营养补充。待静息心率回归基线后再逐步恢复强度。
```

---

#### 设计原则

- **LLM 自由生成 > 固定模板**：前面所有模块已经完成了结构化分析，Report Generator 应发挥 LLM 的叙事能力，而非再用 JSON 框定输出
- **所有结论可追溯**：报告中任何判断都对应上游某个 Agent 的结论，LLM 不在报告层做新分析
- **Prompt 即策略**：叙事结构、语气控制、特殊事件处理全部写在 System Prompt 中，不单独实现模块


# RAG

## 概述

RAG 知识库为 Recovery Agent、Training Load Agent、Performance Agent、Risk Agent 提供专业运动科学知识支持。Data Agent 不使用 RAG（仅做数据解析）。

---

## 知识源

| 书籍 | 知识域 | 对应 Agent | 语言 |
|------|--------|-----------|------|
| 《丹尼尔斯经典跑步训练法》Jack Daniels | `training_load` | Training Load Agent | 英文/中文 |
| 《无伤跑法》戴剑松 | `recovery`、`risk` | Recovery Agent、Risk Agent | 中文 |
| 《丹尼尔斯经典跑步训练法》Jack Daniels | `training_load` | Training Load Agent | 英文/中文 |
| 《无伤跑法》戴剑松 | `recovery`、`risk` | Recovery Agent、Risk Agent | 中文 |
| 《80/20 Running》Matt Fitzgerald | `performance` | Performance Agent | 英文 |
| 《科学跑步》 | `recovery` | Recovery Agent | 中文 |
| 《马拉松终极训练指南》 | `performance`、`load` | Performance Agent、Load Agent | 中文 |

每条入库数据附带元数据标签 `book`、`chapter`、`domain`，供检索时过滤。

---

## 技术栈

| 组件 | 用途 |
|------|------|
| **Unstructured** | PDF 解析 |
| **Pandoc** | EPUB 解析，转为纯文本 |
| **LlamaIndex** | 文本切片（SentenceSplitter） |
| **Milvus Lite** | 本地向量库，稠密向量检索（1024 维），无需 Docker |
| **text-embedding-v3** | Embedding 模型，DashScope API，1024 维 |

---

## 核心策略

### 1. 文本切片

使用 LlamaIndex `SentenceSplitter`，chunk_size=512 tokens，overlap=50 tokens。
### 2. 稠密向量检索

使用 `text-embedding-v3` 对查询文本生成 1024 维向量，在 Milvus Lite 中通过 COSINE 相似度检索。
### 3. 元数据过滤

每个 Agent 查询时只搜自己域，砍掉 75% 无关数据：

| Agent | 检索 domain |
|-------|------------|
| Recovery Agent | `recovery` |
| Training Load Agent | `training_load` |
| Performance Agent | `performance` |
| Risk Agent | `recovery`、`risk` |

## 各 Agent 触发 RAG 的场景

| Agent | 触发条件 | 检索目标 |
|-------|----------|----------|
| **Recovery** | 静息心率偏离基线 > 5bpm | 静息心率升高与恢复不足的关联 |
| | Recovery Score < 50 | 低恢复评分下的训练调整建议 |
| **Training Load** | ACWR > 1.5 或 < 0.8 | ACWR 偏离最优区间的风险 |
| | Ramp Rate > 0.15 | 周负荷增长的安全上限 |
| **Performance** | Pace-HR Decoupling > 10% | 高解耦率的原因与改进方法 |
| | Zone2 占比偏离目标 | Zone2 训练的科学分配原则 |
| **Risk** | Injury Risk > 60 | 高伤病风险下的训练调整策略 |
| | Recovery Debt 持续上升 | 恢复负债与过度使用损伤的关系 |

**原则**：不在每次 agent 调用时都查 RAG，仅在指标异常、需要专业解释和建议时才触发。

---

## 检索链路总览

```
Agent 检测到指标异常
        │
        ▼
构造自然语言 query + domain filter
        │
        ▼
text-embedding-v3 向量化 → Milvus Lite 稠密检索 → Top-3
        │
        ▼
注入 Agent prompt 作为上下文 + 引用来源
        │
        ▼
        │
        ▼
Agent 将 RAG 检索结果注入 prompt，LLM 生成 summary（RAG 内容融入总结，不单独暴露）
```
