"""aos-team init／start／stop／ls／rm（spec/team/cli.md、roster.md、templates.md）：建隊、列隊、拆隊。

init 照 team.json 建團隊資料夾與每個成員的家（模板）；重跑只補新成員、補完沒生完的、更新工具包的團隊設定。
start／stop 對每個成員叫 aos-agent 的 start／stop（同一個函式），有郵差、心跳模組就一起。
不叫模型。
"""
import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

import aos_agent
import aos_agent_init
from aos_agent_home import AgentError
from aos_team_format import (HUMAN, TERMINAL, Layout, TeamError, json_files, load_roster, project_dir,
                             read_json, short_time, template_dir, validate_roster, write_json)

HOOKS = ('aos_team_post', 'aos_team_beat')   # 第 2 隊：有 start(team)／stop(team) 就叫


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


def _parser(name, text):
    return Parser(prog='aos-team ' + name, description=text)


def member_context(lay, roster, name):
    m = roster['members'][name]
    return {'name': name, 'team_dir': str(lay.root), 'project': str(project_dir(lay.root, roster)),
            'mail_to': m['mail_to'], 'members': list(roster['members']), 'tz': roster.get('tz'),
            'model': m['model'], 'mounts': m['mounts'], 'tools': m['tools']}


def _inside(child, parent):
    child, parent = os.path.realpath(child), os.path.realpath(parent)
    return child == parent or child.startswith(parent.rstrip(os.sep) + os.sep)


# ------------------------------------------------------------------ init ----

def cmd_init(team_dir, argv):
    ap = _parser('init', '照 team.json 建團隊資料夾與每個成員的家；重跑只補新成員')
    ap.add_argument('--config', help='名冊檔；會抄成 <團隊>/team.json（團隊裡已經有 team.json 就不用給）')
    args = ap.parse_args(argv)
    lay = Layout(team_dir)
    lay.root.mkdir(parents=True, exist_ok=True)
    if args.config:
        src = Path(os.path.abspath(os.path.expanduser(args.config)))
        obj = read_json(src)
        validate_roster(obj, str(src))
        if lay.roster.exists() and src != lay.roster:
            if read_json(lay.roster) != obj:
                raise TeamError('AlreadyExists', '%s 已經在、內容不一樣；要改就直接編輯它再跑 aos-team init（不用 --config）'
                                % lay.roster)
        elif src != lay.roster:
            write_json(lay.roster, obj, indent=2)
    elif not lay.roster.exists():
        raise TeamError('NotFound', '%s 沒有 team.json；第一次請給 --config 名冊檔（範例：proto5/spec/team/examples/team.json）'
                        % lay.root)
    roster = load_roster(lay.root)
    project = project_dir(lay.root, roster)
    if not project.is_dir():
        raise TeamError('NotFound', '專案資料夾 %s 不存在（team.json 的 project，相對 %s）；先 mkdir -p %s'
                        % (project, lay.root, project))
    if _inside(lay.root, project) or _inside(project, lay.root):
        raise TeamError('BadProject', '團隊資料夾 %s 跟專案 %s 不能一個包著另一個（工人把專案掛成可寫，會蓋到成員的家）'
                        % (lay.root, project))
    pending = sorted(lay.members.glob('.removing-*.json')) if lay.members.is_dir() else []
    if pending:
        raise TeamError('Pending', '上次 aos-team rm 沒做完（%s）；先再跑一次 aos-team rm %s'
                        % (pending[0], pending[0].name[len('.removing-'):-5]))
    for name, m in roster['members'].items():
        if '/' in m['template'] and _inside(template_dir(m['template']), project):
            raise TeamError('BadTemplate', '%s 的模板 %s 在專案裡面（工人改得到它的 may 與人格）；搬到專案外'
                            % (name, m['template']))
    for d in lay.skeleton(roster['members']):
        d.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name in roster['members']:
        try:
            lines = aos_agent_init.init_from_template(lay.member(name), roster['members'][name]['template'],
                                                      member=member_context(lay, roster, name))
            for line in lines:
                print('%s: %s' % (name, line))
        except (AgentError, TeamError) as e:
            failed += 1
            print('%s: 失敗 %s: %s' % (name, e.code, e.msg), file=sys.stderr)
    stray = [p.name for p in lay.members.iterdir()
             if p.is_dir() and not p.name.startswith('.') and p.name not in roster['members']]
    if stray:
        print('注意：members/ 裡有名冊沒有的家：%s（aos-team 不管它們）' % '、'.join(sorted(stray)), file=sys.stderr)
    if failed:
        return 1
    need = '' if os.path.isabs(os.environ.get('AOS_KERNEL_HOME', '')) else 'export AOS_KERNEL_HOME=… 後 '
    print('團隊在 %s：%d 個成員。下一步：%saos-team start --target %s'      # 試玩 r2：已設好就不叫人再 export
          % (lay.root, len(roster['members']), need, lay.root))
    return 0


