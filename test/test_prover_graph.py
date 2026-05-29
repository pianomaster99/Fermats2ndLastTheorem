from pathlib import Path
import os
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.prover.agents import OpenRouterProverAgent, ScriptedProverAgent
from src.prover.controllers import LeanValidityController
from src.prover.graph_search import GraphOfThoughtProver
from src.prover.lean_interface import MockLeanBackend, PantographLeanBackend
from src.prover.data_types import TheoremTask


class TestGraphProver(unittest.TestCase):
    def test_mock_graph_prover_solves_and_comm(self):
        backend = MockLeanBackend()
        prover = GraphOfThoughtProver(
            backend=backend,
            provers=[ScriptedProverAgent()],
            controllers=[LeanValidityController(backend)],
            candidates_per_prover=5,
            max_expansions=16,
        )

        result = prover.prove(
            TheoremTask(
                name="and_comm_test",
                statement="∀ {p q : Prop}, p ∧ q → q ∧ p",
            )
        )

        self.assertTrue(result.solved)
        self.assertEqual(
            result.proof,
            ["intro h", "constructor", "exact h.right", "exact h.left"],
        )
        self.assertGreater(result.rejected_thoughts, 0)

    def test_pantograph_graph_prover_solves_and_comm(self):
        try:
            backend = PantographLeanBackend()
        except Exception as exc:
            self.skipTest(f"Pantograph backend is unavailable: {exc}")

        prover = GraphOfThoughtProver(
            backend=backend,
            provers=[ScriptedProverAgent()],
            controllers=[LeanValidityController(backend)],
            candidates_per_prover=5,
            max_expansions=16,
        )

        result = prover.prove(
            TheoremTask(
                name="and_comm_test",
                statement="∀ {p q : Prop}, p ∧ q → q ∧ p",
            )
        )

        self.assertTrue(result.solved)
        self.assertIn("constructor", result.proof)
        self.assertIn("exact h.right", result.proof)
        self.assertIn("exact h.left", result.proof)
        self.assertGreater(result.graph_thoughts, 1)

    def test_openrouter_prover_returns_candidates_when_enabled(self):
        model = os.environ.get("OPENROUTER_TEST_MODEL")
        if not model:
            self.skipTest("Set OPENROUTER_TEST_MODEL to run the OpenRouter integration test.")

        backend = MockLeanBackend()
        agent = OpenRouterProverAgent(model=model, name=f"openrouter:{model}")
        root_state = backend.initial_state(
            TheoremTask(
                name="and_comm_test",
                statement="∀ {p q : Prop}, p ∧ q → q ∧ p",
            )
        )

        candidates = agent.propose(
            TheoremTask(
                name="and_comm_test",
                statement="∀ {p q : Prop}, p ∧ q → q ∧ p",
            ),
            {"lean_state": root_state, "proof_prefix": []},
            k=3,
        )

        self.assertGreater(len(candidates), 0)
        self.assertTrue(all(candidate.tactic for candidate in candidates))


if __name__ == "__main__":
    unittest.main()
