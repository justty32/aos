"""驗收⑧：真 daemon＋kernel。郵差當 kernel 的反覆工作跑；一封信從 outbox 到對方記憶；
再走一整圈：領隊的 handoff → 工人（假模型，不叫真模型）在牢裡叫 team_say 回 DONE → 郵差把驗收當 kernel 一次性工作提交 → done。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import unittest

import aos_team_format as fmt
import aos_team_post
from _kernel_util import CLI, PY, KernelCase, read_json, wait_for
from _team_util import ROSTER, fake_home

HAS_BWRAP = shutil.which('bwrap') is not None


class LiveTeamTests(KernelCase):
    def setUp(self):
        super().setUp()
        self.requests = []
        records = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                records.append(body)
                msgs = body['messages']
                last_user = next(m['content'] for m in reversed(msgs) if m['role'] == 'user')
                tools = {t['function']['name'] for t in body.get('tools', [])}
                if msgs[-1]['role'] == 'user' and '· REQUEST · t-0001' in last_user and 'team_say' in tools:
                    args = {'to': 'lead', 'status': 'DONE', 'reply_to': 't-0001', 'rev': 1, 'text': 'AGENTS.md 好了'}
                    message = {'role': 'assistant', 'content': None, 'tool_calls': [
                        {'id': 'c1', 'type': 'function',
                         'function': {'name': 'team_say', 'arguments': json.dumps(args)}}]}
                else:
                    message = {'role': 'assistant', 'content': '收到'}
                raw = json.dumps({'choices': [{'message': message}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        self.addCleanup(self.close_server)
        config = self.root / 'llm.json'
        self.write(config, {'_metainfo': {'_type': 'llm_config', '_version': 1}, 'models': {
            'default': {'endpoint': 'http://127.0.0.1:%d/v1' % self.server.server_port,
                        'model': 'local-test', 'timeout_ms': 3000}}})
        path = str(CLI) + os.pathsep + os.environ.get('PATH', '/usr/bin:/bin')
        self.env = dict(os.environ, AOS_KERNEL_HOME=str(self.home), PATH=path, PYTHONDONTWRITEBYTECODE='1')
        self.pools = {'default': {'count': 2, 'envs': {'PATH': path}},
                      'llm': {'count': 1, 'envs': {'PATH': path, 'AOS_LLM_CONFIG': str(config)}}}
        self.team = self.root / 'team'
        self.project = self.root / 'p'
        self.project.mkdir()
        self.team.mkdir()
        (self.team / 'team.json').write_text(json.dumps(ROSTER), encoding='utf-8')
        self.lay = fmt.Layout(self.team)
        for d in self.lay.skeleton(ROSTER['members']):
            d.mkdir(parents=True, exist_ok=True)
        fake_home(self.lay.member('lead'))
        fake_home(self.lay.member('reviewer'))
        self.worker = self.lay.member('worker-1')
        self.addCleanup(self.orderly_stop)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def orderly_stop(self):
        if self.daemon_process is not None and self.daemon_process.poll() is None:
            if self.state().get('phase') != 'stopped':
                self.kernel_stop()
            self.daemon_stop()

    def agent(self, *args):
        r = subprocess.run([PY, str(CLI / 'aos-agent'), *map(str, args)], env=self.env, capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def make_worker(self, with_team_say=False):
        """真的 agent 家：aos-agent init＋input 資料夾＋（可選）team 工具包與牢（ws＝專案、outbox）。"""
        self.agent('init', '--target', self.worker)
        info = read_json(self.worker / 'info.json')
        info['tick']['interval_ms'] = 5
        if with_team_say:
            info['tools'] = []
        self.write(self.worker / 'info.json', info)
        self.write(self.worker / 'state.json', {'input': 'input/'})
        if with_team_say:
            self.agent('tools', 'add', 'team', '--target', self.worker)
            cfg = self.worker / 'tools' / 'team' / 'config.json'
            self.write(cfg, {'member': 'worker-1', 'mail_to': ['lead', 'human'],
                             'members': ['lead', 'worker-1', 'reviewer'], 'outbox': '/work/outbox',
                             'board': '/work/board', 'tz': 'Asia/Taipei'})
            self.write(self.worker / 'access.json', {
                '_metainfo': {'_type': 'agent_access', '_version': 1},
                'mounts': {'ws': '../../../p', 'outbox': '../../team/outbox/worker-1',
                           'board': {'$opt': 'ro', '$val': '../../team/tasks'}},
                'cwd': 'ws', 'net': False})
        self.agent('start', '--target', self.worker)

    def start_post(self):
        with open(os.devnull, 'w') as null:
            import contextlib
            with contextlib.redirect_stdout(null):
                self.assertEqual(aos_team_post.start(self.team, env=self.env, interval_ms=50), 0)
        self.addCleanup(self.stop_post)

    def stop_post(self):
        if self.daemon_process is not None and self.daemon_process.poll() is None \
                and self.state().get('phase') != 'stopped':
            import contextlib
            with open(os.devnull, 'w') as null, contextlib.redirect_stdout(null):
                aos_team_post.stop(self.team, env=self.env)

    def history_text(self):
        return '\n'.join(str(m.get('content')) for m in read_json(self.worker / 'prompts/history.json', []))

    def test_letter_from_outbox_to_memory(self):
        """一封信：lead 的 outbox → 郵差（kernel 反覆工作）→ worker-1 的 input → 記憶；紀錄標成已收。"""
        self.setup_running(pools=self.pools)
        self.make_worker()
        self.start_post()
        lid = '%d-%d-lead' % (1790000000000000001, 4242)
        letter = {'id': lid, 'from': 'lead', 'to': 'worker-1', 'status': 'REQUEST', 'reply_to': None, 'rev': None,
                  'text': '先讀 IMPORT.md', 'at': '2026-09-25T10:03:00+08:00'}
        fmt.write_new(self.lay.outbox('lead') / (lid + '.json'), letter)
        wait_for(lambda: '【來信 lead → worker-1 · REQUEST · 09-25 10:03】\n先讀 IMPORT.md' in self.history_text(),
                 timeout=30)
        wait_for(lambda: '收到' in self.history_text(), timeout=30)
        wait_for(lambda: bool(read_json(self.lay.post_sent / (lid + '.json'), {}).get('picked_up_at')), timeout=30)
        rec = read_json(self.lay.post_sent / (lid + '.json'))
        self.assertTrue(rec['complete'])
        self.assertTrue((self.lay.outbox('lead') / 'done' / (lid + '.json')).exists())
        procs = self.state()['procs']
        self.assertIn(aos_team_post.proc_name(self.team, 'post'), procs)
        self.agent('stop', '--target', self.worker)

    @unittest.skipUnless(HAS_BWRAP, '這台沒有 bwrap')
    def test_handoff_team_say_verify_by_kernel_done(self):
        """整圈：handoff → 工人在牢裡 team_say DONE → 驗收是 kernel 一次性工作 → done，領隊與人收到完成。"""
        self.setup_running(pools=self.pools)
        (self.project / 'AGENTS.md').write_text('# p\n', encoding='utf-8')
        self.make_worker(with_team_say=True)
        self.start_post()
        rid = '%d-%d-lead' % (1790000000000000002, 4242)
        req = {'id': rid, 'from': 'lead', 'kind': 'handoff', 'at': '2026-09-25T10:00:00+08:00',
               'assignee': 'worker-1', 'workflow': 'IMPORT.md', 'goal': '確認 AGENTS.md 在',
               'done_when': [{'kind': 'file_exists', 'path': 'AGENTS.md'}]}
        fmt.write_new(self.lay.outbox('lead') / (rid + '.json'), req)

        def status():
            return read_json(self.lay.task('t-0001'), {}).get('status')
        wait_for(lambda: status() == 'done', timeout=60)
        done_job = self.lay.team / 'post' / 'jobs-done' / 'v-t-0001-r1-a1' / 'job.json'
        wait_for(done_job.exists, timeout=30)
        job = read_json(done_job)
        run = job['runs'][0]
        self.assertEqual((run['mode'], job['status'], job['complete'], run['acked']), ('kernel', 'collected', True, True))
        wait_for(lambda: not (self.home / 'responses' / run['request']).exists(), timeout=10)   # 簽收了，kernel 收掉
        sent = sorted(self.lay.outbox('worker-1').glob('done/*.json'))
        self.assertEqual(len(sent), 1)                      # 牢裡的 team_say 寫的那封
        wait_for(lambda: any('完成' in json.loads(p.read_text())['text'] for p in self.lay.human_inbox.glob('*.json')),
                 timeout=30)
        lead_mail = [json.loads(p.read_text())['content'] for p in (self.lay.member('lead') / 'input').glob('mail-*')]
        self.assertTrue(any('· DONE · t-0001' in m and 'AGENTS.md 好了' in m for m in lead_mail), lead_mail)
        self.assertTrue(any('t-0001 完成' in m for m in lead_mail), lead_mail)
        tool_results = [m for m in read_json(self.worker / 'prompts/history.json') if m['role'] == 'tool']
        self.assertIn('queued', tool_results[0]['content'])
        self.agent('stop', '--target', self.worker)


    @unittest.skipUnless(HAS_BWRAP, '這台沒有 bwrap')
    def test_real_init_start_whole_team(self):
        """在 aos-team init 生出來的家上：aos-team start（連郵差、心跳一起登記）→ 人寄 handoff →
        工人在牢裡 team_say DONE → 驗收（kernel 一次性工作）→ done → 領隊記憶裡有完成信 → aos-team mail 看得到整串。"""
        self.setup_running(pools=self.pools)
        shutil.rmtree(self.team)
        (self.project / 'AGENTS.md').write_text('# p\n', encoding='utf-8')
        src = self.root / 'roster.json'
        # 郵差預設 5 秒一輪（team.json 的 post.interval_s）；測試要快，自己設 1 秒
        src.write_text(json.dumps(dict(ROSTER, post={'interval_s': 1})), encoding='utf-8')
        env = dict(self.env)

        def team(*args):
            r = subprocess.run([PY, str(CLI / 'aos-team'), *map(str, args), '--target', str(self.team)], env=env,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            return r.stdout
        team('init', '--config', src)
        for name in ROSTER['members']:
            info = read_json(self.lay.member(name) / 'info.json')
            info['tick']['interval_ms'] = 5
            self.write(self.lay.member(name) / 'info.json', info)
        out = team('start')
        self.assertIn('started team-post-team-', out)
        self.assertIn('started team-beat-team-', out)
        self.addCleanup(lambda: subprocess.run([PY, str(CLI / 'aos-team'), 'stop', '--target', str(self.team)],
                                               env=env, capture_output=True, timeout=60)
                        if self.daemon_process is not None and self.daemon_process.poll() is None
                        and self.state().get('phase') != 'stopped' else None)
        rid = fmt.new_id('human')
        fmt.write_new(self.lay.outbox('human') / (rid + '.json'), {
            'id': rid, 'from': 'human', 'kind': 'handoff', 'at': fmt.now_iso(), 'assignee': 'worker-1',
            'workflow': '無', 'goal': '確認 AGENTS.md 在', 'done_when': [{'kind': 'file_exists', 'path': 'AGENTS.md'}]})
        wait_for(lambda: read_json(self.lay.task('t-0001'), {}).get('status') == 'done', timeout=60)
        lead = self.lay.member('lead')
        try:
            wait_for(lambda: any('· DONE · t-0001' in str(m.get('content'))       # 工人牢裡 team_say 寄的那封
                                 for m in read_json(lead / 'prompts/history.json', [])), timeout=60)
        except AssertionError:
            err = (lead / 'log/agent.err').read_text() if (lead / 'log/agent.err').exists() else ''
            self.fail('領隊記憶裡沒有工人的 DONE：input=%s history=%s err=%s' % (
                sorted(p.name for p in (lead / 'input').iterdir()),
                read_json(lead / 'prompts/history.json', [])[-3:], err[-800:]))
        mail = team('mail')
        self.assertIn('post → worker-1  REQUEST  t-0001 rev1', mail)
        self.assertIn('worker-1 → lead  DONE  t-0001 rev1', mail)
        self.assertIn('post → 人  DONE  t-0001 rev1', mail)             # 開單人是人：完成信給人
        self.assertTrue(any('t-0001 完成' in json.loads(p.read_text())['text'] for p in self.lay.human_inbox.glob('*.json')))
        out = team('stop')
        self.assertIn('stopped team-post-team-', out)


if __name__ == '__main__':
    unittest.main()
