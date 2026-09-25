"""郵差的停滯與書記：`_PostWatch`（混入 Post）看停滯與期限、成員健康、發通知，書記同步 SESSION-LOG／WAIT_USER。"""
import datetime
import hashlib
import json
import os

import aos_team_ask
import aos_team_format as fmt
from aos_team_format import HUMAN, TeamError
import aos_team_task

from aos_team_post_base import _mtime, _zone, CLERK_FILES
from aos_team_post_text import session_line, update_section, wait_line


class _PostWatch:
    """Post 的停滯與書記那幾格（混入 Post）：看停滯與期限、成員健康、通知，書記同步 SESSION-LOG／WAIT_USER。"""

    # ------------------------------------------------------------ 停滯 ----

    def watch(self, force=False):
        path = self.base / 'watch.json'
        state = fmt.read_json(path) if path.exists() else {}
        now = self.now()
        last = fmt.parse_iso(state.get('last'))
        if not force and last is not None and (now - last).total_seconds() < self.watch_every:
            return
        for tid, ev in aos_team_task.due_deadlines(self.lay, now.isoformat(timespec='seconds')):
            if self.waiting_for_checker(tid):
                continue                    # 檢查器壞了等人修（或人剛要求重驗）：不算隊員逾時
            self.notice('expire.%s.%s' % (tid, hashlib.sha1(ev['src'].encode()).hexdigest()[:10]),
                        [{'do': 'step', 'task': tid, 'event': ev}])
        tickets = aos_team_task.all_tickets(self.lay)
        health = state.get('health', {})
        seen = {}
        stale = self.roster['limits']['stale_minutes'] * 60
        for t in tickets:
            if t['status'] not in ('sent', 'working') or t.get('waiting_on'):
                continue            # 在等別人（blocked／waiting_user）、驗收審查中、結束了：不報
            m = t['assignee']
            if m not in seen:
                code, message = self.member_health(m)
                old = health.get(m) or {}
                # 連續不健康的起點：代碼換來換去（retrying → paused）也算同一段，回到 ok 才重算
                since = None if code == 'ok' else (old.get('since') or now.isoformat(timespec='seconds'))
                seen[m] = {'code': code, 'message': message, 'since': since}
            h = seen[m]
            if h['code'] != 'ok':
                if (now - fmt.parse_iso(h['since'])).total_seconds() >= self.health_grace:
                    key = '%s|%d|%d|health|%s' % (t['id'], t['rev'], t['attempt'], h['since'])
                    self.stall(t, key, '健康不是 ok：%s（從 %s 起）' % (h['message'], fmt.short_time(h['since'], self.tz)))
                continue
            progress = self.last_progress(t, m)
            if (now - progress).total_seconds() >= stale:
                key = '%s|%d|%d|idle|%s' % (t['id'], t['rev'], t['attempt'], progress.isoformat())
                self.stall(t, key, '%s 超過 %d 分鐘沒進展（最後進展 %s）'
                           % ('收了單' if t['status'] == 'working' else '單子投了還沒被收',
                              self.roster['limits']['stale_minutes'], fmt.short_time(progress.isoformat(), self.tz)))
        state = {'last': now.isoformat(timespec='seconds'), 'health': seen}
        fmt.write_json(path, state)

    def waiting_for_checker(self, tid):
        """單子（目前這一次 rev／attempt、還在 verifying）在等人修檢查器（有標記），或人 --again 重驗的那份工作還在跑。"""
        try:
            t = aos_team_task.load(self.lay, tid)
        except TeamError:
            return False
        if t['status'] != 'verifying':
            return False
        mark = self.base / 'checker-broken' / tid
        try:
            if mark.read_text().split() == [str(t['rev']), str(t['attempt'])]:
                return True
        except OSError:
            pass
        prefix = 'v-%s-r%d-a%d-x' % (tid, t['rev'], t['attempt'])
        return any(d.name.startswith(prefix) for d in self.jobs.iterdir() if d.is_dir())

    def member_health(self, name):
        if self.health_fn is not None:
            return self.health_fn(name)
        try:
            import aos_agent_status
            data = aos_agent_status.collect(str(self.lay.member(name)), self.env)
            return data['health']['code'], data['health']['message']
        except Exception as e:
            return 'unreadable', '看不到 %s 的狀態：%s' % (name, e)

    def last_progress(self, t, m):
        """最後進展：單子最後一次變動、成員記憶最後一次變長、事件紀錄最後一次寫。"""
        stamps = [fmt.parse_iso(t.get('updated_at'))]
        home = self.lay.member(m)
        history = home / 'prompts' / 'history.json'
        try:
            h = json.loads((home / 'info.json').read_text(encoding='utf-8')).get('history')
            if isinstance(h, str):
                history = home / h
        except (OSError, ValueError, AttributeError):
            pass
        for p in (history, self.lay.events(m)):
            mt = _mtime(p)
            if mt is not None:
                stamps.append(datetime.datetime.fromtimestamp(mt, datetime.timezone.utc))
        stamps = [s if s.tzinfo else s.replace(tzinfo=datetime.timezone.utc) for s in stamps if s is not None]
        return max(stamps).astimezone(_zone(self.tz))

    def stall(self, t, key, why):
        """同一次停滯只報一次：紀錄 id 由停滯的鍵算出來，紀錄在＝報過了。"""
        rid = 'stall.%s.%s' % (t['id'], hashlib.sha1(key.encode()).hexdigest()[:12])
        text = '觀察到停滯：%s（%s，%s，rev%d 第 %d 次）%s。這只是觀察，不代表對方 BLOCKED。' % (
            t['id'], t['assignee'], t['status'], t['rev'], t['attempt'], why)
        to = [n for n in fmt.members_by_template(self.roster, 'lead') if n != t['assignee']] + [HUMAN]
        effects = [{'do': 'letter', 'to': n, 'status': 'PROGRESS', 'reply_to': t['id'], 'rev': t['rev'], 'text': text}
                   for n in to]
        if self.notice(rid, effects, key=key):
            self.say('停滯 %s %s：%s' % (t['id'], t['assignee'], why))

    def notice(self, rid, effects, **extra):
        """郵差自己起的事（停滯、期限）：紀錄在＝做過了。回這次有沒有新開。"""
        rec = self.load_rec(rid)
        new = rec is None
        if new:
            rec = self.new_rec(rid, 'notice', effects=effects, **extra)
            self.start_rec(rec)
        self.finish(rec)
        return new

    # ------------------------------------------------------------ 書記 ----

    def clerk(self, force=False):
        path = self.base / 'clerk.json'
        project = fmt.project_dir(self.root, self.roster)
        sig = [os.stat(p).st_mtime_ns if p.exists() else 0 for p in (self.lay.tasks, self.lay.wait_user)]
        sig.append(str(project))
        old = fmt.read_json(path) if path.exists() else {}
        if not force and old.get('sig') == sig:
            return
        tickets = [t for t in aos_team_task.all_tickets(self.lay) if t['status'] not in fmt.TERMINAL]
        questions = aos_team_ask.open_questions(self.lay)
        lines = {'SESSION-LOG.md': [session_line(t) for t in tickets],
                 'WAIT_USER.md': [wait_line(q) for q in questions]}
        for name, heading in CLERK_FILES:
            target = next((p for p in (project / name, project / 'wf' / name) if p.is_file()), None)
            if target is not None and update_section(target, heading, lines[name]):
                self.say('書記 %s：%d 條' % (target, len(lines[name])))
        fmt.write_json(path, {'sig': sig})
