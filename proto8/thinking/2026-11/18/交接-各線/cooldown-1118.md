cooldown-1118 交接：腦出錯原因寫進 cooldown.json（件 A）、獨立驗證三小題（件 B），程式與測試都改完、改後全套測試還沒跑成。

# cooldown-1118 交接（11-18 16:5x）

**狀態**：件 A、件 B 三項程式＋文件＋測試都寫完；**改後全套測試沒跑成**——rsync 工作樹做複本時別線正改到一半（`proto8/py/aos/agentlib/cli_a2a.py` 第 90 行沒收尾的字串），`aos.apps.agent` 整個 import 不起來，那輪 133 failures／17 errors 與本線無關、作廢。假腦實操也沒跑。沒 commit、沒 `git add`。

## 件 A：cooldown.json 多兩欄（選配，舊六欄不動，沒這兩欄的檔照讀）
- `retry`（布林）＝寫的那支之後會不會自己重送；`error`＝`{"code","msg"}`，下層的錯誤代號與原話一行（fsm＝kernel 回信的 error，也就是 `aos-llm: error: 代號 原因` 那行的後半）。欄名照 brain_failed 事件既有的 `retry`、`error`。型別不對只丟那欄；每次失敗整份重寫。
- 寫：fsm wait 格（`templates/agent-fsm/wait.py`＝`templates/start-api/agents/ann/wait.py`）——SendFailed `retry` true 無 error；BudgetMissing true＋error；kernel retry true 的 BrainFailed true＋error；退 1 停下的 BrainFailed false＋error（解得到才寫）。eca `handoff.py`——claude 暫時錯 true，其他（含 codex）false，不寫 error。
- 讀：`hints.brain_failure`（listen／ask）有 `retry` 欄就只看欄位（停下＝`retry` false 且沒 `think/pending.txt`；原話取 `error`，沒有用冷卻的代號＋原因）；沒 `retry` 欄才退回舊的 stderr 判法（註解寫明是給自寫 body，不是為了舊版）。`ctl ls --json` 的 cooldown 照帶兩欄；`ctl ls -l` 的 LAST ERROR 有 error 時顯示「代號＋下層代號＋原話」。
- listen 印的字：
  - 停下 以前 `…stopped on an error before answering: aos-llm: error: EndpointFailed HTTP 400: model not supported / agent-fsm: error: BrainFailed aos-llm recv exited 1 (its reason is above) (failure 1 in a row; …)`
  - 停下 現在 `…stopped on an error before answering: EndpointFailed HTTP 400: model not supported / BrainFailed aos-llm recv exited 1 (failure 1 in a row; …)`
  - 重送中 以前 `aos-llm: error: EndpointFailed HTTP 503 …` → 現在 `EndpointFailed HTTP 503 …`；SendFailed 以前帶 stderr 最後一行錯誤行，現在是 `SendFailed aos-llm send exited N …`（fsm 不攔 send 的 stderr，原話少了）。
- 兩題裁「不動」（無限慢重試、AnswerMissing 代號）沒碰。

## 件 B
1. `重建步驟單.md`：「關」格再起的視窗 B 與更新第 5 步改成 `cd ~/aos-home && source env.sh && cd llms && aos-exec --stack stacks/llm def`；更新第 4 步示範加 `diff -r $AOS_HOME/templates/daemon-root ~/aos-home/root`，「實跑」欄改成「前一句列 llm.json、後一句列 root/.env」（複本上核過兩邊各只差這一檔）；install 耗時補「同時有別的編譯在跑時會更久」。
2. set-def 後工作區欄 `-`：根因在 daemon C++（`reconcile.cpp`）——add＋stop／sleep 同一封信的列沒寫 `ws`（只在 launch）；改成列上也寫 `ws`。結束碼／reason 不保留（daemon 文件：add＋stop 的列 code 本來是 null；沿用 agent2 代定）。daemon 舊測試 `test_never_started_stopped_row_starts_after_daemon_restart` 原本斷言「沒有 ws」，改成斷言有且對。
3. 到期單殘留：改在 `aos-eca-screen close`（main_screen.py `cmd_close`）關畫面時在小格鎖裡 `cli_linger.drop`；set-def、`ctl rm`、`aos-agent close` 都走它，三者都會清（計時在被關掉的 tmux 裡，單子留著永遠沒人收）。

