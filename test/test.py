from dotenv import load_dotenv
load_dotenv()

import os

assert os.environ.get("GITHUB_ACCESS_TOKEN"), "Missing GITHUB_ACCESS_TOKEN"
assert os.environ.get("HF_TOKEN"), "Missing HF_TOKEN"

from pantograph.server import Server
from lean_dojo_v2.prover import ExternalProver

# Basic Pantograph server.
# This is enough for simple Lean goals using Lean's core/Init library.
server = Server()

# ExternalProver uses a Hugging Face external model backend.
prover = ExternalProver()

goal = "∀ {p q : Prop}, p ∧ q → q ∧ p"

print("Goal:")
print(goal)

result, used_tactics = prover.search(
    server=server,
    goal=goal,
    verbose=True,
)

print("\nResult:")
print(result)

print("\nUsed tactics:")
for tac in used_tactics:
    print(tac)