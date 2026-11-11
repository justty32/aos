# do-task-rename：工具 thought 改名 do_task、預設用呼叫者自己的定義（11-11，線 I）

← [2026-11-11](README.md)｜[thinking](../../README.md)

## 使用者原話與裁定（11-11）

- 「thought，我記得是"小念頭"這個工具。我在想是不是該改名為do_task，也就是執行一個任務，執行完後history中不會殘留細節(或是可選要殘留哪些)。」選項框：名字選「do_task」；除短結論外另帶回什麼選「不加，維持現狀」。
- 兩個環境變數 `AOS_THOUGHT_FROM`、`AOS_THOUGHT_DEPTH`：「沒事，這個還好。我只是怕又濫用環境變數」。
- 預設的小幫手定義（線 C 待裁第 3 題，[knowledge-fix 02](knowledge-fix/02-施工結果與待裁.md#待使用者裁可直接貼進選項框)）：「啊？不是就呼叫者自己的範本嗎？應該說呼叫者的stack內，本身就會放自身的定義來源吧。」

## 決定與施工

- **改名**（不留舊名）：工具夾 `lib/agent/thought` → `lib/agent/do_task`（`git mv`）；gadgets 包登記名 `do_task`；錯誤行開頭 `do_task:`；`AOS_THOUGHT_FROM` → `AOS_DO_TASK_FROM`、`AOS_THOUGHT_DEPTH` → `AOS_DO_TASK_DEPTH`（程式、tooldef、cli_session 的轉送清單、沙箱例子的白名單、defs 的 refs）；開場文 `You are a small thought: …` → `You are a helper started for this one task only.`；警告訊息的 thought → task helper；知識庫 `aos/agents/thought.json` → `aos/agents/do_task.json`、`aos/agents.json#/do_task`，其餘節點（me、world、packs、_index、README）照改；沙箱例子 `examples/thought-boxed/` → `examples/do-task-boxed/`（兩個捷徑重指）；review_round、measure、defs、templates 測試與文件、lib 文件、kernel 文件。json_rewrite 給內部腦的 system 句 `You are a small thought …` 也順成 `small helper`。
- 條文只加「11-11 改名 `do_task`」註（C-42 續、C-52 例外表 ⑥、03 基礎設施〈資料夾程式、工作區與 stack〉、05-agent 目錄、條號表、N-63、N-68、時空）；NORMS 附錄 3 舊名對照加一列，附錄 4 寫入者改新名。
- **預設定義**：優先序 `from` ＞ 登記格的 `AOS_DO_TASK_FROM` ＞ **呼叫者自己的定義**＝daemon 表上叫我那隻那列的 `def`（`aos-agent ctl who --json` 本來就回 `def`，已拼回絕對路徑）。不另開記錄位置。三者都沒有＝`FromMissing`（daemon 管的 agent 表上一定有 `def`，所以實際上幾乎碰不到）。`from` 給了但空白＝`ArgumentsBad`（照舊，不退回預設）。
- 驗證（真 daemon＋假腦，`templates/tests/agent-fsm/test_do_task_own_def.py`）：一份從 agent-fsm 範本抄的定義（hooks.json 照帶、工具只有 do_task），父不給 `from` 叫 do_task → 子的帳 `def`＝父的定義 → 子照同一份劇本再叫 → 孫也是同一份定義 → 孫再叫＝`DepthExceeded`（帳上 code 1）→ 孫、子、父依序答 `Done.`，子孫都收掉。hook（範本的 `timer`）跟著帶也沒出事。
- 測試：do_task 4 支、defs、review_round、measure、lib/agent/tests、knowledge_check、templates 的 test_batch3 全綠；knowledge_check 0 錯誤、40 warning（do_task 節點三段略超 1 KB，推薦值）。

## 代定

1. 子名前綴 `t-` 照舊（讀成 task；名字長度不加）、工具小格 `children/<子名>/` 照舊（線 C 代定 3 同理）。
2. 用呼叫者自己的定義時，只拿**定義**，不拿呼叫者 stack 上的改動（`self_tools`、`self_system`、`self_hook` 改的都在 stack）——小幫手是新 stack。知識庫節點寫了這句。
3. tooldef 的 `env` 欄照舊只列 `AOS_DAEMON`（它是「找東西的 hub 變數」清單）；`AOS_DO_TASK_FROM`、`AOS_DO_TASK_DEPTH` 寫在說明文字裡。

## 環境變數掃描（使用者「我只是怕又濫用環境變數」）

do_task 讀的環境變數：`AOS_DO_TASK_FROM`、`AOS_DO_TASK_DEPTH`（說明裡有）、`AOS_DAEMON`（tooldef `env`）、`AOS_STACK`、`AOS_WS`（每支工具的契約）、`AOS_CLOCK`、`AOS_CLOCK_INTERVAL`（給 `timeout_cycles` 時經 tool_io 讀，`timeout_cycles` 的參數說明有寫）。**沒有說明裡沒寫的**。

## eca 體的呼叫者

eca（claude／codex）叫 do_task 不給 `from`＝小幫手也是 eca 定義：會另起一個 CLI 程序（claude 或 codex）、照 eca 的 `llm_keys` 抄 model。實跑結果見 [mail-notify](mail-notify.md#真腦) 那段（同一次 codex 真腦一起驗）。

## 要重建什麼

- 試驗場（兩台）與任何舊定義：`tools.json` 的 `$override` 串指 `lib/packs/gadgets.json` 的會自動拿到 `do_task`；但登記檔或覆蓋層手寫了 `thought` 那格（path 指 `lib/agent/thought`）的＝那支工具不見，要改成 `do_task`。舊的 `AOS_THOUGHT_FROM`（`aos-agent tools add --envs`）要改設 `AOS_DO_TASK_FROM`。
- 舊 stack 的工具小格 `tools/thought/`（observed 抄本、children 紀錄）不會被新名字讀到；要留就手搬、不留就刪。
- `~/.cache/aos-mcp-aos/tools.json` 這類 tooldef 快取要重刷才看得到新名字。
