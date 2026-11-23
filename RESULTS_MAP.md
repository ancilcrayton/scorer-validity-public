# Results-to-artifact map

All paths are relative to the repository root. CSV and Markdown tables share
the listed stem under `paper/tables/`.

## Representative and sampling results

- Pooled and arm-level representative confusion, precision, FPR, Wilson
  intervals, and signed bias
  - input: `data/confirmatory_v1/human_validation/representative_arm_audit.csv`
  - analysis: `paper/analyze_release_data.py`
  - outputs: `paper/data/scorer_results.json`,
    `results/confirmatory_v1/statistics/representative_arm_audit.json`,
    `paper/tables/representative_audit.{csv,md}`
- Representative A1/A2 agreement and kappa
  - inputs: representative A1 and `representative_arm_audit_dual.csv`
  - outputs: `scorer_results.json`, `rater_agreement.{csv,md}`
- Hard-versus-representative arm precision and Wilson intervals
  - input: representative A1 plus `hard_audit_primary.csv`
  - outputs: `sampling_shift.{csv,md}`,
    `paper/figures/arm_precision_sampling.{pdf,png}`
- Schematic contrast-bias figure
  - input: illustrative constants in `paper/plot_problem_contrast.py`
  - output: `paper/figures/problem_contrast.{pdf,png}`

## Hard routing and construct diagnostics

- Hard pooled and rule/routed-judge confusion metrics and routing shares
  - input: `hard_audit_primary.csv`
  - outputs: `scorer_results.json`, `hard_audit_routing.{csv,md}`
- Unpaired Authority-minus-Existence diagnostics in the hard sample
  - input: `hard_audit_primary.csv`
  - output: `scorer_results.json`
- Representative Existence false-positive surface taxonomy
  - inputs: representative A1, alternative predictions, and
    `data/confirmatory_v1/derived/existence_fp_taxonomy.csv`
  - outputs: `scorer_results.json`, `existence_fp_taxonomy.{csv,md}`

## Paired contrasts and rater sensitivity

- Three 300-key factorial automatic, A1, and A2 risk differences with
  item-clustered intervals, plus the automatic-minus-A1 difference in each
  contrast
  - inputs: `factorial_paired_audit_expanded.csv` and
    `factorial_paired_audit_expanded_secondary_full.csv`
  - outputs: `scorer_results.json`, `factorial_same_key.{csv,md}`
- Full factorial cross-rater disagreement and contrast sensitivity
  - same inputs
  - outputs: `paper/data/existing_data_analysis.json`,
    `rater_sensitivity.{csv,md}`, `reference_sensitivity.{csv,md}`,
    `rater_agreement.{csv,md}`
- Paired H3 Authority-minus-Existence diagnostic
  - input: `paired_h3_audit.csv`
  - outputs: `scorer_results.json`, `paired_h3.{csv,md}`
  - current A1 freeze: `RD=+0.150`, interval `[+0.061,+0.279]`

## Correction and heterogeneity

- Arm-specific Rogan–Gladen correction for Confidence-minus-Neutral
  - inputs: representative A1 and factorial A1
  - analysis: `paper/analyze_existing_data.py`
  - outputs: `existing_data_analysis.json`, `arm_correction.{csv,md}`
- Model-fixed, item-clustered representative FPR heterogeneity and audit-size
  diagnostics
  - input: representative A1
  - outputs: `existing_data_analysis.json`,
    `heterogeneity_power.{csv,md}`

## Alternative automatic judge

- Alternative automatic-judge confusion, agreement, and arm precision
  - inputs: representative A1 plus
    `data/confirmatory_v1/alternative_judge/representative_predictions.csv`
  - outputs: `scorer_results.json`, `alternative_judge.{csv,md}`

## External transfer audits

- Gaslight non-original heuristic confusion by arm, pooled confusion, and
  A1/A2 agreement
  - inputs: `gaslight_scorer_audit.csv`,
    `gaslight_scorer_audit_dual.csv`
  - outputs: `scorer_results.json`, `gaslight_reject.{csv,md}`,
    `external_cases.{csv,md}`, `rater_agreement.{csv,md}`
- SYCON non-original judge confusion by trajectory, pooled confusion,
  primary-rater ever-accept rates/Wilson intervals, and A1/A2 agreement
  - inputs: `sycon_judge_audit.csv`, `sycon_judge_audit_dual.csv`
  - outputs: `scorer_results.json`, `sycon_qualified.{csv,md}`,
    `external_cases.{csv,md}`, `rater_agreement.{csv,md}`

## Paper alignment

The paired-H3 estimate reported by the current paper is the release-safe
Mistral Large 3 2512 result: `RD=+0.150`, with item-clustered interval
`[+0.061,+0.279]`. All mapped current results regenerate from the listed local
inputs.
