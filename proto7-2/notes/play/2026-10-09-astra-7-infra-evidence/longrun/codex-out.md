astra-7／longrun（2026-10-09，HEAD `ad1dfa25`）：本線驗收全部通過，無新發現、無未做項目。

- 通過｜全套一次：458 項、0 failure／error／skip，rc 0；unittest 244.845 秒、外部計時 245.035 秒。兩個已知偶紅案例本次皆綠，未觸發補跑。證據：[suite.json](suite.json)、[suite.log](suite.log)；重跑：[probe_suite.py](probe_suite.py)。
- 通過｜step：真 daemon 跑完並關閉 r1～r450，88.486 秒；150／150 個完成工作快照正確，兩步 attempt 均為 1，halt／error=0。證據：[step.json](step.json)、[step-snapshots.tar.gz](step-snapshots.tar.gz)；重跑：[probe_longrun.py](probe_longrun.py) 的 `step`。
- 通過｜step 檔案與框架：含隱藏檔／tmp 的逐回合 job／槽／.aosd 檔名數最高 10／8／9；完成工作的 10 個檔名在替換 instance 識別後完全一致，無舊 instance 結果殘留。`resends` 永遠 `{}`，`tries`／`accepted` 最多各 2 項。證據：[snapshot-audit.json](snapshot-audit.json)、[step-snapshots.tar.gz](step-snapshots.tar.gz)；重驗：[probe_audit.py](probe_audit.py)。
- 通過｜daemon 資源：RSS 21784→21936 KiB（+152，1.007 倍），fd 7→5（0.714 倍）。證據：[step.json](step.json) 的 `resources`。
- 通過｜adapt：真 tick/tock 從 r1 再跑 320 回合至 r321，36.186 秒；321 份暫存器均為 `ok`、`c=80.1`、`hot=true`，來源版本／SHA／已關回合逐份核對，22 個完整檔名逐回合相同，框架與暫存器欄名集合不變。證據：[adapt.json](adapt.json)、[adapt-snapshots.tar.gz](adapt-snapshots.tar.gz)；重跑：[probe_longrun.py](probe_longrun.py) 的 `adapt`。
- 通過｜核心行數／lib 歷史：`test_core_line_budget` rc 0，印出總行 2952／程式行 2305；相對 astra-6 2757／2123，增加 195／182，獨立 AST/token 計數吻合，D7 確實只印不擋。證據：[core-budget.log](core-budget.log)、[core-lines.json](core-lines.json)、[lib-diff-stat.txt](lib-diff-stat.txt)、[lib-history.txt](lib-history.txt)；重跑：[probe_core.py](probe_core.py)。
- 通過｜持久狀態：`nodes.json` 無 `reaping` 鍵；450 回合倒數完 `paused.json={"paused":{"a":["qa"]},"steps":{}}`，狀態為 paused。`.aosd/` r10～r450 共 441 次觀測的固定檔名均為同 8 個；暫態 tmp 未累積。證據：[step.json](step.json)、[step-snapshots.tar.gz](step-snapshots.tar.gz)。
- 通過｜清理／寫入邊界：四個自建 `/tmp/astra7-longrun-*` 根已移除，無本線殘留程序，既有 tracked 檔無修改，證據單檔均低於 300 KiB。證據：[ps-before.txt](ps-before.txt)、[ps-final.txt](ps-final.txt)、[cleanup.json](cleanup.json)；重驗：[probe_cleanup.py](probe_cleanup.py)。

各 lib 檔相對 `510dd134` 的行數變化如下；`aos7_*` 才計入核心總額。完整 `git diff --stat` 為 10 檔、268 insertions／71 deletions。

| lib 檔 | 總行：前→後 | 總行差 | 程式行差 |
|---|---:|---:|---:|
| `aos7_daemon.py` | 630→749 | +119 | +114 |
| `aos7_daemon_timeline.py` | 309→325 | +16 | +15 |
| `aos7_fs.py` | 343→349 | +6 | +6 |
| `aos7_mount.py` | 168→181 | +13 | +13 |
| `aos7_proc.py` | 249→276 | +27 | +20 |
| `aos7_run.py` | 113→116 | +3 | +3 |
| `aos7_task.py` | 334→344 | +10 | +10 |
| `aos7_tick.py` | 414→414 | +0 | +0 |
| `aos7_tock.py` | 197→198 | +1 | +1 |
| `aos_directives.py` | 228→230 | +2 | +2 |
| `aos_directives_base.py` | 111→111 | +0 | +0 |
| `aos_directives_options.py` | 73→73 | +0 | +0 |
| `aos_dirname.py` | 30→30 | +0 | +0 |
| `aos_exec.py` | 270→270 | +0 | +0 |
| `aos_exec_run.py` | 227→227 | +0 | +0 |
| `aos_exec_spawn.py` | 117→117 | +0 | +0 |
| `aos_exec_wait.py` | 124→124 | +0 | +0 |
| `aos_inst.py` | 252→252 | +0 | +0 |

重跑都從 repo 根執行 `python3 <上述探針路徑>`；長跑加 `step` 或 `adapt`。各腳本會自動套用 `TasksMax=800`／`RuntimeMaxSec=1800` 的 systemd scope，依「全套→step→adapt」循序執行。快照重驗另驗過 6 個故意改壞資料的反例，全部拒絕。

新發現：無，未新增 B／G／M／X 編號。已知限制未重報；本次普通長跑未注入產品故障，JSON 已標記注入為 none。