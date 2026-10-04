# proto7-2 — 照使用者建議重做 daemon／tick 的第二次試做

← [proto7](../proto7/README.md)｜要合的：[核心 spec](../proto7/spec/core.md)（條號 S-）｜上一次試做：[proto7-1](../proto7-1/README.md)

**proto7-1 之後的第二次試做：照使用者 10-04 的建議（[user-advice](../proto7/user-advice.md)）重做 daemon 與 tick。10-04 照 spec 做完基礎設施（Python 3.11+ 純標準庫）；kernel／agent 這次不做。**

## 入口

- **[spec.md](spec.md)**：核心 spec，只放規則，每條引 S- 條號或核心選項；條目上的 P2-／A2-／A3- 只是編號，由來寫在 problems。
- **[modules/README.md](modules/README.md)**：模組包總覽（每包做什麼、接法、預設、依賴、入口檔），各包的規則在各包 README；會停下等人的情況與恢復步驟在[診斷包](modules/diag/README.md)。
- **[notes/problems.md](notes/problems.md)**：照 spec 做的時候碰到的問題與各條的由來（沒有待你決定的），含 astra 第一輪 A2、第二輪 A3 的處理，與核心精簡刪掉的誤用保護、搬出核心的設計。
- [notes/changes-from-7-1.md](notes/changes-from-7-1.md)：跟 proto7-1 的對照表，最後是 W1～W12（程式照推薦做）。
- [notes/play/](notes/play/README.md)：astra 回歸與試玩紀錄（一輪一列）。
- **[notes/core-slimming.md](notes/core-slimming.md)**：核心精簡方案——盤點、核心最小集、錯誤四分支、擴充點與模組包、kernel 任務包；已照頂層定案做完（kernel 任務包、aos7-pack 還沒做）。
- [notes/component-contracts.md](notes/component-contracts.md)：組件契約藍圖（Fable；各組件的職責／前置條件／保證／明確不管，錯誤四類 M 誤用／X 外部故障／B 組件 bug／G 契約缺口，A2/A3 試分類）。
- [notes/layer-interfaces.md](notes/layer-interfaces.md)：四層（daemon、tick-tock、kernel、agent）之間的交接點調查——誰寫誰讀、延遲、通用 vs 只為 agent／LLM、proto7-1 的 kernel／agent 接上來會怎樣、缺口清單。

## 一句話看改了什麼

node 改成登記、不再掃資料夾；tock 預設照固定 interval，提前 tock 變成可選；只剩 tasks.json 一個任務表（一次性任務是裡面 `mode: "once"` 的一項）；任務資料夾照名字重用，不再每回合新增；核心只留「上一次」，更前面的歷史交給可選的歷史 module。

10-04 核心精簡：核心 lib 4501→2791 行，restart／子 daemon／retry_lost／診斷／工具／稽核改成模組包。

## 怎麼跑

```sh
P=proto7-2/bin                      # 用 proto7-2 的 bin/（程式名跟 proto7-1 一樣是 aos7-*，見下）
mkdir -p /tmp/sp/team/.aos
echo '{"tasks":[{"name":"hello","argv":["sh","-c","echo hi $AOS7_RUN"]}]}' > /tmp/sp/team/.aos/tasks.json
python3 $P/aos7-ctl daemon /tmp/sp register team    # 登記（daemon 還沒起也行，起來才處理）
python3 $P/aos7-daemon /tmp/sp &                    # 只跑 .aosd/nodes.json 登記的 node
cat /tmp/sp/.aosd/status.json /tmp/sp/team/.aos/last-round.json
python3 $P/aos7-ctl daemon /tmp/sp stop --kill
```

**程式名沿用 `aos7-*`**（`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-wait-tock`，加搬來的 `aos-exec`）。proto7-2 的程式彼此呼叫時一律用自己 `bin/` 的絕對路徑，任務的 `PATH` 前面也加的是 proto7-2 的 `bin/`，所以不會跟 proto7-1 混；人手在 shell 裡用時，把 `proto7-2/bin` 放在 `PATH` 最前面（或像上面直接寫路徑）。

## 測試

在 repo 根跑：

