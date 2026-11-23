# Architecture: The Big Picture

## One-Paragraph Flow

The harness reads the 541 official IFEval prompts (instruction-following tasks) and sends each prompt to three open-weight LLMs through OpenRouter. OpenRouter has an OpenAI-compatible API. For each model, the harness saves the prompt-response pairs as JSONL. Then it runs the official IFEval instruction checkers on each model's responses. The checkers test each response in strict mode (the response as-is) and in loose mode (after text normalization). This gives four accuracy metrics: instruction-level and prompt-level, each in strict and loose. Finally, the harness puts the metrics in one comparison table.

**Models tested (all through OpenRouter):**

| Name | OpenRouter model ID |
|------|---------------------|
| Llama 3.3 70B | `meta-llama/llama-3.3-70b-instruct` |
| Qwen 3.5 27B | `qwen/qwen3.5-27b` |
| Gemma 4 26B | `google/gemma-4-26b-a4b-it` |

## Why This Design?

### Use Official Checkers, Not Reimplemented Ones
The IFEval checkers handle subtle edge cases:
- Strict evaluation uses the response as-is. Loose evaluation applies 8 transformations (for example, it removes the first or last line, or removes asterisks).
- Instruction types range from "contains the phrase X" to "word count in range [a, b]" to "URL pattern matching."
- Off-by-one errors or missed edge cases make scores non-comparable to the official benchmark.

Solution: Import the checkers directly from `instruction_following_eval/evaluation_lib.py`.

### Separate Generation and Scoring
API calls cost money and are slow. Checkers are fast and free. If a run crashes during scoring, the harness does not call the APIs again. You run the scoring code again.

Solution: `generate.py` → JSONL files → `score.py`. The JSONL files also act as a cache, so a partial run can resume for free.

### Parameterized Model List
To add a model, edit `config.py`, not the scripts. Each model is one dict with name, endpoint, API key env var, and model ID.

Solution: All three models go through the same code path (the OpenAI Python client pointed at OpenRouter). To swap a model, change one line in `config.py`.

### Rate Limiting and Backoff
OpenRouter returns HTTP 429 when there are too many requests. A plain loop stops at the first 429.

Solution: `config.py` sets 10,000 requests per minute (paid tier), so there is almost no wait between requests. When OpenRouter sends a 429, `generate.py` catches `RateLimitError` and retries with exponential backoff (base 2, max 120s) plus jitter.

### CSV Output
The table is useful on screen, and also as a CSV for a spreadsheet or more analysis.

Solution: `compare.py` prints the table to the terminal *and* saves it to CSV.

## Data Flow Diagram

```
                        config.py (models, rate limit, folders)
                              ↓
            ┌──────────────────────────────────────────┐
            │         generate.py                      │
            │ For each model in MODELS:                │
            │   - Check OPENROUTER_API_KEY             │
            │   - Load 541 IFEval prompts              │
            │   - For each prompt:                     │
            │     * Call OpenRouter (temperature 0,    │
            │       max_tokens 1024)                   │
            │     * Retry on 429 with backoff          │
            │     * On any other error: log it, skip   │
            │       the prompt                         │
            │     * Append response to JSONL file      │
            │   - Cache: skip prompts already saved    │
            └──────────────────────────────────────────┘
                              ↓
            responses/llama_3.3_70b_responses.jsonl
            responses/qwen_3.5_27b_responses.jsonl
            responses/gemma_4_26b_responses.jsonl
                    (each line: {"prompt": ..., "response": ...})
                              ↓
            ┌──────────────────────────────────────────┐
            │         score.py                         │
            │ For each model's response file:          │
            │   - Load responses from JSONL            │
            │   - Load original prompts + instructions │
            │   - Import official evaluation_lib       │
            │   - Turn None or missing answers into "" │
            │     (the checker then marks them failed) │
            │   - For each response:                   │
            │     * Check each instruction             │
            │     * Record strict/loose pass           │
            │   - Compute 4 metrics (prompt/instr      │
            │     × strict/loose)                      │
            │   - Save to scores.json                  │
            └──────────────────────────────────────────┘
                              ↓
            scores/scores.json
            {
              "name": "Llama 3.3 70B",
              "prompt_level_strict": 88.17,
              ...
            }
                              ↓
            ┌──────────────────────────────────────────┐
            │         compare.py                       │
            │ - Load scores.json                       │
            │ - Format as ASCII table                  │
            │ - Print to terminal                      │
            │ - Save as comparison.csv                 │
            └──────────────────────────────────────────┘
                              ↓
            Terminal:                    scores/comparison.csv
            Model            | P Strict % | ... |
            Llama 3.3 70B   | 88.2       | ... |
            ...
```

