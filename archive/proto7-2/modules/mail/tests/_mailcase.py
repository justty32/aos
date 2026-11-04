"""審查 1–7 的退化測試，以及人類介面驗收。"""
import os
import sys
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"  # 子程序也不寫 bytecode
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tests'))
from base import MODULES
import datetime
import fcntl
import io
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MAIL = Path(MODULES) / 'mail'
sys.path.insert(0, str(MAIL))
import aos7_mail as mail
import aos7_mail_cli as cli
from aos7_events_pub import publish
from aos7_events_read import read


import aos7_mail_box as boxmod
import aos7_mail_ack as ackmod

class MailCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='aos72-mail-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)


    def cli(self, *args, rc=0, env=None):
        p = subprocess.run([str(MAIL / 'aos7-mail'), '--root', str(self.root), *args],
                           capture_output=True, text=True, timeout=30, env=dict(os.environ, **(env or {})))
        self.assertEqual(p.returncode, rc, p.stderr)
        return p


    def send(self, sender='alice', to='bob', status='REQUEST', title='請確認完整信件'):
        return json.loads(self.cli('send', sender, to, status, title).stdout)


    def box(self, who):
        return self.root / who / 'inbox'


    def acked(self, who):
        # ack 0 是公开 CLI 查目前累積確認值；不替事件進位。
        p = subprocess.run([sys.executable, str(Path(MODULES) / 'events/aos7-events'), 'read',
                            '--events', str(self.root / who / 'events'), '--channel', 'must', '--ack', '0'],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)['acked_upto']



class ReviewCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='aos72-mail-review-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)


    def run_cli(self, *args, rc=0, env=None):
        p = subprocess.run([str(Path(MODULES) / 'mail/aos7-mail'), '--root', str(self.root), *args],
                           capture_output=True, text=True, timeout=30, env=dict(os.environ, **(env or {})))
        self.assertEqual(p.returncode, rc, p.stderr)
        return p


    def send(self, status='PROGRESS', title='測試', sender='alice', to='bob'):
        return mail.send(self.root, sender, to, status, title)


