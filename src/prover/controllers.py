from __future__ import annotations

from abc import ABC, abstractmethod

from src.prover.lean_interface import LeanBackend
from src.prover.data_types import ControllerEvaluation, ProofNode, TacticCandidate


class ControllerAgent(ABC):
    name: str

    @abstractmethod
    def evaluate(self, node: ProofNode, candidate: TacticCandidate) -> ControllerEvaluation:
        raise NotImplementedError


class LeanValidityController(ControllerAgent):
    """Controller that uses Lean as the source of truth for candidate tactics."""

    def __init__(self, backend: LeanBackend, name: str = "lean-validity") -> None:
        self.backend = backend
        self.name = name

    def evaluate(self, node: ProofNode, candidate: TacticCandidate) -> ControllerEvaluation:
        result = self.backend.apply_tactic(node.state, candidate.tactic)
        progress = self._progress_score(node.state, result.state, result.valid, result.solved)
        value_hint = self._value_hint(progress, result.valid, result.solved)
        return ControllerEvaluation(
            candidate=candidate,
            result=result,
            progress_score=progress,
            value_hint=value_hint,
            comments=result.error or "",
        )

    def _progress_score(self, old_state: str, new_state: str, valid: bool, solved: bool) -> float:
        if not valid:
            return 0.0
        if solved:
            return 1.0
        if old_state == new_state:
            return 0.05
        old_goals = old_state.count("⊢")
        new_goals = new_state.count("⊢")
        if new_goals < old_goals:
            return 0.75
        if new_goals == old_goals:
            return 0.45
        return 0.25

    def _value_hint(self, progress: float, valid: bool, solved: bool) -> float:
        if solved:
            return 1.0
        if not valid:
            return 0.0
        return progress

