# Data provenance

## Authoritative release boundary

The paper-consumed response frames were prepared from the sibling
`unknown-under-pressure` working tree, then minimized and frozen inside this
repository. Offline reproduction reads only local files. Per-file upstream and
released SHA-256 values in `data/confirmatory_v1/manifest.json` are the
authoritative provenance record; source-tree revision alone is insufficient
because release preparation included uncommitted rerating files.

`provenance/scripts/prepare_release_data.py` is a maintainer packaging utility,
not a reproduction dependency. It requires an explicit `--upstream-root`,
selects only approved columns, derives the H3 subset and false-positive
taxonomy frame, and rewrites the manifest. A clean-clone user does not run it.

## Frozen audit sources

- `representative_arm_audit.csv`: balanced 288-row A1 arm-by-model audit,
  sampled with seed `20260805`.
- `representative_arm_audit_dual.csv`: 96-row A2 subset.
- `factorial_paired_audit_expanded.csv`: A1 labels on four arms for 300
  complete item–model keys, seed `20260804`.
- `factorial_paired_audit_expanded_secondary_full.csv`: A2 labels on the same
  1,200 responses.
- `hard_audit_primary.csv`: minimized A1 form of upstream
  `review_sample.csv`, a 550-row enriched stress sample.
- `paired_h3_audit.csv`: the 200 H3 rows from upstream
  `paired_audit_sample.csv`, sampled with seed `20260803`.
- Gaslight A1/A2: minimized 300/100-row task-specific incorrectness audits,
  seed `20260804`.
- SYCON A1/A2: minimized 900/300-row false-presupposition acceptance audits,
  seed `20260804`.
- `alternative_judge/representative_predictions.csv`: frozen alternative
  automatic predictions on all 288 representative rows.
- `derived/existence_fp_taxonomy.csv`: six author-coded surface categories
  joined to the representative and alternative prediction IDs.

The manifest records exact branch/trajectory counts and raw source hashes for
all of these files.

## LLM-rater process

Historical `human_*` columns are LLM-rater schema fields:

- A1 / primary: Mistral Large 3 2512
  (`mistralai/mistral-large-2512`);
- A2 / secondary: MiniMax M3 (`minimax/minimax-m3`);
- temperature `0.0`, seed `20260729`, run
  `unused_families_20260819`.

Raters received response text and permitted item metadata, not automatic
labels or study hypotheses. A1 and A2 were not adjudicated. Neither is a human
annotator or ground truth. One declared A2 record used MiniMax M3 with low
reasoning effort after repeated null completions; all other settings remained
fixed.

## Release transformation

Retained fields are response text, record/item/model/arm identifiers,
automatic labels, A1/A2 labels, metadata needed by the Gaslight or SYCON
rubric, and compact provenance fields.

Removed fields include:

- message histories and prompts not needed by the rating rubric;
- judge rationales and errors;
- provider and cache fields;
- creation timestamps;
- raw reasoning/API response artifacts;
- redundant generation and scoring internals.

The validator rejects forbidden columns, schema drift, row/branch drift,
checksum changes, model/setting changes, dual-subset mismatches, and incomplete
alternative-prediction coverage.

The release intentionally deletes the former clean-panel and raw factorial
reconstruction inputs. Exact historical sample reconstruction is out of scope;
the frozen sampled frames are authoritative.

## Derived analysis lineage

`paper/analyze_release_data.py` reads the frozen audits and writes:

- `paper/data/scorer_results.json`;
- the current representative summary JSON;
- representative, sampling, routing, factorial, H3, alternative, external,
  taxonomy, and rater-agreement CSV/Markdown tables.

`paper/analyze_existing_data.py` reads representative/factorial A1/A2 data and
writes the correction, reference sensitivity, rater sensitivity,
heterogeneity, and power artifacts.

The empirical sampling figure reads only the regenerated representative
summary. The contrast schematic uses declared illustrative constants.

## Not included

- hosted response generation or its caches;
- automatic-pipeline or alternative-judge API regeneration;
- protected twins or private label archives;
- empty dual scaffolds;
- full GaslightBench or SYCON checkouts;
- manuscript source, venue variants, or manuscript PDFs.

## Paired H3 alignment

Current A1 rows yield paired H3 `RD=+0.150` with item-clustered interval
`[+0.061,+0.279]`. The current paper and generated release artifacts report
this frozen estimate.
