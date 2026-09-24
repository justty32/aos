"""郵差／心跳測試共用：手工擺一份假的團隊資料夾（spec/team/examples 的名冊＋每個成員一個假家）。"""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import aos_team_format as fmt
import aos_team_post as post
import aos_team_task as task

PROTO = Path(__file__).resolve().parents[2]
CLI_TEAM = PROTO / 'cli' / 'aos-team'
EXAMPLES = PROTO / 'spec' / 'team' / 'examples'
ROSTER = {'_metainfo': {'_type': 'aos_team', '_version': 1}, 'project': '../p', 'tz': 'Asia/Taipei',
          'members': {'lead': {'template': 'lead', 'mail_to': ['worker-1', 'reviewer', 'human']},
                      'worker-1': {'template': 'worker', 'mail_to': ['lead', 'human']},
                      'reviewer': {'template': 'reviewer', 'mail_to': ['lead', 'human']}},
          'limits': {'stale_minutes': 10, 'max_members': 6}}
TZ = datetime.timezone(datetime.timedelta(hours=8))


def fake_home(home):
    """最小的假成員家：input/ 資料夾、state.json（input 是資料夾）、access.json（工具關牢用）。"""
    home = Path(home)
    (home / 'input').mkdir(parents=True, exist_ok=True)
    (home / 'prompts').mkdir(exist_ok=True)
    (home / 'state.json').write_text(json.dumps({'input': 'input/'}), encoding='utf-8')
    (home / 'access.json').write_text(json.dumps({'_metainfo': {'_type': 'agent_access', '_version': 1},
                                                  'mounts': {'ws': '../../../p'}, 'cwd': 'ws', 'net': False}),
                                      encoding='utf-8')
    return home


class TeamCase(unittest.TestCase):
    roster = ROSTER

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='aos-team-post-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.team = self.tmp / 'team'
        self.project = self.tmp / 'p'
        self.project.mkdir()
        self.team.mkdir()
        (self.team / 'team.json').write_text(json.dumps(self.roster, ensure_ascii=False), encoding='utf-8')
        self.lay = fmt.Layout(self.team)
        for d in self.lay.skeleton(self.roster['members']):
            d.mkdir(parents=True, exist_ok=True)
        for name in self.roster['members']:
            fake_home(self.lay.member(name))
        self.rost = fmt.load_roster(self.team)
        self.now = datetime.datetime.now(TZ).replace(microsecond=0)
        self.lines, self.submitted, self.health = [], [], {}
        self.seq = 0

    # ------------------------------------------------------------ 郵差 ----

    def clock(self):
        return self.now

    def fake_submit(self, job, argv):
        self.submitted.append((job['id'], argv))
        return {'mode': 'test'}

    def post(self, **kw):
        kw.setdefault('clock', self.clock)
        kw.setdefault('submit', self.fake_submit)
        kw.setdefault('health', lambda name: self.health.get(name, ('ok', 'ok')))
        kw.setdefault('out', self.lines.append)
        kw.setdefault('watch_every', 0)
        return post.Post(self.team, **kw).run()

    def cli(self, *args, env=None, timeout=30):
        e = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        e.pop('AOS_KERNEL_HOME', None)
        e.update(env or {})
        return subprocess.run([sys.executable, str(CLI_TEAM), *map(str, args), '--target', str(self.team)],
                              capture_output=True, text=True, env=e, timeout=timeout)

    # ------------------------------------------------------------ 寫檔 ----

    def new_id(self, sender):
        self.seq += 1
        return '%d-%d-%s' % (time.time_ns() + self.seq, 4242, sender)

    def letter(self, sender, to, status, text='內容', reply_to=None, rev=None, folder=None, **over):
        lid = self.new_id(sender)
        obj = {'id': lid, 'from': sender, 'to': to, 'status': status, 'reply_to': reply_to, 'rev': rev,
               'text': text, 'at': self.now.isoformat()}
        obj.update(over)
        box = self.lay.outbox(folder or sender)
        box.mkdir(parents=True, exist_ok=True)
        (box / (lid + '.json')).write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        return lid

    def request(self, sender, kind, **fields):
        rid = self.new_id(sender)
        obj = dict({'id': rid, 'from': sender, 'kind': kind, 'at': self.now.isoformat()}, **fields)
        box = self.lay.outbox(sender)
        (box / (rid + '.json')).write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        return rid

    def handoff(self, done_when=None, sender='lead', assignee='worker-1', **over):
        fields = {'assignee': assignee, 'workflow': 'IMPORT.md', 'goal': '導入 heartbeat',
                  'done_when': done_when or [{'kind': 'file_exists', 'path': 'AGENTS.md'}]}
        fields.update(over)
        return self.request(sender, 'handoff', **fields)

    # ------------------------------------------------------------ 看結果 ----

    def inbox(self, name):
        return sorted(p.name for p in (self.lay.member(name) / 'input').glob('mail-*.json'))

    def mails(self, name):
        """成員 input/ 裡的信（照檔名）：[(檔名, content)]。"""
        out = []
        for p in sorted((self.lay.member(name) / 'input').glob('mail-*.json')):
            out.append((p.name, json.loads(p.read_text(encoding='utf-8'))['content']))
        return out

    def human_mail(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(self.lay.human_inbox.glob('*.json'))]

    def pick_up(self, name, how='done'):
        """假裝成員 idle 收件：把 input/mail-*.json 搬進 done/（封存名），或停在 intake（state 記了、檔已搬）。"""
        home = self.lay.member(name)
        files = sorted((home / 'input').glob('mail-*.json'))
        cid = '%d-%d' % (time.time_ns(), os.getpid())
        pairs = []
        for f in files:
            dst = home / 'input' / 'done' / ('%s.%s.done' % (f.name, cid))
            dst.parent.mkdir(exist_ok=True)
            pairs.append({'src': str(f), 'dst': str(dst)})
            os.rename(f, dst)
        if how == 'intake':
            state = json.loads((home / 'state.json').read_text())
            state['intake'] = {'id': cid, 'base_len': 0, 'files': pairs}
            (home / 'state.json').write_text(json.dumps(state))
        return [p['dst'] for p in pairs]

    def ticket(self, tid='t-0001'):
        return task.load(self.lay, tid)

    def record(self, rid):
        return json.loads((self.lay.post_sent / (rid + '.json')).read_text(encoding='utf-8'))

    def job_result(self, jid, passed, results=None, run=1, **over):
        """假裝驗收員跑完第 run 次執行：寫 jobs/<jid>/result-<run>.json（身分照 jid：v-<單號>-r<rev>-a<attempt>）。"""
        d = self.lay.team / 'post' / 'jobs' / jid
        import re
        m = re.match(r'v-(t-[0-9]+(?:\.r[0-9]+)?)-r([0-9]+)-a([0-9]+)(?:-x[0-9a-f]+)?\Z', jid)
        head, rev, attempt = m.group(1), int(m.group(2)), int(m.group(3))
        res = {'task': head, 'rev': rev, 'attempt': attempt, 'pass': passed,
               'results': results if results is not None else
               [{'i': 0, 'kind': 'file_exists', 'result': 'pass' if passed else 'fail', 'pass': passed,
                 'why': 'AGENTS.md %s' % ('在' if passed else '不在')}]}
        res.update(over)
        fmt.write_json(d / ('result-%d.json' % run), res)
