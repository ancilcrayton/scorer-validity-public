# Optional LLM reference rerating

This runner can repeat A1/A2 labeling through OpenRouter. It is not required
for offline reproduction and never mutates the authoritative files under
`data/`.

- A1 / primary: Mistral Large 3 2512
  (`mistralai/mistral-large-2512`)
- A2 / secondary: MiniMax M3 (`minimax/minimax-m3`)
- temperature `0.0`, seed `20260729`, maximum completion tokens `1024`

Historical output fields retain the `human_*` prefix, but the labels are from
LLM raters, not human annotators or ground truth.

## No-network dry run

The development environment is sufficient; no API package or key is loaded:

```bash
uv sync --frozen --extra dev
make annotation-dry-run
```

Every config is parsed, every frozen input is hashed and counted, and a dry-run
manifest is written under ignored
`reproductions/llm_reference_annotation/`. Input hashes are checked again
before exit.

## Live run

```bash
cp .env.example .env
# Add OPENROUTER_API_KEY to .env.
uv sync --frozen --extra annotation

uv run --project . --frozen \
  python scripts/llm_reference_annotation/run_validators.py \
  --config scripts/llm_reference_annotation/config_representative_arm.json \
  --role all
```

Use `--limit N` for a bounded run and `--force` to replace existing
reproduction labels. Resume state comes from labels and parsed-label caches in
the reproduction directory, never from editing filled cells in the frozen
input.

Each role writes:

- `labels.csv`: record ID plus the four parsed labels and rater identity;
- `cache/`: ignored, resume-safe parsed-label cache;
- `validation.json`: completeness and agreement with the frozen label;
- `run_manifest.json`: input/config/prompt hashes, model/settings, progress,
  failures, and any fallback used.

No rationale column or raw API response is written or cached. Parsed-label
caches and all reproduction outputs are ignored.

## Configurations

- `config_representative_arm.json`: representative A1 and 96-row A2 subset
- `config_factorial_expanded.json`: full 1,200-row A1 and A2 factorial audits
- `config_hard_audit.json`: primary 550-row hard audit
- `config_paired_h3.json`: primary 200-row paired H3 frame
- `config_gaslight.json`: Gaslight A1/A2 with `prompt_gaslight.md`
- `config_sycon.json`: SYCON A1/A2 with `prompt_sycon.md`

The factorial A2 config records the one exact response for which repeated null
completions trigger MiniMax M3 with low reasoning effort. The model,
temperature, seed, and token limit remain unchanged. No other record may use
that fallback.

Running every configuration entails up to 5,134 API calls. Provider prices,
latency, and model availability can change, so the package does not claim a
fixed rerating cost.