## 動過的檔
**整檔只有本線的改動**：
- `proto8/py/aos/agentlib/cooldown.py`
- `proto8/py/aos/apps/agent/hints.py`
- `proto8/py/aos/apps/agent/listen.py`（只 HELP）
- `proto8/py/aos/apps/agent/ctl/ls.py`
- `proto8/py/aos/apps/eca/main_turn.py`（一行註解）
- `proto8/templates/agent-fsm/wait.py`
- `proto8/templates/start-api/agents/ann/wait.py`
- `proto8/templates/docs/02-agent-fsm.md`
- `proto8/knowledge/aos/brain.json`
- `proto8/docs/NORMS/附錄4-持久檔.json`
- `proto8/cpp/aos-daemon/src/daemon/reconcile.cpp`
- `proto8/cpp/aos-daemon/docs/03-起-停-暫停.md`
- `proto8/cpp/aos-daemon/tests/test_lifecycle.py`
- `proto8/thinking/2026-11/17/重建步驟單.md`
- `proto8/py/tests/apps/agent/test_listen_brain_failure.py`（+4 支）
- `proto8/py/tests/apps/agent/test_ls_health.py`（+1）
- `proto8/py/tests/apps/agent/test_set_def.py`（+2）
- `proto8/py/tests/apps/eca/test_retry.py`（加斷言）
- `proto8/templates/tests/agent-fsm/test_cooldown.py`（+5）
- 本檔

**跟別線混在同一檔（只標的段落是本線）**：
- `proto8/py/aos/apps/eca/main_screen.py`：import 加 `cli_linger`、close 說明多一行 "Also removes the delayed-close order…"、`cli_linger.drop(cell)` 一行（pi 的 describe／agent_settled 不是本線）。
- `proto8/py/aos/apps/eca/handoff.py`：兩處 `cooldown.fail(..., retry=…)`。
- `proto8/py/aos/apps/agent/README.md`：ctl ls 那條（LAST ERROR、`--json` cooldown）與「listen／ask 的問腦失敗」那條。
- `proto8/py/aos/apps/eca/README.md`：「畫面延後關」段結尾那句。

**半成品**：程式邏輯都寫完了，但上面所有檔**都還沒經改後測試驗證**，交件前一定要先跑完下面的步驟。`cli_linger.py`、`ctl/set_def.py` 不是本線的。另：Windows 跑 `py_compile` 在工作樹留了一些 `__pycache__`（gitignore，沒刪）。

## 測試數字
- 改前基準（git archive HEAD，WSL `~/.aos/scratch/cooldown-1118/before`）全綠：
  - apps/agent 195（跳 3）
  - apps/eca 213
  - py/tests 519（跳 1）
  - templates/tests 28（跳 2、預期失敗 2）
  - agent-fsm 204
  - judge-llm／kits／reviewer／tool-python 共 15
  - wf/tools/tests 61
  - cpp/aos-daemon/tests 124
- 改後：作廢（原因見上），在 `res-after`。但不經 aos-agent 的幾支看得出結果：agent-fsm 的 `test_cooldown` 含新加 5 支都過、daemon 改過的 `test_never_started_stopped_row_starts_after_daemon_restart` 過；wf-tools 61 支全過；judge-llm／kits／tool-python 全過。listen 新加的 4 支是 import 錯（cli_a2a），不算數。

## 沒驗的
- 新增的 12 支測試與改過的 daemon 測試，一支都還沒真的跑過；只在 Windows 過了語法檢查。
- C++ 改動只確認 after 複本 install 退 0。
- 假腦實操（400 端點、沒人聽的埠、set-def 對停著／睡著的看 `ctl ls` 與到期單）沒跑；eca 真身沒試。

## 要使用者裁的題
1. listen 的字少了程式名前綴，SendFailed 少了 aos-llm 原話——可以接受嗎？要原話得讓 fsm 攔 aos-llm send 的 stderr（碰「下層 stderr 一律不攔」）。
2. B3 修在 `aos-eca-screen close`，`ctl rm`、`aos-agent close` 也會清到期單；維持，還是只限 set-def？

## 明天怎麼續
1. 確認工作樹能編譯（別線把 `cli_a2a.py` 等收好）。
2. WSL：`cd ~/.aos/scratch/cooldown-1118 && rm -rf after`（自己的暫存，要刪先問；或改 setup 腳本換個夾名），`setsid ./cd1118-setup.sh after < /dev/null`、`setsid ./cd1118-tests.sh after < /dev/null`（腳本已含 cpp/aos-daemon/tests），`diff res-before/fails.txt res-after/fails.txt`；基準的 cpp-daemon log 在 `res-before/cpp-daemon.log`（124 OK）。
3. `setsid ./cd1118-live.sh after 25 < /dev/null`：看各隻 `cooldown.json` 的新欄、listen 印的字、`ctl ls` 的 ws 欄、eve 的 `screen_close.json` 有沒有被清；腳本結尾按記下的 pid 收自己的行程。
4. 全綠再交件；交件按上面清單分 hunk。
