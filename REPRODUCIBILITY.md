# Reproducibility

## Supported environment

- Python 3.11 or newer
- `uv` with the committed `uv.lock`
- no sibling checkout, network access, or credentials for offline reproduction

From a clean clone:

```bash
uv sync --frozen --extra dev
make release-check
```

The release check is read-only with respect to frozen inputs. It regenerates
derived artifacts in place and writes annotation dry-run manifests only below
ignored `reproductions/`.

## Make targets

```bash
make verify-data        # checksums, schemas, rows, branches, rater settings
make reproduce          # all JSON/CSV/Markdown outputs and both figures
make test               # headline, determinism, hygiene, and dry-run tests
make annotation-dry-run # validates all A1/A2 configs without network access
make release-check      # all of the above
```

`make reproduce` runs these scripts in order:

1. `paper/analyze_release_data.py`
2. `paper/analyze_existing_data.py`
3. `paper/plot_problem_contrast.py`
4. `paper/plot_sampling_precision.py`

The first analysis rebuilds
`results/confirmatory_v1/statistics/representative_arm_audit.json`; the sampling
plot therefore cannot silently consume the stale pre-rerating JSON formerly
shipped by this repository.

## Determinism

All bootstrap and simulation procedures use fixed seeds:

- factorial item-cluster bootstrap: `20260804`, 2,000 draws, resampling
  item clusters and pooling the keys inside each draw so the interval keeps
  the same key weights as the point estimate;
- automatic-minus-reference contrast difference: `20260804`, 2,000 draws with
  the same item-cluster resampling;
- paired H3 item-cluster bootstrap: `2`, 4,000 draws;
- Rogan–Gladen uncertainty diagnostic: `20260805`, 200,000 draws;
- optional annotation calls: `20260729`, temperature `0.0`.

Tests rerun the release analysis and compare its JSON/CSV/Markdown outputs byte
for byte. Figure tests verify that both plotting scripts consume current local
statistics. PDF metadata can vary across plotting-library versions, so figure
bytes are not used as cross-platform checksums.

## Frozen inputs and verification

`data/confirmatory_v1/manifest.json` records, for every paper-consumed file:

- upstream and released SHA-256 values;
- exact released schema and row count;
- arm and trajectory coverage;
- sampling design and seed where available;
- A1/A2 model, annotator ID, temperature, seed, and run ID;
- the one MiniMax M3 low-reasoning fallback.

Run `make verify-data` before analysis. The validator also checks paired-file
coverage, dual-subset relations, alternative-judge alignment, and the frozen
six-row Existence false-positive taxonomy.

The source package contains a few genuinely empty hosted response cells. Their
record IDs are enumerated in the manifest rather than silently dropped. No
message histories, judge rationales, provider/cache fields, timestamps, or raw
reasoning artifacts are released.

## Optional live rerating

Live rerating is not required to reproduce paper results.

```bash
cp .env.example .env
# set OPENROUTER_API_KEY in .env
uv sync --frozen --extra annotation
uv run --project . --frozen \
  python scripts/llm_reference_annotation/run_validators.py \
  --config scripts/llm_reference_annotation/config_representative_arm.json \
  --role all
```

The runner always reads a frozen input and writes to ignored
`reproductions/llm_reference_annotation/`. It never writes to
`data/confirmatory_v1/`. Each run records input/config/prompt hashes, fixed
settings, progress, fallbacks, completeness, and agreement with the frozen
labels. Caches retain parsed labels only at the runner layer; raw responses and
rationales are not release artifacts.

## Scope boundaries

The package reproduces analyses from frozen responses, automatic labels, and
LLM-rater labels. It does not reproduce hosted model response generation,
automatic-pipeline or alternative-judge API calls, or the exact historical
sampling draws from raw panel caches. Those operations require upstream
systems and are intentionally excluded.

The current released Mistral Large 3 2512 paired H3 labels imply
`RD=+0.150`, with item-clustered interval `[+0.061,+0.279]`. This is the
estimate reported by the current paper and generated release artifacts.
