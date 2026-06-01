import json
import random
from pathlib import Path

BENCHMARK_ROOT = Path("data/leandojo_benchmark_4")

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def load_split(split):
    path = BENCHMARK_ROOT / "novel_premises" / f"{split}.json"
    if not path.exists():
        raise FileNotFoundError(f"Could not find split file: {path}")
    return load_json(path)

def split_state(before_state: str):
    """
    Splits a Lean proof state into context lines and target.

    Example:
        p q : Prop
        h : p ∧ q
        ⊢ q ∧ p

    Returns:
        givens = ["p q : Prop", "h : p ∧ q"]
        target = "q ∧ p"
    """
    lines = [line.strip() for line in before_state.splitlines() if line.strip()]

    givens = []
    target_lines = []
    in_target = False

    for line in lines:
        if line.startswith("⊢"):
            in_target = True
            target_lines.append(line.removeprefix("⊢").strip())
        elif in_target:
            target_lines.append(line)
        else:
            givens.append(line)

    if not target_lines:
        raise ValueError(f"No target found in state:\n{before_state}")

    target = "\n".join(target_lines).strip()
    return givens, target


def parse_given(given: str):
    """
    Parse a context line like:
        p q : Prop
        h : p ∧ q

    Returns:
        names = ["p", "q"]
        typ = "Prop"

    or:
        names = ["h"]
        typ = "p ∧ q"
    """
    if " : " not in given:
        raise ValueError(f"Cannot parse context line: {given}")

    names_part, typ = given.split(" : ", 1)

    names = names_part.strip().split()
    typ = typ.strip()

    return names, typ


def is_typeclass_instance(names, typ: str) -> bool:
    """
    Heuristic for things like:
        inst✝² : CommRing R
        inst✝¹ : AddCommGroup M
        inst✝ : Module R M

    These should usually become Lean typeclass binders:
        [CommRing R] [AddCommGroup M] [Module R M]
    """
    if len(names) != 1:
        return False

    name = names[0]

    if name.startswith("inst"):
        return True

    # Add more typeclasses here as you encounter them.
    common_typeclasses = [
        "CommRing",
        "Ring",
        "Semiring",
        "Field",
        "LinearOrder",
        "PartialOrder",
        "AddCommGroup",
        "AddGroup",
        "Group",
        "Monoid",
        "Module",
        "TopologicalSpace",
        "NormedAddCommGroup",
        "MetricSpace",
    ]

    return any(typ.startswith(cls + " ") or typ == cls for cls in common_typeclasses)


def is_variable(names, typ: str) -> bool:
    """
    Heuristic for ordinary variables:
        p q : Prop
        n : Nat
        R : Type u
        f g : Module.End R M

    These become forall binders:
        (p q : Prop)
        (n : Nat)
        (R : Type u)
        (f g : Module.End R M)
    """
    if typ.startswith("Type"):
        return True

    if typ.startswith("Sort"):
        return True

    if typ == "Prop":
        return True

    # Usually theorem hypotheses have names like h, hf, hg.
    # Variables can also have lowercase names, so this is imperfect.
    if all(not name.startswith("h") for name in names):
        return True

    return False


def before_state_to_lean_expression(before_state: str) -> str:
    """
    Convert a Lean proof state into a Lean proposition.

    Example input:
        p q : Prop
        h : p ∧ q
        ⊢ q ∧ p

    Output:
        ∀ (p q : Prop), p ∧ q → q ∧ p

    This is heuristic. It works best for simple states.
    Full Mathlib states may require original repo/file context.
    """
    givens, target = split_state(before_state)

    binders = []
    typeclass_binders = []
    hypotheses = []

    for given in givens:
        names, typ = parse_given(given)

        if is_typeclass_instance(names, typ):
            typeclass_binders.append(f"[{typ}]")
        elif is_variable(names, typ):
            names_str = " ".join(names)
            binders.append(f"({names_str} : {typ})")
        else:
            hypotheses.append(typ)

    pieces = []

    all_binders = binders + typeclass_binders

    if all_binders:
        pieces.append("∀ " + " ".join(all_binders) + ", ")

    for hyp in hypotheses:
        pieces.append(f"{hyp} → ")

    pieces.append(target)

    return "".join(pieces)

def extract_lean_expression(example):
    traced_tactics = example.get("traced_tactics", [])

    if not traced_tactics:
        raise KeyError("No traced_tactics found")

    before_state = traced_tactics[0].get("state_before")

    if not before_state:
        raise KeyError("No state_before found in first traced tactic")

    lean_expression = before_state_to_lean_expression(before_state)

    return {
        "initial_state": before_state,
        "lean_expression": lean_expression,
        "proof_tactics": [
            tactic_obj["tactic"]
            for tactic_obj in traced_tactics
            if "tactic" in tactic_obj
        ],
    }

def extract_lean_expressions_by_indices(split, indices):
    examples = load_split(split)
    theorems = []

    for index in indices:
        example = examples[index]
        traced_tactics = example.get("traced_tactics", [])

        if not traced_tactics:
            print(f"Skipping index {index}: no traced_tactics")
            continue

        theorems.append(extract_lean_expression(example))

    return theorems

