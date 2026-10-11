import subprocess
import tempfile
import unittest
from pathlib import Path

from sa_dsl.business_tasks import (
    BusinessTaskError,
    available_verifications,
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
    def test_adjacent_progress_lines_are_all_counted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-progress-lines-") as temporary:
            workspace = Path(temporary)
            directory = workspace / "spec/orders"
            directory.mkdir(parents=True)
            entries = []
            for index, name in enumerate(("First", "Second", "Third"), start=1):
                (directory / f"task{index}.md").write_text(TASK.replace("MakeOrder", name), encoding="utf-8")
                entries.append(f"- [x] orders/task{index}.md \u2014 {name} \u2014 Go \u2014 done\n")
            (workspace / "spec/progress.md").write_text("".join(entries), encoding="utf-8")
            self.assertEqual(3, inspect_business_tasks(workspace)["summary"]["complete"])

    def test_progress_follows_function_not_task_number_after_regeneration(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-renumbered-tasks-") as temporary:
            workspace = Path(temporary)
            directory = workspace / "spec/orders"
            directory.mkdir(parents=True)
            (directory / "task1.md").write_text(TASK.replace("MakeOrder", "AnotherFunction"), encoding="utf-8")
            (directory / "task2.md").write_text(TASK.replace("Task 1/1", "Task 2/2"), encoding="utf-8")
            other = workspace / "spec/other"
            other.mkdir()
            (other / "task1.md").write_text(TASK, encoding="utf-8")
            (directory / "task3.md").write_text(TASK.replace("`Go`", "`Rust`"), encoding="utf-8")
            for separator in ("-", "\u2014"):
                with self.subTest(separator=separator):
                    (workspace / "spec/progress.md").write_text(
                        f"- [x] orders/task1.md {separator} MakeOrder {separator} Go {separator} done\n",
                        encoding="utf-8")
                    result = inspect_business_tasks(workspace)
                    completed = [task["id"] for task in result["tasks"] if task["status"] == "complete"]
                    self.assertEqual(["spec/orders/task2.md"], completed)

    def test_progress_without_identity_does_not_complete_reused_slot(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-ambiguous-progress-") as temporary:
            workspace = Path(temporary)
            directory = workspace / "spec/orders"
            directory.mkdir(parents=True)
            (directory / "task1.md").write_text(TASK, encoding="utf-8")
            (workspace / "spec/progress.md").write_text("- [x] orders/task1.md\n", encoding="utf-8")
            self.assertEqual("pending", inspect_business_tasks(workspace)["tasks"][0]["status"])

    def test_build_is_discovered_from_includes_and_runs_with_fixed_argv(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-build-verification-") as temporary:
            workspace = Path(temporary)
            (workspace / "Makefile").write_text("include make.generated.mk\n", encoding="utf-8")
            (workspace / "make.generated.mk").write_text("build:\n\t@true\n", encoding="utf-8")
            directory = workspace / "spec/orders"
            directory.mkdir(parents=True)
            (directory / "task1.md").write_text(
                TASK.replace("make test", "make build"), encoding="utf-8")
            self.assertEqual([{"id": "build", "argv": ["make", "build"]}],
                             available_verifications(workspace))
            self.assertEqual(["build"], inspect_business_tasks(workspace)["tasks"][0]["verificationIds"])
            captured = []

            def runner(command, **kwargs):
                captured.append(command)
                return subprocess.CompletedProcess(command, 0, "compiled\n", "")

            result = run_verification(workspace, "build", runner=runner)
            self.assertEqual([["make", "build"]], captured)
            self.assertEqual("success", result["status"])

    def test_build_unavailable_without_target_and_rejects_arguments(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-build-verification-") as temporary:
            workspace = Path(temporary)
            (workspace / "Makefile").write_text("test:\n\t@true\n", encoding="utf-8")
            with self.assertRaises(BusinessTaskError) as raised:
                run_verification(workspace, "build")
            self.assertEqual("SA_VERIFICATION_UNAVAILABLE", raised.exception.code)
            for command in ("build; touch unsafe", "build GO=unsafe", "make build"):
                with self.subTest(command=command), self.assertRaises(BusinessTaskError) as raised:
                    run_verification(workspace, command)
                self.assertEqual("SA_VERIFICATION_NOT_ALLOWED", raised.exception.code)

    def test_verifications_follow_generated_make_includes_without_execution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-make-includes-") as temporary:
            workspace = Path(temporary)
            (workspace / "Makefile").write_text(
                "include make.generated.mk\n-include optional.mk\n"
                "include $(shell touch MUST_NOT_RUN)\n", encoding="utf-8")
            (workspace / "make.generated.mk").write_text(
                "test lint:\n\t@true\ninclude Makefile\n"
                "-include $(wildcard make.*.generated.mk)\n", encoding="utf-8")
            (workspace / "make.go.generated.mk").write_text(
                "integration-test:\n\t@true\n", encoding="utf-8")
            self.assertEqual({"test", "lint", "integration-test"},
                             {item["id"] for item in available_verifications(workspace)})
            self.assertFalse((workspace / "MUST_NOT_RUN").exists())
            result = run_verification(workspace, "test", runner=lambda command, **kwargs:
                                      subprocess.CompletedProcess(command, 0, "", ""))
            self.assertEqual("success", result["status"])

    def test_make_discovery_does_not_read_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-make-boundary-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace with spaces"
            workspace.mkdir()
            (root / "external.mk").write_text("test:\n\t@true\n", encoding="utf-8")
            (workspace / "linked.mk").symlink_to(root / "external.mk")
            (workspace / "Makefile").write_text(
                "include ../external.mk linked.mk\ninclude $(CURDIR)/local.mk\n", encoding="utf-8")
            (workspace / "local.mk").write_text("lint:\n\t@true\n", encoding="utf-8")
            self.assertEqual([{"id": "lint", "argv": ["make", "lint"]}],
                             available_verifications(workspace))

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