```sh
python3 proto7-2/tests/run_all.py            # 全套：tests/core/、modules/*/tests/、modules/tests/、packs/*/tests/
python3 proto7-2/tests/run_all.py -k restart # 只跑名字含 restart 的
python3 proto7-2/tests/run_all.py modules/subd/tests   # 只跑某個資料夾（相對 proto7-2/）
```

離線、純標準庫，322 項約 130 秒（`test_matrix*.py` 是 A2／A3 回歸矩陣，每個故障注入案例都斷言故障確實命中）。核心測試在 `tests/core/`，模組包的在 `modules/<包>/tests/`，上層任務包的在 `packs/<包>/tests/`，counter／歷史 module 的在 `modules/tests/`；共用工具（`base.py`、`_matrix.py`、`_proc.py`、測試鉤子 `_hooks.py`）留在 `tests/`。各資料夾的測試檔名要唯一。每個測試類別的 docstring 開頭標類別：`〔core〕`、`〔<包名>〕`（control、subd、once_retry、diag、tools、observe）或 `〔misuse M-<契約卡號>〕`（誤用造成的，照[組件契約藍圖](notes/component-contracts.md)，之後隨精簡刪掉）。測試起的子程序一律**先收程序、再刪空間**（`tests/_proc.py` 的 `track`／`reap`，`tests/base.py` 收尾時再掃一次環境變數 `AOS7_ROOT` 是暫存根的程序）；暫存根在 `/tmp/aos72-test-*`，跑完會刪。