# ------------------------------------------------------------ start／stop ----

def _hooks(action, lay):
    code = 0
    for module in HOOKS:
        try:
            mod = importlib.import_module(module)
        except ModuleNotFoundError as e:
            if e.name == module:
                continue
            raise
        fn = getattr(mod, action, None)
        if fn is not None:
            code = max(code, fn(str(lay.root)) or 0)
    return code


def _each(team_dir, argv, action):
    ap = _parser(action, '全部成員向 kernel %s' % ('登記' if action == 'start' else '撤銷登記'))
    ap.parse_args(argv)
    lay = Layout(team_dir)
    roster = load_roster(lay.root)
    code = 0
    for name in roster['members']:
        home = lay.member(name)
        if not (home / 'info.json').exists():
            print('%s: 還沒有家（先 aos-team init）' % name, file=sys.stderr)
            code = 1
            continue
        sys.stdout.write('%s: ' % name)
        sys.stdout.flush()
        rc = getattr(aos_agent, action)(str(home))
        if rc:
            print()
        code = max(code, 1 if rc else 0)
    return max(code, _hooks(action, lay))


def cmd_start(team_dir, argv):
    return _each(team_dir, argv, 'start')


def cmd_stop(team_dir, argv):
    return _each(team_dir, argv, 'stop')


# -------------------------------------------------------------------- ls ----

def _last_sent(lay, name):
    """這個成員最後寄出的一封（outbox 頂層與 done/，id 開頭是 epoch ns，照檔名排就是照時間）。"""
    files = json_files(lay.outbox(name)) + json_files(lay.outbox(name) / 'done')
    for path in sorted(files, key=lambda p: p.name, reverse=True):
        try:
            obj = read_json(path)
        except TeamError:
            continue
        if isinstance(obj, dict):
            what = obj.get('kind') or obj.get('status')
            to = obj.get('to') or obj.get('assignee') or ''
            return '%s %s%s' % (short_time(obj.get('at')), what, ' → ' + to if to else '')
    return None


def _health(home):
    import aos_agent_status
    try:
        return aos_agent_status.collect(str(home))['health']['code']
    except Exception as e:  # ls 只是看，不因為一個成員讀不到就整個失敗
        return 'unknown(%s)' % type(e).__name__


def rows(team_dir):
    import aos_team_task
    lay = Layout(team_dir)
    roster = load_roster(lay.root)
    tickets = aos_team_task.all_tickets(lay)
    out = []
    for name, m in roster['members'].items():
        home = lay.member(name)
        mine = [t['id'] for t in tickets if t['assignee'] == name and t['status'] not in TERMINAL]
        out.append({'name': name, 'template': m['template'], 'home': str(home),
                    'health': _health(home) if (home / 'info.json').exists() else 'no-home',
                    'tasks': mine, 'last_sent': _last_sent(lay, name)})
    return out


def cmd_ls(team_dir, argv):
    ap = _parser('ls', '一行一個成員：模板、health、手上的單、最後寄出的一封')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    data = rows(team_dir)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    width = max(len(r['name']) for r in data)
    for r in data:
        print('%s  %-8s %-12s 單：%-14s 最後寄出：%s' % (r['name'].ljust(width), r['template'], r['health'],
                                                  ','.join(r['tasks']) or '-', r['last_sent'] or '-'))
    for line in machine_lines(team_dir, os.environ):
        print(line)
    return 0


