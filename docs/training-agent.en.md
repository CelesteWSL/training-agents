# Training Agents — Multi-Agent AI Running Coach System

> **Training Agents** is a multi-agent AI running training analysis system: upload a Garmin / Coros workout file (TCX), and the system automatically produces a coach-level analysis report.
>
> Think of it like a real coaching team — a conditioning coach checks load, a physio checks recovery, a technique coach checks performance, a doctor checks injury risk, and the head coach makes the final call. Five agents each focus on their specialty, with pure Python metric computation + LLM narrative generation. The decision layer uses hardcoded rules for determinism; the report layer leverages the LLM's natural language ability.
>
> **Quick Start:** `training-agents init` to create your profile → `training-agents checkin` to log your morning heart rate → after a run, `training-agents analyze --date YYYY-MM-DD` to get a full report.

> 💡 Sample training data is included in the project — you can run it right away. To use your own data, simply delete the files under data/training/ and replace them with your own TCX files, and delete the daily_checkin data before re-running the CLI.

## Quick Start

### Prerequisites

- Python >= 3.10
- pip (virtual environment recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/training-agents.git
cd training-agents

# Install dependencies
pip install -e .
```

### Configure LLM

The system configures the LLM via environment variables. Supports OpenAI, DeepSeek, Qwen, Anthropic Claude, Google Gemini, and more.

**.env file example:**

```env
# Required: configure at least one provider API key
OPENAI_API_KEY=sk-xxx
# or
DEEPSEEK_API_KEY=sk-xxx

# Optional: specify provider and model
LLM_PROVIDER=deepseek
DEEP_THINK_LLM=deepseek-v4-pro
QUICK_THINK_LLM=deepseek-v4-flash

# Optional: custom API endpoint
LLM_BACKEND_URL=https://your-proxy.com/v1

# Optional: report language (Chinese / English)
OUTPUT_LANGUAGE=English
```

> **Supported Providers:** openai / deepseek / anthropic / google / azure / qwen / glm / minimax / ollama / openrouter

### Prepare Training Data

1. Export your workout from Garmin Connect / Coros / Strava as a **TCX file**
2. Place the TCX file in the `data/training/` directory
3. Naming convention: `{description}{YYYYMMDDHHmmss}.tcx` (e.g. `Morning_Run20240317220508.tcx`)

### Three Steps

**Step 1: Create Your Profile**

```bash
training-agents init
```

> ⚠️ The interactive prompts are currently in Chinese. English users can skip this step and manually create `data/user_profile.json` (see field reference below).

Interactive setup, run only once. Field constraints and valid values:

| Field | Constraint | Valid Values / Notes |
|-------|-----------|----------------------|
| Age | 10 ~ 120 | Integer |
| Gender | `male` / `female` / `other` | Choose one |
| Height | 100 ~ 250 cm | Float |
| Weight | 30 ~ 250 kg | Float |
| Goal | `5km` / `10km` / `half_marathon` / `marathon` | Choose one (plus "other") |
| Training Level | `新手` (beginner) / `进阶` (intermediate) / `高级` (advanced) | Choose one |
| Personal Bests | Optional, press Enter to skip | Format `mm:ss`. Supported distances: `5km` `10km` `半马` (half) `全马` (full) |
| Injury History | Optional, comma-separated | Options: `膝盖` (knee) `跟腱` (achilles) `足底筋膜` (plantar) `髋关节` (hip) `胫骨/应力` (shin/stress) |
| Max HR | Optional, 100 ~ 220 | Defaults to `220 - age` if left blank |

**Manual profile for English users:**

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

**Step 2: Daily Morning Check-in**

```bash
training-agents checkin --date 2024-03-17 --morning-hr 55 --rpe 4 --soreness 2
```

- `--morning-hr`: Morning resting heart rate (bpm), **required**
- `--rpe`: Perceived exertion 1~10, optional
- `--soreness`: Muscle soreness 0~5, optional

Check in even on rest days — the system needs continuous morning HR data to determine recovery trends.

**Step 3: Analyze After a Run**

```bash
training-agents analyze --date 2024-03-17
```

The system automatically:
1. Parses the TCX file → extracts pace, heart rate, cadence, ground contact time, and dozens of other metrics
2. Runs four parallel agents analyzing recovery / load / performance / risk
3. Cross-validates across dimensions to identify hidden physiological states
4. Applies a rule engine for deterministic decisions
5. Generates a natural-language coach-level report via LLM → saved to the `reports/` directory

### View the Report

```bash
# Reports are saved in the reports/ directory
cat reports/2024-03-17_report.md
```

The report includes: training data summary → recovery/load/performance/risk analysis → state recognition conclusions → training recommendations.

## System Architecture

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
                              Final Training Report
```


# 1. Automatic Input (from TCX; FIT/GPX planned)

No manual user input required.

------

## Basic Training Data

- Time
- Distance
- Duration
- Elevation
- Speed (instantaneous m/s, from trackpoint)

------

## Heart Rate Data

- Average Heart Rate
- Maximum Heart Rate
- Heart Rate Curve

------

## Running Dynamics (when supported by device)

- Cadence
- Stride Length
- Ground Contact Time (GCT)
- Vertical Oscillation (VO)
- Left-Right Balance
- Vertical Ratio

------

## Cycling Data 🚧 (planned, not yet implemented)

- Power
- FTP
- Cadence (cycling)
- NP
- IF

------

# 2. User Lightweight Input

Recommended to keep only these.

------

## After Each Workout

### RPE (required)

```text
1~10
```

Perceived exertion.

------

### Muscle Soreness (recommended)

```text
0~5
```

Muscle soreness level.

------

# 3. Daily Input

------

## Morning Resting HR

```text
Morning resting heart rate
```

Just a single number.

------

## Energy Level (optional)

```text
1~5
```

Mental energy level.

------

# 4. User Profile (one-time setup)

Fill in once.

------

## Basic Info

- Age
- Gender
- Height
- Weight

------

## Training Goal

Examples:

- 5km
- 10km
- half_marathon
- marathon

------

## Training Level

Examples:

- Beginner (新手)
- Intermediate (进阶)
- Advanced (高级)

------

## Personal Bests (recommended)

Examples:

- 5km
- 10km
- Half Marathon (半马)
- Full Marathon (全马)

------

## Injury History

Examples:

- Knee (膝盖)
- Achilles (跟腱)
- Plantar Fascia (足底筋膜)
- Hip (髋关节)
- Shin / Stress Fracture (胫骨/应力)

# Analysis Agents

## Data Agent

### Scope

Data Agent is responsible for: **parsing TCX files → structured data + reading historical data**

```
TCX File → parse_tcx() → ParsedActivity + HistoryContext
```

✅ **Does:**
- Parse TCX files (current version; FIT/GPX planned)
- Extract all device data: sport type, time, distance, heart rate, elevation, cadence, speed
- Extract running dynamics (when supported): ground contact time, vertical oscillation, left-right balance, vertical ratio
- Compute derivable metrics: pace, stride length, heart rate zones, HR drift
- Read historical training data + daily checkins via HistoryReader and inject into history field

❌ **Does NOT:**
- Coaching advice, recovery analysis, risk prediction, trend analysis (handled by other Agents)
- User profile processing, user manual input (handled by User Profile / User Input)

---

### Input

| 来源 | 内容 |
|------|------|
| `state.activity_file` | TCX 文件路径 |
| `state.user_profile` | 用户基础画像（age、max_hr 等） |
| `state.date` | 训练日期 |

---

### 输出：ParsedActivity

与 `agent_states.py` 中 `ParsedActivity` TypedDict 完全对齐。

#### Activity Summary

| 字段 | 类型 | 说明 |
|------|------|------|
| `sport` | str | Sport type (Running / Cycling / Swimming) |
| `start_time` | str | ISO 8601 start time |
| `total_distance` | float | Total distance (meters) |
| `total_duration` | float | Total duration (seconds) |
| `avg_pace` | str | Average pace `"m:ss/km"` |
| `avg_hr` | int | Average HR (bpm) |
| `max_hr` | int | Maximum HR (bpm) |
| `hr_drift` | float | HR drift (%), HR change rate between first and second halves |
| `total_ascent` | float | Total ascent (meters) |
| `total_descent` | float | Total descent (meters) |

#### Heart Rate Zones

| 字段 | 类型 | 说明 |
|------|------|------|
| `hr_zones` | dict | `{"zone1": 0.11, "zone2": 0.15, ...}`，基于 trackpoint HR ÷ max_hr |
| `max_hr` 来源 | — | 用户设置的 `max_hr` → `220 - age` → 兜底 220 |

#### Lap Breakdown

`laps: List[LapSummary]`

| 字段 | 类型 | 说明 |
|------|------|------|
| `index` | int | Lap index |
| `distance_m` | float | Distance (meters) |
| `duration_s` | float | Duration (seconds) |
| `avg_hr` | int | Average HR |
| `max_hr` | int | Maximum HR |
| `avg_pace` | str | Pace |
| `avg_cadence` | float \| null | Cadence (corrected ×2) |
| `avg_stride_length` | float \| null | Stride length (meters) |

#### Running Technique Metrics (when supported)

| 字段 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `avg_cadence` | float \| null | spm | Average cadence, TCX raw value ×2 correction |
| `avg_stride_length` | float \| null | m | Stride length, derived from speed ÷ cadence |
| `avg_gct` | float \| null | ms | Ground contact time, requires sensor |
| `avg_vo` | float \| null | cm | Vertical oscillation, requires sensor |
| `lr_balance` | float \| null | % | Left-right balance (50.0 = balanced), requires sensor |
| `avg_vertical_ratio` | float \| null | % | Vertical ratio, sensor-first → VO ÷ stride fallback |

> Fields are `null` when not supported by device. Parser handles multi-vendor aliases such as GroundContactTime / StanceTime, LeftRightBalance / GroundContactTimeBalance.

#### Time Series (TrackpointSeries — columnar)

`trackpoints: TrackpointSeries`，各属性独立等长数组，第 i 个元素对应同一秒采样。

| 列 | 类型 | 说明 |
|------|------|------|
| `time` | List[str] | ISO 8601 timestamps |
| `distance_m` | List[float] | Cumulative distance (meters) |
| `heart_rate` | List[int] | Instantaneous HR (bpm), 0 if missing |
| `speed` | List[float] | Instantaneous speed (m/s), 0.0 if missing |
| `cadence` | List[float\|null] | Cadence (corrected), null if missing |
| `altitude` | List[float] | Altitude (meters) |
| `gct` | List[float\|null] | Ground contact time |
| `vo` | List[float\|null] | Vertical oscillation |
| `lr_balance` | List[float\|null] | Left-right balance |
| `vertical_ratio` | List[float\|null] | Vertical ratio |

> Full data passthrough, no downsampling. All columns are always equal-length and aligned. Missing values filled with 0 / null. Ready for `plt.plot(ts["time"], ts["heart_rate"])`.

#### Historical Context (HistoryContext)

Data Agent reads historical data via `HistoryReader` and injects `parsed_activity.history`. Downstream Agents do not need to read files.

| Data Source                 | Parse Path             | Time Range | Purpose                                                   |
| :-------------------------- | :---------------------- | :------- | :----------------------------------------------------------- |
| `history.daily_checkins`    | `daily_checkin/`        | 近 7 天  | 计算静息心率基线/偏离/趋势                                   |
| `history.training_sessions` | `training/` (re-parse) | 近 7 天  | 一次性读取近 28 天（≈10 次）的完整训练记录，下游 Agent 各取所需窗口 |

---

## Recovery Agent

### Scope

Recovery Agent is responsible for: **comprehensive recovery analysis, outputting recovery score and recommendations**

✅ **Does:**
- All 8 indicators computed via hardcoded rules:
  - **status** — good / moderate / warning / critical
  - **recovery_score** — 0-100
  - **fatigue_trend** — stable / recovering / accumulating
  - **resting_hr_deviation** — deviation of morning HR from 7-day baseline (bpm)
  - **hr_drift** — heart rate drift percentage
  - **hr_drift_interpretation** — <3% normal / 3-6% mild / >6% significant
  - **recovery_debt** — Σ max(0, hr_drift-3.0) × workout duration(h) × 10 (last 7 days)
  - **recovery_debt_trend** — improving / stable / worsening
  - **summary** — LLM natural language summary (including RAG-retrieved expertise)
- Provide professional recovery advice based on RAG knowledge base
- Identify risk signals of insufficient recovery

❌ **Does NOT:**
- Parse raw workout files (handled by Data Agent)
- Compute training load metrics (handled by Training Load Agent)
- Performance analysis (handled by Performance Agent)

---

### Input

#### From ParsedActivity (current workout + history pre-read)

| 字段 | 用途 |
|------|------|
| `avg_hr` | Current workout intensity baseline |
| `max_hr` | Peak stress magnitude |
| `hr_drift` | Fatigue accumulation during this workout |
| `hr_zones` | High-intensity ratio → recovery demand assessment |
| `total_duration` | Duration × intensity interaction → total recovery demand |
| `trackpoints.heart_rate` + `trackpoints.time` | HR recovery rate (post-peak decay slope) |
| `history.morning_hr_series` | 7-day morning resting HR → baseline deviation |
| `history.hr_drift_series` | Last 10 hr_drift values → fatigue trend |

#### From User Input

- `morning_hr` — Morning resting heart rate of the day
- `rpe` — Perceived exertion 1~10
- `muscle_soreness` — Muscle soreness 0~5

#### From User Profile

- `age` — Older age = slower recovery
- `training_level` — Beginner / Intermediate / Advanced
---

### Computation

#### Recovery Score

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
| `recovery_score` | number | Recovery score (0-100, higher is better) |
| `level` | string | Recovery level: `excellent` / `good` / `moderate` / `poor` |
| `factors` | object | Factors affecting recovery |

Score considers:
- Morning Resting HR deviation from baseline
- Recent training load (from Training Load Agent, or self-estimated temporarily)
- RPE / Muscle Soreness trends

#### Fatigue Trend

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
| `fatigue_trend` | string | Trend direction: `decreasing` / `stable` / `accumulating` |
| `trend_score` | number | Trend score (positive=recovering, negative=accumulating) |
| `consecutive_hard_days` | number | Consecutive high-intensity days |
| `warning` | boolean | Whether fatigue warning is triggered |

#### Resting HR Trend

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
| `resting_hr_current` | number | Current resting HR (3-day average) |
| `resting_hr_baseline` | number | Baseline resting HR (14-day average) |
| `resting_hr_deviation` | number | Deviation (positive=elevated, needs attention) |
| `resting_trend` | string | Trend: `stable` / `elevated` / `decreasing` |

Deviations exceeding baseline by 5+ bpm trigger attention.

---

### Output

| 字段                      | 类型   | 说明                                                   |
| ------------------------- | ------ | ------------------------------------------------------ |
| `status`                  | string | Recovery status: `good` / `moderate` / `warning` / `critical` |
| `recovery_score`          | float  | Recovery score 0-100                                    |
| `fatigue_trend`           | string | Fatigue trend: `stable` / `recovering` / `accumulating` |
| `resting_hr_deviation`    | float  | Morning HR deviation from baseline (bpm), positive=elevated |
| `hr_drift`                | float  | HR drift (%)                                            |
| `hr_drift_interpretation` | string | HR drift interpretation                                 |
| `recovery_debt`           | float  | Recovery debt                                           |
| `recovery_debt_trend`     | string | Recovery debt trend: `improving` / `stable` / `worsening` |
| `summary`                 | string | Natural language summary of recovery metrics (LLM-generated) |

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
| Metric | Current | Status | Interpretation |
|------|--------|------|------|
| **Recovery Score** | 29/100 | 🔴 Critical | Recovery severely insufficient, in warning zone — immediate attention needed |
| **Resting HR Deviation** | +12.0 bpm (baseline 56 → today ≈68) | 🔴 Significant | Large deviation suggests autonomic nervous system fatigue or potential overtraining |
| **Fatigue Trend** | Stable | 🟡 Watch | Fatigue not further accumulating, but current level still elevated |
| **HR Drift** | 6.5% | 🔴 Significant Fatigue | Difficulty maintaining HR during exercise, cardiovascular system under stress, high recovery demand |

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

### Scope

Training Load Agent 负责：**计算训练负荷指标，为下游 agent 提供负荷数据**

✅ **Does:**
- Compute Acute Load, Chronic Load, ACWR
- Calculate weekly volume, load growth rate
- Provide structured load data for Recovery / Risk / Performance Agents

❌ **Does NOT:**
- Recovery analysis (handled by Recovery Agent)
- Risk assessment (handled by Risk Agent)
- Training recommendations (handled by Decision Engine + Report Generator)
- User input processing
- RAG retrieval

---

### Input

From `history.training_sessions` (last 28 days of training history, pre-read by Data Agent)

| 字段 | 用途 |
|------|------|
| `total_distance` | 跑量统计（米 → 公里） |
| `total_duration` | 训练时长（秒） |
| `hr_zones` | 心率五区时间占比 → TRIMP 加权 |

不需要 User Input、User Profile、RAG。

### Load Calculation Methods

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

### Computation

#### Acute Load (last 7 days)

```
acute_load = 近 7 天每日 TRIMP 的均值（含休息日，计为 0）
```

#### Chronic Load (last 28 days)

```
chronic_load = 近 28 天每日 TRIMP 的均值（含休息日，计为 0）
```

> 按天平均（而非按训练次数平均）是 ACWR 文献的标准做法，确保休息日的恢复效果被正确纳入计算。

#### ACWR (Acute:Chronic Workload Ratio)

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

#### Weekly Volume (km)

```
weekly_volume_km = 近 7 天 total_distance 累计 / 1000
```

#### Ramp Rate (weekly volume growth)

```
ramp_rate = (本周跑量 - 上周跑量) / 上周跑量
```

| Ramp Rate | Status |
|-----------|------|
| ≤ 0.10 | safe |
| 0.10 ~ 0.15 | moderate (needs attention) |
| 0.15 ~ 0.20 | caution (medium risk) |
| > 0.20 | aggressive (high risk) |

> **Reference**: Nielsen, R.O. et al. (2014). "Training errors and running related injuries." *JOSPT*.

#### TSS 🚧 (planned, not yet implemented)

Not implemented in v1. Training Stress Score based on power or HR thresholds.

---

### Output

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

Pure data structure, no interpretation or advice. Downstream agents consume as needed.

---

## Performance Agent

### Scope

Performance Agent is responsible for: **tracking running efficiency changes and evaluating training structure**

✅ **Does:**
- Compute Efficiency Factor, Aerobic Efficiency, Pace-HR Decoupling
- Analyze heart rate zone distribution trends
- Determine whether training structure matches user goals

❌ **Does NOT:**
- Recovery analysis (handled by Recovery Agent)
- Load computation (handled by Training Load Agent)
- Risk prediction (handled by Risk Agent)
- Training plan creation 🚧 (planned)

---

### Input

#### From Training Data

| 字段 | 用途 |
|------|------|
| `avg_pace` | Current workout performance output |
| `avg_hr` | Current physiological cost (EF denominator) |
| `hr_drift` | HR drift % (computed by Data Agent, ≠ PHRD, see Pace-HR Decoupling formula below) |
| `hr_zones` | Aerobic/anaerobic distribution → training structure assessment |
| `total_ascent` + `total_descent` | Terrain correction (for LLM reference — uphill pace cannot be compared to flat) |
| `avg_cadence` + `avg_stride_length` | Running form |
| `avg_gct` + `avg_vo` + `avg_vertical_ratio` | Running economy indicators |
| `laps` | Per-km pace/HR comparison → segment efficiency analysis (for LLM reference) |
| `trackpoints.heart_rate` + `trackpoints.speed` | Per-second Pace-HR comparison → decoupling calculation |
| `history.training_sessions` | Last 10 complete training records (re-parsed), each containing `avg_hr`, `avg_pace`, `hr_zones`, `hr_drift`, `total_duration` → EF trend / zone distribution / PHRD context |

#### From User Profile

- `goal` — Target event / training type → assess training structure match
- `personal_bests` — Historical PB → performance benchmark comparison

> Note: Performance Agent and Load Agent run in parallel; Performance Agent does not depend on Load Agent output.

### Computation

#### Efficiency Factor

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
| `efficiency_factor` | number | Current running efficiency (pace ÷ HR), higher is better |
| `efficiency_trend` | string | Trend: `improving` / `stable` / `declining` |
| `history` | array | Weekly changes over last 4 weeks |

**Calculation method:**

1. Parse `avg_pace` to speed from `history.training_sessions` (last 10 sessions):
   - `avg_pace` format is `"M:SS/km"`, parse as `seconds_per_km = M×60 + SS`
   - `speed_m_per_min = 1000 / (seconds_per_km / 60)`
   - `EF_i = speed_m_per_min / avg_hr_i`

2. Perform linear regression on EF series (same method as Recovery Agent fatigue_trend), extract slope β:
   - `β = Σ((i − ī)(EF_i − EF̄)) / Σ((i − ī)²)`

3. β unit is "EF change per session", classification:

| β Range | Trend | Meaning |
|--------|------|------|
| β > +0.005 | improving | Pace improving at same HR |
| −0.005 ≤ β ≤ +0.005 | stable | Efficiency stable |
| β < −0.005 | declining | Efficiency drop, possible fatigue signal |
| N < 3 | insufficient_data | Insufficient historical data |

> Typical EF range 1.0~1.5, slope 0.005/session × 10 sessions = 0.05, ~3-5% change, sufficient to exclude random fluctuation.

#### Aerobic Efficiency

```json
{
  "aerobic_efficiency": 0.95,
  "zone2_pace_trend": "faster",
  "zone2_hr_trend": "stable"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `aerobic_efficiency` | number | Aerobic efficiency, Zone2 pace ÷ Zone2 HR |
| `zone2_pace_trend` | string | Zone2 pace trend: `faster` / `stable` / `slower` |
| `zone2_hr_trend` | string | Zone2 HR trend: `lower` / `stable` / `higher` |

Only calculated for workouts with Zone2 ratio > 30%. Same pace with lower HR, or same HR with faster pace, are both positive signals.

#### Pace-HR Decoupling

> **⚠️ Difference from hr_drift**: hr_drift only measures one-sided HR change between halves; PHRD measures **the divergence between pace and HR**. HR drifts but pace drops proportionally → PHRD may be near 0 (decent endurance); HR drifts but pace stays stable → PHRD is high (cardiovascular compensation).

**Formula** (Joe Friel / TrainingPeaks standard):

PHRD = [ (HR_second_half / HR_first_half) / (Pace_second_half / Pace_first_half) − 1 ] × 100%

Where:

+ HR_first_half  = average HR of first 50% of trackpoints
+ HR_second_half = average HR of second 50% of trackpoints
+ Pace_first_half  = average speed of first 50% of trackpoints (m/s)
+ Pace_second_half = average speed of second 50% of trackpoints (m/s)

Simplified approximation (when pace change is small):
PHRD ≈ hr_drift − pace_drift, where pace_drift = (Pace_second_half / Pace_first_half − 1) × 100%

```json
{
  pace_hr_decoupling: 3.5,
  "status": "good"
}
```

| Decoupling | Status | Meaning |
|--------|------|------|
| < 5% | good | Excellent aerobic endurance, pace-HR well coupled |
| 5% ~ 10% | moderate | Moderate aerobic endurance, HR rises faster than pace in second half |
| > 10% | poor | Insufficient aerobic endurance, need more low-intensity long distance training |

Measures HR drift **relative to pace** in the second half of long runs. Low decoupling = good endurance. Unlike simple hr_drift, PHRD accounts for pace changes, better reflecting true physiological efficiency.

#### Zone Distribution Trend

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
| `current_distribution` | object | Duration-weighted zone1~zone5 ratios from last 10 sessions |
| `target_alignment` | string | Alignment with user goal: `on_track` / `mismatch` / `insufficient_data` |

> Zone boundaries follow Load Agent Edwards TRIMP model: Zone1 < 60%, Zone2 60–70%, Zone3 70–80%, Zone4 80–90%, Zone5 90–100% HRmax.

**Calculation method:**

1. **Duration-weighted aggregation** (longer workouts weighted higher, avoiding equal treatment of short intervals and long LSD):
   ```
   total_time = Σ duration_i          (i = 1..N, N ≤ 10)
   aggregated_zone_k = Σ(zone_k_i × duration_i) / total_time   (k = 1..5)
   ```
   If `total_time = 0` or no `hr_zones` data → `target_alignment` returns `insufficient_data`.

2. **Goal match assessment** (`target_alignment`): compare aggregated zone distribution against goal expectations:

| User Goal | Expected Distribution | Mismatch Condition |
|-----------|----------|---------------|
| 5km | zone3+4 ≥ 35% | zone4+5 < 20% |
| 10km | zone2 ≥ 50% | zone2 < 35% |
| half_marathon | zone2 ≥ 55% | zone2 < 40% |
| marathon | zone2 ≥ 60% | zone2 < 45% |
| Other / default | No assessment | Always `on_track` |

   If available sessions < 3 → `insufficient_data`.
> 例如：用户 goal = "half_marathon"，但加权汇总后 zone2 不够，则 `target_alignment = "mismatch"`。

#### Technique Flags

从 `parsed_activity` 提取 Data Agent 已计算好的跑步技术指标，与行业基准做硬编码阈值对比，生成技术异常标记。

**输入**：`avg_cadence`、`avg_gct`、`avg_vo`、`avg_vertical_ratio`、`lr_balance`

**判定规则**：

| 指标 | info | warning | critical |
|------|------|---------|----------|
| cadence (spm) | ≥ 170 | 160–170 | < 160 |
| gct 触地时间 (ms) | < 220 | 220–260 | > 260 |
| vo vertical oscillation (cm) | < 8 | 8–10 | > 10 |
| vertical_ratio (%) | < 8 | 8–10 | > 10 |
| lr_balance left-right | 50/50 ±1% | ±1–2% | > ±2% |

设备不支持时对应字段为 `null`，不生成该条 flag。每条 flag 包含：`metric`（指标名）、`current`（当前值）、`benchmark`（基准值）、`direction`（偏离方向：`low`/`high`/`imbalance`）、`severity`（`info`/`warning`/`critical`）。

---

### Output

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
| cadence (spm) | ≥ 170 | 160–170 | < 160 |
| gct 触地时间 (ms) | < 220 | 220–260 | > 260 |
| vo vertical oscillation (cm) | < 8 | 8–10 | > 10 |
| vertical_ratio (%) | < 8 | 8–10 | > 10 |
| lr_balance left-right | 50/50 ±1% | ±1–2% | > ±2% |

Fields are `null` when not supported; no flag generated.

**Principle**: Performance Agent computes metrics first, then calls LLM to generate summary. Decision Engine may base decisions on summary or raw metrics.

---

## Risk Agent

### Scope

Risk Agent is responsible for: **integrating training load and running technique to assess injury risk and provide early warnings**

✅ **Does:**
- 5 项指标全部硬编码计算：
  - **injury_risk_score** — 0-100 伤病风险综合评分
  - **risk_level** — low / moderate / high / critical
  - **risk_factors** — 触发的风险因子列表，每项含 factor、value、status、source
  - **alerts** — Alert text list
  - **summary** — LLM natural language summary (triggers RAG retrieval when risk is high)
- Provide injury prevention advice via RAG knowledge base (triggered when injury_risk > 60)
- Map technique anomalies to specific injury mechanisms

❌ **Does NOT:**
- Recovery metric computation (handled by Recovery Agent)
- Load metric computation (handled by Training Load Agent)
- Running technique anomaly detection (handled by Performance Agent)
- Training plan adjustment 🚧 (planned)

---

### Input

Risk Agent does not directly read ParsedActivity raw data. All inputs come from other Agent outputs and User Profile.

| 来源 | 字段 | 用途 |
|------|------|------|
| `load_report` | `acwr` | Acute:chronic workload ratio → load dimension risk |
| `load_report` | `ramp_rate` | Weekly volume growth rate → excessive load increase risk |
| `recovery_report` | `recovery_score` | Recovery score → recovery dimension risk |
| `recovery_report` | `fatigue_trend` | Fatigue trend → fatigue accumulation risk |
| `recovery_report` | `recovery_debt_trend` | Recovery debt trend → worsening risk |
| `recovery_report` | `consecutive_hard_days` | Consecutive hard days → overtraining risk |
| `performance_report` | `technique_flags` | Technique anomaly flags (metric/current/benchmark/direction/severity) |
| `user_profile` | `injury_history` | Historical injury sites → increase corresponding risk weights |
| `user_profile` | `age` | Age → older age = lower tissue tolerance |

> `technique_flags` produced by Performance Agent, each entry: `{metric, current, benchmark, direction, severity}`. severity is `info` / `warning` / `critical`. No flag generated when device does not support the metric; Risk Agent does not need to handle null.

---

### Computation

#### Injury Risk Score

Four-dimensional threshold scoring, total 0-100, pure hardcoded rules, no LLM dependency.

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

**Training Load Factor (max 40 points):**

| 因子 | 触发条件 | 得分 |
|------|----------|------|
| ACWR | > 1.5 | +30 |
| ACWR | 1.3 ~ 1.5 | +15 |
| ACWR | < 0.8 | +5 |
| Ramp Rate | > 0.20 | +10 |
| Ramp Rate | 0.15 ~ 0.20 | +5 |

**Recovery Factor (max 25 points):**

| 因子 | 触发条件 | 得分 |
|------|----------|------|
| Recovery Score | < 40 | +25 |
| Recovery Score | 40 ~ 59 | +15 |
| Recovery Score | 60 ~ 79 | +5 |
| Fatigue Trend | accumulating | +5 |
| Consecutive Hard Days | ≥ 6 | +5 |
| Consecutive Hard Days | 4 ~ 5 | +3 |
| Consecutive Hard Days | 3 | +2 |

**Running Technique Factor (max 20 points):**

Based on severity in Performance Agent `technique_flags`:

| severity | Points Each | Cap |
|----------|----------|----------|
| critical | +8 | max 2 entries (16 pts) |
| warning | +4 | max 3 entries (12 pts) |

> Multiple critical/warning entries stack, but total capped at 20.

Each scored technique_flag also generates a risk_factor entry with status matching severity.

**User Profile Factor (max 15 points):**

| 因子 | 触发条件 | 得分 |
|------|----------|------|
| Injury History | injury_history not empty | +10 |
| 年龄 | > 50 岁 | +8 |
| 年龄 | 40 ~ 50 岁 | +5 |

> Age factor uses highest bracket only, no stacking.

**Cross-Factor Interaction (bonus +5):** Extra points when old injury sites overlap with current technique anomalies. Logic:

1. Extract metrics from `technique_flags` with severity ≥ warning
2. Match keywords from `injury_history` per table below:

| Injury Keyword | Related Technique Anomaly | Logic |
|-----------|---------------|------|
| Knee | cadence, gct, lr_balance | Low cadence → runner's knee; long GCT → patellar tendinitis; imbalance → ITBS |
| Achilles | cadence, gct | Low cadence → overstride strains achilles; long GCT → impact transmission |
| Plantar | cadence, lr_balance | Low cadence → braking effect; imbalance → unilateral plantar overload |
| Hip | cadence, lr_balance | Low cadence → hip impingement; imbalance → unilateral hip load |
| Shin / Stress | gct, vo, vertical_ratio | Long GCT → shin stress; high vertical oscillation/ratio → stress fracture |
| Other (no match) | Not triggered | No clear correspondence, conservatively no bonus |

3. If at least one match exists → **bonus +5 points**

This cross-factor bonus is not subject to the 15-point profile factor cap.

**Total = min(load + recovery + technique + profile + cross_interaction, 100)**, floor 0.

---

#### Risk Level Mapping

| Risk Level | Score Range | Meaning |
|----------|----------|------|
| `low` | 0 ~ 30 | Manageable risk, normal training |
| `moderate` | 31 ~ 60 | Moderate risk, needs attention |
| `high` | 61 ~ 80 | High risk, recommend reduction or adjustment |
| `critical` | 81 ~ 100 | Critical risk, recommend suspending high-intensity training |

---

#### Alerts

Each scored risk_factor generates one hardcoded alert. Rules:

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

### Output

| 字段                | 类型     | 说明                                                       |
| ------------------- | -------- | ---------------------------------------------------------- |
| `risk_level`        | string   | Risk level: `low` / `moderate` / `high` / `critical`      |
| `injury_risk_score` | float    | Injury risk score 0-100                                   |
| `risk_factors`      | array    | Triggered risk factors, each with factor, value, status, source |
| `alerts`            | string[] | Hardcoded alert list, auto-generated from risk factors    |
| `summary`           | string   | LLM natural language risk summary (includes RAG when injury_risk > 60) |

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

## Analysis & Decision Layer

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

> **Key Constraint**: Recognition Engine and Decision Engine do not call LLM — all hardcoded rules + pattern matching.
> Report Generator 是 Coach Agent 中**唯一调用 LLM 的节点**。

---


### State Recognition Engine

**节点函数**：`recognition_node(state: AgentState) → Dict`，纯规则引擎 + Pattern Matching，不调 LLM。

职责是**识别训练数据背后的潜在生理状态（Hidden Physiological State），解释当前恢复水平、训练表现和风险状态形成的原因。**

它通过融合 Recovery Agent、Load Agent、Performance Agent、Risk Agent 的输出，发现单个 Agent 无法独立识别的跨维度模式，并将其转换为可解释的训练状态。

---

#### Questions Answered

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

#### Architecture

The State Recognition Engine is a **pure rule engine** with no LLM dependency and no tool calls. It directly reads structured reports from each Analyst in AgentState, matches via hardcoded rules, and outputs the list of recognized physiological states.

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

#### Output: StateRecognitionResult

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

Multiple physiological states can be recognized simultaneously (Multi-State Coexistence). Suppressed states (e.g. FOR suppressed by CNS Fatigue) do not appear in the output list — suppression is an internal engine behavior, output only contains actually triggered states.

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | State identifier |
| `priority` | `int` | 响应优先级，1（最高）~ 3（最低），Decision Engine 据此排序 |
| `confidence` | `float` | Rule Match Score (0.0 ~ 1.0), `total_score / max_score` |
| `total_score` | `float` | Raw weighted total score |
| `threshold` | `int` | Trigger threshold |
| `explanation` | `str` | Template + variable substitution (non-LLM), embeds actual metric values for Report Generator direct reference |
| `indicators` | `list` | Individual indicator details |
| `indicators[].metric` | `str` | Metric name |
| `indicators[].value` | `float` | Actual value |
| `indicators[].match` | `float` | Match_Strength (0~1) |
| `indicators[].weight` | `int` | Indicator weight |
| `indicators[].contribution` | `float` | `weight × match`, actual contribution score |

### State Priority Mapping

| State | priority | Description |
|------|----------|------|
| Injury Onset Pattern | 1 | Highest priority — acute injury risk, immediate response needed |
| Non-Functional Overreaching | 1 | Highest priority — entered vicious cycle, immediate load reduction needed |
| CNS Fatigue | 1 | Highest priority — systemic recovery collapse precursor |
| Cardiovascular Strain | 2 | Medium priority — cardiovascular system overload, needs attention |
| Muscular Fatigue | 3 | Lower priority — localized issue, can train with adjustments |
| Functional Overreaching | 3 | Positive signal, no intervention needed |

---
#### Core Mechanism: Gatekeeper + Weighted Scoring

Each physiological state recognition is split into two parts:

- **Gatekeeper**: Required fundamental preconditions (1-2), representing the core driver of the state. If not met, vetoed — score resets to zero.
- **Scoring Indicators**: Multiple supporting signals, each contributing points based on deviation degree.

**Triggering and Confidence Calculation:**

```
Total_Score = sum(Weight_i × Match_Strength_i)

若 Total_Score >= Trigger_Threshold → 状态触发
Confidence = min(1.0, Total_Score / Max_Possible_Score)
```

Match_Strength value rules:

- Numeric indicators: linear interpolation between start-score line and full-score line. Below start-score = 0, at full-score = 1.0
  Example: `recovery_score` full-score line `< 50`, start-score line `< 65`, actual value 55 → `(65-55)/(65-50) = 0.67`
- Categorical indicators (severity / trend): fixed mapping by level (e.g. `critical` = 1.0, `warning` = 0.6, `good` = 0)

> This mechanism solves the fatal flaw of traditional absolute AND logic: **missing diagnosis by a single point**. recovery_score 61 vs 60 is no longer "trigger vs not trigger", but match strength drops from 0.27 to 0.20 — the impact on total score is diluted by weights. Gatekeeper guards core preconditions; scoring indicators contribute smoothly; tiny fluctuations in a single metric will not cause system thrashing.

---
### State Library

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

#### Responsibilities

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

#### Step 1: State Modifier (SRA threshold adjustment)

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

#### Step 2: Waterfall Gate (layered decision)

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

#### Step 3: Technique Modifier

**独立于 Waterfall Gate 并行执行**。根据 `performance_report.technique_flags` 生成技术修饰建议，叠加到最终裁决上。`full_rest` 时不激活。

| 规则 | 条件 | 输出 |
|------|------|------|
| `cadence_drill` | cadence flag severity == critical | 步频练习 |
| `gct_drill` | gct flag severity >= warning | 触地时间练习 |
| `vo_drill` | vo flag severity >= warning | 垂直振幅练习 |
| `lr_balance_drill` | lr_balance flag severity >= warning | 左右平衡练习 |
| `technique_focus` | warning+ flags ≥ 2 且无 critical | 综合技术关注 |

---

#### Action Summary

| Action | 含义 | status |
|--------|------|--------|
| `full_rest` | 建议完全休息 | `critical` |
| `recovery_run` | 建议进行恢复跑 | `warning` |
| `reduce_load` | 建议减量训练 | `warning` |
| `quality_session` | 可以执行高质量训练 | `good` |
| `normal_training` | 按目标正常训练 | `good` |

---

#### Output: RulingResult

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

## Communication Layer

### Report Generator（`report_node`）

**Node function**: `report_node(state: AgentState) → Dict`, the **only LLM-calling node** in the pipeline.

#### Module Positioning

报告生成节点，负责将上游所有分析结论转化为面向跑者的自然语言报告。它不分析、不诊断、不决策，只做一件事——

> 把上游所有专家结论讲成一个完整故事。

所有分析工作已由上游四个 Analyst 和两个分析决策节点完成。report_node 读取这些结论，用 LLM 生成一份面向跑者的教练报告。

---

#### Overall Flow

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

#### Output

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

#### Design Principles

- **LLM free generation > fixed templates**: All upstream modules have completed structured analysis. Report Generator should leverage LLM narrative ability rather than constraining output with JSON
- **All conclusions traceable**: Every judgment in the report corresponds to an upstream Agent conclusion. LLM does not perform new analysis at the report layer
- **Prompt is policy**: Narrative structure, tone control, and special event handling are all written in the System Prompt — no separate module implementation


# RAG

## Overview

The RAG knowledge base provides professional sports science knowledge support for Recovery Agent, Training Load Agent, Performance Agent, and Risk Agent. Data Agent does not use RAG (data parsing only).

---

## Knowledge Sources

| Book | Knowledge Domain | Target Agent | Language |
|------|--------|-----------|------|
| "Daniels' Running Formula" Jack Daniels | `training_load` | Training Load Agent | EN/ZH |
| "Injury-Free Running" Dai Jiansong | `recovery`, `risk` | Recovery Agent, Risk Agent | ZH |
| "Daniels' Running Formula" Jack Daniels | `training_load` | Training Load Agent | EN/ZH |
| "Injury-Free Running" Dai Jiansong | `recovery`, `risk` | Recovery Agent, Risk Agent | ZH |
| "80/20 Running" Matt Fitzgerald | `performance` | Performance Agent | EN |
| "Science of Running" | `recovery` | Recovery Agent | ZH |
| "Ultimate Marathon Training Guide" | `performance`, `load` | Performance Agent, Load Agent | ZH |

Each ingested data entry carries metadata tags `book`, `chapter`, `domain` for retrieval filtering.

---

## Tech Stack

| Component | Purpose |
|------|------|
| **Unstructured** | PDF parsing, auto-chunking by heading hierarchy, preserving document structure |
| **Pandoc** | EPUB parsing to plain text |
| **LlamaIndex** | Text chunking (SentenceSplitter) |
| **Milvus Lite** | Local vector database, dense vector retrieval (1024-dim), no Docker required |
| **text-embedding-v3** | Embedding model, DashScope API, 1024-dim |

---

## Core Strategies

### 1. Text Chunking

Uses LlamaIndex `SentenceSplitter`, chunk_size=512 tokens, overlap=50 tokens.

### 2. Dense Vector Retrieval

Uses `text-embedding-v3` to encode queries into 1024‑dim vectors, searched via COSINE similarity in Milvus Lite.

### 3. Metadata Filtering

Each Agent queries only its own domain, cutting 75% irrelevant data:

| Agent | Retrieval Domain |
|-------|------------|
| Recovery Agent | `recovery` |
| Training Load Agent | `training_load` |
| Performance Agent | `performance` |
| Risk Agent | `recovery`, `risk` |

## RAG Trigger Scenarios per Agent

| Agent | Trigger Condition | Retrieval Target |
|-------|----------|----------|
| **Recovery** | Resting HR deviation from baseline > 5bpm | Link between elevated resting HR and insufficient recovery |
| | Recovery Score < 50 | Training adjustment recommendations for low recovery score |
| **Training Load** | ACWR > 1.5 or < 0.8 | Risks of ACWR deviation from optimal range |
| | Ramp Rate > 0.15 | Safe upper limit for weekly load growth |
| **Performance** | Pace-HR Decoupling > 10% | Causes and improvement methods for high decoupling rate |
| | Zone2 ratio deviates from target | Scientific allocation principles for Zone2 training |
| **Risk** | Injury Risk > 60 | Training adjustment strategies under high injury risk |
| | Recovery Debt continuously rising | Relationship between recovery debt and overuse injury |

**Principle**: Do not query RAG on every agent call. Only trigger when indicators are abnormal and professional explanation/advice is needed.

---

## Retrieval Pipeline Overview

```
Agent detects abnormal indicator
        │
        ▼
Construct natural language query + domain filter
        │
        ▼
text-embedding-v3 encode → Milvus Lite dense retrieval → Top-3
        │
        ▼
Inject into Agent prompt as context + citation source
        │
        ▼
Inject into Agent prompt as context + citation source
        │
        ▼
Agent injects RAG results into prompt, LLM generates summary (RAG content integrated into summary, not separately exposed)
```
