from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

import numpy as np

from src.prover.data_types import ControllerEvaluation, TacticCandidate


@dataclass
class HeuristicValueModel:
    """Baseline value model before learned training data exists."""

    def predict(
        self,
        parent: dict,
        candidate: TacticCandidate,
        evaluation: ControllerEvaluation,
    ) -> float:
        if evaluation.result.solved:
            return 1.0
        if not evaluation.result.valid:
            return 0.0

        shorter_bonus = max(0.0, 1.0 - 0.03 * len(parent["proof_prefix"]))
        return (
            0.45 * candidate.confidence
            + 0.45 * evaluation.value_hint
            + 0.10 * shorter_bonus
        )


@dataclass
class TinyNeuralValueModel:
    """Small one-hidden-layer scorer for learned branch values.

    This is deliberately simple: hashed bag-of-text features plus controller
    signals. It is enough to compare learned search against heuristic search.
    """

    feature_dim: int = 512
    hidden_dim: int = 64
    learning_rate: float = 0.01
    w1: np.ndarray = field(init=False)
    b1: np.ndarray = field(init=False)
    w2: np.ndarray = field(init=False)
    b2: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        rng = np.random.default_rng(0)
        self.w1 = rng.normal(0.0, 0.02, size=(self.feature_dim + 3, self.hidden_dim))
        self.b1 = np.zeros(self.hidden_dim)
        self.w2 = rng.normal(0.0, 0.02, size=(self.hidden_dim,))

    def predict(
        self,
        parent: dict,
        candidate: TacticCandidate,
        evaluation: ControllerEvaluation,
    ) -> float:
        x = self._features(parent, candidate, evaluation)
        hidden = np.maximum(0.0, x @ self.w1 + self.b1)
        return float(self._sigmoid(hidden @ self.w2 + self.b2))

    def train_batch(
        self,
        examples: list[tuple[dict, TacticCandidate, ControllerEvaluation, float]],
        epochs: int = 10,
    ) -> None:
        for _ in range(epochs):
            for parent, candidate, evaluation, label in examples:
                x = self._features(parent, candidate, evaluation)
                z1 = x @ self.w1 + self.b1
                hidden = np.maximum(0.0, z1)
                pred = self._sigmoid(hidden @ self.w2 + self.b2)
                dz2 = pred - label

                grad_w2 = dz2 * hidden
                grad_b2 = dz2
                dhidden = dz2 * self.w2
                dz1 = dhidden * (z1 > 0)
                grad_w1 = np.outer(x, dz1)
                grad_b1 = dz1

                self.w2 -= self.learning_rate * grad_w2
                self.b2 -= self.learning_rate * grad_b2
                self.w1 -= self.learning_rate * grad_w1
                self.b1 -= self.learning_rate * grad_b1

    def _features(
        self,
        parent: dict,
        candidate: TacticCandidate,
        evaluation: ControllerEvaluation,
    ) -> np.ndarray:
        text = "\n".join(
            [
                parent["lean_state"],
                candidate.tactic,
                candidate.rationale,
                evaluation.result.state if evaluation.result.valid else "",
            ]
        )
        vec = np.zeros(self.feature_dim + 3)
        for token in text.split():
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            index = int(digest, 16) % self.feature_dim
            vec[index] += 1.0

        norm = np.linalg.norm(vec[: self.feature_dim])
        if norm > 0:
            vec[: self.feature_dim] /= norm

        vec[self.feature_dim] = candidate.confidence
        vec[self.feature_dim + 1] = evaluation.progress_score
        vec[self.feature_dim + 2] = 1.0 if evaluation.result.valid else 0.0
        return vec

    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + float(np.exp(-x)))
