# Training Agents — Multi-Agent AI Running Coach System

> A multi-agent AI running training analysis system: upload a Garmin / Coros workout file (TCX), and the system automatically produces a coach-level analysis report.

💡 Sample training data is included — you can run it right away. To use your own data, simply delete the files under `data/training/` and replace them with your own TCX files, and delete the `data/daily_checkin/` data before re-running the CLI.

## Quick Start

### Prerequisites

- Python >= 3.10
- pip (virtual environment recommended)

### Installation

```bash
git clone https://github.com/CelesteWSL/training-agents.git
cd training-agents
pip install -e .
```

### Models Used

| Layer | Model | Notes |
|-------|-------|-------|
| **LLM** (text generation) | DeepSeek V3 / GPT-4o / Claude / Gemini / Qwen / etc. | Swappable via `.env`, any OpenAI-compatible provider works |
| **Embedding** (RAG) | `text-embedding-v3` (DashScope) | Fixed 1024‑dim vectors. If you switch to a different embedding model, you must rebuild the Milvus index. |

### Supported Models

The system supports multiple LLM providers: **OpenAI** (GPT-4o, GPT-4o-mini), **DeepSeek** (V3, R1), **Anthropic** (Claude), **Google** (Gemini), **Azure OpenAI**, **Qwen** (通义千问), **GLM** (智谱), **MiniMax**, **Ollama** (local), and **OpenRouter**.

### Configure LLM

Create a `.env` file:

```env
DEEPSEEK_API_KEY=sk-xxx
LLM_PROVIDER=deepseek
QUICK_THINK_LLM=deepseek-v4-flash
OUTPUT_LANGUAGE=Chinese
```

### Three Steps

```bash
# Step 1: Create your profile
training-agents init

# Step 2: Daily check-in
training-agents checkin --date 2024-03-17 --morning-hr 55 --rpe 4 --soreness 2

# Step 3: After a run, get your report
training-agents analyze --date 2024-03-17
```

## Architecture

```
TCX File → [Data Agent] → Recovery / Load / Performance / Risk Agents (parallel)
                                    ↓
                          State Recognition Engine
                                    ↓
                          Decision Engine
                                    ↓
                          Report Generator → Markdown Report
```

## Documentation

- [中文文档](docs/training-agent.md)
- [English Documentation](docs/training-agent.en.md)