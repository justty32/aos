eca-aos-core 的工作筆記：這個位子是什麼、開工先讀哪幾份，以及做過之後學到、下一個人該照做的事；代班的 Claude 子 agent 也讀這份、收工前寫回。

← [我的地盤](README.md)｜[地盤規矩](../../README.md)

## 這個位子是什麼

- 專管 aos 本體程式庫 `proto8/py/` 與 `proto8/cpp/`。使用者 11-23 答七題：「都按照推薦。但py/cpp可以開了，這是aos本體程式庫，是重要對象。」
- 名字 `eca-aos-core` 是 eca-aos 取的。有活才掛；沒掛時由 eca-aos 派 Claude 子 agent 代班。代班沒有對話記憶，全靠這份筆記。
- 職責、讀寫範圍、交接、模型的正本在角色卡 [wf/org/core](../../../org/core/README.md)，這裡不重抄。

## 開工先讀

1. 角色卡 [wf/org/core](../../../org/core/README.md)。
2. 規矩卡 [rules-card](../../../workflows/common/rules-card.md)（「活樹旁九條硬規則」全部適用）。
3. [conventions](../../../workflows/common/conventions.md)（程式碼慣例）與 [code map](../../../knowledge/code-map.json)（只讀要動的那個夾的逐檔表）。
4. [feature-dev](../../../workflows/feature-dev/README.md)、[testing](../../../workflows/testing.md)。
5. 這份筆記下面「學到的」。

## 學到的（給下一個人）

做過一件之後，把下次要照做的步驟、踩過的坑寫在這裡；使用者直接交代給這個位子的規矩，逐字附日期另開一節。

### 問腦這條路在哪幾個檔（11-23 代班查 index_view「全部必填」）

- agent-fsm 的 think 格 `templates/agent-fsm/brain.py`（約 190～244 行）：`aos-tools ls --json` 取每支工具的 `description`、`parameters`，原樣包成 chat 寫法 `{"type":"function","function":{...}}`，不補 `required`、不帶 `strict`。
- llm kernel 收信後叫包的 `exec`：範本 `templates/kernel/llm-kernel/kernel.json`，gpt 那幾包寫 `"api": "responses"`；`endpoints/litellm/_entry` 是 `aos-exec lib/tools/base/llm_http --key-env LITELLM_KEY`。
- `py/tools/base/llm_http/_entry`（約 90～123 行）組 body、決定打 `/chat/completions` 還是 `/responses`；`responses_api.py` 的 `_tool()`（30～34 行）只把 `function` 那層攤平，`parameters` 不動。
- 之後是 `~/repo/llm_proxy` 起的 LiteLLM 1.87.5（uv 暫存環境，site-packages 在 `~/.cache/uv/archive-v0/<雜湊>/lib/python3.12/site-packages/`，看 `_uv_ephemeral_overlay.pth` 找）；chatgpt 那支是 `litellm/llms/chatgpt/responses/transformation.py`，tools 原樣過。
- 工具入口的參數檢查在 `py/aos/tool_io.py`：`arguments()` 驗型別，`_drop_nulls()` 把有型別的鍵的 `null` 當成沒給（空字串不算）。

### 不叫真模型、把 aos 送出去的請求抓下來

- 做法：抄 `templates/kernel/llm-kernel` 到暫存樹、`kernel.json` 的 `endpoints` 整個換成兩包（一包 `"api": "responses"`、一包不寫），`url` 指到自己起的 Python 假伺服器（`http.server` 綁 `127.0.0.1` 埠 0，存 POST body、回最小合法回應），`exec` 照用 `endpoints/litellm`。`aos-exec --stack T/k T/kdef` 起 kernel，`AOS_LLM_KERNEL=T/k AOS_STACK=T/ws/.stack/ aos-daemon daemon.json` 起 daemon，`aos-agent ctl add`、`llm set model=<包>`、`say`、`listen`。腳本與做法留在 `~/.aos/scratch/idxview-1123/`（`run.sh` 清 `AOS_*` 並 `unset LITELLM_KEY`、`setup.sh`、`ask.sh`、`teardown.sh`、`server.py`）。
- 收工：`aos-daemon-ctl -d <stack> shutdown` 兩次（daemon、kernel），假伺服器 kill 自己記的 pid。
- 工具單叫（不經腦）：`echo '<JSON>' | aos-tools --file $AOS_HOME/templates/agent-fsm/tools.json call <工具>`，設好 `AOS_WS`、`AOS_STACK`（`calltool.sh`）。
- 收尾核對 `pgrep` 時，活樹別的 eca 可能剛好起來（11-23 遇到 eca-aos-kb、eca-aos-templates），用 `readlink /proc/<pid>/cwd` 分清楚是不是自己的，不要動。

