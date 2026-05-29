from openai import OpenAI
from graph_of_thoughts.operations.thought import Thought
from src.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from pantograph.server import Server

class EvaluatorAgent():
    """LLM that evaluate Lean tactics through OpenRouter."""

    def __init__(self, model: str, name: str = "openrouter") -> None:

        #Setting up the model
        self.name = name
        self.model = model
        self.client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
        self.server = Server()
        self.lean_states = {}

    def start_problem(self, problem: str) -> Thought:
        goal_state = self.server.goal_start(problem)
        lean_state = str(goal_state).strip()
        self.lean_states[lean_state] = goal_state

        return Thought({
            "problem": problem,
            "lean_state": lean_state,
            "proof": [],
            "goals": [lean_state],
            "candidate": "",
            "feedback": "",
            "valid": False,
            "solved": False,
        })


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

    def evaluate(self, previous_thought: Thought):
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