def machine_lines(team_dir, env):
    """郵差、心跳在 kernel 那邊的狀態（T5：真跑時郵差壞了，成員那幾行全是 ok、人看不出信為什麼不動）。"""
    import aos_kernel_store
    import aos_team_post
    home = env.get('AOS_KERNEL_HOME')
    if not home or not os.path.isabs(home):
        return ['郵差、心跳：沒設 AOS_KERNEL_HOME，看不到']
    try:
        procs = aos_kernel_store.procs(home)               # one-boot 起帳本是 K/ledger.sqlite
    except Exception as exc:                              # 帳本讀不到：只少這兩行，不擋 ls
        return ['郵差、心跳：kernel 帳本讀不到（%s）' % exc]
    lay = Layout(team_dir)
    out = []
    for what, label, err in (('post', '郵差', 'post.err'), ('beat', '心跳', 'beat.err')):
        name = aos_team_post.proc_name(team_dir, what)
        p = procs.get(name)
        if not isinstance(p, dict):
            state = '沒登記（aos-team start）'
        elif p.get('status') == 'bad':
            state = '壞了（連錯 %s 次）：看 %s，修好後 aos-kernel rm %s 再 aos-team start' % (
                p.get('fails'), lay.team / 'post' / err, name)
        else:
            state = 'ok'
        out.append('%s  %s  %s' % (label, name, state))
    return out


# -------------------------------------------------------------------- rm ----

def cmd_rm(team_dir, argv):
    ap = _parser('rm', '拿掉一個成員：家搬進 members/.removed/（已拆）、名冊刪那列（也從別人的 mail_to 拿掉）；'
                       '預設不刪檔，加 --purge 才真的刪掉那個家')
    ap.add_argument('name')
    ap.add_argument('--purge', action='store_true', help='真的刪掉家（不搬進 members/.removed/，刪了救不回來）')
    args = ap.parse_args(argv)
    lay = Layout(team_dir)
    name = args.name
    intent = lay.members / ('.removing-%s.json' % name)
    if intent.exists():                                   # 上次搬了家、還沒改名冊就崩了：照紀錄做完
        plan = read_json(intent)
        if args.purge:
            plan['purge'] = True
        return _finish_rm(lay, name, plan, intent)
    roster = load_roster(lay.root)
    if name not in roster['members']:
        raise TeamError('NotFound', '%s 不在名冊裡（有：%s）' % (name, '、'.join(roster['members'])))
    if len(roster['members']) == 1:
        raise TeamError('Usage', '%s 是最後一個成員；要拆整個團隊就 aos-team stop 後自己搬走資料夾' % name)
    home = lay.member(name)
    import aos_agent_status
    if home.exists():
        k = aos_agent_status.kernel_status(str(home), os.environ)
        if not aos_agent_status.unregistered(k):
            raise TeamError('StillRunning', '%s 還登記在 kernel（%s）；先 aos-agent stop --target %s 或 aos-team stop'
                            % (name, k['home'], home))
    dest = lay.members / '.removed' / ('%s-%d' % (name, time.time_ns()))
    plan = {'name': name, 'dest': str(dest), 'purge': bool(args.purge)}
    write_json(intent, plan)                              # 先記下要做什麼，崩了 rm／init 都看得到
    return _finish_rm(lay, name, plan, intent)


def _finish_rm(lay, name, plan, intent):
    home, dest = lay.member(name), Path(plan['dest'])
    if home.exists() and not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(home), str(dest))
        print('%s 的家搬到 %s' % (name, dest))
    raw = read_json(lay.roster)
    if name in raw.get('members', {}):
        del raw['members'][name]
        for other in raw['members'].values():
            if isinstance(other.get('mail_to'), list) and name in other['mail_to']:
                other['mail_to'] = [x for x in other['mail_to'] if x != name]
        validate_roster(raw, str(lay.roster))
        write_json(lay.roster, raw, indent=2)
    if plan.get('purge') and dest.exists():            # 先搬再刪：搬是原子的，刪到一半崩了重跑 rm 會接著刪
        shutil.rmtree(dest)
        print('%s 的家已刪除（--purge）' % name)
    intent.unlink(missing_ok=True)
    print('team.json 拿掉了 %s（也從別人的 mail_to 拿掉）；已裝的工具設定要更新就重跑 aos-team init' % name)
    import aos_team_task
    left = [t['id'] for t in aos_team_task.all_tickets(lay) if t['assignee'] == name and t['status'] not in TERMINAL]
    if left:
        print('注意：%s 手上還有沒結束的單 %s；用 aos-team task reassign 或 cancel' % (name, '、'.join(left)),
              file=sys.stderr)
    return 0


__all__ = ['cmd_init', 'cmd_start', 'cmd_stop', 'cmd_ls', 'cmd_rm', 'member_context', 'HUMAN']
