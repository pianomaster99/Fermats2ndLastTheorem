from openai import OpenAI
from graph_of_thoughts.operations.thought import Thought
from src.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from pantograph.server import Server
import json
from pathlib import Path
from abc import ABC, abstractmethod






#Points to project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#Points to lean_project
LEAN_PROJECT = PROJECT_ROOT / "lean_project"

class EvaluatorAgent(ABC):
    def __init__(self):
        self.server = Server(imports=["Mathlib.Tactic"], project_path=str(LEAN_PROJECT), timeout = 60)
        self.lean_states = {}

    @abstractmethod
    def evaluate(self, previous_thought: Thought):
        pass

    def lean_check(self, thought: Thought):
        #Run a lean_check through Pentagraph, this is deterministic
        #Example of input thought
        """
        Thought(
            state={
                "problem": "theorem add_zero (n : Nat) : n + 0 = n := by",
                "lean_state": "induction n",
                "goals": ["case zero ...", "case succ ..."],
                "candidate": "simp",
                "feedback": "",
                "valid": False,
            }
        )"""
        state = thought.state
        lean_state = state["lean_state"]
        tactic = state["candidate"]

        goal_state = self.lean_states.get(lean_state)


        try:
            #When lean check goes through
            next_goal_state = self.server.goal_tactic(goal_state, tactic)
            next_lean_state = str(next_goal_state).strip()
            self.lean_states[next_lean_state] = next_goal_state

            return Thought({
                **state,
                "lean_state": next_lean_state,
                "proof": state.get("proof", []) + [tactic],
                "goals": [next_lean_state],
                "feedback": "Lean accepted the tactic.",
                "valid": True,
                "solved": self.is_solved(next_lean_state),
            })

        except Exception as exc:
            #When lean check fails
            return Thought({
                **state,
                "feedback": str(exc),
                "valid": False,
                "solved": False,
            })
    
    def is_solved(self, lean_state: str):
        #Return whether or not the problem is solved
        text = lean_state.lower()
        return "no goals" in text or text in {"", "[]"}


class OpenRouterEvaluatorAgent(EvaluatorAgent):
    """LLM that evaluate Lean tactics through OpenRouter."""

    def __init__(self, model, name ="openrouter") -> None:
        super().__init__()

        #Setting up the model
        self.name = name
        self.model = model
        self.client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)

    def evaluate(self, previous_thought: Thought):
        #Return LLM evaluation along with deterministic lean check
        #Example previous thought that evaluator needs to evaluate
        """
        Thought(
            state={
                "problem": "theorem add_zero (n : Nat) : n + 0 = n := by",
                "lean_state": "induction n",
                "goals": ["case zero ...", "case succ ..."],
                "candidate": "simp",
                "feedback": "",
                "valid": False,
            }
        )"""

        checked_state = self.lean_check(previous_thought).state


        #If lean solves the proof, it is correct
        if checked_state["solved"]:
            return Thought({
                **checked_state,
                "feedback": "Lean accepted the tactic and solved the goal.",
                "score": 1.0,
            })
        
        #Called when proof is not solved
        prompt = f"""
        You are evaluating a Lean tactic attempt.

        Theorem:
        {checked_state["problem"]}

        Candidate tactic:
        {checked_state["candidate"]}

        Lean accepted tactic:
        {checked_state["valid"]}

        Solved:
        {checked_state["solved"]}

        Lean feedback:
        {checked_state["feedback"]}

        Current Lean state after tactic:
        {checked_state["lean_state"]}

        Return exactly JSON:
        {{
        "feedback": "short critique",
        "score": number from 0 to 1
        }}

        Do not include markdown.
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        
        response = response.choices[0].message.content or "{}"
        print(response)
        response = response.strip()

        if response.startswith("```"):
            response = response.removeprefix("```json").removeprefix("```").strip()
            response = response.removesuffix("```").strip()

        llm_eval = json.loads(response)
        llm_feedback = llm_eval.get("feedback", llm_eval.get("evaluation", ""))

        #When lean is inccorect
        if not checked_state["valid"]:
            return Thought({
                **checked_state,
                "failed_candidate": checked_state.get("candidate", ""),
                "feedback": f"Lean rejected the tactic: {checked_state['feedback']} LLM feedback: {llm_feedback}",
                "score": 0.0,
            })

        return Thought({
            **checked_state,
            "feedback": f"Lean accepted the tactic. {llm_feedback}".strip(),
            "score": float(llm_eval.get("score", 0.5)),
        })

class GeminiEvaluatorAgent(EvaluatorAgent):
    """LLM that evaluates Lean tactics through Gemini."""

    def __init__(self, model = "gemini-2.5-flash", name = "gemini") -> None:
        super().__init__()
        from src.gemini import GeminiClient

        #Setting up the model
        self.name = name
        self.model = model
        self.client = GeminiClient(model=model)

    def evaluate(self, previous_thought: Thought):
        #Return LLM evaluation along with deterministic lean check
        #Example previous thought that evaluator needs to evaluate
        """
        Thought(
            state={
                "problem": "theorem add_zero (n : Nat) : n + 0 = n := by",
                "lean_state": "induction n",
                "goals": ["case zero ...", "case succ ..."],
                "candidate": "simp",
                "feedback": "",
                "valid": False,
            }
        )"""

        checked_state = self.lean_check(previous_thought).state


        #If lean solves the proof, it is correct
        if checked_state["solved"]:
            return Thought({
                **checked_state,
                "feedback": "Lean accepted the tactic and solved the goal.",
                "score": 1.0,
            })
        
        #Called when proof is not solved
        prompt = f"""
        You are evaluating a Lean tactic attempt.

        Theorem:
        {checked_state["problem"]}

        Candidate tactic:
        {checked_state["candidate"]}

        Prover rationale:
        {checked_state.get("rationale")}

        Prover confidence:
        {checked_state.get("confidence")}

        Lean accepted tactic:
        {checked_state["valid"]}

        Solved:
        {checked_state["solved"]}

        Lean feedback:
        {checked_state["feedback"]}

        Current Lean state after tactic:
        {checked_state["lean_state"]}

        Return only a valid JSON object.
        Do not include markdown, code fences, explanations, or any text before or after the JSON.

        Score valid tactics by how much they reduce the remaining Lean goal.
        A tactic that normalizes the goal close to the final obstruction should score higher.
        A tactic that solve the goal apart from syntax should be scored higher.
        Do not score 1 unless it is solved
        Schema:
        {{
        "feedback": "short critique",
        "score": number from 0 to 0.99,
        }}
        """

        response = self.client.ask(prompt) or "{}"
        print(response)
        response = response.strip()

        if response.startswith("```"):
            response = response.removeprefix("```json").removeprefix("```").strip()
            response = response.removesuffix("```").strip()

        llm_eval = json.loads(response)
        llm_feedback = llm_eval.get("feedback", llm_eval.get("evaluation", ""))

        #LLM score only matters when all the ideas are rejected, which one is still closest

        #When lean is inccorect
        if not checked_state["valid"]:
            return Thought({
                **checked_state,
                "failed_candidate": checked_state.get("candidate", ""),
                "feedback": f"Lean rejected the tactic: {checked_state['feedback']} LLM feedback: {llm_feedback}",
                "score": 0,
                "llm score": float(llm_eval.get("score", 0.5)),

            })

        return Thought({
            **checked_state,
            "feedback": f"Lean accepted the tactic. {llm_feedback}".strip(),
            "score": float(llm_eval.get("score", 0.5)),
            "llm score": float(llm_eval.get("score", 0.5)),

        })
