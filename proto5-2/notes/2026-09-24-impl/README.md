# proto5-2 第 1 版實作總報告（2026-09-24）

← [notes 索引](../README.md)｜[proto5-2 README](../../README.md)｜[進度](progress.md)｜[決定](decisions.md)｜[真跑](run.md)｜[astra 審查](review-astra.md)（[任務書](review-task.md)）｜[各隊守則](team-rules.md)

**結論：proto5-2 照 16 檔規範做完了。** kernel 和 daemon 改成「以池為單位、宣告式」：kernel 只說「池 P 要 N 顆」，daemon 自己補、死了照退避重拉、多了先等做完再收。
全套測試 **1277 條、連跑兩次全綠**（約 89 秒）；用真的指令＋LiteLLM `deepseek-chat` 從頭跑到尾**十步全過**；astra 唯讀審查挑出 **7 條必修，7 條全修**（另 3 條建議修 1 條、記 2 條）。

## 做了什麼（白話）

| 段 | 做了什麼 |
|---|---|
| 1 | `proto5/lib`、`proto5/cli` 整份複製到 `proto5-2/`，先確認 1153 條在新位置照樣全綠。proto5 一個字沒動 |
| 2 | kernel 的設定改成池表（`info.json` 第 2 版）；`init --config` 只放 kernel 參數＋池，池可以 0 顆；帳本改第 2 版（只記忙的 cpu、閒的只記號碼） |
| 3 | daemon 重寫成按池管：每池一份宣告 `pool.json`、一顆一個小檔、一池一份摘要；補齊、死了等 1→2→4…→60 秒再拉、每秒最多拉 50 顆、批次停；`aos-daemon boot` 會照上次的宣告把池拉回來；`ls／scale／kill` |
| 4 | kernel↔daemon 之間只剩 `scale` 一種單（一池一張）；`aos-kernel cpu add／rm／ls`；cpu 回完音往 kernel 家丟一張通知，kernel 每格只看通知、剛派的、輪到巡檢的；kernel boot 改成「kernel 池縮到 0 再拉 1」；kernel halt 改成每池縮到 0 |
| 5 | aos-agent 跟著改兩處：cpu.log 的路徑、「是不是被丟掉的工作」改看新帳本 |
| 6 | 舊測試搬到池表；新加池／縮放／通知／交接／退避／halt-boot 拉回的測試；崩潰窗口：daemon 拉一半死、kernel 改宣告一半死、cpu 跑到一半死，另外 astra 點名的 8 個窗口也補了 |
| 7 | 真跑，見下 |
| 8 | README 狀態改「已實作」、加十分鐘上手；`lib/README.md` 重寫檔案表；`spec/proto5-diffs.md` 逐句列 proto5 那邊要換的 11 句（proto5 的字沒改） |
| 9 | astra 審查與修正，見下 |

## 測試數字

| 時點 | 條數 | 結果 |
|---|---:|---|
| 第 1 段（剛複製） | 1153 | 全綠 |
| 第一階段收（daemon、kernel 核心、cpu 通知） | 1227 | 183 條紅（舊整合測試還照 proto5 寫），當時就知道、第二階段搬 |
| 第二階段收（指令、搬遷、agent 線） | 1247 | 連跑兩次全綠 |
| astra 修正後 | **1277** | **連跑兩次全綠**，跑完沒有殘留行程 |

## 真跑數字（[run.md](run.md)）

- 加 5 顆（default 3、llm 2）：daemon **2.1 秒**全部活著；kernel 那邊等一格確認。
- `cpu rm` 一顆正在跑 10 秒工作的：先標「收掉中」，**做完 0.5 秒內才收**，從下指令算 4.6 秒。
- kill -9 同一顆四次：分別等 **1.07／2.03／4.04／8.07 秒**才拉回，跟規範算式一致。
- `aos-daemon halt` 再 `boot`、**不跑 `aos-kernel boot`**：池自己回來、kernel 的 health 馬上 ok、鏈自己接上。
- 兩次 `say --wait`：14.9 秒（有跑工具）、6.3 秒；agent 的記憶跨過 daemon 重開還在。
- 真跑看到幾處字眼會讓人誤會（剛加完一兩秒顯示「在路上」、收掉瞬間寫「pending」等），已改字（D-120～D-126）。

## astra 審查（[review-astra.md](review-astra.md)）

