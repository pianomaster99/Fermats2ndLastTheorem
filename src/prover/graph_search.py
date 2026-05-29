from __future__ import annotations

import heapq
from itertools import count
from types import SimpleNamespace

from graph_of_thoughts.operations import KeepBestN, Score, Thought

from src.prover.agents import ProverAgent
from src.prover.controllers import ControllerAgent
from src.prover.lean_interface import LeanBackend
from src.prover.data_types import SearchResult, TacticCandidate, TheoremTask
from src.prover.value_model import HeuristicValueModel


def prove_with_graph_of_thoughts(
    task: TheoremTask,
    backend: LeanBackend,
    provers: list[ProverAgent],
    controllers: list[ControllerAgent],
    value_model: HeuristicValueModel | object | None = None,
    candidates_per_prover: int = 4,
    max_expansions: int = 64,
) -> tuple[SearchResult, dict[int, Thought], list[Thought]]:
    value_model = value_model or HeuristicValueModel()
    thoughts: dict[int, Thought] = {}
    rejected_thoughts: list[Thought] = []

    root = Thought(
        {
            "lean_state": backend.initial_state(task),
            "proof_prefix": [],
            "status": "open",
        }
    )
    root.score = 1.0
    thoughts[root.id] = root

    frontier: list[tuple[float, int, int]] = []
    tie_breaker = count()
    heapq.heappush(frontier, (-root.score, next(tie_breaker), root.id))

    expanded = 0
    while frontier and expanded < max_expansions:
        _, _, thought_id = heapq.heappop(frontier)
        parent = thoughts[thought_id]
        if parent.state["status"] != "open":
            continue

        expanded += 1
        children = _next_thoughts(
            task,
            parent,
            provers,
            controllers,
            value_model,
            candidates_per_prover,
            rejected_thoughts,
        )

        for child in children:
            thoughts[child.id] = child
            if child.solved:
                return (
                    _result(True, child, expanded, thoughts, rejected_thoughts),
                    thoughts,
                    rejected_thoughts,
                )
            heapq.heappush(frontier, (-child.score, next(tie_breaker), child.id))

        parent.state["status"] = "expanded"

    best = max(thoughts.values(), key=lambda thought: thought.score)
    return (
        _result(False, best, expanded, thoughts, rejected_thoughts),
        thoughts,
        rejected_thoughts,
    )


def _next_thoughts(
    task: TheoremTask,
    parent: Thought,
    provers: list[ProverAgent],
    controllers: list[ControllerAgent],
    value_model: HeuristicValueModel | object,
    candidates_per_prover: int,
    rejected_thoughts: list[Thought],
) -> list[Thought]:
    valid_children: list[Thought] = []

    for candidate in _candidate_tactics(task, parent, provers, candidates_per_prover):
        evaluation = max(
            (
                controller.evaluate(parent.state, candidate)
                for controller in controllers
            ),
            key=lambda item: item.value_hint,
        )
        state = {
            "lean_state": evaluation.result.state,
            "proof_prefix": parent.state["proof_prefix"] + [candidate.tactic],
            "status": "solved" if evaluation.result.solved else "open",
            "incoming_tactic": candidate.tactic,
            "candidate": candidate,
            "evaluation": evaluation,
            "parent_state": parent.state,
        }
        thought = Thought(state)
        thought.valid = evaluation.result.valid
        thought.solved = evaluation.result.solved

        if evaluation.result.valid:
            valid_children.append(thought)
        else:
            rejected_thoughts.append(thought)

    return _keep_best(valid_children, value_model, candidates_per_prover, len(provers))


def _candidate_tactics(
    task: TheoremTask,
    parent: Thought,
    provers: list[ProverAgent],
    candidates_per_prover: int,
) -> list[TacticCandidate]:
    seen: set[str] = set()
    candidates: list[TacticCandidate] = []

    for prover in provers:
        for candidate in prover.propose(task, parent.state, candidates_per_prover):
            tactic = candidate.tactic.strip()
            if not tactic or tactic in seen:
                continue
            seen.add(tactic)
            candidates.append(candidate)

    return candidates


def _keep_best(
    thoughts: list[Thought],
    value_model: HeuristicValueModel | object,
    candidates_per_prover: int,
    prover_count: int,
) -> list[Thought]:
    if not thoughts:
        return []

    source = SimpleNamespace(executed=True, get_thoughts=lambda: thoughts)
    score = Score(scoring_function=lambda state: _score(state, value_model))
    keep = KeepBestN(n=max(1, candidates_per_prover * prover_count))
    source.add_successor = lambda operation: None
    score.predecessors = [source]
    keep.predecessors = [score]

    score.execute(None, None, None)
    keep.execute(None, None, None)
    return keep.get_thoughts()


def _score(state: dict, value_model: HeuristicValueModel | object) -> float:
    return float(
        value_model.predict(
            state["parent_state"],
            state["candidate"],
            state["evaluation"],
        )
    )


def _result(
    solved: bool,
    thought: Thought,
    expanded: int,
    thoughts: dict[int, Thought],
    rejected_thoughts: list[Thought],
) -> SearchResult:
    return SearchResult(
        solved=solved,
        proof=thought.state["proof_prefix"],
        final_state=thought.state["lean_state"],
        thoughts_expanded=expanded,
        graph_thoughts=len(thoughts),
        rejected_thoughts=len(rejected_thoughts),
    )
