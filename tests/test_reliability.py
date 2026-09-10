import os
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sa_dsl.execution import write_canonical_yaml
from sa_dsl.process_runner import run_bounded, OUTPUT_LIMIT
from sa_dsl.business_tasks import run_verification, BusinessTaskError
from sa_dsl.operation_audit import record_operation_safely
from sa_dsl import generation_transaction as gt
from test_generation_transaction import project_workspace, Client, generated_archive


class ReliabilityTest(unittest.TestCase):
    def test_parallel_exports_are_complete_and_leave_no_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = SimpleNamespace(workspace=root, canonical=SimpleNamespace(output='graph.yaml'))
            barrier = threading.Barrier(2)
            original = Path.replace
            def replace(path, target):
                barrier.wait(timeout=3)
                return original(path, target)
            with patch.object(Path, 'replace', replace), ThreadPoolExecutor(2) as pool:
                list(pool.map(lambda text: write_canonical_yaml(manifest, text), ['a'*10000, 'b'*10000]))
            self.assertIn((root/'graph.yaml').read_text(), ['a'*10000, 'b'*10000])
            self.assertEqual(['graph.yaml'], [p.name for p in root.iterdir()])

    def test_apply_is_exclusive_per_workspace_and_rechecks_replay(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            manifest = project_workspace(Path(tmp))
            token = gt.preview_generation_transaction(manifest, client_factory=lambda _: Client(generated_archive()), now=lambda:1000)['preview']
            entered, release = threading.Event(), threading.Event()
            original = gt._run_merge
            def merge(*args, **kwargs):
                entered.set()
                self.assertTrue(release.wait(5))
                return original(*args, **kwargs)
            def apply():
                return gt.apply_generation_transaction(manifest, preview_id=token['previewId'], preview_revision=token['previewRevision'], now=lambda:1001)
            with patch.object(gt, '_run_merge', merge), ThreadPoolExecutor(1) as pool:
                first = pool.submit(apply)
                try:
                    self.assertTrue(entered.wait(5))
                    self.assertEqual('SA_GENERATION_BUSY', apply()['diagnostics'][0]['code'])
                    # A separate process observes the lock too.
                    import subprocess
                    script = 'from sa_dsl.manifest import load_manifest; from sa_dsl.generation_transaction import apply_generation_transaction as a; import sys; print(a(load_manifest(sys.argv[1]),preview_id=sys.argv[2],preview_revision=sys.argv[3],now=lambda:1001)["diagnostics"][0]["code"])'
                    result = subprocess.run([sys.executable, '-c', script, tmp, token['previewId'], token['previewRevision']], capture_output=True, text=True, timeout=5)
                    self.assertEqual('SA_GENERATION_BUSY', result.stdout.strip(), result.stderr)
                    other_manifest = project_workspace(Path(other))
                    result = gt.apply_generation_transaction(other_manifest, preview_id='x'*24, preview_revision='invalid')
                    self.assertNotEqual('SA_GENERATION_BUSY', result['diagnostics'][0]['code'])
                finally:
                    release.set()
                self.assertEqual('success', first.result()['status'])
            self.assertEqual('SA_PREVIEW_ALREADY_APPLIED', apply()['diagnostics'][0]['code'])

    @unittest.skipUnless(os.name == 'posix', 'POSIX make fixture')
    def test_timeout_kills_descendants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'Makefile').write_text("test:\n\t@sh -c 'sleep 0.6; echo survived > survived.txt'\n")
            with self.assertRaises(BusinessTaskError) as raised:
                run_verification(root, 'test', timeout_seconds=0.15)
            self.assertEqual('SA_VERIFICATION_TIMEOUT', raised.exception.code)
            time.sleep(0.8)
            self.assertFalse((root/'survived.txt').exists())

    def test_output_is_bounded_and_full_log_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_bounded([sys.executable, '-c', 'print("a"*200000); print("THE END")'], cwd=tmp, env=os.environ.copy(), timeout=5, log_directory=Path(tmp)/'logs')
            self.assertLess(len(result.stdout), OUTPUT_LIMIT+100)
            self.assertIn('THE END', result.stdout)
            self.assertGreater(Path(result.log_paths['stdout']).stat().st_size, 200000)

    def test_audit_failure_preserves_success_and_application(self):
        payload = {'status':'success', 'application':{'previewId':'done'}, 'diagnostics':[]}
        with patch('sa_dsl.operation_audit.record_operation', side_effect=OSError('disk full')):
            record_operation_safely(Path('.'), 'apply-generation', payload, time.monotonic())
        self.assertEqual('success', payload['status'])
        self.assertEqual('done', payload['application']['previewId'])
        self.assertEqual('warning', payload['diagnostics'][0]['severity'])
