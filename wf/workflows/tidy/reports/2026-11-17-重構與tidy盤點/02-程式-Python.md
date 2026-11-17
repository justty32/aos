← [入口](../2026-11-17-重構與tidy盤點.md)｜涵蓋：cmd、py、lib、templates、extras 的重構拆檔清單｜上一份 [01-程式-C++與kernel](01-程式-C++與kernel.md)｜下一份 [03-文件-wf](03-文件-wf.md)

## 程式重構拆檔：Python（cmd、py、lib、templates、extras）

注意：入口 `bin/*` 沒副檔名，按 `*.py` 算會漏掉最大的幾支。最大的（不含測試）：`extras/aos-view/aos-view` 3031、`cmd/aos-tools/bin/aos-tools` 1170、`aos-daemon-ctl` bin 767（前 384 行是 HELP）、`templates/agent-fsm/wait.py` 653、`lib/agent/guard/guard.py` 653、`lib/…/tools_def/_entry` 651、`lib/tool_io.py` 601、`llm_rules.py` 581、aos-grow 494。多數是一檔一件事、說明字長，不必拆。

| # | 檔或夾 | 現況（證據） | 問題 | 建議做法 | 工作量 | 風險 | 已知／新 |
|---|---|---|---|---|---|---|---|
| P1 | `extras/aos-view/aos-view` | 3031 行、103 個函式（頂層核過行數），檔裡已用 `# ----` 分 11 段：樹 220、relay 601–1184、頁面、動作 1418、server 2061、v2 2462、布告欄 2768、指令 2824 | 一檔多職責 | 照現有段拆成同夾幾支模組，主程式只留入口；改名時（使用者說之後會改）一起做較省 | 大 | 中（正在常改、正在用） | 新 |
| P2 | `extras/aos-view/aide-def/{idle,brain,act,wait}.py` | 跟 `templates/agent-fsm` 同名檔比，差 6／61／94／287 行；`atomic_file`、`cell_common`、`llm_settings` 三支一模一樣 | 整份範本格被複製後各自走樣 | 要不要併回範本是方向題（見裁題 Q3） | 中 | 中 | 新 |
| P3 | `extras/aos-view/web/` 與 `ui/v1/` | `map.js` md5 一樣（頂層核過）、`app.js` 差 26 行；`web/README` 寫「舊位置，不再提供」；`aos-view:2065` 沒有 ui/v1 時退回 web | 死副本＋舊位置退路 | 刪 `web/` 與 2065 退路（刪檔要使用者點頭） | 小 | 低 | 新 |
| P4 | `cmd/aos-tools/bin/aos-tools` | 1170 行：說明 1–270，讀定義與快取 311–520、疊層合併 587–790、子命令 808–1135 | 一檔多職責、cmd 最大 | 照 aos-eca 11-12 的拆法：bin 只留找模組＋main，本體放 `aos_tools/` | 中 | 中（測試多） | 新 |
| P5 | 「從 HELP 抓 usage 那行」 | 5 份規則各異：tools:274、grow:94、eca-screen:141（後兩份一字不差）、daemon-ctl:385、agent `common.py:46 usage_of`；`sub_reason` 兩份 | 錯誤行各支自己拼 | 收進 `py/aos_flags.py` | 小 | 低 | 新 |
| P6 | `cmd/aos-eca/…/screen_slash.py:92` | 直接寫 `"aos-eca: warning: …"` | 沒走 `aos_flags.warn` | 改叫 warn | 小 | 低 | 新 |
| P7 | `cmd/aos-mcp-launch` | 用 `lib/tool_io.die`，全 cmd 只有它沒 import aos_flags | 慣例說 cmd 走 aos_flags | 改走 aos_flags，或在文件寫明例外 | 小 | 低 | 新 |
| P8 | TERM→等→KILL | `lib/process_group.stop` 已有；`cmd/aos-mcp/bin/aos-mcp:206–215` 自寫一份（頂層核過：迴圈 SIGTERM、SIGKILL、killpg）；lib 的 `hook_run.py:88–106`、`mcp_client.py:199` 也各一份 | 重複（SESSION-LOG 提過這類） | 改叫 `process_group.stop`；`aos_sweep_proc.py:209–240`（pidfd 收別人的）、`aos-tools:399`（逾時直接 KILL）情況不同，列著就好 | 小 | 低 | 已知（延伸） |
| P9 | 兩份 `read_env_file` | 本體 `lib/env_file.py:19`；`lib/mcp_server_file.py:99` 只包一層換錯誤代號（頂層核過兩處都在） | 其實已收好，只是同名易看錯 | 可把包裝那支改名（例 `read_server_env`） | 小 | 低 | 已知（已大致解） |
| P10 | 讀 /proc 判活（N-17，只列） | stat＋boot_id 比對兩份：`py/daemon_ctl/poke.py:33–60`、`aos_sweep_proc.py:24–40,175–190`；agent `ctl/state.py:231–290`、`ctl/shared.py:66`、`hints.py:81`；lib `cli_linger.py:79–83`、`quiet.py:56` | 散 6＋處；N-17 使用者說「盡量只讓 daemon 相關的碰 pid…推薦遵守」、維持未裁 | sweep_proc 改用 poke 的那份；agent 幾處搬不搬由使用者定 | 中 | 中 | 已知 |
| P11 | 靠位置找模組（只列） | cmd：13 支 bin 寫死 `../../../py`（5 支再寫死 `../lib`）、4 支往上找、3 支列清單用完拿掉；`aos_flags.py:49` 往上找；templates／aide-def 各格往上找 `py/aos_flags.py`（共 10 檔）；插 `sys.path` 的 67 檔（55 是測試） | 四種寫法並存（使用者 11-16：之後專門規劃） | 等使用者排規劃 | 中 | 中 | 已知 |
| P12 | 「暫存再改名」寫檔 | cmd／py 18 檔各自 `os.replace` | 重複 | 收一支共用寫檔函式（先查 lib 有沒有現成的） | 中 | 中 | 新 |
| P13 | 14 處「同夾有 `agent_files.py`／`hooks.py` 就用它」 | templates/agent-fsm 與 aide-def 各格，例 `act.py:35、39`、`wait.py:75、83`；repo 裡沒有定義這樣放、測試也不抄 | 舊放法的退路 | 刪掉，只留 lib 那條路 | 小 | 低 | 新 |
| P14 | `cmd/aos-agent` `listen.py:74–81,153`、`ask.py:36` | 對方沒寫 `aos.letter` 時退回舊配法 | 舊格式相容碼 | 確認所有 body 都寫了就拿掉 | 小 | 中 | 新 |
| P15 | `lib/agent/hook_fire/_entry:6` | 沒設 cause 當 null，註解「舊版 aos-loop」 | 舊版相容 | 拿掉 | 小 | 低 | 新 |
| P16 | `lib/agent/subagent/_entry:92–97`「BookOld」 | 偵測 11-14 前的相對路徑名冊就擋下（11-15 才加） | 為舊格式留的碼，但是使用者裁過要擋的 | 何時拿掉見裁題 Q4 | 小 | 低 | 新 |
| P17 | `lib/base/{move,copy,mkdir,trash,stat,view}/_entry` | 六支的 `def out()` 一模一樣（頂層核過 md5 全同） | 複製貼上 | 收進 `tool_io` | 小 | 低 | 新 |
| P18 | `lib/tool_io.py`（601 行，204 檔引用） | 五塊：時鐘 35–110、tooldef 驗證 112–168、輸出錯誤 169–225、路徑 226–299、旗標 300–560；只有 7 檔用時鐘 | 時鐘跟「工具 IO」無關 | 時鐘抽一支，其餘不動 | 中 | 中 | 新 |
| P19 | hook／helper 自寫 die、read_json | `context_wrap/_entry:47`、`brain_notify:37`、`mail_notify:38`、`hook_fire:31` 自寫 die；`gate_lib.py:44`、`kernel/runner.py:20` 自寫 read_json | 疑似重複 tool_io；hook 算不算「工具」沒把握 | 見裁題 Q5 | 小 | 低 | 新 |
| P20 | 測試 `clean_env` | 23 檔各一份（agent 11、tools 10…） | 重複 helper | 各 tests 夾放一個共用小檔 | 小 | 低 | 新 |
| P21 | 測試 `run_tool` | 23 個測試檔各定義，8 份前 12 行一樣 | 同上 | 抽 lib 共用測試 helper | 中 | 低 | 新 |
| P22 | 測試起假 daemon | `cmd/…/tests/reply_fixture.py` 有 `Daemon` 類別只 2 檔用；另 6 檔（add_dotenv、add_parent_daemon、kernel_state_path、rm_keep、set_def、who_registered_daemon）各寫 `until()`、各起 daemon | 重複 | 改用 reply_fixture | 中 | 中 | 新 |
| P23 | 大測試檔 | test_guard 1656、test_daily 961、test_sweep 921（一個 class 47 測試）、test_switch 915（7 個 class） | 大但結構清楚 | test_switch 可照 class 拆；其餘不急 | 小 | 低 | 新 |
| P24 | `lib/agent/guard/` | README 標「under review. Do not mount」，沒定義接它；guard.py 自寫 out／fail | 整包審查中 | 審完再整理，現在別動 | — | 高 | 已知 |

不拆：`lib/aos/kernel/letters.py` 剛好 300 行、30 個小函式都繞著信，單一職責（SESSION-LOG 記的「到 300 行」核過，**已知、不必拆**）；`wait.py` 653 行是單一函式長（`ensure_box` 422–548），不算多職責；`llm_rules.py`、`mcp_client.py` 各管一件事。

沒把握：`aos_flags` 除旗標外還放 `read_window`、`aos_note`、`confirm`，名字跟職責不太對；`hints.py:27`「舊 state.json 的 paused」像是上次留下的狀態、不像相容碼；`kernel-chain-check/check.py` 699 行（一個 class 佔 123–668）是手跑劇本沒細看；`tools_def/_entry`、`fork/_entry` 只看結構；重複只抽查常見函式名，沒做全面相似度比對。
