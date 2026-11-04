"""第二波 C 隊：T-lock（catalog.md〈T-lock〉、spec/team/lock.md）。單元測 aos_team_lock，郵差整合走
tools/task/lock 的 ToolUnitTests（test_team_init.py）與 aos-team lock 這條 CLI。"""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import aos_team_format as fmt
import aos_team_lock as lock
import aos_team_requests as requests

ROSTER = {'_metainfo': {'_type': 'aos_team', '_version': 1}, 'project': '../p', 'tz': 'Asia/Taipei',
          'members': {'lead': {'template': 'lead', 'mail_to': ['worker-1', 'worker-2', 'human']},
                      'worker-1': {'template': 'worker', 'mail_to': ['lead', 'human']},
                      'worker-2': {'template': 'worker', 'mail_to': ['lead', 'human']}}}


def req(sender, rid, **over):
    base = {'id': rid, 'from': sender, 'kind': 'lock', 'at': fmt.now_iso('Asia/Taipei')}
    base.update(over)
    return base


class LockTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-team-lock-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.team = self.root / 'team'
        self.team.mkdir()
        (self.root / 'p').mkdir()
        (self.team / 'team.json').write_text(json.dumps(ROSTER, ensure_ascii=False), encoding='utf-8')
        self.lay = fmt.Layout(self.team)
        for d in self.lay.skeleton(ROSTER['members']):
            d.mkdir(parents=True, exist_ok=True)
        self.roster = fmt.load_roster(self.team)

    def err(self, code, fn, *a):
        with self.assertRaises(fmt.TeamError) as cm:
            fn(*a)
        self.assertEqual(cm.exception.code, code, cm.exception.msg)

    def test_acquire_then_ls_shows_owner(self):
        r = req('worker-1', 'r1', op='acquire', name='shared.md', why='改共用檔', ttl_seconds=120)
        eff = lock.on_lock(self.lay, self.roster, r)
        self.assertEqual(eff[0]['to'], 'worker-1')
        self.assertIn('取得鎖 shared.md', eff[0]['text'])
        rec = fmt.read_json(self.lay.lock('shared.md'))
        self.assertEqual((rec['owner'], rec['ttl_seconds'], rec['why']), ('worker-1', 120, '改共用檔'))
        out = lock.on_lock(self.lay, self.roster, req('worker-2', 'r2', op='ls'))
        self.assertIn('worker-1 拿著', out[0]['text'])

    def test_busy_rejects_other_owner(self):
        lock.on_lock(self.lay, self.roster, req('worker-1', 'r1', op='acquire', name='x'))
        self.err('Busy', lock.on_lock, self.lay, self.roster, req('worker-2', 'r2', op='acquire', name='x'))

    def test_same_owner_reacquire_ok(self):
        lock.on_lock(self.lay, self.roster, req('worker-1', 'r1', op='acquire', name='x'))
        eff = lock.on_lock(self.lay, self.roster, req('worker-1', 'r3', op='acquire', name='x'))
        self.assertEqual(eff[0]['to'], 'worker-1')

    def test_acquire_idempotent_same_request(self):
        r = req('worker-1', 'r1', op='acquire', name='x')
        eff1 = lock.on_lock(self.lay, self.roster, r)
        eff2 = lock.on_lock(self.lay, self.roster, r)
        self.assertEqual(eff1, eff2)

    def test_release_by_owner_then_others_can_acquire(self):
        lock.on_lock(self.lay, self.roster, req('worker-1', 'r1', op='acquire', name='x'))
        eff = lock.on_lock(self.lay, self.roster, req('worker-1', 'r2', op='release', name='x'))
        self.assertIn('放掉鎖 x', eff[0]['text'])
        eff2 = lock.on_lock(self.lay, self.roster, req('worker-2', 'r3', op='acquire', name='x'))
        self.assertEqual(eff2[0]['to'], 'worker-2')

    def test_release_by_non_owner_rejected(self):
        lock.on_lock(self.lay, self.roster, req('worker-1', 'r1', op='acquire', name='x'))
        self.err('NotOwner', lock.on_lock, self.lay, self.roster, req('worker-2', 'r2', op='release', name='x'))

    def test_release_idempotent_same_request(self):
        lock.on_lock(self.lay, self.roster, req('worker-1', 'r1', op='acquire', name='x'))
        r = req('worker-1', 'r2', op='release', name='x')
        eff1 = lock.on_lock(self.lay, self.roster, r)
        eff2 = lock.on_lock(self.lay, self.roster, r)
        self.assertEqual(eff1, eff2)

    def test_release_no_such_lock(self):
        self.err('NoSuchLock', lock.on_lock, self.lay, self.roster, req('worker-1', 'r1', op='release', name='ghost'))

    def test_release_already_released_by_non_owner_rejected(self):
        lock.on_lock(self.lay, self.roster, req('worker-1', 'r1', op='acquire', name='x'))
        lock.on_lock(self.lay, self.roster, req('worker-1', 'r2', op='release', name='x'))
        self.err('NotOwner', lock.on_lock, self.lay, self.roster, req('worker-2', 'r3', op='release', name='x'))

    def test_expired_lock_can_be_taken_over(self):
        r = req('worker-1', 'r1', op='acquire', name='x', ttl_seconds=60)
        lock.on_lock(self.lay, self.roster, r)
        rec = fmt.read_json(self.lay.lock('x'))
        rec['expires_at'] = '2000-01-01T00:00:00+08:00'   # 假裝早就過期
        fmt.write_json(self.lay.lock('x'), rec, indent=2)
        eff = lock.on_lock(self.lay, self.roster, req('worker-2', 'r2', op='acquire', name='x'))
        self.assertEqual(eff[0]['to'], 'worker-2')

    def test_expired_lock_release_by_anyone_ok(self):
        r = req('worker-1', 'r1', op='acquire', name='x', ttl_seconds=60)
        lock.on_lock(self.lay, self.roster, r)
        rec = fmt.read_json(self.lay.lock('x'))
        rec['expires_at'] = '2000-01-01T00:00:00+08:00'
        fmt.write_json(self.lay.lock('x'), rec, indent=2)
        eff = lock.on_lock(self.lay, self.roster, req('worker-2', 'r2', op='release', name='x'))
        self.assertIn('放掉鎖 x', eff[0]['text'])

    def test_ls_empty(self):
        out = lock.on_lock(self.lay, self.roster, req('human', 'r1', op='ls'))
        self.assertEqual(out[0]['text'], '沒有任何鎖')

    def test_forged_future_at_does_not_extend_expiry(self):
        """astra 審查：req['at'] 不可信（模型能自己塞一份帶未來時刻的申請），expires_at 一律用郵差的時鐘算。"""
        r = req('worker-1', 'r1', op='acquire', name='x', ttl_seconds=60, at='2099-01-01T00:00:00+08:00')
        eff = lock.on_lock(self.lay, self.roster, r)
        rec = fmt.read_json(self.lay.lock('x'))
        self.assertNotIn('2099', rec['expires_at'])
        self.assertNotIn('2099', rec['acquired_at'])
        self.assertIn('取得鎖', eff[0]['text'])

    def test_name_with_slash_and_unicode_does_not_need_subdirs(self):
        """astra 審查 M2：docs/WORKFLOWS.md、中文名不用先建子目錄，ls 也列得到（平面檔名、原名存內容裡）。"""
        lock.on_lock(self.lay, self.roster, req('worker-1', 'r1', op='acquire', name='docs/WORKFLOWS.md'))
        lock.on_lock(self.lay, self.roster, req('worker-1', 'r2', op='acquire', name='共用設定'))
        out = lock.on_lock(self.lay, self.roster, req('worker-2', 'r3', op='ls'))
        self.assertIn('docs/WORKFLOWS.md', out[0]['text'])
        self.assertIn('共用設定', out[0]['text'])
        # 檔名本身是平面、固定長度的十六進位，不含 name 原文、不含 /
        names = [p.name for p in self.lay.locks.iterdir()]
        self.assertEqual(len(names), 2)
        self.assertTrue(all(len(n) == len('0' * 64 + '.json') and '/' not in n for n in names), names)

    def test_bad_op_and_bad_name(self):
        self.err('FormatInvalid', lock.on_lock, self.lay, self.roster, req('worker-1', 'r1', op='bogus'))
        self.err('FormatInvalid', lock.on_lock, self.lay, self.roster, req('worker-1', 'r1', op='acquire', name='BAD NAME'))

    def test_may_send_enforced_through_requests_handle(self):
        """需要模板 may 有 'lock'（worker 模板已加，見 templates/worker/template.json）。"""
        r = req('worker-1', 'r1', op='acquire', name='y')
        eff = requests.handle(self.lay, self.roster, r)
        self.assertEqual(eff[0]['to'], 'worker-1')

    def test_cmd_lock_ls_and_acquire_write_outbox(self):
        import io
        import contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = lock.cmd_lock(str(self.team), ['ls'])
        self.assertEqual(code, 0)
        self.assertIn('沒有任何鎖', out.getvalue())
        out2 = io.StringIO()
        with contextlib.redirect_stdout(out2):
            code2 = lock.cmd_lock(str(self.team), ['acquire', 'shared.md', '--why', '人工搶一把', '--ttl', '120'])
        self.assertEqual(code2, 0)
        [f] = fmt.json_files(self.lay.outbox('human'))
        body = json.loads(f.read_text(encoding='utf-8'))
        self.assertEqual((body['kind'], body['op'], body['name'], body['ttl_seconds']),
                         ('lock', 'acquire', 'shared.md', 120))


if __name__ == '__main__':
    unittest.main()
