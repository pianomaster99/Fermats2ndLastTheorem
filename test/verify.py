from src.gemini import GeminiClient
from src.verifier import Verifier


def main():
    verifier = Verifier()
    gemini = GeminiClient()

    goal = "forall (p q : Prop), p ∧ q -> q ∧ p"

    state = verifier.start_goal(goal)

    prompt = f"""
You are proving this Lean 4 theorem using tactics.

The original theorem goal is:
{goal}

The current Lean proof state is:
{state}

Return a complete Lean tactic proof that solves the goal.

Important:
- If the goal starts with forall, introduce ALL variables and hypotheses first.
- Return ONLY Lean tactics.
- No explanation.
- No markdown.
- No backticks.

Example format:
intro p q h
exact ⟨h.right, h.left⟩
"""

    proof = gemini.ask(prompt)

    print("Gemini proof:")
    print(proof)

    try:
        final_state = verifier.run_tactic(state, proof)

        print("\nFinal state:")
        print(final_state)

        if verifier.is_solved(final_state):
            print("\nSolved!")
        else:
            print("\nNot solved.")

    except Exception as e:
        print("\nVerification failed:")
        print(e)


if __name__ == "__main__":
    main()
