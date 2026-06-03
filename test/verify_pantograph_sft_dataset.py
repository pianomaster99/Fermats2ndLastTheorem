import json
import time
from pathlib import Path


from src.verifier import Verifier


INPUT_PATH = Path("data/pantograph_supervised_tuning_dataset.json")

OUTPUT_JSON_PATH = Path("data/pantograph_supervised_tuning_dataset_verified.json")
OUTPUT_JSONL_PATH = Path("data/pantograph_supervised_tuning_dataset_verified.jsonl")
REPORT_PATH = Path("data/pantograph_supervised_tuning_dataset_verified_report.json")

PROJECT_PATH = "lean_project"

# Set to None to verify the whole dataset.
MAX_EXAMPLES = None

# Set to 0 if you want to start from the beginning.
START_INDEX = 0

SAVE_EVERY = 25
SLEEP_SECONDS = 0.0


def load_json(path: Path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

    tmp_path.replace(path)


def save_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    tmp_path.replace(path)


def load_existing_json(path: Path):
    if not path.exists():
        return []

    with open(path, "r") as f:
        return json.load(f)


def load_existing_jsonl(path: Path):
    if not path.exists():
        return []

    rows = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def get_goal(example):
    goal = example.get("goal_for_goal_start")
    if isinstance(goal, str) and goal.strip():
        return goal.strip()

    goal = example.get("goal")
    if isinstance(goal, str) and goal.strip():
        return goal.strip()

    return None


def get_solution(example):
    solution = example.get("solution")
    if isinstance(solution, str) and solution.strip():
        return solution.strip()

    suggested = example.get("suggested_tactic_sequence")
    if isinstance(suggested, list) and suggested:
        return "\n".join(str(t).strip() for t in suggested if str(t).strip())

    proof_tactics = example.get("proof_tactics")
    intro_tactic = example.get("intro_tactic")

    if isinstance(proof_tactics, list) and proof_tactics:
        tactics = []

        if isinstance(intro_tactic, str) and intro_tactic.strip():
            tactics.append(intro_tactic.strip())

        tactics.extend(str(t).strip() for t in proof_tactics if str(t).strip())
        return "\n".join(tactics)

    return None


def verify_example(verifier, example):
    goal = get_goal(example)
    solution = get_solution(example)

    if not goal:
        return False, None, "Missing goal_for_goal_start/goal."

    if not solution:
        return False, None, "Missing solution/suggested_tactic_sequence/proof_tactics."

    try:
        state = verifier.start_goal(goal)
    except Exception as e:
        return False, None, f"start_goal failed: {e}"

    try:
        final_state = verifier.run_tactic(state, solution)
    except Exception as e:
        return False, None, f"run_tactic failed: {e}"

    try:
        solved = verifier.is_solved(final_state)
    except Exception as e:
        return False, str(final_state), f"is_solved failed: {e}"

    if not solved:
        return False, str(final_state), "Tactic ran but did not solve the goal."

    return True, str(final_state), None


def make_verified_example(example, final_state):
    row = dict(example)

    row["goal_for_goal_start"] = get_goal(example)
    row["solution"] = get_solution(example)
    row["pantograph_goal_start_verified"] = True
    row["pantograph_solution_verified"] = True
    row["verified_final_state"] = final_state

    return row


def make_finetuning_row(example):
    goal = example["goal_for_goal_start"]
    initial_state = example.get("initial_state")
    solution = example["solution"]

    if initial_state:
        input_text = f"""
You are proving Lean 4 theorems in tactic mode.

Original theorem statement:
{goal}

Current Lean proof state:
{initial_state}

Return a complete Lean tactic proof that solves the current proof state.

Very important output rules:
- Return ONLY Lean tactics.
- Do NOT explain anything.
- Do NOT use markdown.
- Do NOT use triple backticks.
- Do NOT write `by`.
- Do NOT write a theorem declaration.
- Your entire response should be directly valid as the second argument to Pantograph's `goal_tactic`.
""".strip()
    else:
        input_text = f"""
You are proving Lean 4 theorems in tactic mode.

Original theorem statement:
{goal}

Return a complete Lean tactic proof that solves the goal.

Very important output rules:
- Return ONLY Lean tactics.
- Do NOT explain anything.
- Do NOT use markdown.
- Do NOT use triple backticks.
- Do NOT write `by`.
- Do NOT write a theorem declaration.
- Your entire response should be directly valid as the second argument to Pantograph's `goal_tactic`.
""".strip()

    return {
        "input_text": input_text,
        "output_text": solution,
    }


def save_progress(verified, finetuning_rows, failures, total_seen):
    save_json(OUTPUT_JSON_PATH, verified)
    save_jsonl(OUTPUT_JSONL_PATH, finetuning_rows)

    report = {
        "input_path": str(INPUT_PATH),
        "output_json_path": str(OUTPUT_JSON_PATH),
        "output_jsonl_path": str(OUTPUT_JSONL_PATH),
        "total_seen": total_seen,
        "verified_count": len(verified),
        "failed_count": len(failures),
        "failures": failures,
    }

    save_json(REPORT_PATH, report)


def main():
    print("\n==============================")
    print("Starting Pantograph verifier")
    print("==============================")

    # Important: this mirrors your working Gemini test script.
    # Start one Pantograph server with Mathlib and reuse it for all examples.
    verifier = Verifier(
        imports=["Mathlib"],
        project_path=PROJECT_PATH,
    )

    print("Pantograph verifier started.")

    print(f"Loading dataset from {INPUT_PATH}")
    data = load_json(INPUT_PATH)

    if not isinstance(data, list):
        raise RuntimeError(f"{INPUT_PATH} should be a JSON list.")

    if MAX_EXAMPLES is not None:
        data = data[:MAX_EXAMPLES]

    verified = load_existing_json(OUTPUT_JSON_PATH)
    finetuning_rows = load_existing_jsonl(OUTPUT_JSONL_PATH)

    completed_keys = set()
    for row in verified:
        if row.get("id") is not None:
            completed_keys.add(("id", row.get("id")))
        else:
            completed_keys.add(("name_goal", row.get("name"), row.get("goal_for_goal_start")))

    failures = []

    total = len(data)

    print("\n==============================")
    print(f"Verifying {total} examples")
    print(f"Starting at index {START_INDEX}")
    print(f"Already verified examples loaded: {len(verified)}")
    print("==============================")

    for i, example in enumerate(data[START_INDEX:], start=START_INDEX):
        name = example.get("name", f"example_{i}")

        if example.get("id") is not None:
            key = ("id", example.get("id"))
        else:
            key = ("name_goal", name, get_goal(example))

        if key in completed_keys:
            print(f"Skipping [{i + 1}/{total}] {name}; already verified.")
            continue

        print("\n------------------------------")
        print(f"[{i + 1}/{total}] {name}")
        print("------------------------------")

        ok, final_state, error = verify_example(verifier, example)

        if ok:
            row = make_verified_example(example, final_state or "no goals")
            verified.append(row)
            finetuning_rows.append(make_finetuning_row(row))
            completed_keys.add(key)

            print("Verified.")
        else:
            failure = {
                "index": i,
                "id": example.get("id"),
                "name": name,
                "file_path": example.get("file_path"),
                "goal_for_goal_start": get_goal(example),
                "solution": get_solution(example),
                "error": error,
                "final_state": final_state,
            }
            failures.append(failure)

            print("Failed.")
            print(error)

        if (i + 1) % SAVE_EVERY == 0:
            save_progress(
                verified=verified,
                finetuning_rows=finetuning_rows,
                failures=failures,
                total_seen=i + 1,
            )

            print("\nProgress saved.")
            print(f"Verified so far: {len(verified)}")
            print(f"Failed this run: {len(failures)}")

        if SLEEP_SECONDS > 0:
            time.sleep(SLEEP_SECONDS)

    save_progress(
        verified=verified,
        finetuning_rows=finetuning_rows,
        failures=failures,
        total_seen=total,
    )

    print("\n==============================")
    print("Done.")
    print(f"Verified total saved: {len(verified)}")
    print(f"Failed this run: {len(failures)}")
    print(f"Saved verified structured JSON to: {OUTPUT_JSON_PATH}")
    print(f"Saved fine-tuning JSONL to: {OUTPUT_JSONL_PATH}")
    print(f"Saved report to: {REPORT_PATH}")
    print("==============================")


if __name__ == "__main__":
    main()