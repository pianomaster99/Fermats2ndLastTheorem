from openai import OpenAI
from graph_of_thoughts.operations.thought import Thought
from src.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
import json
from abc import ABC, abstractmethod

class ProverAgent():
    @abstractmethod
    def propose(self, previous_thought: Thought, numThoughts: int):
        pass

class OpenRouterProverAgent(ProverAgent):
    """LLM prover that proposes Lean tactics through OpenRouter."""

    def __init__(self, model: str, name: str = "openrouter"):
        #Setting up the model
        self.name = name
        self.model = model
        self.client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)

    def propose(self, previous_thought: Thought, numThoughts: int):
        #Input and output of prover agent should be list of "Thoughts" as defined in graph of thoughts
        """
        Thought(
            state={
                "problem": str,
                "lean_state": str,
                "goals": list[str],
                "candidate": str,
                "feedback": str,
                "valid": bool,
            }
        )
        """
        state = previous_thought.state

        prompt = f"""
        Lean environment:
        - Lean 4 project
        - Mathlib version: leanprover-community/mathlib v4.29.1
        - Backend: Pantograph `goal_tactic`
        
        You are a Lean theorem-proving agent.

        Return exactly a JSON array of up to {numThoughts} objects. Each object must have:
        - "tactic": one Lean tactic line
        - "rationale": short reason
        - "confidence": number from 0 to 1

        Do not include markdown.

        Theorem:
        {state["problem"]}

        Lean state so far:
        {state.get("lean_state", "") or "(empty)"}

        Current goals:
        {state.get("goals", [])}

        Previous evaluator feedback:
        {state.get("feedback", "") or "(none)"}

        Take lean feedback as fact and LLM feedback as suggestion

        Previous failed attempts:
        {state.get("failed_candidates", "") or "(none)"}

        Do not repeat failed tactics.
        Use the evaluator feedback to propose a substantially different tactic.

        """
            
        response  = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}], max_tokens=1024)
        raw_text = response.choices[0].message.content or "[]"

        proposals = json.loads(raw_text)
        thoughts = []
        for proposal in proposals:
            new_state = {**state, "candidate": proposal["tactic"], "rationale": proposal.get("rationale", ""), "confidence": proposal.get("confidence", 0.0), "valid": False, "solved": False}

            thoughts.append(Thought(new_state))

        return thoughts
class GeminiProverAgent(ProverAgent):
    def __init__(self, model = "gemini-2.5-flash", name = "gemini") -> None:
        super().__init__()
        from src.gemini import GeminiClient

        #Setting up the model
        self.name = name
        self.model = model
        self.client = GeminiClient(model=model)
    def propose(self, previous_thought: Thought, numThoughts: int):
        #Input and output of prover agent should be list of "Thoughts" as defined in graph of thoughts
        """
        Thought(
            state={
                "problem": str,
                "lean_state": str,
                "goals": list[str],
                "candidate": str,
                "feedback": str,
                "valid": bool,
            }
        )
        """
        state = previous_thought.state

        prompt = f"""
        You are a Lean theorem-proving agent.

        Return exactly a JSON array of up to {numThoughts} objects. Each object must have:
        - "tactic": one Lean tactic line
        - "rationale": short reason
        - "confidence": number from 0 to 1

        Do not include markdown.

        Theorem:
        {state["problem"]}

        Lean state so far:
        {state.get("lean_state", "") or "(empty)"}

        Previous failed attempts:
        {state.get("failed_candidates", [])}

        Lessons from previous failed attempts:
        {state.get("lessons", [])}

        Hard rules:
        - Do not repeat failed tactics.
        - Do not reuse identifiers that Lean reported as unknown.
        - Do not reuse syntax styles that caused parse errors.
        - If a lemma name was unknown, try a different lemma name or a tactic that avoids naming it.
        """
            
        response = self.client.ask(prompt) or "{}"
        response = response.strip()

        if response.startswith("```"):
            response = response.removeprefix("```json").removeprefix("```").strip()
            response = response.removesuffix("```").strip()
        try:
            proposals = json.loads(response)
        except json.JSONDecodeError:
            proposal = []

        proposals = json.loads(response)
        thoughts = []
        for proposal in proposals:
            new_state = {**state, "candidate": proposal["tactic"], "rationale": proposal.get("rationale", ""), "confidence": proposal.get("confidence", 0.0), "valid": False, "solved": False}

            thoughts.append(Thought(new_state))

        return thoughts
