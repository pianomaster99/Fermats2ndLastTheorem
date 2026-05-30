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

# problem = "∀ {p q : Prop}, p ∧ q → q ∧ p"
problem = "∀ {p q : Prop}, p ∧ q → p"

model = "google/gemma-4-26b-a4b-it:free"
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

problems = [
    # Propositional logic
    "∀ {p q : Prop}, p ∧ q → p",
    "∀ {p q : Prop}, p ∧ q → q",
    "∀ {p q : Prop}, p ∧ q → q ∧ p",
    "∀ {p q r : Prop}, p ∧ (q ∧ r) → (p ∧ q) ∧ r",

    "∀ {p q : Prop}, p → p ∨ q",
    "∀ {p q : Prop}, q → p ∨ q",
    "∀ {p q : Prop}, p ∨ q → q ∨ p",
    "∀ {p q r : Prop}, (p ∨ q) ∨ r → p ∨ (q ∨ r)",

    "∀ {p : Prop}, p → p",
    "∀ {p q r : Prop}, (p → q) → (q → r) → p → r",
    "∀ {p q r : Prop}, (p → q → r) → (p → q) → p → r",

    "∀ {p : Prop}, False → p",
    "∀ {p : Prop}, p → True",

    # Negation
    "∀ {p : Prop}, ¬¬¬p → ¬p",
    "∀ {p q : Prop}, (p → q) → ¬q → ¬p",
    "∀ {p q : Prop}, ¬(p ∨ q) → ¬p ∧ ¬q",
    "∀ {p q : Prop}, ¬p ∨ ¬q → ¬(p ∧ q)",

    # Classical logic
    "∀ {p : Prop}, p ∨ ¬p",
    "∀ {p : Prop}, ¬¬p → p",
    "∀ {p q : Prop}, (p → q) → (¬p ∨ q)",

    # Quantifiers
    "∀ {α : Type} {P : α → Prop} {x : α}, (∀ y, P y) → P x",
    "∀ {α : Type} {P Q : α → Prop}, (∀ x, P x ∧ Q x) → (∀ x, P x)",
    "∀ {α : Type} {P Q : α → Prop}, (∃ x, P x ∧ Q x) → ∃ x, P x",
    "∀ {α : Type} {P Q : α → Prop}, (∃ x, P x) → (∀ x, P x → Q x) → ∃ x, Q x",

    # Equality
    "∀ {α : Type} {x : α}, x = x",
    "∀ {α : Type} {x y : α}, x = y → y = x",
    "∀ {α : Type} {x y z : α}, x = y → y = z → x = z",
    "∀ {α β : Type} {f : α → β} {x y : α}, x = y → f x = f y",

    # Natural numbers
    "∀ n : Nat, n + 0 = n",
    "∀ n : Nat, 0 + n = n",
    "∀ n m : Nat, n + m = m + n",
    "∀ n m k : Nat, (n + m) + k = n + (m + k)",
    "∀ n : Nat, n * 0 = 0",
    "∀ n : Nat, n * 1 = n",

    # Sets
    "∀ {α : Type} (A B : Set α), A ∩ B ⊆ A",
    "∀ {α : Type} (A B : Set α), A ∩ B ⊆ B",
    "∀ {α : Type} (A B : Set α), A ∩ B = B ∩ A",
    "∀ {α : Type} (A B C : Set α), A ⊆ B → B ⊆ C → A ⊆ C",

    # Harder
    "∀ {p q r : Prop}, (p → q ∨ r) → (q → False) → p → r",
    "∀ {α : Type} {f g : α → α}, (∀ x, f x = g x) → f = g",
    "∀ {α : Type} {P : α → Prop}, ¬ (∃ x, P x) ↔ ∀ x, ¬ P x",
]

for problem in problems:
    model = "google/gemma-4-26b-a4b-it:free"
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