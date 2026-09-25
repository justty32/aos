"""驗收員（spec/team/verify.md）：照任務單的 done_when 跑**固定的檢查器**，每條回 過／不過／檢查器壞。

兩種「沒過」分開（2026-09-24 使用者裁）：
- 不過（fail）＝隊員交的東西不合：檔不在、表沒填、殘留還在、lint 沒過…→ 郵差寄修正、扣一次機會；
- 檢查器壞（error）＝沒辦法判：檢查器載不到、跑不完、本身故障、done_when 寫錯（不認得的名字、缺參數、絕對路徑）
  → 整份結果 broken，不扣隊員次數，郵差寄信給人，單子停在 verifying 等人修好再 `aos-team verify ID --again`。

- 只跑這裡登記的檢查器（CHECKS）；不執行專案裡的任何檔，唯一例外是 cmd_ok：
  跑名冊 team.json 的 cmd_ok 白名單裡的一條指令，**關在牢裡**（專案唯讀掛 /work/ws、不上網、清環境），退出碼 0＝過。
- 會執行程式的檢查器（wf_lint_strict 跑快照的 bash＋git、cmd_ok）一律經 aos-jail 關牢；純讀檔的
  （file_exists、table_filled、contains、wf_residue）在牢外讀，靠 realpath 圍在專案裡（第二波 B 隊，見 verify.md〈牢〉）。
- 路徑一律相對專案資料夾（team.json 的 project），解開符號連結後在專案外＝檢查失敗。
- `judge` 條目不歸這裡（審查員判），結果裡不列。
- 郵差把它當 kernel 一次性工作提交（aos-team verify ID --rev R --attempt A --out 檔），結果寫檔、郵差下一輪收；
  人也可以直接跑 `aos-team verify t-0001` 看結果（不改任何檔）。
別隊加檢查器：在 CHECKS 加一行 '名字': '模組:函式'；函式 fn(project: Path, args: dict) → (過了沒, 一句白話)，
隊員交的東西不合丟 NotMet（＝不過），檢查器自己沒辦法判丟 CheckError（＝檢查器壞）。
這個檔留檢查器登記表 CHECKS（字串指回這支，所以檢查器都從這裡匯出）、逐條跑、verify 主體、印法與命令列；
檢查器分在 aos_team_verify_checks／jail。
"""
import argparse
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from aos_team_format import TeamError, Layout, load_roster, now_iso, project_dir, write_json
import aos_team_task

from aos_team_verify_checks import (
    _args, _wf, check_contains, check_file_exists, check_last_line_contains, check_max_bytes,
    check_not_contains, check_table_filled, check_wf_residue, CheckError, ERROR, FAIL, NotMet,
    PASS, PROTO, read_text, WORDS
)
from aos_team_verify_jail import check_cmd_ok, check_wf_lint_strict


CHECKS = {
    'contains': 'aos_team_verify:check_contains',
    'not_contains': 'aos_team_verify:check_not_contains',
    'wf_residue': 'aos_team_verify:check_wf_residue',
    'wf_lint_strict': 'aos_team_verify:check_wf_lint_strict',
    'last_line_contains': 'aos_team_verify:check_last_line_contains',
    'max_bytes': 'aos_team_verify:check_max_bytes',
}


def checker(name):
    spec = CHECKS.get(name)
    if spec is None:
        raise CheckError('不認得的檢查器 %r（認得：%s）' % (name, '、'.join(sorted(CHECKS))))
    module, func = spec.split(':')
    try:
        return getattr(importlib.import_module(module), func)
    except (ImportError, AttributeError) as e:
        raise CheckError('檢查器 %s 載不到（%s：%s）' % (name, spec, e))


def run_item(project, item, roster=None):
    kind = item['kind']
    if kind == 'cmd_ok':
        return check_cmd_ok(project, item, roster or {})
    if kind == 'file_exists':
        return check_file_exists(project, item)
    if kind == 'table_filled':
        return check_table_filled(project, item)
    if kind == 'check':
        return checker(item['name'])(project, _args(item))
    raise CheckError('不認得的條目種類 %r' % kind)


def run_items(project, done_when, roster=None):
    """每條機械條目一筆 {i, kind, result, pass, why}；judge 不列。"""
    out = []
    for i, item in enumerate(done_when):
        if item.get('kind') == aos_team_task.JUDGE:
            continue
        try:
            ok, why = run_item(project, item, roster)
            result = PASS if ok else FAIL
        except NotMet as e:
            result, why = FAIL, str(e)
        except CheckError as e:
            result, why = ERROR, str(e)
        except Exception as e:   # 檢查器自己的 bug：算這一條檢查器壞，不讓整份驗收崩掉
            result, why = ERROR, '%s: %s' % (type(e).__name__, e)
        out.append({'i': i, 'kind': kind_label(item), 'result': result, 'pass': result == PASS, 'why': why})
    return out


