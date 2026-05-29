from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.prover.agents import OpenRouterProverAgent, ScriptedProverAgent
from src.prover.controllers import LeanValidityController
from src.prover.graph_search import GraphOfThoughtProver
from src.prover.lean_interface import MockLeanBackend, PantographLeanBackend
from src.prover.data_types import TheoremTask


def build_prover(args: argparse.Namespace) -> GraphOfThoughtProver:
    backend = PantographLeanBackend() if args.backend == "pantograph" else MockLeanBackend()

    provers = [] if args.openrouter_only else [ScriptedProverAgent()]
    if args.model:
        provers.append(OpenRouterProverAgent(model=args.model, name=f"openrouter:{args.model}"))
    if not provers:
        raise ValueError("No prover agents configured. Pass --model or remove --openrouter-only.")

    controllers = [LeanValidityController(backend)]
    return GraphOfThoughtProver(
        backend=backend,
        provers=provers,
        controllers=controllers,
        candidates_per_prover=args.candidates_per_prover,
        max_expansions=args.max_expansions,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the graph-of-thought Lean prover.")
    parser.add_argument("--backend", choices=["mock", "pantograph"], default="mock")
    parser.add_argument("--model", default="", help="Optional OpenRouter model id for LLM tactics.")
    parser.add_argument(
        "--openrouter-only",
        action="store_true",
        help="Use only the OpenRouter prover instead of adding the scripted baseline.",
    )
    parser.add_argument("--candidates-per-prover", type=int, default=5)
    parser.add_argument("--max-expansions", type=int, default=32)
    args = parser.parse_args()

    task = TheoremTask(
        name="and_comm_test",
        statement="∀ {p q : Prop}, p ∧ q → q ∧ p",
    )
    prover = build_prover(args)
    result = prover.prove(task)

    print(f"solved: {result.solved}")
    print(f"nodes expanded: {result.nodes_expanded}")
    print(f"graph nodes: {result.graph_nodes}")
    print(f"failed edges: {result.failed_edges}")
    print("proof:")
    for tactic in result.proof:
        print(f"  {tactic}")
    print("final state:")
    print(result.final_state)


if __name__ == "__main__":
    main()
