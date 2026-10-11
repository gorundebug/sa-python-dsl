import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests.test_mcp_protocol import tool_payload


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "processorder"
ORDER_SOURCE = "services/order_service/pipelines/order.py"
CONNECTOR_SOURCE = "connectors/order_service_api.py"


def canonical_copy(parent: Path) -> Path:
    destination = parent / "processorder"
    shutil.copytree(EXAMPLE, destination,
                    ignore=shutil.ignore_patterns("__pycache__", "build", "previews", "edits"))
    return destination


class McpAuthoringWorkflowTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_modular_project_node_connection_endpoint_and_error_route(self):
        with tempfile.TemporaryDirectory(prefix="sa-mcp-authoring-") as temporary:
            workspace = canonical_copy(Path(temporary))
            original_order = (workspace / ORDER_SOURCE).read_bytes()
            original_connector = (workspace / CONNECTOR_SOURCE).read_bytes()
            business = workspace / "business.py"
            business.write_text("# User-owned business implementation\nVALUE = 17\n")
            business_before = business.read_bytes()
            server = StdioServerParameters(command=sys.executable,
                args=["-m", "sa_dsl.mcp_server", "--workspace", str(workspace)], cwd=workspace)
            async with stdio_client(server) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()

                    async def call(name, arguments):
                        result = tool_payload(await session.call_tool(name, arguments))
                        self.assertEqual("success", result.get("status"), json.dumps(result, indent=2))
                        return result

                    async def site(source):
                        inspected = await call("inspect_python_authoring", {"source_file": source})
                        return {"source_file": source, "source_revision": inspected["sourceRevision"],
                                "before_line": inspected["insertionSites"][-1]["beforeLine"]}

                    async def apply(preview):
                        self.assertTrue(preview["sourceDiff"])
                        self.assertGreater(preview["architectureDiff"]["summary"]["total"], 0)
                        return await call("apply_python_changes", {
                            "preview_id": preview["previewId"], "preview_revision": preview["previewRevision"]})

                    node = await call("add_node", {
                        **await site(ORDER_SOURCE), "receiver": "order_pipeline", "factory": "map",
                        "symbol": "check_order_limits", "name": "Check Order Limits",
                        "arguments": {"function": "Function('CheckOrderLimits', package=order_package, module=LOCAL_MODULE)",
                                      "source": "split_pipeline", "value_type": "order_state"},
                    })
                    self.assertEqual(original_order, (workspace / ORDER_SOURCE).read_bytes())
                    await apply(node)
                    connection = await call("connect_ports", {
                        **await site(ORDER_SOURCE), "source": "check_order_limits", "target": "merge_results",
                        "role": "additional",
                    })
                    self.assertIn("merge_results << check_order_limits", connection["sourceDiff"])
                    await apply(connection)

                    endpoint = await call("add_endpoint", {
                        **await site(CONNECTOR_SOURCE), "receiver": "connector_order_service_api", "factory": "post",
                        "symbol": "preview_quote_endpoint", "name": "Preview Quote", "imports": ["Function"],
                        "arguments": {"function": "Function('PreviewQuote')", "path": "'/quote/preview'"},
                    })
                    await apply(endpoint)
                    error_route = await call("preview_python_changes", {
                        **await site(ORDER_SOURCE), "operations": [
                            {"kind": "add_node", "receiver": "order_pipeline", "factory": "process",
                             "symbol": "record_audit", "name": "Record Order Audit",
                             "arguments": {"function": "Function('RecordOrderAudit', package=order_package, module=LOCAL_MODULE)",
                                           "source": "split_pipeline", "value_type": "order_state"}},
                            {"kind": "add_node", "receiver": "order_pipeline", "factory": "error",
                             "symbol": "audit_error", "name": "Order Audit Error", "arguments": {"value_type": "order_state"}},
                            {"kind": "connect_ports", "source": "record_audit", "target": "audit_error", "role": "error"},
                        ]})
                    self.assertIn("record_audit >> audit_error", error_route["sourceDiff"])
                    self.assertIn("record_audit.on_error(audit_error)", error_route["sourceDiff"])
                    await apply(error_route)
                    await call("validate_project", {"project_path": "."})
                    await call("export_project", {"project_path": "."})
                    canonical = (workspace / ".service-architect/build/processorder.yaml").read_text()
                    self.assertIn("Check Order Limits", canonical)
                    self.assertIn("Preview Quote", canonical)
                    self.assertIn("Order Audit Error", canonical)
                    self.assertTrue((workspace / ORDER_SOURCE).read_bytes().startswith(original_order))
                    self.assertTrue((workspace / CONNECTOR_SOURCE).read_bytes().startswith(original_connector))
                    self.assertEqual(business_before, business.read_bytes())


class PythonAuthoringConcurrencyTest(unittest.TestCase):
    def test_two_previews_cannot_apply_concurrently_to_one_workspace(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch
        from sa_dsl import python_authoring as editor

        with tempfile.TemporaryDirectory(prefix="sa-edit-lock-") as temporary:
            workspace = canonical_copy(Path(temporary))
            info = editor.inspect_python_authoring(workspace, CONNECTOR_SOURCE)
            arguments = {"source_file": CONNECTOR_SOURCE, "source_revision": info["sourceRevision"],
                         "before_line": info["insertionSites"][-1]["beforeLine"], "imports": ["Function"],
                         "operations": [{"kind": "add_endpoint", "receiver": "connector_order_service_api",
                                         "factory": "post", "symbol": "quote_preview", "name": "Quote Preview",
                                         "arguments": {"function": "Function('QuotePreview')", "path": "'/quote/preview'"}}]}
            first = editor.preview_python_changes(workspace, **arguments)
            second = editor.preview_python_changes(workspace, **arguments)
            self.assertEqual("success", first["status"], first)
            self.assertEqual("success", second["status"], second)
            entered, release = Event(), Event()
            original_validation = editor._validated

            def held_validation(root):
                entered.set()
                if not release.wait(10):
                    raise AssertionError("concurrency test did not release validation")
                return original_validation(root)

            def apply(preview):
                return editor.apply_python_changes(workspace, preview_id=preview["previewId"],
                                                   preview_revision=preview["previewRevision"])

            with patch.object(editor, "_validated", held_validation), ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(apply, first)
                try:
                    self.assertTrue(entered.wait(10))
                    with self.assertRaises(editor.AuthoringError) as raised:
                        apply(second)
                    self.assertEqual("SA_AUTHORING_EDIT_BUSY", raised.exception.code)
                finally:
                    release.set()
                self.assertEqual("success", pending.result(timeout=10)["status"])
            with self.assertRaises(editor.AuthoringError) as raised:
                apply(second)
            self.assertEqual("SA_STALE_WORKSPACE", raised.exception.code)
