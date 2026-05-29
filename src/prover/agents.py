from __future__ import annotations

from abc import ABC, abstractmethod
import json
import os
import re

from src.prover.data_types import ProofNode, TacticCandidate, TheoremTask


class ProverAgent(ABC):
    name: str

    @abstractmethod
    def propose(self, task: TheoremTask, node: ProofNode, k: int) -> list[TacticCandidate]:
        raise NotImplementedError


class ScriptedProverAgent(ProverAgent):
    """Deterministic prover for smoke tests and baseline comparisons."""

    def __init__(self, name: str = "scripted") -> None:
        self.name = name

    def propose(self, task: TheoremTask, node: ProofNode, k: int) -> list[TacticCandidate]:
        tactics = [
            ("intro h", "Introduce the implication hypothesis.", 0.9),
            ("constructor", "Split the conjunction goal.", 0.85),
            ("exact h.right", "Use the right side of the hypothesis.", 0.8),
            ("exact h.left", "Use the left side of the hypothesis.", 0.8),
            ("simp", "Try simplification as a fallback.", 0.25),
        ]
        return [
            TacticCandidate(tactic=t, rationale=r, confidence=c, prover_name=self.name)
            for t, r, c in tactics[:k]
        ]


class OpenRouterProverAgent(ProverAgent):
    """LLM prover that proposes Lean tactics through OpenRouter."""

    def __init__(self, model: str, name: str = "openrouter") -> None:
        from openai import OpenAI

        from src.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

        self.name = name
        self.model = model
        self.client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)

    def propose(self, task: TheoremTask, node: ProofNode, k: int) -> list[TacticCandidate]:
        prompt = f"""
You are a Lean theorem-proving agent.

Return exactly a JSON array of up to {k} objects. Each object must have:
- "tactic": one Lean tactic line
- "rationale": short reason
- "confidence": number from 0 to 1

Do not include markdown.

Theorem:
{task.statement}

Current Lean state:
{node.state}

Proof prefix so far:
{os.linesep.join(node.proof_prefix) if node.proof_prefix else "(empty)"}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception:
            return []
        content = response.choices[0].message.content or "[]"
        return self._parse_candidates(content, k)

    def _parse_candidates(self, content: str, k: int) -> list[TacticCandidate]:
        content = self._strip_json_fence(content)
        try:
            raw_items = json.loads(content)
        except json.JSONDecodeError:
            return []

        candidates: list[TacticCandidate] = []
        for item in raw_items[:k]:
            tactic = str(item.get("tactic", "")).strip()
            if not tactic:
                continue
            candidates.append(
                TacticCandidate(
                    tactic=tactic,
                    rationale=str(item.get("rationale", "")),
                    confidence=float(item.get("confidence", 0.5)),
                    prover_name=self.name,
                )
            )
        return candidates

    def _strip_json_fence(self, content: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.DOTALL)
        if match:
            return match.group(1)
        return content.strip()
