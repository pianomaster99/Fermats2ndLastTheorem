import json
import time
from pathlib import Path

from src.gemini import GeminiClient
from src.verifier import Verifier


DATASET_PATH = Path("data/pantograph_goals_mathlib_tactic_verified.json")
OUTPUT_PATH = Path("test/gemini_five_try_results.json")

NUM_OF_EXAMPLES = 140
MAX_TRIES = 5

# Problem 86 means index 85 because Python is 0-indexed.
START_INDEX = 85


TACTIC_RULES_AND_EXAMPLES = """
Very important output rules:
- Return ONLY Lean tactics.
- Do NOT explain anything.
- Do NOT use markdown.
- Do NOT use triple backticks.
- Do NOT write `by`.
- Do NOT write a theorem declaration.
- Your entire response should be directly valid as the second argument to Pantograph's `goal_tactic`.

Good example response:
intro p q h
exact ⟨h.right, h.left⟩

Another good example response:
intro n
rfl

Another good example response:
intro R x y
simp

Another good example response:
constructor
 · intro h
   exact h
 · intro h
   exact h

Bad response:
by
  intro p q h
  exact ⟨h.right, h.left⟩

You may use multi-line tactic scripts.
You may use tactics such as intro, intros, exact, apply, rw, simp, simpa, aesop, omega, ring, ext, constructor, cases, rcases, refine, have, let, rfl.
""".strip()


def make_initial_prompt(goal, state) -> str:
    return f"""
You are proving Lean 4 theorems in tactic mode.

Original theorem statement:
{goal}

Current Lean proof state:
{state}

Return a complete Lean tactic proof that solves the current proof state.

{TACTIC_RULES_AND_EXAMPLES}
""".strip()


def format_failed_attempts(proof_attempts) -> str:
    """
    Formats all previous failed attempts so Gemini can learn from them.
    """

    if not proof_attempts:
        return "No previous failed attempts."

    chunks = []

    for attempt in proof_attempts:
        attempt_number = attempt["attempt"]
        proof = attempt["proof"]
        final_state = attempt.get("final_state")
        error = attempt.get("error")

        if error is None:
            feedback = f"Proof ran but did not solve the goal. Final state:\n{final_state}"
        else:
            feedback = f"Lean/Pantograph error:\n{error}"

        chunks.append(
            f"""
Failed attempt {attempt_number}:

Proof:
{proof}

Feedback:
{feedback}
""".strip()
        )

    return "\n\n------------------------------\n\n".join(chunks)


def make_retry_prompt(goal, state, proof_attempts) -> str:
    failed_attempts_text = format_failed_attempts(proof_attempts)

    return f"""
You are proving Lean 4 theorems in tactic mode.

Your previous proof attempts failed. Use all previous failed attempts and Lean/Pantograph feedback to produce a corrected proof.

Important:
- Do NOT repeat a failed proof unless you have clearly fixed the cause of failure.
- The new proof should be a complete replacement proof starting from the original proof state.
- Do NOT try to continue from a failed intermediate state.
- Pay close attention to whether previous attempts failed because of syntax, missing assumptions, unsolved goals, wrong theorem names, or tactics that did not close the goal.

Original theorem statement:
{goal}

Original Lean proof state:
{state}

Previous failed attempts and feedback:
{failed_attempts_text}

Return a corrected complete Lean tactic proof that solves the original proof state.

{TACTIC_RULES_AND_EXAMPLES}
""".strip()


def try_proof(verifier, state, proof):
    """
    Runs one proof attempt.

    Returns:
        (solved, final_state, error)
    """
    try:
        final_state = verifier.run_tactic(state, proof)
        solved = verifier.is_solved(final_state)
        return solved, str(final_state), None
    except Exception as e:
        return False, None, str(e)


def load_existing_results(output_path: Path):
    """
    Loads the existing output JSON file if it exists.

    This lets us resume from a later problem without deleting old results.
    """
    if not output_path.exists():
        return []

    try:
        with open(output_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"{output_path} exists but is not valid JSON. "
            "Back it up or fix it before resuming."
        )


def save_results(output_path: Path, results):
    """
    Safely saves all results.

    This rewrites the full JSON file, but because we loaded old results first,
    it preserves old entries and appends new entries to the results list.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = output_path.with_suffix(".tmp")

    with open(tmp_path, "w") as f:
        json.dump(results, f, indent=2)

    tmp_path.replace(output_path)


verifier = Verifier(
    imports=["Mathlib"],
    project_path="lean_project",
)

with open(DATASET_PATH, "r") as f:
    data = json.load(f)

data = data[:NUM_OF_EXAMPLES]

gemini = GeminiClient()

results = load_existing_results(OUTPUT_PATH)

# This prevents duplicate entries if you accidentally restart the script.
completed_indices = {r.get("index") for r in results}

for i, item in enumerate(data[START_INDEX:], start=START_INDEX):
    if i in completed_indices:
        print(f"Skipping problem {i + 1}; already in output file.")
        continue

    name = item.get("name", f"theorem_{i}")
    goal = item.get("goal_for_goal_start", item["goal"])

    print("\n==============================")
    print(f"[{i + 1}/{NUM_OF_EXAMPLES}] {name}")
    print("==============================")

    result = {
        "index": i,
        "name": name,
        "file_path": item.get("file_path"),
        "goal": goal,
        "solved": False,
        "proof": None,
        "proof_attempts": [],
        "final_state": None,
        "error": None,
        "solved_on_attempt": None,
    }

    try:
        state = verifier.start_goal(goal)

        for attempt_number in range(1, MAX_TRIES + 1):
            if attempt_number == 1:
                prompt = make_initial_prompt(goal, state)
            else:
                prompt = make_retry_prompt(
                    goal=goal,
                    state=state,
                    proof_attempts=result["proof_attempts"],
                )

            proof = gemini.ask(prompt)

            print(f"\nGemini proof attempt {attempt_number}:")
            print(proof)

            solved, final_state, error = try_proof(verifier, state, proof)

            attempt_result = {
                "attempt": attempt_number,
                "proof": proof,
                "solved": solved,
                "final_state": final_state,
                "error": error,
            }

            result["proof_attempts"].append(attempt_result)

            if solved:
                result["solved"] = True
                result["proof"] = proof
                result["final_state"] = final_state
                result["error"] = None
                result["solved_on_attempt"] = attempt_number

                print(f"\nSolved on attempt {attempt_number}.")
                break

            print(f"\nAttempt {attempt_number} failed.")

            if error:
                print(error)
            else:
                print("Proof ran but did not solve the goal.")
                print(final_state)

            result["proof"] = proof
            result["final_state"] = final_state
            result["error"] = error

        if not result["solved"]:
            print(f"\nFailed after {MAX_TRIES} attempts.")

    except Exception as e:
        result["error"] = str(e)
        print("\nFailed before proof attempts:")
        print(e)

    results.append(result)

    save_results(OUTPUT_PATH, results)

    time.sleep(1)

solved_count = sum(1 for r in results if r["solved"])

print("\n==============================")
print(f"Solved {solved_count}/{len(results)} total saved results")

for attempt_number in range(1, MAX_TRIES + 1):
    solved_on_this_attempt = sum(
        1
        for r in results
        if r.get("solved_on_attempt") == attempt_number
    )
    print(f"Solved on attempt {attempt_number}: {solved_on_this_attempt}")

print(f"Saved results to {OUTPUT_PATH}")
print("==============================")