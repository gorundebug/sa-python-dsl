import subprocess
import tempfile
import unittest
from pathlib import Path

from sa_dsl.business_tasks import (
    BusinessTaskError,
    inspect_business_tasks,
    run_verification,
)


TASK = """# Task 1/1: `MakeOrder`

| Field | Value |
|-------|-------|
| Language | `Go` |
| Kind | `StreamFunction` |
| File | `orders/internal/functions/order.go` |
| Test | `orders/internal/functions/order_test.go` |
| Service | `Orders` |

## Stream types

- Input: `Order` - `model/order.go`
- Output: `OrderState` - `model/order_state.go`

## Checklist

- [ ] Run `make test`
"""


class BusinessTasksTest(unittest.TestCase):
    def test_inspect_returns_structured_tasks_and_progress(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-tasks-") as temporary:
            workspace = Path(temporary)
            directory = workspace / "spec/orders"
            directory.mkdir(parents=True)
            (directory / "task1.md").write_text(TASK, encoding="utf-8")
            (workspace / "spec/progress.md").write_text(
                "- [x] orders/task1.md - MakeOrder - Go - done\n", encoding="utf-8"
            )
            (workspace / "Makefile").write_text("test:\n\t@true\n", encoding="utf-8")

            result = inspect_business_tasks(workspace)

            self.assertEqual({"total": 1, "complete": 1, "pending": 0, "migrations": 0}, result["summary"])
            task = result["tasks"][0]
            self.assertEqual("MakeOrder", task["name"])
            self.assertEqual("complete", task["status"])
            self.assertEqual("orders/internal/functions/order.go", task["file"])
            self.assertEqual(["test"], task["verificationIds"])
            self.assertEqual([{"id": "test", "argv": ["make", "test"]}], result["verifications"])

    def test_verification_uses_fixed_argv(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-verification-") as temporary:
            workspace = Path(temporary)
            (workspace / "Makefile").write_text("test:\n\t@true\n", encoding="utf-8")
            captured = {}

            def runner(command, **kwargs):
                captured["command"] = command
                captured["kwargs"] = kwargs
                return subprocess.CompletedProcess(command, 0, "passed\n", "")

            ticks = iter((10.0, 10.25))
            result = run_verification(
                workspace, "test", runner=runner, monotonic=lambda: next(ticks)
            )

            self.assertEqual(["make", "test"], captured["command"])
            self.assertEqual(250, result["durationMs"])
            self.assertEqual("success", result["status"])

    def test_verification_rejects_arbitrary_command(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-verification-") as temporary:
            with self.assertRaises(BusinessTaskError) as raised:
                run_verification(Path(temporary), "rm -rf .")
            self.assertEqual("SA_VERIFICATION_NOT_ALLOWED", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
