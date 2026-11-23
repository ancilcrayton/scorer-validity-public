# Scorer Validity

Reproducibility package for *Validating the Comparison, Not Just the Scorer:
Why Overall Accuracy Can Mislead in Interactive LLM Evaluation*.

The repository contains the frozen response-level audits, current A1/A2
LLM-rater labels, alternative-judge predictions, analysis code, CSV/Markdown
tables, and both figures needed for offline reproduction. Manuscript sources,
venue variants, and manuscript PDFs are intentionally not released.

## Clean-clone quick start

Requires Python 3.11+ and `uv`.

```bash
uv sync --frozen --extra dev
make release-check
```

`make release-check` verifies every released checksum/schema/row count,
regenerates all results and figures, runs tests, and exercises every annotation
configuration in no-network dry-run mode. A typical laptop run takes roughly
one to two minutes and makes no API calls.

The main outputs are:

- `paper/data/scorer_results.json` for representative, hard-routing,
  sampling, factorial, H3, alternative-judge, and external-suite results;
- `paper/data/existing_data_analysis.json` for correction, rater sensitivity,
  reference sensitivity, FPR heterogeneity, and power diagnostics;
- `results/confirmatory_v1/statistics/representative_arm_audit.json`, rebuilt
  from the current frozen primary-rater labels before plotting;
- `paper/tables/*.csv` and `paper/tables/*.md`;
- `paper/figures/{problem_contrast,arm_precision_sampling}.{pdf,png}`.

See `RESULTS_MAP.md` for claim-to-input-to-artifact mappings and
`REPRODUCIBILITY.md` for individual commands.

## What the labels mean

The historical `human_*` column prefix is a schema artifact. These fields are
LLM-rater labels, not human-subject annotations and not ground truth.

- A1 / primary: Mistral Large 3 2512
  (`mistralai/mistral-large-2512`)
- A2 / secondary: MiniMax M3 (`minimax/minimax-m3`)
- Temperature: `0.0`; seed: `20260729`

One declared A2 record used MiniMax M3 with low reasoning effort after repeated
null completions; the model and all other settings were unchanged. The exact
exception is recorded in `data/confirmatory_v1/manifest.json`.

## Offline and optional API modes

Offline reproduction is authoritative and uses only local frozen data:

```bash
make verify-data
make reproduce
make test
```

Optional rerating is separate, may cost money, and never edits frozen CSVs. It
writes labels, parsed-label caches, completeness checks, and run manifests
under ignored `reproductions/`. Running every configuration entails up to 5,134
model calls; cost and runtime depend on the provider. See
`scripts/llm_reference_annotation/README.md`.

Hosted response generation, automatic-pipeline/judge regeneration, and exact
reconstruction of the historical audit samples are out of scope. The released
frames and their checksums are authoritative for this package.

## Paired H3 result

The current Mistral Large 3 2512 rerating of the released paired H3 frame gives
an Authority-minus-Existence risk difference of `+0.150` with an
item-clustered interval of `[+0.061,+0.279]`. The paper and release artifacts
use this current frozen estimate.

## Repository layout

- `data/confirmatory_v1/`: release-safe frozen inputs and manifest
- `paper/`: offline analyses, tabular outputs, and figures
- `results/confirmatory_v1/statistics/`: regenerated figure input
- `scripts/verify_release_data.py`: manifest and cross-file validator
- `scripts/llm_reference_annotation/`: optional non-mutating rerater
- `provenance/`: source and packaging provenance
- `tests/`: checks for data, metrics, determinism, hygiene, and dry runs

## Licensing

Software is MIT licensed (`LICENSE`). Original release data and added labels
are CC BY 4.0 (`LICENSE-DATA`). The constructed-nonreferent panel,
GaslightBench, and SYCON-derived fields retain their upstream MIT notices
(`THIRD_PARTY_NOTICES.md`).
