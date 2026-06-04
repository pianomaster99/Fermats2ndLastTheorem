# Tree of Thoughts for Lean Theorem Proving

Authors: Henry Songyang Wang and Tom Liu

This repository experiments with using LLM agents to generate Lean 4 tactic proofs. The main workflow is:

1. Build or use a Pantograph-startable Lean goal dataset.
2. Run a baseline one-shot prover.
3. Run a tree-of-thought proof search that proposes tactics, checks them with Lean, and keeps the best valid branches.
4. Compare solved, unsolved, and errored examples.

## Setup

Run all commands from the repository root.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The code also depends on the Lean project in `lean_project/`. If Mathlib has not been fetched yet, run:

```bash
cd lean_project
lake exe cache get
cd ..
```

## API Keys

Create a `.env` file in the repository root. Do not commit this file.

For OpenRouter models:

```bash
OPENROUTER_API_KEY=your_openrouter_key_here
```

For Gemini models through the Gemini Developer API:

```bash
GOOGLE_API_KEY=your_gemini_key_here
GOOGLE_GENAI_USE_VERTEXAI=False
```

If you want to use Vertex AI instead of the Gemini Developer API, set `GOOGLE_GENAI_USE_VERTEXAI=True` and authenticate with Google Cloud Application Default Credentials.

## Important Files

- `src/verifier.py`: Thin wrapper around Pantograph/Lean verification.
- `src/gemini.py`: Gemini client wrapper.
- `src/prover_agent/prover.py`: Prover agents that ask the LLM for tactic proposals.
- `src/evaluator_agent/evaluator.py`: Evaluator agents that check tactic proposals with Lean.
- `src/initalize_graph/initalize_graph.py`: Single-problem tree-of-thought experiment script.
- `test/baseline.py`: One-shot Gemini baseline.
- `test/test_tree_of_thoughts.py`: Tree-of-thought run over the full Mathlib.Tactic-verified dataset.
- `test/run_multiple_test_tree_of_thoughts.py`: Tree-of-thought run over a selected index range.
- `test/make_pantograph_startable_dataset.py`: Builds the Pantograph-startable dataset.

The main dataset used for experiments is:

```text
data/pantograph_goals_mathlib_tactic_verified.json
```

This file contains goals that initialize successfully with `Mathlib.Tactic`.

## Test the Gemini Client

After setting your `.env`, run:

```bash
python -m test.google_api_test
```

If this fails with a Google credentials error, make sure you are using:

```bash
GOOGLE_GENAI_USE_VERTEXAI=False
```

for API-key based Gemini access.

## Build the Startable Dataset

To regenerate the dataset whose goals can be initialized by Pantograph:

```bash
python -m test.make_pantograph_startable_dataset
```

This reads:

```text
data/pantograph_goals_from_test.json
```

And writes:

```text
data/pantograph_goals_mathlib_tactic_verified.json
```

Use this dataset for experiments that require initialization with `Mathlib.Tactic`.

## Run the One-Shot Baseline

The baseline asks Gemini for one complete tactic proof per problem and checks it with Lean.

```bash
python -m test.baseline
```

By default, this script uses:

```text
data/pantograph_goals_mathlib_tactic_verified.json
```

and writes:

```text
test/gemini_one_shot_results.json
```

To change the number of examples, edit `NUM_OF_EXAMPLES` in `test/baseline.py`.

## Run Tree-of-Thought Search on One Problem

The single-problem script has a hardcoded `problem`, model, prover, evaluator, and search settings.

```bash
python -m src.initalize_graph.initalize_graph
```

Edit `src/initalize_graph/initalize_graph.py` to change:

- `problem`
- `model`
- `keep_n_thoughts`
- number of rounds
- number of tactic proposals per round
- Gemini vs. OpenRouter prover/evaluator

## Run Tree-of-Thought Search on the Dataset

To run over the full `Mathlib.Tactic` verified dataset:

```bash
python -m test.test_tree_of_thoughts
```

This writes detailed logs to:

```text
test/output.txt
```

The current search hyperparameters are set near the top of `test/test_tree_of_thoughts.py`:

```python
NUM_ROUNDS = 10
KEEP_N_THOUGHTS = 3
NUM_PROPOSALS = 3
```

To run only part of the dataset, use:

```bash
python -m test.run_multiple_test_tree_of_thoughts START_INDEX END_INDEX
```

For example:

```bash
python -m test.run_multiple_test_tree_of_thoughts 1 28
```

This writes logs to:

```text
test/output1-28.txt
```

The index arguments are intended to be 1-based dataset ranges.

## Existing Outputs

The repository includes saved experiment outputs:

- `test/output_summary.csv`: Summary of tree-of-thought results.
- `test/output*.txt`: Detailed tree-of-thought logs by index range.
- `test/gemini_one_shot_results.json`: One-shot baseline results.
- `test/gemini_two_try_results.json`: Two-try baseline results.
- `test/gemini_five_try_results.json`: Five-try baseline results.
- `test/gemini_five_try_results_filtered.json`: Filtered five-try baseline results used for comparison.

When reporting results, track solved, unsolved, and errored examples separately. Errors usually mean the run failed before producing an evaluable Lean proof attempt, for example because of JSON parsing, API, or verification exceptions.

## Notes

- Run scripts from the repository root so relative paths resolve correctly.
- Keep the virtual environment active while running experiments.
- If imports fail for `google.genai`, reinstall dependencies with `pip install -r requirements.txt`.
- If Lean initialization fails, make sure `lean_project/` exists and Mathlib has been downloaded with `lake exe cache get`.
