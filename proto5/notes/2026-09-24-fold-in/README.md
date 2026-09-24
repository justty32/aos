# proto5-2 納入 proto5＋拆檔 tidy（2026-09-24）

← [notes 索引](../README.md)｜[proto5 README](../../README.md)｜[astra 審查任務書](review-task.md)｜[astra 回報](review-astra.md)

**結論：proto5 現在就是池式那一版。** proto5-2 的 daemon／kernel／cpu 通知搬進 `proto5/lib`、`proto5/cli`，取代舊的；proto5 分岔後加的 agent 線（check、ls --json、listen、talk、tools、access.json、aos-jail、cli-agents 範本、教程 03～07、04b）全部留著。規範照 `proto5-2/spec/proto5-diffs.md` 換了 11 句，新章節搬進 `proto5/spec/`。`proto5-2/` 只剩 `spec/` 與 `notes/` 當歷史。

## 怎麼合的

proto5-2 第 1 段是把 proto5 整份複製過去（分岔點 `c81a98b`），所以用三方合併：base＝分岔點的 `proto5/lib`，一邊是 proto5 現在的、一邊是 proto5-2 現在的。只有一邊改過的檔直接取那邊；兩邊都改過的只有 3 支程式（`aos_kernel_check.py`、`aos_kernel_cli.py`、`aos_agent_init.py`）和 7 個測試檔，手解。

| 來自 proto5-2（池式，以它為準） | 保留 proto5（agent 線，以它為準） |
|---|---|
| `aos_daemon.py`＋新的 `aos_daemon_cli／loop／pools／rpc` | `aos_agent_*`（access、access_cli、check、listen_render、talk、tools、tools_edit 都是分岔後加的） |
| `aos_kernel.py`、`_boot`、`_engine`、`_health`、`_info`、`_ledger`＋新的 `aos_kernel_cpu`、`_pools` | `aos_jail.py`、`aos_home.py` |
| `aos_exec_cpu.py`（多 `notify`） | `aos_kernel_ls.py`（advice-r1 的表與 `--json`，改接池資料） |
| `aos_agent.py`、`aos_agent_results.py`（配合池式必要的兩處：cpu.log 路徑、discard 查法） | |

兩邊都重寫過的兩處怎麼合：
- **`aos-kernel ls`**：proto5-2 的按池摘要＋`--pool`／`--procs`，加上 proto5 的對齊表、`-v`、`--json`。行程表預設只列 bad 與暫停／重試中的（上萬個行程時不洗版），`--procs` 全列。`--json` 升 `aos_kernel_ls` 第 2 版：`cpus[]` 換成 `pools{}`（daemon 已經沒有孩子表）。
- **check**：`aos-kernel check` 只查 kernel（proto5 的做法），按池表查（proto5-2 的做法）。`aos-agent check` 查 agent 的三個池，llm 只查它自己那池。

## 規範

改了 `proto5/spec/` 底下的 kernel、daemon、cpu 三個資料夾，另外改了 aos-llm、agent、aos-agent 裡被點名的幾句。新檔：kernel `info／names／pools／cli-cpu／health／scale`、daemon `pools／cli`、cpu `notify`。舊檔名都保留（很多筆記和教程連過去），內容換新。五題照調度者代裁寫進去：退休號只增不減、boot 也等 draining 0、池刪掉後舊單把池建回來算「保證外」、`running 2（含 restarting 1）`、cpu add 後一兩秒顯示「下一格確認」是正常的。

## 拆檔（不改行為，拆前拆後都 1597 條全綠）

| 原檔 | 前 | 後 |
|---|---:|---|
| `aos_exec.py` | 619 | `aos_exec.py` 253（讀目標＋命令列）、`aos_exec_run.py` 282（開串流、起子行程、等、逾時、寫 exit）、`aos_exec_spawn.py` 114（給 daemon 的 spawn） |
| `aos_kernel_cpu.py` | 412 | `aos_kernel_cpu.py` 215（cpu add／rm／ls）、`aos_kernel_rows.py` 203（按池摘要與一顆一行，cpu ls／ls／health／check 共用） |

超過 400 行但**刻意不拆**：`aos_agent_access.py`、`aos_agent_talk.py`。這兩支是 agent 線，別隊正在改，拆了之後合併會很痛。

**刪掉的**：
- 沒人用的程式碼：`aos_kernel_info.work_pools`、`aos_daemon` 的 `serve`／`_log` 別名、`aos_kernel_cli` 的 `_stderr_hint` 舊名與 `DAEMON_ENV`。
- `aos_kernel.py` 的匯出表縮到只剩真的有人用的 13 個名字。
- 兩份一樣的 `_peek` 收成 `aos_daemon_pools.peek`。
- `proto5-2/lib`、`proto5-2/cli` 整個刪掉。`proto5-2/README.md` 改成一頁「已納入」。

