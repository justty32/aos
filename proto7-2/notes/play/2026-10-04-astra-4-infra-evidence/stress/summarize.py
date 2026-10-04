#!/usr/bin/env python3
"""Render compact review evidence after run_stress.py completes."""
import json
from pathlib import Path

out = Path(__file__).resolve().parent
r = json.loads((out / 'results.json').read_text())
confirm = json.loads((out / 'confirm/identity.json').read_text())
snap = confirm['snapshots'][0]
rows = ['# 三次全套與 G3 壓力', '', f"HEAD：`{r['head']}`。正式 G3 10 次各自與全套重疊；三次全套依序跑，配 4／3／3 次 G3。原始 log 與每次回合／PID 證據均保留，無重跑覆蓋。", '', '| 全套 | 測試數 | unittest 秒 | wall 秒 | 結果 |', '|---|---:|---:|---:|---|']
for s in r['suites']:
    rows.append(f"| {s['run']} | {s['test_count']} | {s['unittest_s']:.3f} | {s['elapsed_s']:.3f} | rc={s['returncode']}；fail/error/skip={len(s['failures'])}/{len(s['errors'])}/{len(s['skips'])} |")
rows += ['', '沒有觀察到全套測試不穩定案。執行命令為 `PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/tests/run_all.py -v`，`-v` 只增加逐案 log。', '', '## G3：10／10 未通過', '', '三個任務只安裝 SIGTERM 忽略 handler、寫 ready 檔後 sleep；保留 AOS7 身分、不改 session／pgid。使用合法父槽 `ctl.json`（kill＋目前 run），父 keep 自動起下一個 subd。每次父 kill 都回 `ok:true`，舊子 daemon 死後三個舊任務仍活，新子 daemon 已關完 round 2、3 到開 round 4 仍全部活；期限從新子 daemon 首次可見的 round 1 起算。', '', '| 次數 | 同時全套 PID | 舊／新子 daemon | 原任務 PID | 新 daemon 起點 → 最後觀察 | 通過 |', '|---|---|---|---|---|---|']
for g in r['g3']:
    e = g['events'][-1]
    rows.append(f"| {g['case']} | {g['suite_pid']} | {g['old_daemon']}／{g['new_daemon_seen']['status_pid']} | {', '.join(str(p['pid']) for p in g['old_tasks'])} | {g['new_daemon_seen']['round']} → {e['round']}（{len(e['old_tasks_alive'])} 活） | 否 |")
rows += ['', '補強確認例（不計入上述 10 次）：[confirm/identity.json](confirm/identity.json) 證明新子 daemon `gen=2`、`last-round=7` 後，原三任務仍為同一 PID／starttime 的 `S` 狀態，三個原 runner 也活，`last-round.alive` 仍列 `s0#1`、`s1#1`、`s2#1`。`Z` 不算活，並保留 `sid`、`pgid`、`AOS7_*`、SIGTERM 忽略旗標。此補強例傳入的 suite PID 已完成，所以不拿它計算並行壓力通過率；正式 10 次的 start/end 檢查全部為 true。', '', '## 發現：B（subd）', '', '契約：`modules/subd/README.md` 契約卡「父 kill」保證與界線末二條，尤其第 55 行「下一個子 daemon 起來時的身分掃描收」。這項承諾未兌現。忽略 SIGTERM 是本輪指定且合法的工作負載，沒有違反任務身分前置條件，故非 M；已不是僅有外部被殺而正常復原的 X。', '', '程式對照：`aos7_task.judge` 第 92～98 行只要原 runner 或任務尚活便當 LIVE；`resolve` 第 118～123 行只對 SUSPECT 作 lost 前掃描。因此下一代 daemon 沿用原活槽，沒有 README 宣稱的收尾；這是實測與程式對照的推論，不主張核心一般 daemon 重啟應殺全部活任務。', '', '建議修法一行：由 subd 明確辨識並回收前一代未完成的 stop 殘留，或依 loop4 藍圖評估可配置父 kill 寬限並以此 3 任務案例驗證，不能只保留目前的回收承諾。', '', '## 清場與重現', '', '每例先 SIGTERM 自己的父 daemon，再只對自己 AOS7_ROOT 下殘留的確切 PID 發 SIGKILL；所有已知 PID 以 `ps -o pid,ppid,pgid,stat,args -p ...` 複核。探針啟用 Linux child-subreaper 只為接收／wait 自己的孤兒，避免留下 zombie；不更改 production argv 或 AOS7 身分。每例 `cleanup.after=[]`、`known_alive=[]`，三個 suite 暫存目錄皆空，最後自己的 `/tmp/astra4-stress-*` 已刪；scratchpad 未碰。', '', '重現：在 repo 根執行 `PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-4-infra-evidence/stress/run_stress.py`。本次原始檔：[results.json](results.json)、[suite-1.log](suite-1.log)、[suite-2.log](suite-2.log)、[suite-3.log](suite-3.log)、[confirm/results.json](confirm/results.json)。']
(out / 'summary.md').write_text('\n'.join(rows)+'\n')
identities = []
for slot in snap['slots']:
    p = slot['pid']
    live = next(x for x in snap['processes'] if x['pid'] == p['pid'])
    identities.append({'slot': slot['name'], 'pid': p['pid'], 'same_starttime': p['starttime'] == live['starttime'], 'live_state': live['state'], 'sid': live.get('sid'), 'runner_pid': p['runner_pid']})
compact = {'suites': r['suites'], 'g3_total': len(r['g3']), 'g3_pass': sum(g['pass'] for g in r['g3']), 'g3_fail': sum(not g['pass'] for g in r['g3']), 'g3_all_overlapped_suite': all(g['suite_running_at_start'] and g['suite_running_at_end'] for g in r['g3']), 'confirmation_gen': snap['generation']['gen'], 'confirmation_closed_round': snap['last_round']['round'], 'confirmation_identities': identities, 'all_g3_clean': all(not g['cleanup']['after'] and not g['cleanup']['known_alive'] and g['tmp_removed'] for g in r['g3']), 'tmp_removed': r.get('tmp_removed'), 'final_proc_remaining': r.get('final_proc_remaining'), 'finding': {'classification': 'B', 'component': 'subd', 'guarantee': 'README 界線：下一個子 daemon 起來時的身分掃描收寬限內收不完的子任務'}}
(out / 'summary.json').write_text(json.dumps(compact, ensure_ascii=False, indent=2)+'\n')