| 條 | 問題（白話） | 處理 |
|---|---|---|
| P1 必修 | kernel boot 用「開始等之前」讀的帳本蓋回去，等待中舊 tick 做的事會不見、甚至重跑 | 修：交接完重讀帳本（D-47） |
| P2 必修 | boot 沒等「正在收」的舊 kernel cpu 死透就開新鏈 | 修：多等 `draining 0`（D-5；比 handoff §1 第 2 步字面嚴） |
| P3 必修 | 舊鏈的 scale 回音把 boot 要求的「整份重送」取消了 | 修：`boot_redeclare` 只有新鏈那張成功才清（D-48） |
| P4 必修 | 第一次宣告就撞名、改 `dpool` 後永遠卡在等別人的池消失 | 修：從沒取得過的位置直接放棄（D-49） |
| P5 必修 | daemon 寫摘要／刪池失敗一次就不再試 | 修：每圈重試直到成功（D-67） |
| P6 必修 | 摘要讀壞了被當成「池已消失」，會放行搬池／boot／halt | 修：`pool_summary_state` 分 gone／ok／unknown，只有 gone 算消失（D-66、D-49a） |
| P7 必修 | 一張怪通知（路徑含 NUL、5000 位數字）讓每一格都失敗 | 修：解析例外一律當壞通知刪掉（D-49b） |
| P8 建議 | 池刪掉後忘了宣告序號，舊鏈晚到的單會把池建回來 | 不做，記成保證外（D-69），列在下面要拍的 |
| P9 建議 | daemon 每圈還是掃全部池 | 修：只碰有事的池（D-68） |
| P10 建議 | 補跨邊界崩潰窗口測試 | 補：kernel 側 9 條、daemon 側 4 個窗口 |

## decisions 摘要（[decisions.md](decisions.md)，共 71 條 D＋九題）

- **九題**：第 1～3 題（帳本整份讀寫、agent 偷看整份帳本、一顆 cpu 一支 Python）先不動、以幾百到一千顆為準；第 4～9 題全部照草稿。每題寫了翻案要改哪裡。
- 幾條值得你知道的：
  - **D-4／D-38**：`cpu rm P/<最大號>` 退休的號，規範說「大於最大成員號的 skip 寫入時丟掉」，但那樣退休號下次 `cpu add` 又會被用回來。隊長裁定 **skip 一律保留**（永久退休優先），代價是 skip 只增不減。
  - **D-5**：boot 等舊 kernel 池時多等 `draining 0`（規範原句漏列，規範沒改）。
  - **D-43**：「池少 N 顆」「搬池中」在 health 算「會自己好」，`aos-agent status` 不會喊 kernel 壞了。
  - **D-53**：沒帶 `decl` 的 scale（人用 `aos-daemon scale`）永遠不算過期。
  - **D-80**：K 的路徑經過 symlink 時通知全被當成壞通知——已修（兩邊 realpath 再比）。
- 其他多是「規範沒寫、選最保守」的小事（錯誤碼、印什麼字、欄位預設），各條都寫了翻案要改哪裡。

## 沒做的

- 規範 `spec/` 一個字沒改（定稿）；proto5 的規範也沒改，要換的句子列在 [spec/proto5-diffs.md](../../spec/proto5-diffs.md)。
- 九題的前三題（規模）照指示先不動：帳本仍整份讀寫、agent 仍每格讀整份帳本、一顆 cpu 一支 Python。實際上限以千顆為準，沒做上萬顆的壓測。
- 退休 cpu 家的清理指令、`cpu rm --now`、「放棄一張沒人跑的單」協定：照草稿不做。
- P8 的 tombstone：不做（見下）。
- 文件同步員重數條數時看到 `test_daemon.RestartTest` 紅過一次（當時可能與別的測試同時跑）；隊長單跑 8 次、四份平行 3 輪共 12 次都綠，沒重現，先記著。
- 修正後沒有再真跑一次一條龍；修正都有真 daemon 的端到端測試蓋著（`test_p52_e2e.py`、`test_kernel_fix_astra.py`）。

## 要使用者拍的新題

1. **退休號的 skip 只增不減，可以嗎？**（D-4／D-38）規範原本要丟掉「大於最大成員號」的 skip 讓它不變長，但會讓剛退休的最大號被 `cpu add` 用回來。現在選「永久退休優先」。要改回：`aos_kernel_cpu._set_count`。
2. **handoff.md §1 第 2 步要不要補「`draining 0`」？**（D-5）程式已經多等了，規範原句沒寫；要不要讓人把規範那句補上（同時改 proto5-diffs 那列）。
3. **池刪掉後的舊單要不要擋？**（P8／D-69）現在：池縮到 0、被 daemon 拿掉後，daemon 忘了它的宣告序號；如果舊鏈的單在那之後才到，會把池建回來。平常靠檔名順序與 boot 先縮 kernel 池擋掉大半，剩下的算保證外。要完全擋就得加「墓碑」（記每池最後的序號與 owner），並訂 owner 換手的規則。
4. **`aos-daemon ls` 的 `restarting` 要不要改寫法？**（D-126）現在 `running 2 restarting 1` 容易被看成三顆；建議印成 `running 2（含 restarting 1）`。
5. **剛 `cpu add` 的一兩秒 `aos-kernel ls` 顯示「宣告已送出，下一格確認」**：kernel 一格才收一次 daemon 的回音，所以 daemon 已經全部活著、kernel 還要等一格才算確認。要不要接受這個延遲（`tick_ms` 越大越明顯）？
