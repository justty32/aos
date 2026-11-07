"""Provide isolated offline board fixtures and an inspectable fake explanation endpoint."""
import datetime as dt
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collect
import eli5
import eli5_inputs

WORDS = "這件事像整理家裡的抽屜。現在已經整理好一部分，接著會繼續檢查。"


def nest(blocks):
    result = {}
    for key in blocks:
        target = result
        parts = key.split('.')
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = WORDS
    return result


class OfflineBoard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos_eli5_')
        self.addCleanup(self.tmp.cleanup)
        self.board = Path(self.tmp.name)
        self.cfg = {'aos_repo': str(self.board), 'read_roots': [str(self.board)],
                    'repos': [], 'report_globs': [], 'port': 8765,
                    'summary': {'enabled': False, 'eli5_enabled': True,
                                'eli5_min_interval_min': 4,
                                'base_url': 'http://offline.invalid/v1', 'model': 'fake'},
                    'lines': [{'id': 'alpha', 'title': 'First', 'handoff': 'handoff.md'},
                              {'id': 'beta', 'title': 'Second', 'handoff': None}]}
        self.write('handoff.md', 'The work is progressing.')
        self.write('summary/latest.md', 'Summary evidence.')
        self.events = [self.event('alpha', 'First evidence.'),
                       self.event('beta', 'Second evidence.')]
        self.flush()
        self.calls = []
        self.responses = []
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {'AOS_PROGRESS_DIR': str(self.board)}).start()
        patch('eli5_inputs.codex_processes', return_value=[]).start()
        patch('urllib.request.urlopen', side_effect=self.endpoint).start()

    def event(self, line, text, **extra):
        return dict(ts=collect.iso_now(), line=line, text=text,
                    links=[], **{'status': 'progress', **extra})

    def write(self, path, content):
        target = self.board / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')

    def flush(self):
        self.write('data/progress.jsonl', '\n'.join(json.dumps(x) for x in self.events)+'\n')

    def endpoint(self, request, **kwargs):
        self.assertEqual(request.full_url, 'http://offline.invalid/v1/chat/completions',
                         'Unexpected network call refused')
        body = json.loads(request.data)
        payload = json.loads(body['messages'][1]['content'])['items']
        self.calls.append(payload)
        result = self.responses.pop(0) if self.responses else {'items': {key: WORDS for key in payload}}
        if callable(result):
            result = result(payload)
        reply = {'choices': [{'message': {'content': json.dumps(result)}}],
                 'usage': {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18}}
        return io.BytesIO(json.dumps(reply).encode())

    def stored(self, kind):
        return json.loads((self.board / f'eli5/{kind}.json').read_text())

    def age(self, kind):
        value = self.stored(kind)
        value['generated_at'] = (dt.datetime.now().astimezone()-dt.timedelta(hours=2)).isoformat()
        self.write(f'eli5/{kind}.json', json.dumps(value))

    def generate(self, **kwargs):
        return (eli5.maybe_main(self.board, self.cfg, **kwargs),
                eli5.maybe_detail(self.board, self.cfg, **kwargs))
