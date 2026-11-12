# Verify MCP reads shared timeout metadata and keeps its CLI fallback.
import json
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch

MCP = runpy.run_path(str(Path(__file__).parents[1] / 'bin/aos-mcp'))


class TimeoutTests(unittest.TestCase):
    def test_metadata_timeout_shapes(self):
        for value in (1200, {'val': 1200}):
            data = [{'name': 'demo', 'tooldef': {}, 'metainfo':
                     {'cost': {'time_ms': 1}, 'timeout_ms': value}}]
            result = subprocess.CompletedProcess([], 0, json.dumps(data).encode(), b'')
            with patch.object(MCP['subprocess'], 'run', return_value=result):
                self.assertEqual(MCP['load_tools'](['tools.json'])['demo']['max_s'], 1.2)

    def test_absent_timeout_keeps_fallback_available(self):
        data = [{'name': 'demo', 'tooldef': {}, 'metainfo': {'cost': {'time_ms': 1}}}]
        result = subprocess.CompletedProcess([], 0, json.dumps(data).encode(), b'')
        with patch.object(MCP['subprocess'], 'run', return_value=result):
            self.assertIsNone(MCP['load_tools'](['tools.json'])['demo']['max_s'])
        with patch.object(MCP['subprocess'], 'Popen') as popen:
            popen.return_value.communicate.return_value = (b'ok', b'')
            popen.return_value.returncode = 0
            MCP['call']('demo', {'reg': 'tools.json', 'max_s': None}, {}, '/tmp', '/tmp', 17)
            self.assertEqual(popen.return_value.communicate.call_args.kwargs['timeout'], 17)

    def test_bad_timeout_uses_fallback_with_warning(self):
        """壞的 timeout_ms＝當沒寫：max_s 是 None（用 --timeout-s），stderr 一行帶工具名的提醒，不是 ToolsBad。"""
        import contextlib
        import io
        for value in ('soon', 1.5, True, {'val': None}):
            data = [{'name': 'demo', 'tooldef': {}, 'metainfo': {'timeout_ms': value}}]
            result = subprocess.CompletedProcess([], 0, json.dumps(data).encode(), b'')
            errors = io.StringIO()
            with patch.object(MCP['subprocess'], 'run', return_value=result), contextlib.redirect_stderr(errors):
                self.assertIsNone(MCP['load_tools'](['tools.json'])['demo']['max_s'])
            self.assertIn('aos-mcp: warning: tool demo: ', errors.getvalue())
            self.assertIn('skipped', errors.getvalue())


if __name__ == '__main__':
    unittest.main()
