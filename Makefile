PY ?= python
PROFILE ?= quick

.PHONY: install test test-all smoke replicate all report clean-cache

install:            ## install package + dev tools
	$(PY) -m pip install -e ".[dev]"

test:               ## fast tests (no OR-Tools searches)
	$(PY) -m pytest -m "not slow"

test-all:           ## all tests incl. short OR-Tools runs
	$(PY) -m pytest

smoke:              ## whole pipeline in ~1 minute (writes results_smoke/)
	$(PY) -m lastmile all --profile smoke

replicate:          ## Component 0 only: exact replication + solver benchmark
	$(PY) -m lastmile c0 --profile $(PROFILE)

all:                ## every component + SUMMARY.md
	$(PY) -m lastmile all --profile $(PROFILE)

report:             ## rebuild results/SUMMARY.md from saved numbers
	$(PY) -m lastmile report --profile $(PROFILE)

clean-cache:        ## forget cached solutions (forces re-solving)
	rm -f results/cache/solutions.jsonl results_smoke/cache/solutions.jsonl
