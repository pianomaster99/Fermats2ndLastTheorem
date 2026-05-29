from __future__ import annotations

import heapq
from itertools import count

from src.prover.agents import ProverAgent
from src.prover.controllers import ControllerAgent
from src.prover.lean_interface import LeanBackend
from src.prover.data_types import ProofEdge, ProofNode, SearchResult, TheoremTask
from src.prover.value_model import HeuristicValueModel


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
            candidates = self._dedupe_candidates(
                candidate
                for prover in self.provers
                for candidate in prover.propose(task, node, self.candidates_per_prover)
            )

            for candidate in candidates:
                evaluation = self._evaluate(node, candidate)
                if not evaluation.result.valid:
                    self.edges.append(
                        ProofEdge(
                            from_node=node.node_id,
                            to_node=None,
                            candidate=candidate,
                            evaluation=evaluation,
                        )
                    )
                    continue

                proof_prefix = node.proof_prefix + [candidate.tactic]
                child = ProofNode(
                    state=evaluation.result.state,
                    proof_prefix=proof_prefix,
                    parent_id=node.node_id,
                    incoming_tactic=candidate.tactic,
                    status="solved" if evaluation.result.solved else "open",
                )
                child.value_score = float(self.value_model.predict(node, candidate, evaluation))
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

                heapq.heappush(frontier, (-child.value_score, next(tie_breaker), child.node_id))

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

    def _evaluate(self, node: ProofNode, candidate):
        evaluations = [controller.evaluate(node, candidate) for controller in self.controllers]
        return max(evaluations, key=lambda item: item.value_hint)

    def _dedupe_candidates(self, candidates):
        seen: set[str] = set()
        unique = []
        for candidate in candidates:
            key = candidate.tactic.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    def _failed_edge_count(self) -> int:
        return sum(1 for edge in self.edges if edge.to_node is None)

