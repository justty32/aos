"""menu 測試共用：暫存 node、CLI 與獨立 fake 帳任務。"""
import json
import os
from pathlib import Path
import subprocess
import sys

PACK = Path(__file__).resolve().parents[1]
TOP = PACK.parents[1]
sys.path[:0] = [str(TOP / 'tests'), str(PACK), str(TOP / 'packs/budget')]
from base import CoreCase
import _proc
import aos7_budget as bg
from aos7_fs import read_json, write_json

BIN = PACK / 'bin/aos7-menu'
HELLO = PACK / 'examples/hello/menu.json'
TOOLS = {'v': 1, 'tools': {'check': {'argv': ['true'], 'args': ['path'], 'out': 'code'}}}


def simple(slot=None):
    layer = {'ask': '問一層', 'exit': {'text': '交回'}, 'next': 'end'}
    if slot is None:
        layer['options'] = [{'text': '繼續', 'next': 'end'}]
    else:
        layer.update(slot=slot, do={'write': 'out/reply.txt'})
    return {'v': 1, 'name': 'test', 'start': 'one', 'required': [], 'layers': {'one': layer}}


class MenuCase(CoreCase):
    def setUp(self):
        super().setUp()
        self.node = Path(self.root) / 'node'
        self.node.mkdir()

    def cli(self, *args, rc=0, env=None, wait=30):
        p = subprocess.run([sys.executable, '-B', str(BIN), *map(str, args)],
                           capture_output=True, text=True, timeout=wait,
                           env=dict(os.environ, **(env or {})))
        self.assertEqual(p.returncode, rc, p.stdout + p.stderr)
        self.assertLessEqual(len(p.stderr.splitlines()), 1, p.stderr)
        if rc in (1, 2, 3):
            self.assertEqual(len(p.stderr.splitlines()), 1, p.stderr)
        return p

    def run_menu(self, *extra, menu=HELLO, **kw):
        return self.cli('run', self.node, menu, *extra, **kw)

    def state(self, run='hello'):
        return read_json(str(self.node / 'menu' / run / 'state.json'))

    def logs(self, run='hello'):
        return [json.loads(x) for x in (self.node / 'menu' / run / 'log.jsonl').read_text().splitlines()]

    def fixture(self, obj, replies=('選：1',)):
        d = self.node / 'fixture'
        d.mkdir(exist_ok=True)
        write_json(str(d / 'menu.json'), obj)
        write_json(str(d / 'practice.json'), {'v': 1, 'replies': list(replies)})
        return d / 'menu.json'

    def ledger(self):
        bd = self.node / 'budget/llm'
        write_json(str(self.node / '.aos/round.json'), {'round': 5, 'open': False})
        write_json(str(bd / 'grant.json'), {'v': 1, 'grant': 'menu-test', 'budget': 'llm',
            'holder': 'menu', 'resource': 'llm.tokens', 'gateway': 'llm.fake', 'amount': 1000000,
            'clock': 'completed_tock', 'from': 0, 'until': 1000, 'delegate': False})
        binary = TOP / 'packs/budget/bin/aos7-budget'
        p = subprocess.run([sys.executable, str(binary), 'init', 'budget/llm'], cwd=self.node,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        p = subprocess.Popen([sys.executable, str(binary), 'ledger', 'budget/llm'], cwd=self.node,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        _proc.track(self, p, group=True)
        self.wait_for(lambda: bg.ledger_running(bg.Bud(str(bd)), wait=0))