def kind_label(item):
    return 'check:%s' % item['name'] if item['kind'] == 'check' else item['kind']


def verify(team_dir, tid, rev=None, attempt=None, roster=None):
    """跑一張單的機械條目，回 {task, rev, attempt, pass, broken, results, at}。只讀，不改任何檔。
    pass＝每條都過；broken＝有一條以上檢查器壞（這時 pass 一定是 false，但不算隊員沒過）。"""
    lay = Layout(team_dir)
    roster = roster or load_roster(team_dir)
    t = aos_team_task.load(lay, tid)
    project = project_dir(team_dir, roster)
    if not project.is_dir():
        raise TeamError('NotFound', '專案資料夾 %s 不在（team.json 的 project）' % project)
    results = run_items(project, t['done_when'], roster)
    return {'task': t['id'], 'rev': t['rev'] if rev is None else rev,
            'attempt': t['attempt'] if attempt is None else attempt,
            'pass': all(r['pass'] for r in results), 'broken': any(r['result'] == ERROR for r in results),
            'results': results, 'at': now_iso(roster.get('tz'))}


def render(res, ticket=None):
    ok = sum(1 for r in res['results'] if r['pass'])
    word = '過' if res['pass'] else ('檢查器壞了（不算隊員沒過）' if res.get('broken') else '不過')
    head = '%s rev%d 第 %d 次 驗收：%s（%d/%d 條過）' % (res['task'], res['rev'], res['attempt'], word, ok,
                                                  len(res['results']))
    lines = [head]
    for r in res['results']:
        lines.append('  %-4s %d. %s：%s' % (WORDS[r['result']], r['i'], r['kind'], r['why']))
    if ticket is not None:
        for i, it in enumerate(ticket['done_when']):
            if it['kind'] == aos_team_task.JUDGE:
                lines.append('  略過 %d. （審查員判）%s' % (i, it['text']))
    return '\n'.join(lines)


def cmd_verify(team_dir, argv):
    p = argparse.ArgumentParser(prog='aos-team verify', description='對一張單跑固定檢查器（只讀）；全過退 0，沒過退 1')
    p.add_argument('task', help='任務單號，例 t-0001')
    p.add_argument('--rev', type=int, help='（郵差用）這次驗收是哪個 rev')
    p.add_argument('--attempt', type=int, help='（郵差用）第幾次交件')
    p.add_argument('--json', action='store_true', help='印一行 JSON')
    p.add_argument('--out', help='（郵差用）結果另寫進這個檔（暫存檔＋rename）')
    p.add_argument('--again', action='store_true',
                   help='檢查器修好了：請郵差對這張單（停在 verifying 的）重交一次驗收（寄申請，不在這裡跑）')
    args = p.parse_args(argv)
    if args.again:
        return request_again(team_dir, args.task)
    res = verify(team_dir, args.task, args.rev, args.attempt)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_json(out, res)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(render(res, aos_team_task.load(Layout(team_dir), args.task)))
    if res['broken']:
        sys.stderr.write('aos-team: CheckerBroken: %s 有檢查器壞了（不是隊員沒過）\n' % args.task)
        return 1
    if not res['pass']:
        sys.stderr.write('aos-team: NotPassed: %s 驗收沒過\n' % args.task)
        return 1
    return 0


def request_again(team_dir, tid):
    """人：檢查器修好了 → 往 team/outbox/human/ 放一份 reverify 申請，郵差下一輪重交驗收。"""
    from aos_team_format import HUMAN, new_id, write_new
    lay = Layout(team_dir)
    roster = load_roster(team_dir)
    t = aos_team_task.load(lay, tid)
    if t['status'] != 'verifying':
        raise TeamError('NotVerifying', '%s 現在是 %s，不是停在 verifying（只有等驗收的單能重交）' % (tid, t['status']))
    req = {'id': new_id(HUMAN), 'from': HUMAN, 'kind': 'reverify', 'at': now_iso(roster.get('tz')), 'task': tid}
    box = lay.outbox(HUMAN)
    box.mkdir(parents=True, exist_ok=True)
    write_new(box / (req['id'] + '.json'), req)
    print('已交給郵差：%s 重交驗收（rev%d 第 %d 次；不算新的一次交件）' % (tid, t['rev'], t['attempt']))
    return 0
