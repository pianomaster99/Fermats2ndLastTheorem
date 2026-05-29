from __future__ import annotations

import heapq
from itertools import count
from typing import Any

from graph_of_thoughts.controller import Controller
from graph_of_thoughts.language_models import AbstractLanguageModel
from graph_of_thoughts.operations import (
    GraphOfOperations,
    KeepBestN,
    Operation,
    Score,
    Thought,
)
from graph_of_thoughts.parser import Parser
from graph_of_thoughts.prompter import Prompter

from src.prover.agents import ProverAgent
from src.prover.controllers import ControllerAgent
from src.prover.lean_interface import LeanBackend
from src.prover.data_types import (
    ControllerEvaluation,
    ProofEdge,
    ProofNode,
    SearchResult,
    TacticCandidate,
    TheoremTask,
)
from src.prover.value_model import HeuristicValueModel


class _NoLanguageModel(AbstractLanguageModel):
    """Placeholder LM for Graph-of-Thoughts operations that call local agents."""

    def __init__(self) -> None:
        self.model_name = "local-prover-agents"
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost = 0.0

    def query(self, query: str, num_responses: int = 1) -> list[str]:
        return []

    def get_response_texts(self, query_responses: Any) -> list[str]:
        return []


class _NoPrompter(Prompter):
    """Required by the package controller; local operations do not prompt."""

    def aggregation_prompt(self, state_dicts: list[dict], **kwargs) -> str:
        return ""

    def improve_prompt(self, **kwargs) -> str:
        return ""

    def generate_prompt(self, num_branches: int, **kwargs) -> str:
        return ""

    def validation_prompt(self, **kwargs) -> str:
        return ""

    def score_prompt(self, state_dicts: list[dict], **kwargs) -> str:
        return ""


class _NoParser(Parser):
    """Required by the package controller; local operations parse typed objects."""

    def parse_aggregation_answer(
        self,
        states: list[dict],
        texts: list[str],
    ) -> dict | list[dict]:
        return states

    def parse_improve_answer(self, state: dict, texts: list[str]) -> dict:
        return state

    def parse_generate_answer(self, state: dict, texts: list[str]) -> list[dict]:
        return []

    def parse_validation_answer(self, state: dict, texts: list[str]) -> bool:
        return False

    def parse_score_answer(self, states: list[dict], texts: list[str]) -> list[float]:
        return [0.0 for _ in states]


class _GenerateTacticThoughts(Operation):
    def __init__(
        self,
        task: TheoremTask,
        node: ProofNode,
        provers: list[ProverAgent],
        candidates_per_prover: int,
    ) -> None:
        super().__init__()
        self.task = task
        self.node = node
        self.provers = provers
        self.candidates_per_prover = candidates_per_prover
        self.thoughts: list[Thought] = []

    def get_thoughts(self) -> list[Thought]:
        return self.thoughts

    def _execute(
        self,
        lm: AbstractLanguageModel,
        prompter: Prompter,
        parser: Parser,
        **kwargs,
    ) -> None:
        candidates = self._dedupe_candidates(
            candidate
            for prover in self.provers
            for candidate in prover.propose(
                self.task,
                self.node,
                self.candidates_per_prover,
            )
        )
        self.thoughts = [
            Thought(
                {
                    "task": self.task,
                    "node": self.node,
                    "candidate": candidate,
                }
            )
            for candidate in candidates
        ]

    def _dedupe_candidates(self, candidates) -> list[TacticCandidate]:
        seen: set[str] = set()
        unique = []
        for candidate in candidates:
            key = candidate.tactic.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique


class _EvaluateTacticThoughts(Operation):
    def __init__(self, controllers: list[ControllerAgent]) -> None:
        super().__init__()
        self.controllers = controllers
        self.thoughts: list[Thought] = []
        self.rejected: list[dict] = []

    def get_thoughts(self) -> list[Thought]:
        return self.thoughts

    def _execute(
        self,
        lm: AbstractLanguageModel,
        prompter: Prompter,
        parser: Parser,
        **kwargs,
    ) -> None:
        for thought in self.get_previous_thoughts():
            state = dict(thought.state)
            node = state["node"]
            candidate = state["candidate"]
            evaluation = self._evaluate(node, candidate)
            state["evaluation"] = evaluation

            if not evaluation.result.valid:
                self.rejected.append(state)
                continue

            state["proof_prefix"] = node.proof_prefix + [candidate.tactic]
            state["lean_state"] = evaluation.result.state
            state["solved"] = evaluation.result.solved
            evaluated_thought = Thought(state)
            evaluated_thought.valid = True
            evaluated_thought.solved = evaluation.result.solved
            self.thoughts.append(evaluated_thought)

    def _evaluate(
        self,
        node: ProofNode,
        candidate: TacticCandidate,
    ) -> ControllerEvaluation:
        evaluations = [
            controller.evaluate(node, candidate)
            for controller in self.controllers
        ]
        return max(evaluations, key=lambda item: item.value_hint)


