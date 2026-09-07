PYTHON ?= .venv/bin/python

.PHONY: test mcp-conformance release-check

test:
	$(PYTHON) -m unittest discover -s tests

mcp-conformance:
	$(PYTHON) scripts/mcp_release_check.py --skip-tests

release-check:
	$(PYTHON) scripts/mcp_release_check.py