| 檔 | 測什麼 |
|---|---|
| `tests/core/test_tick_tock.py` | 槽與 run 號、換 run 清基礎設施檔留任務的檔、each 跳過與 max_live 槽、keep 不雙開、from_round／enabled、once、刪槽（報完再一回合）、**200 回合檔案數不變**、tock 之後才結束的 run 照樣報、inst |
| `tests/core/test_ctl.py` | kill（run 必填）、kill 範圍（setsid 孫程序、偽造 pgid、inst 的另一個 session）、**lost 前的身分掃描（NODE＋TID＋RUN）**、掛載與執行中加掛 |
| `tests/core/test_once_threestate.py` | **once 在 launch 標記後、birth 後、Popen 後、刪項目前各點 kill -9 tick**、成組 once 中途被殺；**三態**：round.json／birth.json 讀不到、starttime 讀不到、槽列不出來 |
| `tests/core/test_daemon.py` | **登記／取消登記**、node 刪掉／搬走／換掉 → missing、看不到≠不存在、**early_tock 兩種**、**pause owner**、resume 順便 wake、resume rounds、stop／SIGTERM、第二個 daemon、root 搬走、回條同名蓋掉、控制檔洪水與壞檔、處理丟例外的請求刪掉不重做、log.on、卡住的 tick／tock、**kill -9 daemon 後新 daemon 收回合不雙開**、舊動作接管 |
| `modules/subd/tests/test_subd_ownership.py` | **子 daemon 包**（包裝程式 aos7-subd）：守門檔與 owner、allow-stop、stopped.json、人手重開、子根位置檢查與重複認領 |
| `modules/subd/tests/test_subd_recover.py` | 子 daemon 包 **重開前回收前代**（A5-01）：父 kill 後原任務收乾淨、paused node、起 argv 前／回收中／回收完被殺可接續、掃不完不起新代、壞紀錄、不碰 sibling 與本代 |
| `packs/step/tests/test_step.py` | **step 任務包**：步驟表直譯器、槽外結果檔、檢查器；直譯器各中斷點接回不多派、unknown 不誤報、耐性、pause、wake、restart_on_end、close |
| `packs/budget/tests/test_budget_ledger.py`、`test_budget_step.py` | **budget 任務包**：grant／帳／入口，競爭、各持久點真 SIGKILL、效期與時鐘、獨立核帳（可用＋在途＋已用＝初始）、接 step 的同 request 不重扣 |
| `modules/audit/tests/test_audit_wrapper.py` | 稽核包：包裝過的任務寫檔有紀錄 |
| `modules/control/tests/test_control.py` | 控制包：restart（同槽新 run、state 接得上、加掛帶過去）、reload 與拒絕、壞表不 kill、req_id 去重、請求端／tick／tock 在交接點被殺只重起一次 |
| `modules/once_retry/tests/test_once_retry.py` | once 保證包：x.retry_lost 的 once 從沒起來過就加回跑一次、預設最多一次、舊欄位被拒、模組當 keep 任務跑 |
| `tests/core/test_errors.py`、`test_exits.py` | 錯誤四分支（G1 寫表三態、G2 tick 失敗不算回合、不是一般檔＝不知道）；核心給模組的出口（`x` 照抄、`never_started`、stop-guard.json） |
| `modules/diag/tests/test_diag.py` | 診斷包：aos7-diag 照抄 last_error 並給恢復步驟、按需列出判不出的槽、唯讀（跑前後檔案不變） |
| `tests/core/test_budget.py` | **防再胖**：核心 `lib/aos7_*.py` 總行 ≤ 2800、實際程式 ≤ 2200，超過就失敗 |
| `modules/tests/test_modules_history.py` | counter 示範、歷史 module、history 事件也截行 |
| `tests/core/test_matrix_faults.py` | **A2 回歸矩陣：讀不到＝不知道**——/proc（list／stat／environ／cmdline）× EIO／ESTALE／EACCES × 情境（健康、孤兒、兩者都死、birth 壞）；birth／exit／pid／round／last-round 開檔與列槽讀不到；daemon 看 node 讀不到 |
| `tests/core/test_matrix_docs.py` | **A2 矩陣：檔案半寫、缺欄、型別錯**——round.json（不知道、不 tick、人寫回後接著數）、birth.json × 其他證據（活程序／exit／pid／都沒有）、last-round.json（重新產生、不跳號） |
| `tests/core/test_matrix_once.py` | **A2 矩陣：once／keep 在 tick 七個點與 aos7-run 兩個點 SIGKILL**——執行次數、lost 只報一次、同槽不雙開 |
| `tests/core/test_matrix_a3.py` | **A3 回歸**：kill 帶 run 的重播（請求刪不掉、處理到一半被殺）只對同一個 run、生命週期檔換 FIFO、mount 子目錄暫存、重播通知失敗記錄（F47：不跨回合補送）、P2-01 wake 提前結束固定 interval 回合 |
| `tests/core/test_options_a3.py` | `until_round` |
| `tests/core/test_matrix_misc.py`、`test_matrix_daemon.py` | **A2 矩陣其餘**：node 本身換成符號連結（同 inode／指到 root 外）＝missing 且不寫出 root、rounds 按 owner、暫存檔清理、wake 不保留、tock.json 晚於總結 |

## 防再胖：新功能預設進模組

核心（`lib/aos7_*.py`）有行數預算：**總行 ≤ 2800、實際程式（去空行、註解、docstring）≤ 2200**，之後收到 2000；`tests/core/test_budget.py` 超過就失敗（不算 `lib/aos_*.py` 搬來的 inst 執行器、模組包、測試）。新功能**預設進模組**（`modules/<包>/`：任務、argv 包裝程式、工具三種接法，加上核心給的 `x` 透傳、事實欄位與 log.on、stop-guard.json 三個小出口）。要進核心，三件事都要答得出來：

1. 引得到哪條 S- 條（[核心 spec](../proto7/spec/core.md)）或核心選項；
2. 為什麼不能用任務、包裝程式、工具三個接面做到；
3. 它是通用的，不是只為 agent／LLM（[設計原則](../proto7/notes/principles.md)第 5 條）。

新保護先答「防的是哪一類」（[組件契約藍圖](notes/component-contracts.md)的 M 誤用／X 外部故障／B 組件 bug）：誤用的不做；外部故障只能走錯誤四分支，不加新分支。要加預算，在 [problems](notes/problems.md) 寫一行理由並經使用者同意。

## 結構

