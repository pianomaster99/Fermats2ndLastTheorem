from graph_of_thoughts.operations.thought import Thought
from graph_of_thoughts.operations import KeepBestN, Score

from src.prover_agent.prover import ProverAgent
from src.evaluator_agent.evaluator import EvaluatorAgent

def start_problem(self, problem: str):
    #Initalize problem to check with lean
    goal_state = self.server.goal_start(problem)
    lean_state = str(goal_state).strip()
    self.lean_states[lean_state] = goal_state

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

problem = "∀ {p q : Prop}, p ∧ q → q ∧ p"
model = "google/gemma-4-31b-it:free"
prover = ProverAgent(model=model)
evaluator = EvaluatorAgent(model=model)
thought = start_problem(evaluator, problem)


#Trialling a problem
for i in range(10):
    #Printing out the thoughts
    print(f"\n=== Round {i + 1} ===")
    print("Current thought:")
    print(thought.state)

    proposals = prover.propose(thought, numThoughts=5)

    checked = [evaluator.evaluate(proposal) for proposal in proposals]
    print("\nChecked thoughts:")
    for j, checked_thought in enumerate(checked, start=1):
        print(f"\nChecked {j}:")
        print(checked_thought.state)

    solved = [t for t in checked if t.state.get("solved")]
    if solved:
        print("Solved!")
        print(solved[0].state["proof"])
        break

    valid = [t for t in checked if t.state.get("valid")]
    if not valid:
        print("No valid tactics.")
        break

    for t in valid:
        t.score = t.state.get("score", 0.0)

    thought = max(valid, key=lambda t: t.score)