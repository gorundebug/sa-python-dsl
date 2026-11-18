PYTHON ?= .venv/bin/python

.PHONY: test mcp-conformance release-check

test:
	$(PYTHON) -m pytest tests

mcp-conformance:
	$(PYTHON) scripts/mcp_release_check.py --skip-tests

release-check:
	$(PYTHON) scripts/mcp_release_check.py

# Local artifacts only. The Codex archive preserves its immutable runtime pin;
# producing an archive does not publish or update that runtime.
.PHONY: package package-dsl package-plugin
package: package-dsl package-plugin

package-dsl:
	$(PYTHON) -m pip wheel --no-deps --wheel-dir dist .

package-plugin:
	$(PYTHON) scripts/build_plugin_archive.py

.PHONY: package-check
package-check:
	$(PYTHON) scripts/check_broker_packages.py $(PACKAGE_CHECK_ARGS)