| 位置 | 是什麼 |
|---|---|
| `spec.md` | 核心 spec（只放規則） |
| `bin/` | 薄入口：`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-wait-tock`（後兩個的本體在工具包），與搬來的 `aos-exec` |
| **核心** `lib/aos7_*.py` | 受行數預算管（見上），共九檔： |
| `lib/aos7_daemon.py`、`aos7_daemon_timeline.py` | daemon：登記、控制檔、node 消失、status；每個 node 一條時間線（spec 第 1、2 節） |
| `lib/aos7_tick.py`、`aos7_tock.py` | 開回合（tasks.json、once 的 launch 標記）／關回合（last-round.json、刪槽）（第 3、4、7 節） |
| `lib/aos7_task.py` | 槽、三態判定、lost 前的身分掃描、kill（第 5、6 節） |
| `lib/aos7_proc.py` | 程序的事實（`proc`：不在／starttime／不知道）、同一個程序嗎、身分掃描、Q1 範圍的收程序 |
| `lib/aos7_run.py` | 任務的包裝：pid.json、exit.json（帶 run） |
| `lib/aos7_fs.py` | 錯誤四分支的入口（讀檔 `fact`、紀錄 `hold`、例外 `Unknown`）、原子寫、flock、動作鎖與世代、測試鉤子的轉接（`AOS7_TEST_HOOKS` 有設才載入 `tests/_hooks.py`） |
| `lib/aos7_mount.py` | 掛載（4.5）：tick 建掛載、審核執行中加掛 |
| `lib/aos_*.py` | 搬來的 inst 執行器（不算核心預算） |
| **模組** `modules/` | [總覽](modules/README.md)；每包一個資料夾，自帶 README 與 `tests/` |
| `modules/tools/` | [工具包](modules/tools/README.md)：`aos7-ctl`、`aos7-wait-tock`、任務端函式 |
| `modules/control/` | [控制包](modules/control/README.md)：restart／reload 在請求端做 |
| `modules/subd/` | [子 daemon 包](modules/subd/README.md)：包裝程式 `aos7-subd` |
| `modules/once_retry/` | [once 保證包](modules/once_retry/README.md)：`retry_lost.py`（keep 任務） |
| `modules/audit/` | [稽核包](modules/audit/README.md)：包裝程式 `aos7-audit`，可選的寫入紀錄 |
| `modules/diag/` | [診斷包](modules/diag/README.md)：唯讀工具 `aos7-diag`＋會停下等人的情況與恢復步驟 |
| `modules/counter.py`、`history.py` | 最小示範任務、歷史 module 的參考實作（觀測任務包的雛形） |
| **上層任務包** `packs/` | kernel 的任務包（工作語意；通用／agent／LLM 分層，原則 8）；每包一個資料夾，自帶 README（契約卡）、spec、`tests/` |
| `packs/step/` | [step 包](packs/step/README.md)：步驟表直譯器 `aos7-step`＋槽外結果檔＋檢查器 |
| `packs/budget/` | [budget 包](packs/budget/README.md)：grant／帳／入口（預留→執行→結算），示範資源＝假 API 受理次數；原名 account，為避免跟 Linux account 重疊改名 |
| `tests/` | 核心測試 `tests/core/`、共用工具、`run_all.py`（見上） |
| `notes/` | problems.md、core-slimming.md、component-contracts.md、layer-interfaces/、changes-from-7-1.md、play/ |

## 來源（複製進來，不 import 外部路徑）

- `lib/aos_inst.py`、`aos_directives*.py`、`aos_dirname.py`、`aos_exec*.py`、`bin/aos-exec`：**原樣複製自 proto7-1**（10-04；proto7-1 當初從 proto6 複製）。
- `lib/aos7_fs.py`、`aos7_run.py`、`aos7_mount.py`、`modules/tools/aos7_ctl.py`、`modules/audit/aos7_audit.py`、`modules/audit/audit_site/`、`tests/_proc.py`：從 proto7-1 複製後改寫（`aos7_audit.py`、`audit_site/`、`_proc.py`、`aos7_mount.py` 幾乎沒改）。
- `lib/aos7_daemon*.py`、`aos7_tick.py`、`aos7_tock.py`、`aos7_task.py`、`aos7_proc.py`：照 proto7-1 同名檔的結構重寫（程序工具從 proto7-1 `aos7_task.py` 拆出來）。