### Responses 沒帶 strict＝strict true（11-23 線 eca-aos-core-1123 實證、已修）

- 實證：直接打 `http://127.0.0.1:4000/v1/responses`（這台 llm kernel 設定 `~/aos-home/llm/kernel.json` 的包寫 `localhost:4000`；LiteLLM 不用金鑰就收，`LITELLM_KEY` 在我的殼裡沒設），模型 `chatgpt-gpt-6-luna-low`，一支三個選填屬性的假工具、`tool_choice: required`。不帶 strict：回顯 `strict: true`、`required` 列滿三個、`additionalProperties: false`，模型叫 `{"query":"apples","limit":10,"pointer":""}`；帶 `"strict": false`：回顯 false、不加 required，模型只給 `{"query":"apples"}`。腳本 `~/.aos/scratch/eca-aos-core-1123/probe.sh none|false <模型>`（清 `AOS_*`，請求與回覆存在同夾 `req-*.json`、`resp-*.json`）。
- 修法：`responses_api.py` 的 `_tool()` 對沒寫 strict 的 function tool 補 `"strict": false`（寫了的照留）；`_tooldef.json` 與 `--help` 各補一句。chat completions 那條不動（strict 預設本來就是 false）。
- 驗：乾淨複本 `install.py` 後跑 llm_http 48 條、kernel_llm 89 條、`py/tests` 762 條全過；再用複本的 llm_http（`e2e.sh`）真打一次，模型只給 query。
- **還沒 install.py 進活樹**：活樹那份 lib/ 照舊會讓 gpt 腦把選填參數填滿，要等 eca-aos 問使用者裝。
- 坑：`zsh` 下 `grep --include=*.md` 會被 glob 吃掉（no matches found），用 Grep 工具或加引號。
- 坑：`commit-request claim/submit` 的檔名在 zsh 裡用 `$F` 傳不會拆字，整串變成一個「檔名」被 claim 住；用陣列 `"${F[@]}"` 或直接寫開。claim 錯了用 `release --line <線> "<那整串>"` 收掉，`claims` 確認空了。

### json_search 的 key:"" 改成報錯（11-23 線 eca-aos-core-1123 第二件）

- `py/aos/json.py` 的 `do_search` 擋 `key == ""`（ArgumentsBad），json_search 與 jsonx_search 共用這支；`value:""` 照字面用不動。兩支的 `_tooldef.json` 的 key 說明補「not empty」。
- jsonx_* 的工具夾在 `py/tools/aos/`，不在 `base/`。
- 動到工具說明時，順手跑 `templates/tests/agent-fsm`（250 條，約 4～5 分鐘）與 `py/tests`（762 條，約 3 分鐘）。

### 工具經 aos-tools call 時看到的環境（11-23 第三件第 1 項）

- `AOS_STACK`＝叫方 stack 裡的小格 `<stack>/tools/<名>/`（不先建），`AOS_STACK_IN_CALLER`＝`tools/<名>`；`AOS_CD` 被 aos-exec 換成**工具自己的夾**。所以工具裡拿得到叫方的 stack（`tool_io.caller_stack()`，11-23 新增），拿不到叫方的定義夾。
- guard 的 `py/tools/agent/guard/scope.py` 早就處理過同一題：`own_stack()` 照 `<stack>/{tools,hookeds}/<名>` 剝小格，`definition()` 去 daemon 表找 stack 裝著 `AOS_STACK` 的那列取 `def`。要再碰「工具怎麼知道 agent 的定義」先看它。
- ws_write 經 aos-tools 叫的定義夾保護怎麼補，11-23 回 NEEDS-USER（三個做法），還沒定。

### 這次的坑

- 測試的跑法：`py/tests/apps/agent` 232 條約 4 分鐘；`py/tests` 765 條約 3 分鐘。
- `py/tools/agent/user_send/tests` 的 `test_tool_missing` 在複本 `source env.sh` 之後一定失敗（PATH 上有真的 `aos-user`），改之前就這樣，不是新壞的。
- 在 Bash 工具裡（zsh）直接寫 `for v in $(compgen -e …)` 不可靠，清 `AOS_*` 一律寫成 `#!/bin/bash` 腳本再跑。
- 一份文件兩項都要改又要一項一個 commit：先把完整版改在複本，回 repo 時先只套第一項的那幾段交掉，再整份抄回去交第二項。

### 讀 daemon 表找定義夾：py/aos/daemon_table.py（11-23 第四件）

