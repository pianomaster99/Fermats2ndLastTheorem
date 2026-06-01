import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Run this from your project root, where src/verifier.py and lean_project/ exist.
# It creates a dataset whose `goal` field has been replaced by a candidate that
# Pantograph's goal_start actually accepts in YOUR Lean/Mathlib environment.

INPUT_PATH = Path('data/pantograph_goals_from_test.json')
OUTPUT_PATH = Path('data/pantograph_goals_goal_start_verified.json')
FAILED_PATH = Path('data/pantograph_goals_goal_start_failed.json')
PROJECT_PATH = 'lean_project'
MAX_ITEMS = None  # set to 100 while testing

try:
    from src.verifier import Verifier
except Exception:
    Verifier = None

SUBSCRIPT_MAP = str.maketrans({
    '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
    '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
})

LEAN_KEYWORDS = {
    'Type', 'Sort', 'Prop', 'True', 'False', 'Nat', 'Int', 'Rat', 'Bool', 'List', 'Option',
    'Set', 'Function', 'Subtype', 'Finset', 'Fintype', 'PUnit', 'Unit', 'Prod', 'Sum',
    'forall', 'fun', 'let', 'in', 'by', 'if', 'then', 'else', 'match', 'with',
}

# Very conservative namespace fixes for symbols that repeatedly fail at goal_start.
# These are used only to produce candidates. The validator below tests candidates.
REPLACEMENTS = [
    # LinearMap/BilinForm
    (r'(?<![\.\w])BilinForm(?![\.\w])', 'LinearMap.BilinForm'),
    (r'(?<![\.\w])skewAdjointSubmodule(?![\.\w])', 'LinearMap.BilinForm.skewAdjointSubmodule'),
    (r'(?<![\.\w])IsAdjointPair(?![\.\w])', 'LinearMap.IsAdjointPair'),

    # Category theory common names
    (r'(?<![\.\w])ShortComplex(?![\.\w])', 'CategoryTheory.ShortComplex'),
    (r'(?<![\.\w])Category(?![\.\w])', 'CategoryTheory.Category'),
    (r'(?<![\.\w])HasZeroMorphisms(?![\.\w])', 'CategoryTheory.HasZeroMorphisms'),
    (r'(?<![\.\w])homologyMap(?![\.\w])', 'CategoryTheory.ShortComplex.homologyMap'),
    (r'(?<![\.\w])cyclesMap(?![\.\w])', 'CategoryTheory.ShortComplex.cyclesMap'),
    (r'(?<![\.\w])IsTerminal(?![\.\w])', 'CategoryTheory.Limits.IsTerminal'),
    (r'(?<![\.\w])SmallCategory(?![\.\w])', 'CategoryTheory.SmallCategory'),

    # MonCat / category colimits
    (r'(?<![\.\w])coconeMorphism(?![\.\w])', 'MonCat.Colimits.coconeMorphism'),

    # Lie weights
    (r'(?<![\.\w])Weight(?![\.\w])', 'LieModule.Weight'),
    (r'(?<![\.\w])weightSpace(?![\.\w])', 'LieModule.weightSpace'),
    (r'(?<![\.\w])weightSpaceOf(?![\.\w])', 'LieModule.weightSpaceOf'),
    (r'(?<![\.\w])chainBot(?![\.\w])', 'LieModule.chainBot'),
    (r'(?<![\.\w])chainTop(?![\.\w])', 'LieModule.chainTop'),
    (r'(?<![\.\w])posFittingCompOf(?![\.\w])', 'LieModule.posFittingCompOf'),

    # Algebraic geometry / PrimeSpectrum
    (r'(?<![\.\w])Scheme(?![\.\w])', 'AlgebraicGeometry.Scheme'),
    (r'(?<![\.\w])IsAffineOpen(?![\.\w])', 'AlgebraicGeometry.IsAffineOpen'),
    (r'(?<![\.\w])toBasicOpen(?![\.\w])', 'AlgebraicGeometry.toBasicOpen'),
    (r'(?<![\.\w])PrimeSpectrum(?![\.\w])', 'PrimeSpectrum'),
    (r'(?<![\.\w])zariskiTopology(?![\.\w])', 'PrimeSpectrum.zariskiTopology'),
    (r'(?<![\.\w])comap(?![\.\w])', 'PrimeSpectrum.comap'),

    # Batteries List internal names
    (r'(?<![\.\w])fillNones(?![\.\w])', 'List.fillNones'),
    (r'(?<![\.\w])fillNonesTR(?![\.\w])', 'List.fillNonesTR'),
]


