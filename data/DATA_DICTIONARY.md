# Data dictionary

The exact column order for each CSV is machine-readable in
`confirmatory_v1/manifest.json`. This document defines the union of released
fields.

## Common identifiers and content

- `record_id`: unique response or prediction identifier within a file.
- `model_slug`: evaluated response model identifier; never the A1/A2 rater.
- `item_id`: benchmark item or constructed-nonreferent identifier.
- `branch`: conversational arm or turn-specific arm.
- `domain`: item domain where applicable.
- `layer`: source benchmark/screening layer.
- `response_text`: frozen assistant response consumed by the rater. A small
  set of upstream-empty cells is declared in the manifest.
- `trajectory`: SYCON condition (`neutral`, `pressure`, or `existence`).
- `turn`: zero-indexed SYCON turn.
- `topic_id`: SYCON topic identifier.
- `paired_contrast`: paired-audit family; the released subset is `H3`.

## Automatic-pipeline fields

- `unsupported_assertion`: binary automatic-pipeline label.
- `unsupported_answer_subtype`: automatic subtype assigned by the
  automatic pipeline.
- `baseline_appropriate`: automatic boundary-behavior label.
- `epistemic_behavior`: automatic response-behavior category.
- `transition`: automatic transition category relative to the earlier turn.
- `scoring_source`: rule/routed-judge route marker. It identifies the frozen
  automatic pipeline, not an A1/A2 rater.
- `auto_incorrect`: non-original Gaslight incorrectness-heuristic label.
- `auto_accepts`: non-original SYCON presupposition-acceptance label.

## Historical `human_*` reference fields

These are LLM-rater fields, not human annotations.

- `human_unsupported_assertion`: A1 or A2 binary reference label. In the
  constructed-nonreferent panel it denotes an entity-specific unsupported
  factual assertion; in Gaslight it
  denotes factual incorrectness; in SYCON it denotes acceptance of the false
  presupposition.
- `human_appropriate_boundary`: whether the response sets an appropriate
  uncertainty, correction, clarification, or premise boundary under the
  audit-specific rubric.
- `human_subtype`: `none`, `referent_substitution`,
  `novel_entity_fabrication`, or `unsupported_speculation`.
- `human_h4_appropriate`: evidence-branch appropriateness (`true`, `false`,
  or `na`).
- `annotator_id`: `A1` for primary or `A2` for secondary.
- `dual_annotation`: historical marker for dual-rater subset membership.
- `annotator_model`: fixed API model identifier for A1/A2.
- `annotation_run_id`: frozen labeling-run identifier.
- `annotation_prompt`: prompt filename used by the frozen run.
- `audit_role`: audit/frame role.
- `audit_schema`: external-suite rubric identifier.

## Gaslight task metadata

- `statement_id`, `modifier_id`: source statement/modifier identifiers.
- `modifier_category`, `statement_category`: source benchmark categories.
- `truth`: task-provided true statement used by the special rating rubric.
- `false_statement`: task-provided false statement tested by the response.

## SYCON task metadata

- `question`: original question.
- `presupposition`: false presupposition evaluated by the special rubric.
- `correction`: task-provided factual correction.

## Alternative automatic judge

- `pipeline_unsupported_assertion`: frozen primary automatic-pipeline label on
  the representative row.
- `alternative_judge_model`: alternative automatic scorer identifier. This is
  not A2.
- `alternative_unsupported_assertion`: frozen alternative automatic
  unsupported-assertion prediction.
- `alternative_appropriate_boundary`: frozen alternative automatic boundary
  prediction.

## Existence false-positive taxonomy

- `scorer`: `automatic_pipeline` or `alternative_automatic_judge`.
- `category`: mutually exclusive, author-coded surface category.

## Removed fields

Release transformations intentionally remove `messages`, `judge_rationale`,
provider/cache fields, timestamps, raw reasoning or response payloads, and
redundant generation-pipeline columns. Their absence is enforced by
`scripts/verify_release_data.py`.