- guard 的 scope.py 與 ws_write 共用 `aos.daemon_table`（`table_rows`、`definition(env, stack=)`、`TableError`）。scope.py 用兩支薄包裝把 `TableError` 轉成 `ScopeError`，guard 的測試照舊改 `scope.time.sleep`、看 `scope.TABLE_RETRY_S`。
- scope.py 找 aos 套件時自己插 `sys.path`、import 完自己拿掉：guard.py 與 test_scope 都是「插第 0 格、import scope、pop(0)」，插在第 0 格不拿掉會被它們 pop 錯格。
- 真 daemon 的暫存樹做法：`AOS_STACK=$T/d/ aos-daemon daemon.json &`、等 `$T/d/state.json`、`AOS_DAEMON=$T/d aos-agent ctl add --name me <定義>`（不用 llm kernel，agent 起來閒著），收工 `aos-daemon-ctl -d $T/d shutdown`。腳本 `~/.aos/scratch/eca-aos-core-1123/repro4.sh`。
- 讀表一次約 0.2 ms（一列）；經 aos-tools 整次呼叫 125～155 ms，差異在雜訊裡。
- user_send 的 `test_tool_missing` 11-23 修好（PATH 去掉放著 aos-user 的夾），上一節那條坑已不成立。

### arbitrary_exec 怎麼標（11-23 晚線 arbexec-1123，d20cc7d34、19d8ef838）

- 判準在 C-22：工具本身直接執行、或登記叫的人給的東西才標 true；經由寫檔間接達成的不算（write、edit、json_set 這類不標；使用者 11-23 晚「可以」）。讀這旗標的只有 `py/tools/aos/shell_report/report.py`（`arbitrary_exec is True`、沒 `sandbox`＝open）。
- 標 true 的現在有：shell、run_python、self_tools、self_hook、tools_def、agents_ctl、subagent、agent_def、measure、review_round、promote；fork、screen_linger、do_task、self_llm、self_system 是 false。`py/tools/aos/` 那幾支的 `_metainfo.json` 是單行緊湊寫法，照原樣接在 `"parallel":false` 後面。
- 跑法：`~/.aos/scratch/arbexec-1123/setup.sh`（git archive HEAD＋改動、複本 install.py）、`test.sh`（清 `AOS_*`，六支工具測試＋`py/tests/apps/tools` 124＋`py/tests` 768，全部約 3 分鐘）。

### 11-24 三件只讀調查（線 eca-aos-core-1124）

- 報告在 [report-1124.md](report-1124.md)。要再量閒置輪詢就照抄 `~/.aos/scratch/eca-aos-core-1124/` 的 `sample.py`（60 秒）、`names.py`（daemon 表的 pid 對名字）、`analyze.py sample.json names.json`。
- 量法的坑：aos-loop 的 cwd 是**定義夾**不是 stack；表上那列的 pid 有時是包在外面的 aos-daemon，aos-loop 是它的子行程（看 ppid）。忙著跑長一輪的 eca，`cutime` 一直是 0（子行程還沒收），不能當成「不花錢」。剛 fork 還沒 exec 的行程 cmdline 會是父行程的（`aos-loop loop.json`），別當成它在做事。
- 這台沒有 perf、pidstat、bpftrace；`/proc/<pid>/stat` 的 cutime/cstime 已經夠算每隻的格子 CPU。
- claude 的 MCP：local 範圍存在 `$CLAUDE_CONFIG_DIR/.claude.json` 的 `projects[cwd].mcpServers`，只認完全相同的 cwd；`--strict-mcp-config` 擋掉它，多給一個 `--mcp-config` 就帶得進去。MCP 在檢查登入之前就起，暫存的沒登入設定資料夾就能測，不會叫到模型。

## 交接（11-24 壓縮前寫）

- **做完的**：11-23 第一～四件（a30197e52、733a5fecc、8e14a5e38、a69d96ae7、4226bd3a5、259e8afa9、0093988b0、9ce053bfa、07f639035，都已回 DONE；eca-aos 說都裝過了，最後兩個要它裝）。11-24 三件只讀調查做完：報告 [report-1124.md](report-1124.md)（5d9081236），已回 DONE。
- **還沒開的信**：信箱裡一封 eca-aos 的 REQUEST `01795486423393288569.1105429.695740`「（排在三件調查之後）三件小程式：aos-llm ls 印通道與排隊、列出表外留下的 stack、ctl ls --deep」——還沒 mailbox_read，壓縮後先讀它。
- **要記得的限制**：eca-aos 11-24 說 templates 三分切換延到 11-25 早上，**在那之前 proto8/ 底下一個檔都不能改、不能交**；寫程式的活要先確認這條解了沒（問 eca-aos 或看 wf/progress.json）。不碰 `~/.aos/scratch/tri-split-1124/`。
- 暫存：`~/.aos/scratch/eca-aos-core-1123/`（乾淨複本 clean～clean4、重現腳本）、`~/.aos/scratch/eca-aos-core-1124/`（量測腳本與數據）；沒有留下行程。
