import json
from pathlib import Path

from src.prover_agent.prover import GeminiProverAgent
from src.evaluator_agent.evaluator import GeminiEvaluatorAgent
from graph_of_thoughts.operations.thought import Thought


def start_problem(evaluator, problem):
    goal_state = evaluator.server.goal_start(problem)
    lean_state = str(goal_state).strip()
    evaluator.lean_states[lean_state] = goal_state

    return Thought({
        "problem": problem,
        "lean_state": lean_state,
        "proof": [],
        "goals": [lean_state],
        "candidate": "",
        "feedback": "",
        "valid": False,
        "solved": False,
    })

DATASET_PATH = Path("data/pantograph_goals_mathlib_tactic_verified.json")

NUM_ROUNDS = 20
KEEP_N_THOUGHTS = 5
NUM_PROPOSALS = 5

#Having our model try the problem as specified in initialized_graph
def run_problem(problem, prover, evaluator, name="unknown"):
    print("\n" + "=" * 80)
    print("Problem: " + name)
    print("=" * 80)
    start_thought = start_problem(evaluator, problem)


    frontier = [start_thought]
    for round_idx in range(NUM_ROUNDS):
        print()
        print("Amount of current thoughts")
        print(len(frontier))

        next_frontier = []

        for thought in frontier:
            print(f"\n=== Round {round_idx + 1} ===")
            print("Current thought:")
            print(thought.state)

            proposals = prover.propose(thought, numThoughts=NUM_PROPOSALS)
            checked = [evaluator.evaluate(proposal) for proposal in proposals]

            print("\nChecked thoughts:")
            for j, checked_thought in enumerate(checked, start=1):
                print(f"\nChecked {j}:")
                print(checked_thought.state)

            solved = [t for t in checked if t.state.get("solved")]

            if solved:
                proof = solved[0].state["proof"]
                print("Solved!")
                print(proof)
                return {
                    "solved": True,
                    "proof": proof,
                    "error": None,
                }

            valid = [t for t in checked if t.state.get("valid")]

            if not valid:
                print("No valid tactics. Retrying same context with feedback.")
                checked.sort(key=lambda t: t.state.get("llm score", 0.0), reverse=True)
                failed_candidates = []
                for failed in checked:
                    candidate = failed.state.get("candidate")
                    if candidate and candidate not in failed_candidates:
                        failed_candidates.append(candidate)

                #Keep top 3 invalid thoughts
                for retry in checked[:3]:
                    retry.state["failed_candidates"] = failed_candidates
                    retry.state["candidate"] = ""
                    retry.state["valid"] = False
                    retry.state["solved"] = False
                    next_frontier.append(retry)

            next_frontier.extend(valid)

        #So t.score is actually defined for lambda
        for t in next_frontier:
            t.score = t.state.get("score", 0.0)
        next_frontier.sort(key=lambda t: (t.score, t.state.get("llm score", 0)),reverse=True)
        frontier = next_frontier[:KEEP_N_THOUGHTS]

        if not frontier:
            break

    print("Not solved.")
    return {
        "solved": False,
        "proof": None,
        "error": None,
    }

with DATASET_PATH.open() as f:
    data = json.load(f)

prover = GeminiProverAgent()
evaluator = GeminiEvaluatorAgent()

results = []
solved_count = 0

for i, item in enumerate(data):
    name = item.get("name", f"item_{i}")
    problem = item.get("goal_for_goal_start") or item["goal"]

    print(f"\n\nDATASET ITEM {i + 1}/{len(data)}")

    result = run_problem(problem, prover, evaluator, name=name)

    if result["solved"]:
        solved_count += 1

    results.append({
        "index": i,
        "name": name,
        "problem": problem,
        **result,
    })

    print(f"\nRunning solved count: {solved_count}/{i + 1}")

print("\n" + "=" * 80)
print("FINAL RESULTS")
print("=" * 80)
print(f"Solved {solved_count}/{len(data)}")
print(f"Accuracy: {solved_count / len(data):.2%}")