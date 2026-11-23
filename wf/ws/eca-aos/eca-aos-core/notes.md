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
