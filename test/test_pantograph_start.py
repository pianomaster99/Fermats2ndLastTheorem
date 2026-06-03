from src.verifier import Verifier
import time

print("Starting verifier...")
t0 = time.time()

verifier = Verifier(
    imports=["Mathlib"],
    project_path="lean_project",
)

print(f"Started in {time.time() - t0:.2f}s")

goal = "∀ {p q : Prop}, p ∧ q → q ∧ p"
state = verifier.start_goal(goal)
print(state)

final_state = verifier.run_tactic(state, "intro h\nexact ⟨h.right, h.left⟩")
print(final_state)
print("Solved?", verifier.is_solved(final_state))
EOF