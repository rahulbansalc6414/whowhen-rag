# Contributing

Bug reports, example queries that whowhen-rag gets wrong, and pull requests are all welcome.

## Set up

```bash
git clone https://github.com/rahulbansalc6414/whowhen-rag.git
cd whowhen-rag
uv sync
uv run pytest        # no network or API keys needed
uv run ruff check .
```

## Ground rules

- **Tests need no network or keys.** Use the fake LLM and classifier in `tests/conftest.py`.
- **Failures never break search.** A classifier or LLM problem returns "no filter" and logs a warning; keep it that way.
- **Synthetic data only.** Test and benchmark queries use made-up names and topics. Do not add real company, customer or personal data.
- **No em dashes** in docs or messages; use colons, commas or parentheses.

## Changing the gates or the prompt

These change what the package returns, so they need numbers:

- **Regex gate** (`src/whowhen_rag/gates.py`): add the queries it should now catch to `tests/queries.py`, and check the plain questions still miss. Then run the benchmark (below).
- **Prompt**: add a new file (`src/whowhen_rag/prompts/v5.txt`) rather than editing an existing version, and score it: `uv run python benchmarks/run.py --prompt v5`. See [docs/prompts.md](docs/prompts.md).
- **The benchmark** (`benchmarks/run.py`, needs `TYPESAFE_API_KEY` and `OPENROUTER_API_KEY`) runs every labelled question in `benchmarks/cases.py` through the real `Detector` and reports what the regex, Jev and the LLM each caught and missed. Add new labelled queries to `cases.py` before changing a prompt, not after.
- Append the results to `benchmarks/RESULTS.md` with the date and commit. Do not overwrite earlier rows.

## Releases

Maintainers release by moving the "unreleased" section of `CHANGELOG.md` under the new version, bumping `version` in `pyproject.toml` (the only place it is set), and pushing a matching tag `vX.Y.Z`. User-visible changes go in `CHANGELOG.md` in the same pull request. The publish workflow builds and uploads to PyPI.
