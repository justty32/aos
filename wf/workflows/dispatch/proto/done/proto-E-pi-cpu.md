# 任務：pi 當 LLM CPU 單元——`aos agent --engine pi`，思考者換成 pi coding agent

> 交接書是唯一契約。協定 [PROTOCOL](../PROTOCOL.md)；隊 B 對 pi 的調查在 `core/agent/docs/pi-interface.md`（**那份把 pi 當介面，方向已被使用者改掉**——本任務是把 pi 當 CPU，調查裡關於 pi 能力的部分仍可參考）。

## 背景與唯一目標

使用者 2026-08-30：「先前的 pi 當介面說錯了，應該是要 pi 作為 llm cpu 單元。開一隊去試試。」
LLM CPU 的定義（使用者）：**仍以 inst 為核心，只是有個 llm 程式可以被指令呼叫**。現在那支程式是 `aos llm`（打 LM Studio）；本任務讓 **pi**（本機 `pi` 0.84.2，`pi --help` 有 `--print`、`--mode json`、`--session-id`、`--provider`、`--model`、`--tools`、`--no-context-files`）成為另一顆可被呼叫的 CPU：agent 的一次 `step` ＝ 在世界資料夾裡跑一次 `pi -p`，pi 自帶 read/bash/edit/write 工具直接在資料夾動手，會話記憶住在 pi 的 session。
**唯一目標**：`aos agent init --engine pi` 之後，`aos say "..."` → 一回合 → `aos listen` 看得到 pi 的回覆，且 pi 真的能在世界資料夾裡用它自己的工具做事（例如建一個檔）。**這是「試試」——做得到就落地最小版，做不到就交一份誠實的報告說卡在哪。**

## 團隊（你是 Opus 隊長）

工作量押給 codex（`codex exec -m gpt-5.6-sol -C <worktree> --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`；最多 4 條、量力而為）。建議：① 調查線（pi 的 provider／auth／print 模式／json 輸出／session 行為，先用 shell 跑通一次 `pi -p` 再說）；② 實作線（`core/agent` 的 engine 抽象＋pi 後端）；③ 測試＋文件。隊長寫任務書、審 diff、跑 ctest、commit；不親自寫實作。

## 工作

1. 讀 PROTOCOL、`core/agent/README.md`、`core/agent/src/step.cpp`、`core/llm/README.md`、`pi-interface.md`。
2. **調查（先做，寫進 `core/agent/docs/pi-cpu.md`）**：
   - `pi auth` 與 `pi --list-models`：目前哪個 provider 可用、要不要金鑰。**不要新建任何帳號、不要填金鑰**；使用者已有的設定能用就用，不能用就試 **把 LM Studio 當 pi 的 provider**（OpenAI 相容端點 `http://localhost:1234/v1`，模型 `qwen/qwen3.5-9b`；查 pi 的自訂 provider 設定方式，可能在 `~/.pi/` 或 `pi config`）。兩條都不通就回報 NEEDS-USER，寫清楚要使用者做哪一步。
   - 跑通 `cd W && pi -p --mode json --no-context-files --session-id <uuid> "..."`，看 stdout 的 JSON 形狀、回覆文字在哪、工具呼叫長怎樣、退出碼、第二次同 session-id 是否記得上一句。
   - pi 的工具在 cwd 動手時，跟 aos 的 `.aos/` 會不會互撞（例如它 `ls` 到 `.aos`、或 AGENTS.md 發現）——用 `--no-context-files`、`--append-system-prompt` 圈住。
3. **實作最小版**：`core/agent` 加 engine 抽象——`agents/<name>/engine.json`（`{"engine":"lmstudio"}` 或 `{"engine":"pi","session_id":"…","model":"…"}`）；`aos agent init --engine pi [--model …]`；`step` 在 engine=pi 時**不走 tools.json／`aos llm`**，改成組 prompt（persona＋`say/` 新訊息）→ `pi -p --mode json --session-id … --no-context-files --append-system-prompt <persona>`（cwd＝世界資料夾）→ 解析回覆寫 `log.md`／`status.json`。自我投遞／every 那段照既有行為，不動。engine=lmstudio 行為完全不變。
4. 測試：engine 選擇一案、pi 後端用**假 pi**（PATH 上一支腳本印固定 JSON）一案；真 pi 只在 smoke 跑。
5. README、code map 檔尾追加；`pi-cpu.md` 最後一節寫「pi 當 CPU 跟 `aos llm` 當 CPU 的差異與不順手處」（給使用者看，≤ 30 行）。
6. commit 到你的 worktree 分支，**不 merge 進 main**。

## 硬性限制

- **禁區**：`core/exec`、`core/wire`、`core/loop`、`core/llm`、`core/tick`、`reference/`、`app/`、`wf/` 除 code-map 檔尾與本資料夾之外。**注意隊 C 正同時在 main 上改 `core/agent`**（cwd 即世界、頂層 `aos say`、init 改寫 every）——你改 `core/agent` 時**只加檔、少改既有檔**（engine 抽象放新檔 `src/engine_*.cpp`，`step.cpp`／`init.cpp` 只插最小分支），rebase 時衝突才小。
- 不新建帳號、不填金鑰、不 `pi install` 任何遠端 extension、不 load／unload LM Studio、不開 GUI、不取鎖。pi 的互動 TUI **不要開**（只用 `-p`）。
- `git add` 只加明確路徑；不 push。
- 邊緣狀況跳過；小裁決記「隊長裁決」。

## 交付

| 產物 | 路徑 |
|---|---|
| 調查與結論 | `core/agent/docs/pi-cpu.md` |
| 實作 | `core/agent/`（engine 抽象＋pi 後端） |
| 回報 | `wf/workflows/dispatch/proto/reports/E.md` |

## 驗收（就這 5 條）

1. worktree build＋ctest 全綠。
2. `pi-cpu.md` 有：可用 provider 與怎麼知道的、`pi -p --mode json` 的輸出範例、session 記憶實測結果。
3. `aos agent init W --name bob --engine pi` → `engine.json` 存在；`aos agent init W --name x`（不帶）仍是 lmstudio。
4. `aos agent say W bob "在這個資料夾建一個 hello.txt 內容是 hi"` → 跑一回合 → `W/hello.txt` 存在、log.md 有 pi 的回覆。（真 pi 跑不通就在報告寫死在哪一步、附原始輸出，本條算 BLOCKED 不算 FAILED。）
5. 再 `say "剛才建了什麼檔"` → 跑一回合 → 回覆提到 hello.txt（session 記憶成立）。

## 回報

最後一則訊息＝ `reports/E.md` 摘要（≤ 30 行）＋STATUS＋worktree 路徑與分支名。

## 隊長裁決

（隊長追加）

## 使用者裁決（2026-08-30）

pi 工具動作繞過 inst 的洞：**先接受**，等隊 T 的工具規劃定了再補（候選接法：pi extension 攔工具呼叫→投遞回填 `batch/`）。
