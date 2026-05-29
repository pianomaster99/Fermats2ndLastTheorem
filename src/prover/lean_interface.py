from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.prover.data_types import LeanStepResult, TheoremTask


class LeanBackend(ABC):
    """Small boundary around Lean so search code is independent of the tool."""

    @abstractmethod
    def initial_state(self, task: TheoremTask) -> str:
        raise NotImplementedError

    @abstractmethod
    def apply_tactic(self, state: str, tactic: str) -> LeanStepResult:
        raise NotImplementedError

    def verify_proof(self, task: TheoremTask, proof: list[str]) -> LeanStepResult:
        state = self.initial_state(task)
        last = LeanStepResult(valid=True, solved=False, state=state)
        for tactic in proof:
            last = self.apply_tactic(last.state, tactic)
            if not last.valid:
                return last
        return last


class MockLeanBackend(LeanBackend):
    """Fast deterministic backend for testing graph search without launching Lean.

    This encodes one toy theorem:
        p ∧ q -> q ∧ p
    It is intentionally tiny; real proof checking should use PantographLeanBackend.
    """

    TRANSITIONS: dict[str, dict[str, tuple[str, bool]]] = {
        "initial": {
            "intro h": ("introduced", False),
        },
        "introduced": {
            "constructor": ("left_goal", False),
            "apply And.intro": ("left_goal", False),
        },
        "left_goal": {
            "exact h.right": ("right_goal", False),
        },
        "right_goal": {
            "exact h.left": ("solved", True),
        },
    }

    STATE_TEXT = {
        "initial": "p q : Prop\n⊢ p ∧ q → q ∧ p",
        "introduced": "p q : Prop\nh : p ∧ q\n⊢ q ∧ p",
        "left_goal": "case left\np q : Prop\nh : p ∧ q\n⊢ q",
        "right_goal": "case right\np q : Prop\nh : p ∧ q\n⊢ p",
        "solved": "no goals",
    }

    def initial_state(self, task: TheoremTask) -> str:
        return self.STATE_TEXT["initial"]

    def apply_tactic(self, state: str, tactic: str) -> LeanStepResult:
        key = self._state_key(state)
        transition = self.TRANSITIONS.get(key, {}).get(tactic.strip())
        if transition is None:
            return LeanStepResult(
                valid=False,
                solved=False,
                state=state,
                error=f"mock Lean rejected tactic from state '{key}': {tactic}",
            )

        next_key, solved = transition
        return LeanStepResult(
            valid=True,
            solved=solved,
            state=self.STATE_TEXT[next_key],
        )

    def _state_key(self, state: str) -> str:
        for key, text in self.STATE_TEXT.items():
            if state == text:
                return key
        return "unknown"


class PantographLeanBackend(LeanBackend):
    """Lean backend using Pantograph, which is part of the LeanDojo workflow here."""

    def __init__(self, server: Optional[object] = None) -> None:
        if server is None:
            from pantograph.server import Server

            server = Server()
        self.server = server
        self._states: dict[str, object] = {}

    def initial_state(self, task: TheoremTask) -> str:
        goal_state = self.server.goal_start(task.statement)
        text = self._render_state(goal_state)
        self._states[text] = goal_state
        return text

    def apply_tactic(self, state: str, tactic: str) -> LeanStepResult:
        goal_state = self._states.get(state)
        if goal_state is None:
            return LeanStepResult(
                valid=False,
                solved=False,
                state=state,
                error="unknown Pantograph state; this state was not created by this backend",
            )

        try:
            next_state = self.server.goal_tactic(goal_state, tactic)
        except Exception as exc:  # Pantograph surfaces Lean tactic errors as exceptions.
            return LeanStepResult(
                valid=False,
                solved=False,
                state=state,
                error=str(exc),
                raw=exc,
            )

        text = self._render_state(next_state)
        self._states[text] = next_state
        return LeanStepResult(
            valid=True,
            solved=self._is_solved(text),
            state=text,
            raw=next_state,
        )

    def _render_state(self, goal_state: object) -> str:
        return str(goal_state).strip()

    def _is_solved(self, state_text: str) -> bool:
        lowered = state_text.lower()
        return "no goals" in lowered or lowered in {"", "[]"}
