"""Instructions each model fails"""

from collections import Counter
from pathlib import Path
import random

from config import MODELS, RESPONSES_DIR
from instruction_following_eval import evaluation_lib
from langdetect import DetectorFactory

# fixes the language detector seed, so every run gives the same result
DetectorFactory.seed = 0

# Loads 541 prompts into inputs
inputs = evaluation_lib.read_prompt_list("instruction_following_eval/data/input_data.jsonl")

# failure is empty box = holds list of failed prompts | empty holds the number of empty responses generated.
failures ={}
empty = {}

# goes through all 3 models, gets the model name, turns it into file path, replaces the space with underscore and makes the name lowercase
# loads 541 responses and starts with empty lists of 0 count. 
for model in MODELS:
    name = model["name"]
    file = Path(RESPONSES_DIR) / f"{name.replace(' ', '_').lower()}_responses.jsonl"
    responses = evaluation_lib.read_prompt_to_response_dict(str(file))
    failures[name] = []
    empty[name] = 0

    # goes through all 541 prompts. empty or missing answer becomes "" and only gets counted, not checked.
    # runs google's checker on the rest and keeps the names of the instructions that failed.
    for inp in inputs:
        response = responses.get(inp.prompt) or ""
        if not response.strip():
            empty[name] += 1
            continue
        # same dice roll every time (google's letter checker picks a random letter for # and !)
        random.seed(0)
        output = evaluation_lib.test_instruction_following_strict(inp, responses)
        failed = [i for i, ok in zip(output.instruction_id_list, output.follow_instruction_list) if not ok]
        if failed:
            failures[name].append((inp.prompt, failed))

# counts how many times each instruction type failed for each model
counts = {}
for name in failures:
    counts[name] = Counter()
    for prompt, failed in failures[name]:
        counts[name].update(failed)

# adds up the counts of all 3 models, so the table shows the hardest instruction type first
total = Counter()
for name in counts:
    total.update(counts[name])
names = list(failures)

# table 1: failed prompts and empty answers for each model
lines = ["# Failure Analysis", ""]
lines.append("Strict mode. Empty answers are counted on their own and are not in the instruction table.")
lines.append("")

# highlights the bug i found in google's ifeval
lines += [
    "> [!IMPORTANT]",
    "> **Bug found in Google's IFEval.** 2 prompts (key 1122 and key 1129) ask the model to use `#` and `!` a number of times.",
    "> But the official `letter_frequency` checker only accepts the letters a–z. For any other character, it picks a random letter and counts that letter instead.",
    "> So these 2 checks never test `#` or `!`, and the score can change by 1 prompt between runs.",
    "> I fixed the random choice with `random.seed(0)`, so every run gives the same score.",
    "",
]

lines.append("| Model | Failed prompts | Empty answers |")
lines.append("|---|---|---|")
for name in names:
    lines.append(f"| {name} | {len(failures[name])} | {empty[name]} |")

# table 2: how many times each instruction type failed, for all 3 models
lines += ["", "## Failed Instructions by Type", ""]
lines.append("| Instruction type | " + " | ".join(names) + " |")
lines.append("|---" * (len(names) + 1) + "|")
for kind, _ in total.most_common():
    lines.append(f"| `{kind}` | " + " | ".join(str(counts[name][kind]) for name in names) + " |")

# list: every failed prompt for each model, with the names of the instructions that failed
lines += ["", "## Every Failed Prompt", ""]
for name in names:
    lines += [f"### {name}", ""]
    for prompt, failed in failures[name]:
        short = prompt.replace("\n", " ")
        if len(short) > 150:
            short = short[:150] + "..."
        lines.append(f"- {short}  ")
        lines.append("  Failed: " + ", ".join(f"`{i}`" for i in failed))
    lines.append("")

# saves the report
Path("FAILURE_ANALYSIS.md").write_text("\n".join(lines), encoding="utf-8")
print("Saved FAILURE_ANALYSIS.md")