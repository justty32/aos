# 交接：eca-pi-bc-1118（pi 乙案＋丙案），11-18 16:5x 收手

← [eca-pi 研究](../eca-pi/README.md)｜任務：pi 非互動改 rpc（回答途中收信）＋pi 畫面（tmux＋aos 的 pi 外掛）

## 11-18 晚家機收尾（接手線，opus）

- **真 pi 整樹實跑過了**（家機 pi 1.5.2、tmux 3.7c、ChatGPT 訂閱 `openai-codex/gpt-6.1-sol`；暫存夾 `~/.aos/scratch/eca-pi-home-1118/`：本機 HEAD `01458f544` 的 clone 套本線補丁、`install.py`、start-eca 換掛一隻 eca-pi）。問、續問、回答途中再寄一封（同一則回答答兩封）、aos 工具、`/compact`（太短不壓）、`aos-agent open`（`pi_aos_screen.mjs` 在真 pi 上回報每輪、`turns.jsonl` 有字）、畫面開著寄信（經 `pi_inbox/` 進畫面、listen 拿到）、畫面正在答時寄信（steer 進同一則）、畫面開著的 `/compact`／`/clear`／`/goal`／`/status`、close 後一問一答再開畫面、`ctl stop` 延後關、`ctl set-def` 都對；逐步結果寫在 [templates/docs/03](../../../../templates/docs/03-eca-pi.md#11-18-實跑)。`ctl rm` 沒跑（這輪的權限設定擋了含 rm 字樣的指令）。
- 實跑順手修：pi 新版在 tmux 3.5+ 開場提醒 `extended-keys-format csi-u`，`cli_screen.PI_TMUX` 加 `set -gq extended-keys-format csi-u`（`-q`＝公司 3.4 不認也不報錯），`test_pi_screen` 跟著多驗一行；`slash.py` 一句過時註解（「json 模式不認」）改掉。
- 文件補完：`templates/docs/03-eca-pi.md` 整份改成乙＋丙、已知限制；knowledge `cli/eca.json` 的 `pi`；`apps/eca/README.md` 第 12 行。
- 踩到的環境坑（不是程式）：家機 pi 的預設供應商是 deepseek（沒登入）、又留著過期的 anthropic 登入，`llm.json` 是 `{}` 時第一輪 `CliFailed`；寫明 `{"model": "openai-codex/gpt-6.1-sol"}` 就好（03「登入」那條寫了）。另：家機 `~/.tmux.conf` 有 resurrect／continuum，開私人 tmux 伺服器要 `-f /dev/null`（aos 的畫面本來就用小格自己的 tmux.conf，不受影響）。
- 測試（同一份 clone，install 後）：apps/eca 223、apps/agent 202、py/tests 527、templates/tests 28 支（略過 2、預期失敗 2）全綠。這條線交了，progress.json 那條拿掉；上面「還沒做」1、3、4 都做了，2 只跑了這四夾。
- 觀察到、沒改的：畫面開著打 `/compact` 而 pi 不壓時沒有事件，aos 等滿 120 秒才回；畫面 `/new` 後沒講話就關畫面，下一次一問一答開新對話（那段是空的）。都寫進 03 的已知限制。

## 先講結論（11-18 16:5x 公司機收手時）

- **程式部分乙、丙都寫完了，單元測試 21 支（test_pi＋test_pi_screen）在 WSL 暫存複本全綠**；全套測試改後還沒跑、真模型的整樹實跑還沒做、說明文件只改了一半。沒 commit。
- 甲案（`--mode json`）**沒留**：乙完全涵蓋甲（同樣的事件、多了 steer 與 compact），照「proto8 當沒有舊版」只留 rpc 一套。

## 11-18 實測（pi 1.5.2、使用者的 ChatGPT 訂閱，暫存夾 `~/.aos/scratch/eca-pi-bc-1118/exp/`）

- rpc：答題中送 `steer`＝回 `queued`，在下一次叫模型之前以一則 user 送進去；工具跑到一半送＝同一則回答（`DONE1 BANANA`），講字途中送＝另開一段（詩、然後 `BANANA`）；全部在 `agent_settled` 之前送到。`follow_up`＝等它講完再一段。答題中再送 `prompt`＝`success false "Agent is already processing…"`。
- 互動畫面（tmux，`--session-id` 同一個 id＝接回那段，`--tui-mode regular`）：`-e` 帶的 .mjs 外掛拿得到 session_start（startup／new）、agent_start、agent_end（messages）、agent_settled；`node:child_process` 的 spawnSync 叫得動外部指令；`paste-buffer -p`＋Enter 多行照樣送出；`/new`＝session_start reason new、新 id；外掛的 `pi.sendUserMessage(字)`（閒著）與 `{deliverAs: "steer"}`（答題中）都把字送進對話——拿來當 pi 畫面的收件口（比照 claude 的 a2a）。
- 畫面裡 `/compact` 在很短的對話上沒觸發 session_compact（多半是 pi 嫌太短不壓，沒確認畫面字）。

## 動過的檔

新增：
- `proto8/py/aos/agentlib/cli_pi_rpc.py`（完成）：rpc 一輪的迴圈（prompt、steer、agent_settled 後 clear_queue／再送 prompt、收工）與 `rpc_once`（compact 用）。
- `proto8/py/aos/agentlib/pi_aos_screen.mjs`（完成，只在 fake 與實驗外掛驗過同樣做法，**這支本身還沒在真 pi 上跑過**）：畫面外掛，回報 hook、讀小格 `pi_inbox/` 送進對話。
- `proto8/py/tests/apps/eca/test_pi_screen.py`（完成）：hook pi、收件夾、真 tmux＋fake_pi 開畫面答題、rpc 迴圈。
- `proto8/templates/eca-pi/screen/_entry`、`screen/interfaces.json`（完成，抄 eca-claude）。
- 本檔。

修改：
- `proto8/py/aos/agentlib/cli_pi.py`（完成）：改走 rpc、`answer_of` 分段、畫面用 `pi_argv(mode=None)`、`screen_extension_argv`。
- `cli_ask.py`（完成）：pi 傳 more；live_a2a 改叫 `cli_a2a.post`。
- `cli_a2a.py`（完成）：pi 收件夾分岔（`socket_path`、`post`、`deliver_inbox`、`note_inbox`、`note_acks`）。
- `cli_hook.py`（完成）：`pi_hook`、hook_main 認 pi。
- `cli_screen.py`（完成）：pi 開畫面、tmux.conf 加 extended-keys。
- `cli_linger.py`（完成）：KINDS 加 pi。
- `cli_session.py`（完成）：檔頭 pi 說明、usage 加 pi。
- `cli_cfg.py`、`context_use.py`（完成，只改註解）。
- `proto8/py/aos/apps/eca/slash.py`（完成）：畫面開著時 pi 的 /compact、/clear→/new、/goal 一律回不支援。
- `proto8/py/aos/apps/eca/main_screen.py`（完成；**cooldown-1118 也改了這檔**，我只加了 describe 的 pi 事件與 watch 認 agent_settled）。
- `proto8/py/tests/apps/eca/fake_pi`（完成）：rpc（prompt／steer／clear_queue／compact／get_state、FAKE_PI_DELAY）與互動畫面（照外掛的樣子叫 hook、收件夾）。
- `proto8/py/tests/apps/eca/test_pi.py`（完成）：改 rpc、加中途收信、live_mail false、answer_of。
- `proto8/templates/tests/test_eca_pi.py`（完成，**還沒跑**）：改成有畫面、hook 四格。
- `proto8/templates/eca-pi/README.md`、`_metainfo.json`、`interfaces.json`、`hooks.json`（完成）：畫面、screen_linger 兩格。
- `proto8/templates/README.md`（完成，一句）。
- `proto8/py/tools/agent/screen_linger/README.md`（完成，一句）。
- `proto8/thinking/2026-11/18/eca-pi/04-接法選項與待裁.md`（完成）：補使用者傍晚原話。

刪除、改名：無。

## 還沒做

1. **文件半成品**：`proto8/templates/docs/03-eca-pi.md`（還是甲案的字，整份要改：rpc、回答途中收信、畫面、slash、已知限制）、`proto8/knowledge/aos/cli/eca.json` 的 `#/pi`（還寫 json 模式、沒畫面）、`proto8/py/aos/apps/eca/README.md` 第 12 行（同）。研究 02 的「tmux 說明」那段可補實測。
2. 全套測試改後（apps/eca、apps/agent、py/tests、templates/tests）沒跑。
3. 真跑整樹沒做：問、續問、回答途中再寄一封、/compact、`aos-agent open`、畫面裡送一句看 turns、畫面與一問一答交替、ctl stop 延後關、close、set-def、ctl rm。
4. 已知限制待寫：畫面開著時人在畫面上打的字不進 history；開畫面那個殼也要有 node／pi 的 PATH；`pi_aos_screen.mjs` 綁 pi 的外掛 API；收件夾送進去的信不署名。

## 測試跑到哪

- 改前基準（`git archive HEAD`，`~/.aos/scratch/eca-pi-bc-1118/base`）：py-tests、apps-eca、apps-agent、tpl-agent-fsm、tpl-judge-llm、tpl-kits、tpl-reviewer、tpl-tool-python rc=0；tpl-image-move-check rc=5；之後各夾沒跑完就被我收掉（收手）。結果在 `tests-before/`。
- 改後：只跑 `test_pi`、`test_pi_screen`，21 支全綠（`~/.aos/scratch/eca-pi-bc-1118/repo`，已 install）。

## 明天怎麼續

- 腳本都在 `~/.aos/scratch/eca-pi-bc-1118/bin/`：`sync.sh`（工作樹→repo 複本）、`install.sh`（REPO_NAME=base|repo）、`quick.sh 測試模組…`（不重編 C++，py 抄進 lib 再跑 apps/eca 的模組）、`runtests.sh`＋`envrun.sh`（`REPO_NAME=repo bin/envrun.sh bin/runtests.sh after`）、`cmp.sh`（比 before／after 失敗名）、`tree.sh`（起暫存樹：start-eca＋eca-pi 叫 pip，env.sh 加 node 與 ~/.local/bin 的 PATH；還沒起過）。
- 先補基準剩下的夾（或直接跑 before 全套），再跑 after、比；然後照「還沒做」1、3。
- 行程：我起的 tmux（exp/t.sock）與基準測試已收掉；`/tmp/kernel-state-path-*` 有一批 aos-daemon 殘留，看不出是不是我基準測試留下的，沒動。使用者的 daemon 沒碰。
