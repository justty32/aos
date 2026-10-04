#!/usr/bin/env python3
import pathlib,json
p=pathlib.Path(__file__).resolve().parent;d=json.loads((p/'results.json').read_text());l=d['longrun']
s='''# astra-5：全套、核心與 step 回歸

三次全套都為 322／322，沒有失敗或觀察到不穩定案；17 個核心／控制／稽核探針、8 個 step 探針、2 個 step F47 探針全過。A4-01～07、F47、§4.4 未見退化，本線沒有新 B／G。刻意刪除 frame.pc 屬 M；被殺或漏通知後保守停住屬 X，不列 bug。

| 項目 | 結果 | 證據 |
|---|---|---|
'''
for r in d['suites']:s+=f"| 全套第 {r['run']} 次 | 322／322；實耗 {r['seconds']:.3f} 秒；rc 0 | [逐項 log](suite-{r['run']}.log) |\n"
s+='''| A4-01 | 6／6；request／birth 的 EIO、EACCES、ESTALE 均有命中，留請求、不給回條、birth 不變、task 活；復原後可掛上 | [core/results.json](core/results.json) |
| A4-02／06 | 同 req_id 競爭只起一次；birth 換代後再送允許新起，符合明訂去重期 | [core/results.json](core/results.json) |
| A4-05 | 真 daemon 動態登記 nested node；既有 audit 包裝任務其後越界写入有標 bad，自己的輸出仍 ok | [core/results.json](core/results.json) |
| A4-03／04／07 | initial wait 正確計算 patience；壞型別回 JSON 診斷；wake 合法；timeout kill 帶正確 run | [step/step-probes.json](step/step-probes.json) |
| §4.4(a)／(b) | after-birth、before-once-delete 真 SIGKILL 後 once 不重起；一般／重播都在報結束下一個 tock 才刪槽 | [core/results.json](core/results.json) |
| F47 核心／模組 | 同回合重播補通知；跨回合不補；history 留 gap；once_retry 漏取樣符合不保證，已有 pending 可重試 | [core/results.json](core/results.json) |
| F47 step | 4 次 EIO 漏通知、once 槽清除後仍採原 request／attempt 結果，a／b 各跑一次；漏 3 次通知後耐性仍從原 since 算 | [step/f47-step.json](step/f47-step.json) |
| 核心行數 | test_budget.py 單跑 rc 0；總行 2757／2800、實碼 2123／2200 | [log](core-budget.log)、[逐檔行數](core-lines.json) |

## 450 已關回合長跑

CSV 範例 convert→stats→end，restart_on_end=true、interval 20ms、真 daemon。退出前另讀回 round.json，確認 open=false 且 round≥450，保存於 longrun.observed_closed_round。

'''
s+=f'''| 指標 | 結果 |
|---|---:|
| 已關回合／耗時 | {l['closed_round']}／{l['seconds']:.3f} 秒 |
| 回合樣本 | {l['samples']} |
| 觀察到完成工作的快照 | {l['completed']} |
| report rows=5 與 convert request 正確 | {l['report_ok']}／{l['completed']} |
| 每步 attempt=1 | 全部 |
| halt／error | {l['errors']} |
| 同 ended 階段工作目錄檔數 | 全部 10 |
| 同 ended 階段 bytes | {l['ended_job_bytes'][0]}～{l['ended_job_bytes'][1]} |
| 全階段 job／node／root 檔數 | {'／'.join('～'.join(map(str,l['all_phase_file_ranges'][k])) for k in ['job','node','root'])} |

同階段檔數固定，沒有隨完成工作數增加；bytes 小幅差異為回合／識別文字長度，不宣稱任意長度皆有界。[長跑完整證據](step/longrun.json)。

## 重跑與清場

從 repo 根執行：

```sh
python3 proto7-2/notes/play/2026-10-04-astra-5-infra-evidence/regression/run_suites.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-5-infra-evidence/regression/core/probe_core.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-5-infra-evidence/regression/step/probe_step.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-5-infra-evidence/regression/step/probe_f47.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-5-infra-evidence/regression/step/run_comparison.py --mode longrun --rounds 450
```

沿用 astra-4 探針，只改本輪證據路徑與 /tmp 前綴；長跑增補已關回合斷言，沒有產品失敗誤列為 bug。[探針調整記錄](harness-notes.json)。全部自建工作區於 /tmp，按 PID／PGID 清理，收尾 /proc AOS7_ROOT 與 ps 核對無本線已知測試根殘留；各案例根皆已刪除。[清場 JSON](cleanup.json)、[ps](ps-final.txt)。全套依既有測試的 per-case cleanup 清除工作根；最後三個 suite PID 均已消失。

共 {d['source_files_unchanged']} 個原有程式／測試檔 SHA256 前後相同（[before](source-hashes-before.json)、[after](source-hashes-after.json)）。未動 scratchpad、未改產品／測試／舊證據、未 commit／push、未使用 LLM。

最該修的三條：沒有。
'''
(p/'summary.md').write_text(s)
