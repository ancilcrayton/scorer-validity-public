# Offline paper analyses

Run from the repository root:

```bash
uv sync --frozen --extra dev
make reproduce
```

The pipeline first validates `data/confirmatory_v1/manifest.json`, then runs:

1. `analyze_release_data.py` for representative, hard-routing/sampling,
   factorial (including the automatic-minus-reference difference in each
   contrast), paired H3, alternative automatic judge, Gaslight, SYCON, and
   cross-rater summaries;
2. `analyze_existing_data.py` for correction, reference/rater sensitivity,
   clustered FPR heterogeneity, and power diagnostics;
3. `plot_problem_contrast.py` and `plot_sampling_precision.py`.

Generated artifacts:

- `data/scorer_results.json`
- `data/existing_data_analysis.json`
- `tables/*.csv` and `tables/*.md`
- `figures/{problem_contrast,arm_precision_sampling}.{pdf,png}`
- `../results/confirmatory_v1/statistics/representative_arm_audit.json`

The representative JSON is regenerated from the current Mistral Large 3 2512
freeze before the empirical sampling figure is plotted. A2 sensitivity uses
MiniMax M3. Historical `human_*` fields are LLM-rater labels, not human
annotations or ground truth.

LaTeX manuscripts, venue variants, and manuscript PDFs may exist in local
drafting worktrees but are ignored and are not part of this package. The
release does not write into those directories.
