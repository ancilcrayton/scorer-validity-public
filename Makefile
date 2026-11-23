.PHONY: install analyze figure reproduce all verify-data provenance-check test annotation-dry-run release-check

UV ?= uv
PYTHON = $(UV) run --project . --frozen python
ANNOTATION_CONFIGS = \
	scripts/llm_reference_annotation/config_representative_arm.json \
	scripts/llm_reference_annotation/config_factorial_expanded.json \
	scripts/llm_reference_annotation/config_hard_audit.json \
	scripts/llm_reference_annotation/config_paired_h3.json \
	scripts/llm_reference_annotation/config_gaslight.json \
	scripts/llm_reference_annotation/config_sycon.json

install:
	$(UV) sync --project . --frozen --extra dev

verify-data:
	$(PYTHON) scripts/verify_release_data.py

analyze: verify-data
	$(PYTHON) paper/analyze_release_data.py
	$(PYTHON) paper/analyze_existing_data.py

figure: analyze
	$(PYTHON) paper/plot_problem_contrast.py
	$(PYTHON) paper/plot_sampling_precision.py

reproduce: figure

all: reproduce

provenance-check: verify-data

test: verify-data
	$(UV) run --project . --frozen --extra dev pytest -q

annotation-dry-run:
	@for config in $(ANNOTATION_CONFIGS); do \
		$(PYTHON) scripts/llm_reference_annotation/run_validators.py \
			--config "$$config" --role all --dry-run || exit 1; \
	done

release-check: reproduce test annotation-dry-run verify-data
	@echo "Release checks passed."
