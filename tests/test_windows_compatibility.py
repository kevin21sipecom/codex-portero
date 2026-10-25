from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import refresh_catalog

class WindowsCompatibilityTest(unittest.TestCase):
    def test_hook_starts_off_and_returns_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([sys.executable, str(ROOT / "hooks/portero_hook.py")],
                input=json.dumps({"hook_event_name": "SessionStart", "session_id": "windows", "source": "startup"}),
                text=True, capture_output=True, timeout=5,
                env=os.environ | {"PLUGIN_DATA": tmp, "PORTERO_CATALOG_FIXTURE": str(ROOT / "tests/fixtures/catalog.json")})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("OFF", json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_receive_handles_buffered_responses_on_native_pipes(self):
        code = "import sys,time; print('{\"method\":\"notice\"}'); print('{\"id\":1,\"result\":{}}'); print('{\"id\":2,\"result\":{\"data\":[]}}'); sys.stdout.flush(); time.sleep(1)"
        proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(refresh_catalog.receive(proc, 1, .5)["id"], 1)
            self.assertEqual(refresh_catalog.receive(proc, 2, .5)["id"], 2)
        finally:
            proc.terminate()
            proc.wait(timeout=3)
            proc.stdout.close()

    def test_fetch_uses_resolved_cli_and_closes_streams(self):
        script = """import json,sys
for line in sys.stdin:
 request=json.loads(line)
 if 'id' in request:
  print(json.dumps({'id':request['id'],'result':{'data':[]}}),flush=True)
"""
        real_popen = subprocess.Popen
        processes = []
        def launch(args, **kwargs):
            self.assertEqual(args, ["resolved-cli", "app-server", "--stdio"])
            proc = real_popen([sys.executable, "-c", script], **kwargs)
            processes.append(proc)
            return proc
        with patch.object(refresh_catalog.shutil, "which", return_value="resolved-cli"), patch.object(refresh_catalog.subprocess, "Popen", side_effect=launch):
            self.assertEqual(refresh_catalog.fetch(), {"data": []})
        self.assertIsNotNone(processes[0].poll())
        self.assertTrue(processes[0].stdin.closed)
        self.assertTrue(processes[0].stdout.closed)

    def test_receive_timeout_is_bounded_even_with_partial_line(self):
        code = 'import sys,time; sys.stdout.write("partial"); sys.stdout.flush(); time.sleep(3)'
        proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        start = time.monotonic()
        try:
            with self.assertRaises(TimeoutError):
                refresh_catalog.receive(proc, 1, .15)
            self.assertLess(time.monotonic() - start, 1)
        finally:
            proc.terminate()
            proc.wait(timeout=3)
            proc.stdout.close()

if __name__ == "__main__":
    unittest.main()