def normalize_unicode_and_universes(s: str) -> str:
    s = s.translate(SUBSCRIPT_MAP)
    # Remove pretty-printed explicit universe variables. goal_start is not inside a `universe` declaration.
    s = re.sub(r'\b(Type|Sort)\s+[A-Za-z_][A-Za-z0-9_\']*', r'\1 _', s)
    # Remove spaces in some common prefix coercion displays that parse poorly.
    s = s.replace('↑↑', '↑↑')
    return s


def module_from_file_path(file_path: Optional[str]) -> Optional[str]:
    if not file_path:
        return None
    p = file_path.replace('\\', '/')
    if p.startswith('Mathlib/') and p.endswith('.lean'):
        return p[:-5].replace('/', '.')
    if 'Batteries/' in p and p.endswith('.lean'):
        idx = p.index('Batteries/')
        return p[idx:-5].replace('/', '.')
    return None


def split_given(given: str) -> Tuple[Optional[str], Optional[str]]:
    if ':' not in given:
        return None, None
    left, right = given.split(':', 1)
    return left.strip().translate(SUBSCRIPT_MAP), normalize_unicode_and_universes(right.strip())


def is_instance(left: str) -> bool:
    return left.startswith('inst')


def make_binder(given: str) -> Optional[str]:
    left, typ = split_given(given)
    if not left or not typ:
        return None
    # Inaccessible duplicate names like φ✝ are not good standalone binders.
    if '✝' in left and not is_instance(left):
        return None
    if is_instance(left):
        return f'[{typ}]'
    return f'({left} : {typ})'


def goal_from_givens(item: Dict) -> str:
    binders: List[str] = []
    seen = set()
    for given in item.get('givens', []):
        b = make_binder(given)
        if b and b not in seen:
            binders.append(b)
            seen.add(b)
    target = normalize_unicode_and_universes(item.get('target', item.get('goal', 'True')))
    if binders:
        return '∀ ' + ' '.join(binders) + ', ' + target
    return target


def qualify(s: str) -> str:
    out = s
    for pat, repl in REPLACEMENTS:
        out = re.sub(pat, repl, out)
    return out


def remove_unrecoverable_if_needed(s: str) -> Optional[str]:
    # Placeholder ellipsis is not a valid standalone goal. Do not pretend we fixed it.
    if '⋯' in s:
        return None
    return s


def candidates_for_item(item: Dict) -> List[str]:
    base_goal = normalize_unicode_and_universes(item.get('goal', ''))
    givens_goal = goal_from_givens(item)
    candidates = []

    for cand in [givens_goal, qualify(givens_goal), base_goal, qualify(base_goal)]:
        cand = remove_unrecoverable_if_needed(cand)
        if not cand:
            continue
        if cand not in candidates:
            candidates.append(cand)
    return candidates


def make_server(imports):
    if Verifier is None:
        raise RuntimeError('Could not import src.verifier.Verifier. Run this script from your repo root.')
    return Verifier(imports=imports, project_path=PROJECT_PATH)


def main():
    with open(INPUT_PATH, 'r') as f:
        data = json.load(f)
    if MAX_ITEMS is not None:
        data = data[:MAX_ITEMS]

    # One Mathlib server is slow to start, but avoids creating a server for every file.
    verifier = make_server(['Mathlib'])

    fixed = []
    failed = []

    for i, item in enumerate(data):
        name = item.get('name', f'theorem_{i}')
        print(f'[{i+1}/{len(data)}] {name}')
        module_import = module_from_file_path(item.get('file_path'))
        tried = []
        accepted = None
        last_error = None

        for cand in candidates_for_item(item):
            tried.append(cand)
            try:
                verifier.start_goal(cand)
                accepted = cand
                break
            except Exception as e:
                last_error = str(e)

        if accepted is not None:
            new_item = dict(item)
            new_item['original_goal'] = item.get('goal')
            new_item['goal'] = accepted  # replace goal, as requested
            new_item['goal_for_goal_start'] = accepted
            new_item['module_import'] = module_import
            new_item['goal_start_verified'] = True
            fixed.append(new_item)
            print('  ok')
        else:
            bad = dict(item)
            bad['module_import'] = module_import
            bad['goal_start_verified'] = False
            bad['tried_goals'] = tried
            bad['last_error'] = last_error
            failed.append(bad)
            print('  failed:', last_error)

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, 'w') as f:
            json.dump(fixed, f, indent=2, ensure_ascii=False)
        with open(FAILED_PATH, 'w') as f:
            json.dump(failed, f, indent=2, ensure_ascii=False)

    print(f'\nVerified startable goals: {len(fixed)}/{len(data)}')
    print(f'Wrote: {OUTPUT_PATH}')
    print(f'Failures: {FAILED_PATH}')


if __name__ == '__main__':
    main()
