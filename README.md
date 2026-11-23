# IFEval Evaluation Harness

I tested three open-weight LLMs on the [IFEval benchmark](https://arxiv.org/abs/2311.07911) (Google, 2023). IFEval checks if a model follows instructions like "write in all lowercase" or "use at least 300 words". A script checks every answer, so no human or LLM judge is needed.

## Models

All three run through [OpenRouter](https://openrouter.ai) with one API key.

| Model | OpenRouter ID |
|-------|---------------|
| Llama 3.3 70B | `meta-llama/llama-3.3-70b-instruct` |
| Qwen 3.5 27B | `qwen/qwen3.5-27b` |
| Gemma 4 26B | `google/gemma-4-26b-a4b-it` |

## Results

541 prompts per model. An empty answer counts as a fail.

| Model | Pass | Fail | No answer | Pass rate |
|-------|------|------|-----------|-----------|
| Llama 3.3 70B | 477 | 64 | 0 | **88.2%** |
| Gemma 4 26B | 469 | 72 | 0 | **86.7%** |
| Qwen 3.5 27B | 297 | 26 | 218 | **54.9%** |

**Llama 3.3 70B wins.** It answered every prompt.

Qwen looked like the winner at first (92%). But it gave no answer for 218 prompts, and my scoring script skipped them. When I counted them as fails, Qwen dropped to 54.9%. Details: [`BENCHMARK_REPORT_CORRECTED.md`](ifeval-replication/BENCHMARK_REPORT_CORRECTED.md).

Total cost: about $14.97 in OpenRouter credits.

> [!IMPORTANT]
> **I found a bug in Google's IFEval.** 2 prompts (key 1122 and key 1129) ask the model to use `#` and `!` a number of times.
> But the official `letter_frequency` checker only accepts the letters a–z. For any other character, it picks a random letter and counts that letter instead.
> So these 2 checks never test `#` or `!`, and the score can change by 1 prompt between runs.
> I fixed the random choice with `random.seed(0)`, so every run gives the same score.

## How It Works

```
541 IFEval prompts
      ↓
generate.py   → sends each prompt to each model, saves the answers
      ↓
score.py      → checks the answers with the official IFEval checkers
      ↓
compare.py    → prints a table, saves a CSV
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python -c "import nltk; nltk.download('punkt_tab')"   # data the IFEval checkers need
cd ifeval-replication          # all IFEval replication files are here
cp ../.env.example ../.env     # then add your OPENROUTER_API_KEY
bash download_ifeval.sh        # gets the official IFEval code and prompts
```

## Run

```bash
python generate.py             # get the answers (resumes if it stops)
python score.py                # score them
python compare.py              # print the table
```

Optional: `python failure_analysis.py` writes `FAILURE_ANALYSIS.md`. It shows which instructions each model fails.

## Files

All files below are in `ifeval-replication/`. Stage 2 files will go in `stage2/`.

| File | What it does |
|------|--------------|
| `config.py` | The model list. Edit this to add or swap a model. |
| `generate.py` | Gets the answers. Saves them in `responses/`. |
| `score.py` | Scores the answers. Saves `scores/scores.json`. |
| `compare.py` | Prints the table. Saves `scores/comparison.csv`. |
| `failure_analysis.py` | Writes `FAILURE_ANALYSIS.md`: which instructions failed, for every model. |
| `download_ifeval.sh` | One-time setup. Gets the IFEval code. |
| `ARCHITECTURE.md` | How the code works. |
| `BENCHMARK_REPORT.md` | My first report. Wrong: it skipped Qwen's empty answers. |
| `BENCHMARK_REPORT_CORRECTED.md` | The corrected report. |
| `FAILURE_ANALYSIS.md` | Which instruction types each model failed, and every failed prompt. |

## Known Issues

- In the first run, 2 Qwen API calls failed, so those prompts had no answer. I ran `generate.py` again to fill them, and Qwen gave empty answers for both. Now all three models have 541 responses.
- `max_tokens` is 1024, so a long answer can get cut off.

## Next Step

Next, I want to test how many instructions a model can follow at once (1, 2, 3, 5, 8, 13, and more), and if bigger models can follow more. Plan: [`docs/plans/`](docs/plans/ifeval-stack-scaling-study-pilot-plan.md).

## References

- [IFEval paper](https://arxiv.org/abs/2311.07911) (Zhou et al., 2023)
- [Official IFEval code](https://github.com/google-research/google-research/tree/master/instruction_following_eval)
