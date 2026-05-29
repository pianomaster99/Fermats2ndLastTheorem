from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4


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
class ProofNode:
    state: str
    proof_prefix: list[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    incoming_tactic: Optional[str] = None
    node_id: str = field(default_factory=lambda: str(uuid4()))
    value_score: float = 0.0
    status: str = "open"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProofEdge:
    from_node: str
    to_node: Optional[str]
    candidate: TacticCandidate
    evaluation: ControllerEvaluation


@dataclass
class SearchResult:
    solved: bool
    proof: list[str]
    final_state: str
    nodes_expanded: int
    graph_nodes: int
    failed_edges: int

