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

- **Regex gate** (`src/whowhen_rag/gates.py`): add the queries it should now catch to `tests/queries.py`, and check the plain questions still miss. Run `uv run python benchmarks/gates.py` (set `TYPESAFE_API_KEY` to include the classifier).
- **Prompt**: add a new file (`src/whowhen_rag/prompts/v3.txt`) rather than editing an existing version, and score it: `uv run python benchmarks/extraction.py --prompt v3` and `--set holdout`. See [docs/prompts.md](docs/prompts.md).
- Append the results to `benchmarks/RESULTS.md` with the date and commit. Do not overwrite earlier rows.

## Releases

Maintainers release by bumping `version` in `pyproject.toml` (the only place it is set) and pushing a matching tag `vX.Y.Z`. The publish workflow builds and uploads to PyPI.
