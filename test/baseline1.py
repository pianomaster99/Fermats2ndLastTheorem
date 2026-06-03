import json
import time
from pathlib import Path

from src.gemini import GeminiClient
from src.verifier import Verifier


DATASET_PATH = Path("data/pantograph_goals_goal_start_verified.json")
OUTPUT_PATH = Path("test/gemini_two_try_results.json")

NUM_OF_EXAMPLES = 100


def make_prompt(goal, state) -> str:
    return f"""
You are proving Lean 4 theorems in tactic mode.

Original theorem statement:
{goal}

Current Lean proof state:
{state}

Return a complete Lean tactic proof that solves the current proof state.

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

Bad response:
by
  intro p q h
  exact ⟨h.right, h.left⟩

You may use multi-line tactic scripts.
You may use tactics such as intro, exact, apply, rw, simp, simpa, aesop, omega, ring, ext, constructor, cases, rcases, refine, have, let, rfl.
""".strip()


def make_retry_prompt(goal, state, bad_proof, error_message) -> str:
    return f"""
You are proving Lean 4 theorems in tactic mode.

Your previous proof failed. Use the Lean error message to fix it.

Original theorem statement:
{goal}

Current Lean proof state:
{state}

Your failed Lean tactic proof:
{bad_proof}

Lean/Pantograph error message:
{error_message}

Return a corrected complete Lean tactic proof that solves the current proof state.

Very important output rules:
- Return ONLY Lean tactics.
- Do NOT explain anything.
- Do NOT use markdown.
- Do NOT use triple backticks.
- Do NOT write `by`.
- Do NOT write a theorem declaration.
- Your entire response should be directly valid as the second argument to Pantograph's `goal_tactic`.

You may use multi-line tactic scripts.
You may use tactics such as intro, exact, apply, rw, simp, simpa, aesop, omega, ring, ext, constructor, cases, rcases, refine, have, let, rfl.
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


verifier = Verifier(
    imports=["Mathlib"],
    project_path="lean_project",
)

with open(DATASET_PATH, "r") as f:
    data = json.load(f)

data = data[:NUM_OF_EXAMPLES]

gemini = GeminiClient()

results = []

for i, item in enumerate(data):
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
    }

    try:
        state = verifier.start_goal(goal)

        # -------------------------
        # First Gemini attempt
        # -------------------------
        prompt = make_prompt(goal, state)
        proof_1 = gemini.ask(prompt)

        print("\nGemini proof attempt 1:")
        print(proof_1)

        solved_1, final_state_1, error_1 = try_proof(verifier, state, proof_1)

        result["proof_attempts"].append({
            "attempt": 1,
            "proof": proof_1,
            "solved": solved_1,
            "final_state": final_state_1,
            "error": error_1,
        })

        if solved_1:
            result["solved"] = True
            result["proof"] = proof_1
            result["final_state"] = final_state_1

            print("\nSolved on attempt 1.")

        else:
            print("\nAttempt 1 failed.")
            if error_1:
                print(error_1)
            else:
                print("Proof ran but did not solve the goal.")
                print(final_state_1)

            # If Lean did not throw an error but the goal was not solved,
            # use the remaining proof state as the retry feedback.
            retry_feedback = error_1
            if retry_feedback is None:
                retry_feedback = f"Proof did not solve the goal. Final state:\n{final_state_1}"

            # -------------------------
            # Second Gemini attempt
            # -------------------------
            retry_prompt = make_retry_prompt(
                goal=goal,
                state=state,
                bad_proof=proof_1,
                error_message=retry_feedback,
            )

            proof_2 = gemini.ask(retry_prompt)

            print("\nGemini proof attempt 2:")
            print(proof_2)

            solved_2, final_state_2, error_2 = try_proof(verifier, state, proof_2)

            result["proof_attempts"].append({
                "attempt": 2,
                "proof": proof_2,
                "solved": solved_2,
                "final_state": final_state_2,
                "error": error_2,
            })

            result["solved"] = solved_2
            result["proof"] = proof_2
            result["final_state"] = final_state_2
            result["error"] = error_2

            if solved_2:
                print("\nSolved on attempt 2.")
            else:
                print("\nAttempt 2 failed.")
                if error_2:
                    print(error_2)
                else:
                    print("Proof ran but did not solve the goal.")
                    print(final_state_2)

    except Exception as e:
        result["error"] = str(e)
        print("\nFailed before proof attempts:")
        print(e)

    results.append(result)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    time.sleep(1)

solved_count = sum(1 for r in results if r["solved"])

solved_on_first_try = sum(
    1
    for r in results
    if len(r["proof_attempts"]) >= 1 and r["proof_attempts"][0]["solved"]
)

solved_on_second_try = sum(
    1
    for r in results
    if (
        len(r["proof_attempts"]) >= 2
        and not r["proof_attempts"][0]["solved"]
        and r["proof_attempts"][1]["solved"]
    )
)

print("\n==============================")
print(f"Solved {solved_count}/{len(results)}")
print(f"Solved on first try: {solved_on_first_try}")
print(f"Solved on second try: {solved_on_second_try}")
print(f"Saved results to {OUTPUT_PATH}")
print("==============================")