from graph_of_thoughts.operations.thought import Thought
from graph_of_thoughts.operations import KeepBestN, Score

from src.prover_agent.prover import OpenRouterProverAgent, GeminiProverAgent
from src.evaluator_agent.evaluator import OpenRouterEvaluatorAgent, GeminiEvaluatorAgent
import time

from pantograph.server import Server
import json
from pathlib import Path
from abc import ABC, abstractmethod

#Points to project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]

print("hi")
DATASET_PATH = Path("data/pantograph_goals_mathlib_tactic_verified.json")

#Points to lean_project
LEAN_PROJECT = PROJECT_ROOT / "lean_project"
with DATASET_PATH.open() as f:
    data = json.load(f)

server = Server(imports=["Mathlib.Tactic"], project_path=str(LEAN_PROJECT), timeout = 60)
lean_states = {}

def start_problem(problem):
    #Initalize problem to check with lean
    goal_state = server.goal_start(problem)
    lean_state = str(goal_state).strip()
    lean_states[lean_state] = goal_state

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

failed = []

#Checking to see if the problems in the dataset can be initalized to be run
for i, item in enumerate(data):
    name = item.get("name", f"item_{i}")
    problem = item.get("goal_for_goal_start") or item["goal"]

    print(f"[{i + 1}/{len(data)}] {name}")

    try:
        thought = start_problem(problem)
        print("  ok")
        print("  lean_state:", thought.state["lean_state"].splitlines()[0])
    except Exception as e:
        failed.append((i, name, str(e)))
        print("  failed:", e)

print()
print(f"Started {len(data) - len(failed)}/{len(data)}")
print(f"Failed {len(failed)}/{len(data)}")