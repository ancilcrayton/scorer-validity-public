# Data card

## Purpose

This release contains the minimum response-level frozen data needed to
reproduce the scorer-validity paper's analyses without access to hosted APIs,
private caches, or the parent `unknown-under-pressure` checkout.

It supports measurement research on whether an automatic scorer preserves a
declared treatment–comparator contrast. It is not a model leaderboard, a
ground-truth corpus, or a general validation of any scorer.

## Contents

The manifest covers 5,428 released rows across twelve files:

- representative A1 audit: 288 rows; six arms, 48 per arm;
- representative A2 subset: 96 rows; four arms, 24 per arm;
- factorial A1 and A2 audits: 1,200 rows each; four arms on 300 keys;
- primary hard audit: 550 stress-sampled rows;
- primary paired H3 audit: 200 rows on 100 keys;
- Gaslight A1/A2 audits: 300/100 rows;
- SYCON A1/A2 audits: 900/300 turn judgments;
- alternative automatic-judge predictions: 288 rows;
- author-coded Existence false-positive taxonomy: six rows.

Exact schemas, hashes, branch counts, sampling metadata, and annotation
settings are in `confirmatory_v1/manifest.json`.

## Label provenance

Historical `human_*` field names are retained for compatibility. They are LLM
reference-rater labels:

- A1: Mistral Large 3 2512;
- A2: MiniMax M3.

Neither label source is a human annotator or ground truth. The two raters were
not adjudicated into consensus. A2 is used to measure process sensitivity, not
to decide that A1 is correct. Temperature was `0.0` and seed was `20260729`.
One listed MiniMax M3 record used low reasoning effort after repeated null
completions.

## Sampling and intended uses

The representative audit is balanced across arm and evaluated model and
targets that equal-model mixture. The hard audit deliberately enriches
difficult and routed cases and cannot estimate deployment precision. The
factorial and H3 frames preserve item–model keys for paired contrasts.
Gaslight and SYCON are transfer audits of non-original automatic
implementations; they do not evaluate every scorer used with those benchmarks.

Appropriate uses include reproducing the released summaries, testing
contrast-specific measurement methods, and auditing the supplied code.
Inappropriate uses include treating response claims as facts, treating A1/A2
as human labels, estimating provider traffic, or generalizing the stress
sample as a probability sample.

## Release minimization

The release retains response text, record/item/model/arm identifiers,
automatic labels, A1/A2 labels, task metadata needed by the special external
rubrics, and provenance fields. It removes message histories, judge
rationales, provider/cache fields, timestamps, raw reasoning, and redundant
raw-pipeline columns.

Eight unique source records have genuinely empty hosted response text (one
factorial record appears in both A1 and A2). They remain because the frozen
analyses consumed their labels. The manifest enumerates every affected ID.

No protected twins, private archives, empty dual scaffolds, API caches,
manuscript source, or full third-party checkout is included.

## Risks and limitations

Responses can contain confident falsehoods, speculation, or harmful benchmark
content. They are research artifacts and should not be presented as factual
answers. LLM-rater decisions can be wrong or prompt-sensitive. The sparse
representative calibration yields wide intervals, and the external audits use
task-specific schemas and non-original automatic scorers.

The current paired H3 release and paper reflect the current A1 rerating
(`RD=+0.150`, item-clustered interval `[+0.061,+0.279]`).

## Licensing

Original release labels and transformations are CC BY 4.0 under
`../LICENSE-DATA`. Source-derived fields retain upstream MIT terms under
`../THIRD_PARTY_NOTICES.md`.