## 測試數

| 時點 | 條數 |
|---|---:|
| 納入前：proto5／proto5-2 | 1470／1277 |
| 合併去重後（同名檔三方合併，兩邊的功能都蓋到） | 1597 全綠 |
| 拆檔、tidy 後 | 1597 全綠（兩次，約 111 秒） |
| rebase 到最新 main（加上 T1、T3、L2 的新測試）＋審查與真跑修正 | **1724** 全綠 |

C 隊記的 `test_daemon.RestartTest` 偶爾失敗，這次跑了七八輪都沒撞到，沒改它。

## 真跑（LiteLLM deepseek-chat，沒碰 LM Studio）

七步全過：開機 → 加 5 顆 → agent init、check、start、say --wait（12.7 秒）→ kill -9 一顆（1～2 秒拉回）→ cpu rm 兩種 → 再 say、listen --last 2、talk 管線 → 停機。清場後 `pgrep` 是空的。節錄：

```text
# cpu add 之後立刻看 aos-kernel ls：daemon 已經全拉起來，kernel 下一格才確認
  default  want 3  sent 0  busy 0  idle 0  draining 0   daemon default: running 3 pending 0 dead 0 failed 0   宣告已送出，下一格確認
# kill -9 default/0 之後 1.5 秒
  default  want 3  sent 3  busy 1  idle 2  draining 0   daemon default: running 3（含 restarting 1） pending 0 dead 0 failed 0
# say --wait
現在是 2026年9月24日 18:29。
# cpu rm 剛下
default/1  收掉中  daemon 在收
default/2  收掉中  daemon 在收
```

真跑挖到一件並修掉：`cpu rm` 剛下時，health 會喊「池 default 少 2 顆（daemon 在補）」。其實 daemon 是照新數字在收，不是少了。現在改成拿「在途的縮小單」的數字比。

文件組真跑另外挖到三件，也修了：
- `init --config` 用舊的 `{"cpus": …}` 格式時，原本默默只剩 kernel 池，現在明確拒絕。
- 手建的家缺 `requests/`，`boot` 會成功，要到 `add` 才出錯。現在 `boot` 先把資料夾補上。
- `InfoVersion` 錯誤訊息原本指到 proto5-2 的規範，改指 proto5 的。

## astra 審查

3 條必修全修，1 條建議也修了：
- 池的 envs 要用「拉那池的 daemon」的環境去解 `$env`，原本一律用 kernel 池那個 daemon 的。
- `ls --json` 裡「還沒宣告的池」各欄位該是 null 還是 0，規範寫明，並補契約測試。
- `aos-agent check` 的規範改成逐池查 daemon。
- 建議那條：`aos-agent init` 的提示原本指到 proto5-2 README，改指教程 01。

審查的另一個重點「proto5 分岔後的東西有沒有被蓋掉」：astra 逐項對過，沒有被蓋掉的。

## 沒做的

- 開機合一、家不合一、sqlite 帳本：使用者說之後另一輪做。K 隊的停車＋喚醒提案也這次不做，拆檔後 `aos_kernel_engine`、`aos_daemon_loop` 沒動介面，要接還是好接。
- agent 規範裡三處舊說法沒改：`cli-status.md` §1.3 的例句「cpu dead」、`tick.md` 的 `queue`、`cli-talk.md` 的「cpu missing」。那是 L2 的地盤，留給他們。
- 文件組列的幾件小事沒動：
  - boot 撞池名時訊息像「縮到 0 失敗」。
  - `aos-daemon kill` 印的 `killed 0` 看起來像「砍了 0 顆」。
  - 手寫 info 沒寫 daemon 時，boot 不會退回用 `AOS_DAEMON_HOME`。這點教程 06 有寫。
- `wf/WAIT_USER.md` 裡指到 proto5-2 README 九題表的兩項沒改，main 那邊有人在動，怕撞。

## 要你拍的（都已經照預設做了）

1. **`ls` 預設只列有事的行程**（bad、暫停、重試），其他收成一行，要看全部加 `--procs`。預設：照這樣。
2. **`ls --json` 升第 2 版**，舊的 `cpus[]` 拿掉。預設：照這樣。沒有外部程式在讀第 1 版。
3. **`init --config` 給舊的 `cpus` 格式就報錯**，不幫你自動轉成池表。預設：報錯。
4. **`aos-daemon kill` 印 `killed 0`** 要不要改寫法（例如 `killed default/0`）。預設：先不動。
