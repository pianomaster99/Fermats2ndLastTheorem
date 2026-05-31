from graph_of_thoughts.operations.thought import Thought
from graph_of_thoughts.operations import KeepBestN, Score

from src.prover_agent.prover import ProverAgent
from src.evaluator_agent.evaluator import EvaluatorAgent
import time

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
# problem = "∀ {p q : Prop}, p ∧ q → p"
# problem = "∀ {α : Type} (xs ys : List α), (xs ++ ys).length = xs.length + ys.length"
# problem = """∀ {α β γ : Type}
#   (f : β → γ)
#   (g : α → β),
#   Function.Injective f →
#   Function.Injective g →
#   Function.Injective (f ∘ g)
# """
# problem = """
# ∀ {α β γ : Type}
#   (f : β → γ)
#   (g : α → β)
#   (xs : List α),
#   xs.map (f ∘ g) = (xs.map g).map f
# """

problem = """
∀ {α : Type} (xs ys : List α),
  (xs ++ ys).reverse = ys.reverse ++ xs.reverse"""
problem = "∀ a b : Nat, (a + b) * (a + b) = a * a + 2 * a * b + b * b"
problem =     "IsOpen ({x : ℝ | x < 1})"
problem = """
∀ {α : Type*} [TopologicalSpace α] [QuasiSeparatedSpace α]
  {U V : Set α},
  IsCompact U → IsCompact V → IsOpen U → IsOpen V → IsCompact (U ∩ V)
"""
problem = "∀ {α β γ : Type*} (f : β → γ) (g : α → β), Function.Injective f → Function.Injective g → Function.Injective (f ∘ g)"
problem = """
∀ {α : Type*} (xs : List α),
  xs.reverse.reverse = xs
"""

print("hello")
# cantor_problem = """
# import Mathlib

# ∀ {α : Type}
#   (f : α → Set α),
#   ¬ Function.Surjective f"""
model = "meta-llama/llama-3.3-70b-instruct:free'"
prover = ProverAgent(model=model)
evaluator = EvaluatorAgent(model=model)
start_thought = start_problem(evaluator, problem)

#Keeping top _ thoughts
keep_n_thoughts = 3

frontier = [start_thought]
#Trialling a problem
for i in range(10):
    print("Amount of current thoughts")
    print(len(frontier))
    next_frontier = []
    #Printing out the thoughts
    for thought in frontier:
        print(f"\n=== Round {i + 1} ===")
        print("Current thought:")
        print(thought.state)

        proposals = prover.propose(thought, numThoughts=3)

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

        #Valid thoughts
        valid = [t for t in checked if t.state.get("valid")]

        #Invalid thoughts
        invalid = [t for t in checked if not t.state.get("valid")]

        #No valid branches
        if not valid:
            print("No valid tactics. Retrying same context with feedback.")

            # Pick the failed attempt with confident proposal.
            retry = max(checked, key=lambda t: t.state.get("confidence", 0.0))
            
            failed_candidates = retry.state.get("failed_candidates", [])

            #Having list of failed candidates
            if retry.state["candidate"] and retry.state["candidate"] not in failed_candidates:
                failed_candidates.append(retry.state["candidate"])

            retry.state["failed_candidates"] = failed_candidates

            retry.state["candidate"] = ""

            next_frontier.append(retry)
            #Retrying most confident proposal in same lean state
            continue

        #Adding thoughts which work
        next_frontier.extend(valid)

    for t in next_frontier:
        t.score = t.state.get("score", 0.0)
    
    next_frontier.sort(key=lambda t: t.score, reverse=True)
    frontier = next_frontier[:keep_n_thoughts]


# problems = [
#     # Propositional logic
#     "∀ {p q : Prop}, p ∧ q → p",
#     "∀ {p q : Prop}, p ∧ q → q",
#     "∀ {p q : Prop}, p ∧ q → q ∧ p",
#     "∀ {p q r : Prop}, p ∧ (q ∧ r) → (p ∧ q) ∧ r",

#     "∀ {p q : Prop}, p → p ∨ q",
#     "∀ {p q : Prop}, q → p ∨ q",
#     "∀ {p q : Prop}, p ∨ q → q ∨ p",
#     "∀ {p q r : Prop}, (p ∨ q) ∨ r → p ∨ (q ∨ r)",

