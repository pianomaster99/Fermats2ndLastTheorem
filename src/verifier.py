from pantograph.server import Server

class Verifier:
    def __init__(self, imports=None, project_path=None, timeout=120):
        if imports is None:
            imports = ["Init"]
        self.server = Server(imports=imports, project_path=project_path, timeout=timeout)

    def start_goal(self, goal: str):
        return self.server.goal_start(goal)

    def run_tactic(self, state, tactic: str):
        return self.server.goal_tactic(state, tactic)

    def is_solved(self, state) -> bool:
        return len(state.goals) == 0

    def verify(self, goal: str, tactics: list[str]) -> bool:
        try:
            state = self.start_goal(goal)

            for tactic in tactics:
                state = self.run_tactic(state, tactic)

            return self.is_solved(state)

        except Exception as e:
            print("Verification failed:", e)
            return False