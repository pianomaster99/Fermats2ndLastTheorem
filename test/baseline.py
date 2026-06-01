import json
import time
from pathlib import Path

from src.gemini import GeminiClient, DEFAULT_MODEL
from src.verifier import Verifier


DATASET_PATH = Path("data/pantograph_goals_goal_start_verified.json")
OUTPUT_PATH = Path("test/gemini_one_shot_results.json")


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

NUM_OF_EXAMPLES = 100

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
        "error": None,
    }

    proof = None

    try:
        state = verifier.start_goal(goal)

        prompt = make_prompt(goal, state)
        proof = gemini.ask(prompt)

        result["proof"] = proof

        print("\nGemini proof:")
        print(proof)

        final_state = verifier.run_tactic(state, proof)
        solved = verifier.is_solved(final_state)

        result["solved"] = solved
        result["final_state"] = str(final_state)

    except Exception as e:
        result["proof"] = proof
        result["error"] = str(e)
        print("\nFailed:")
        print(e)

    results.append(result)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    time.sleep(1)

solved_count = sum(1 for r in results if r["solved"])

print("\n==============================")
print(f"Solved {solved_count}/{len(results)}")
print(f"Saved results to {OUTPUT_PATH}")
print("==============================")