class GraphOfThoughtProver:
    def __init__(
        self,
        backend: LeanBackend,
        provers: list[ProverAgent],
        controllers: list[ControllerAgent],
        value_model: HeuristicValueModel | object | None = None,
        candidates_per_prover: int = 4,
        max_expansions: int = 64,
    ) -> None:
        self.backend = backend
        self.provers = provers
        self.controllers = controllers
        self.value_model = value_model or HeuristicValueModel()
        self.candidates_per_prover = candidates_per_prover
        self.max_expansions = max_expansions
        self.nodes: dict[str, ProofNode] = {}
        self.edges: list[ProofEdge] = []

    def prove(self, task: TheoremTask) -> SearchResult:
        self.nodes = {}
        self.edges = []

        root = ProofNode(state=self.backend.initial_state(task), value_score=1.0)
        self.nodes[root.node_id] = root

        tie_breaker = count()
        frontier: list[tuple[float, int, str]] = []
        heapq.heappush(frontier, (-root.value_score, next(tie_breaker), root.node_id))

        expanded = 0
        while frontier and expanded < self.max_expansions:
            _, _, node_id = heapq.heappop(frontier)
            node = self.nodes[node_id]
            if node.status != "open":
                continue

            expanded += 1
            rejected, accepted = self._expand_node_with_graph_of_thoughts(task, node)

            for thought_state in rejected:
                self.edges.append(
                    ProofEdge(
                        from_node=node.node_id,
                        to_node=None,
                        candidate=thought_state["candidate"],
                        evaluation=thought_state["evaluation"],
                    )
                )

            for thought_state in accepted:
                candidate = thought_state["candidate"]
                evaluation = thought_state["evaluation"]
                proof_prefix = thought_state["proof_prefix"]
                child = ProofNode(
                    state=thought_state["lean_state"],
                    proof_prefix=proof_prefix,
                    parent_id=node.node_id,
                    incoming_tactic=candidate.tactic,
                    status="solved" if evaluation.result.solved else "open",
                )
                child.value_score = float(thought_state["value_score"])
                self.nodes[child.node_id] = child
                self.edges.append(
                    ProofEdge(
                        from_node=node.node_id,
                        to_node=child.node_id,
                        candidate=candidate,
                        evaluation=evaluation,
                    )
                )

                if evaluation.result.solved:
                    return SearchResult(
                        solved=True,
                        proof=child.proof_prefix,
                        final_state=child.state,
                        nodes_expanded=expanded,
                        graph_nodes=len(self.nodes),
                        failed_edges=self._failed_edge_count(),
                    )

                heapq.heappush(
                    frontier,
                    (-child.value_score, next(tie_breaker), child.node_id),
                )

            node.status = "expanded"

        best = max(self.nodes.values(), key=lambda n: n.value_score)
        return SearchResult(
            solved=False,
            proof=best.proof_prefix,
            final_state=best.state,
            nodes_expanded=expanded,
            graph_nodes=len(self.nodes),
            failed_edges=self._failed_edge_count(),
        )

    def _expand_node_with_graph_of_thoughts(
        self,
        task: TheoremTask,
        node: ProofNode,
    ) -> tuple[list[dict], list[dict]]:
        graph = GraphOfOperations()
        generate = _GenerateTacticThoughts(
            task=task,
            node=node,
            provers=self.provers,
            candidates_per_prover=self.candidates_per_prover,
        )
        evaluate = _EvaluateTacticThoughts(self.controllers)
        score = Score(scoring_function=lambda state: self._score_thought_state(state))
        keep = KeepBestN(n=max(1, self.candidates_per_prover * len(self.provers)))

        graph.append_operation(generate)
        graph.append_operation(evaluate)
        graph.append_operation(score)
        graph.append_operation(keep)

        Controller(
            lm=_NoLanguageModel(),
            graph=graph,
            prompter=_NoPrompter(),
            parser=_NoParser(),
            problem_parameters={},
        ).run()

        accepted: list[dict] = []
        for thought in keep.get_thoughts():
            state = dict(thought.state)
            state["value_score"] = thought.score
            accepted.append(state)
        return evaluate.rejected, accepted

    def _score_thought_state(self, thought_state: dict) -> float:
        node = thought_state["node"]
        candidate = thought_state["candidate"]
        evaluation = thought_state["evaluation"]
        return float(self.value_model.predict(node, candidate, evaluation))

    def _failed_edge_count(self) -> int:
        return sum(1 for edge in self.edges if edge.to_node is None)