One more script reads the responses after `score.py`:
- `failure_analysis.py` checks every answer again in strict mode. It writes `FAILURE_ANALYSIS.md`: how often each instruction type failed for each model, and every failed prompt with the names of the failed instructions. Empty answers get counted on their own, not checked.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Use official IFEval checkers | A reimplementation can add bugs and make results non-comparable. The official code is subtle. |
| One provider: OpenRouter | All three models use the same OpenAI-compatible API and one API key. |
| JSONL for intermediate data | Structured, one record per line, resumable, human-readable. |
| Config as a list of dicts | To swap or add a model, edit `config.py`. |
| Exponential backoff for 429s | OpenRouter rate-limits requests. Backoff with jitter retries without a crash. |
| Cache by prompt text | Long generation runs can crash. A run resumes without new API calls. |
| Four separate metrics | Two levels (prompt, instruction) × two modes (strict, loose) give a full picture of model ability. |

## Files at a Glance

| File | Lines | Purpose |
|------|-------|---------|
| config.py | 33 | Model list, rate limit, and output folders. Edit here to add models. |
| generate.py | 184 | Call the models, save JSONL, back off on 429. |
| score.py | 175 | Run official checkers, compute metrics. |
| compare.py | 89 | Read scores, print table, save CSV. |
| failure_analysis.py | 86 | Write FAILURE_ANALYSIS.md: failed instruction types and every failed prompt. |
| download_ifeval.sh | 71 | Download the official IFEval folder (one-time setup). |
| requirements.txt | 13 | Python dependencies. |

Total: about 650 lines of project code (excluding the IFEval checker code).

## Reports

| File | What it shows |
|------|---------------|
| `BENCHMARK_REPORT.md` | First report, written by the old `detailed_analysis.py` (now replaced by `failure_analysis.py`). It skipped Qwen's empty answers, so it shows Qwen as the winner. Wrong. Kept as a record. |
| `BENCHMARK_REPORT_CORRECTED.md` | Corrected report. It counts the empty answers as failures. Winner: Llama 3.3 70B (88.2%). Qwen: 54.9%. |
| `FAILURE_ANALYSIS.md` | Written by `failure_analysis.py`. Failed instruction types per model, and every failed prompt. |

## Extending the Project

**Add a model:** Edit `config.py`. Then run `generate.py` again.

**Change metrics:** Edit the `metrics` list in `compare.py` to show different columns.

**Analyze by instruction type:** Run `failure_analysis.py`. It counts the failures for each instruction type (for example, "word count" or "contains phrase").

**Change generation settings:** Edit `temperature` or `max_tokens` in `generate.py`. Then generate again.

## Known Limitations

- **Random letter for 2 prompts.** Prompts 1122 and 1129 ask for `#` and `!`. The official `letter_frequency` checker accepts only a–z, so it picks a random letter instead (`instructions.py`, line 1343). `score.py` and `failure_analysis.py` call `random.seed(0)` before each check, so every run gives the same result.
- **Empty answers count as fails.** `score.py` turns a `None` or missing answer into `""`, so the official checkers mark it as failed. Qwen returned `None` for 218 of 541 prompts (40%).
- **Other errors skip the prompt.** If an API call fails with an error other than 429, `generate.py` logs the error and goes to the next prompt. No line is saved. In the first run, this happened for 2 Qwen prompts. A second run of `generate.py` filled them (Qwen returned `None` for both). Now all three response files have 541 lines.
- **Fixed token cap.** `max_tokens` is 1024 for every prompt. A long-answer instruction can fail because the answer was cut off.
- **Official IFEval layout.** `score.py` depends on the folder layout of the official IFEval code. If Google changes that layout, update the imports and paths.
- **No checkpoints in scoring.** If `score.py` crashes, run it again. It scores all responses again.
