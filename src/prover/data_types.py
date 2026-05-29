from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class TheoremTask:
    name: str
    statement: str


@dataclass(frozen=True)
class TacticCandidate:
    tactic: str
    rationale: str
    prover_name: str
    confidence: float = 0.5


@dataclass(frozen=True)
class LeanStepResult:
    valid: bool
    solved: bool
    state: str
    error: Optional[str] = None
    raw: Any = None


@dataclass
class ControllerEvaluation:
    candidate: TacticCandidate
    result: LeanStepResult
    progress_score: float
    value_hint: float
    comments: str = ""


@dataclass
class SearchResult:
    solved: bool
    proof: list[str]
    final_state: str
    thoughts_expanded: int
    graph_thoughts: int
    rejected_thoughts: int