#     "∀ {p : Prop}, p → p",
#     "∀ {p q r : Prop}, (p → q) → (q → r) → p → r",
#     "∀ {p q r : Prop}, (p → q → r) → (p → q) → p → r",

#     "∀ {p : Prop}, False → p",
#     "∀ {p : Prop}, p → True",

#     # Negation
#     "∀ {p : Prop}, ¬¬¬p → ¬p",
#     "∀ {p q : Prop}, (p → q) → ¬q → ¬p",
#     "∀ {p q : Prop}, ¬(p ∨ q) → ¬p ∧ ¬q",
#     "∀ {p q : Prop}, ¬p ∨ ¬q → ¬(p ∧ q)",

#     # Classical logic
#     "∀ {p : Prop}, p ∨ ¬p",
#     "∀ {p : Prop}, ¬¬p → p",
#     "∀ {p q : Prop}, (p → q) → (¬p ∨ q)",

#     # Quantifiers
#     "∀ {α : Type} {P : α → Prop} {x : α}, (∀ y, P y) → P x",
#     "∀ {α : Type} {P Q : α → Prop}, (∀ x, P x ∧ Q x) → (∀ x, P x)",
#     "∀ {α : Type} {P Q : α → Prop}, (∃ x, P x ∧ Q x) → ∃ x, P x",
#     "∀ {α : Type} {P Q : α → Prop}, (∃ x, P x) → (∀ x, P x → Q x) → ∃ x, Q x",

#     # Equality
#     "∀ {α : Type} {x : α}, x = x",
#     "∀ {α : Type} {x y : α}, x = y → y = x",
#     "∀ {α : Type} {x y z : α}, x = y → y = z → x = z",
#     "∀ {α β : Type} {f : α → β} {x y : α}, x = y → f x = f y",

#     # Natural numbers
#     "∀ n : Nat, n + 0 = n",
#     "∀ n : Nat, 0 + n = n",
#     "∀ n m : Nat, n + m = m + n",
#     "∀ n m k : Nat, (n + m) + k = n + (m + k)",
#     "∀ n : Nat, n * 0 = 0",
#     "∀ n : Nat, n * 1 = n",

#     # Sets
#     "∀ {α : Type} (A B : Set α), A ∩ B ⊆ A",
#     "∀ {α : Type} (A B : Set α), A ∩ B ⊆ B",
#     "∀ {α : Type} (A B : Set α), A ∩ B = B ∩ A",
#     "∀ {α : Type} (A B C : Set α), A ⊆ B → B ⊆ C → A ⊆ C",

#     # Harder
#     "∀ {p q r : Prop}, (p → q ∨ r) → (q → False) → p → r",
#     "∀ {α : Type} {f g : α → α}, (∀ x, f x = g x) → f = g",
#     "∀ {α : Type} {P : α → Prop}, ¬ (∃ x, P x) ↔ ∀ x, ¬ P x",
# ]

# for problem in problems:
#     model = "openai/gpt-oss-20b:free"
#     prover = ProverAgent(model=model)
#     evaluator = EvaluatorAgent(model=model)
#     thought = start_problem(evaluator, problem)


#     #Trialling a problem
#     for i in range(10):
#         time.sleep(2) #Wait a bit to refresh open router rate limit
#         #Printing out the thoughts
#         print(f"\n=== Round {i + 1} ===")
#         print("Current thought:")
#         print(thought.state)

#         proposals = prover.propose(thought, numThoughts=2)

#         checked = [evaluator.evaluate(proposal) for proposal in proposals]
#         print("\nChecked thoughts:")
#         for j, checked_thought in enumerate(checked, start=1):
#             print(f"\nChecked {j}:")
#             print(checked_thought.state)

#         solved = [t for t in checked if t.state.get("solved")]
#         if solved:
#             print("Solved!")
#             print(solved[0].state["proof"])
#             break

#         valid = [t for t in checked if t.state.get("valid")]
#         if not valid:
#             print("No valid tactics.")
#             break

#         for t in valid:
#             t.score = t.state.get("score", 0.0)

#         thought = max(valid, key=lambda t: t.score)