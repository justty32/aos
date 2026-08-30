# 隊 E 回報：pi 當 LLM CPU（`aos agent init --engine pi`）

← [交接書](../proto-E-pi-cpu.md)｜[PROTOCOL](../PROTOCOL.md)｜[dispatch](../../README.md)

**STATUS：DONE**
**worktree**：`/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aabf401d3cc5aa3f1`
**分支**：`worktree-agent-aabf401d3cc5aa3f1`（基於 main 的 `25509d3`）
**日期**：2026-08-30

## 一句話

**做得到，而且已經落地。** `aos agent init W --name bob --engine pi` 之後，
`aos say` → `aos run` 一回合 → pi 真的在世界資料夾裡用它自己的工具動手，
回覆進 `log.md`，而且**跨回合記得上一句**。五條驗收全過。

## 產物

| 產物 | 路徑 |
|---|---|
| 調查與取捨 | `core/agent/docs/pi-cpu.md`（198 行） |
| engine 抽象 | `core/agent/src/engine.cpp`（新檔） |
| pi 後端 | `core/agent/src/engine_pi.cpp`（新檔） |
| 測試 | `core/agent/tests/test_agent_engine.cpp`（新檔，7 個 case） |
| CLI／設定 | `init.cpp`／`run.cpp`／`paths.cpp`／`internal.hpp`／`agent.hpp`／`CMakeLists.txt` |
| 文件 | `core/agent/README.md` 檔尾追加、`wf/workflows/common/code-map.md` 檔尾追加 |

`git diff --stat`：**9 個既有檔 +101 −7**（`step.cpp` 只加 6 行，見下）。

## 使用者指定的 provider：DeepSeek，已就緒，不用填任何金鑰

```text
$ PI_OFFLINE=1 pi auth check --provider deepseek
ready
$ PI_OFFLINE=1 pi --list-models deepseek
deepseek  deepseek-v4-flash  1M  384K  yes  no
deepseek  deepseek-v4-pro    1M  384K  yes  no
```

憑證是環境變數 `DEEPSEEK_API_KEY`（`~/.pi/agent/auth.json` 裡沒有 deepseek 條目，
只有 anthropic／lmstudio／openai-codex，所以確定是 pi 自己從環境變數讀的）。
**pi 會自動吃，不需要 `--api-key`**——所以 key 的值沒有進到任何檔案、log 或測試。
唯一的要求：**跑 loop 的那個行程要有 `DEEPSEEK_API_KEY`**。
（備案 lmstudio 也是 `ready`，沒用上。）

## 驗收證據（隊長在 worktree 根目錄親自重跑，不是採信隊員回報）

**1. build ＋ ctest 全綠**：6 個 ctest 全過；`aos_agent_tests` 內 15 個 Catch2 case
（原本 8 個 ＋ 新增 7 個）。新測試全部離線，用 PATH 插銷 `AOS_PI_BIN` 指向假 pi 腳本。

**2/3. `engine.json` 與預設**

```text
$ aos agent init W --name bob --engine pi
{"engine":"pi","model":"deepseek-v4-flash","provider":"deepseek",
 "session_id":"ee8b76ff-5118-41d5-beb2-fefd6b4b341c"}
$ aos agent init W --name plain          # 不帶 --engine
{"engine":"lmstudio"}
```

**4/5. 真 pi 端到端（`aos run`，不是替身）**

```text
$ aos agent say W bob "在這個資料夾建一個 hello.txt 內容是 hi"
$ aos run W --step 1
## turn 1 assistant
已完成。建立了 `hello.txt`，內容是 `hi`。
> pi 用了工具：write hello.txt
$ cat W/hello.txt  →  hi

$ aos agent say W bob "剛才建了什麼檔？"      # session 記憶
## turn 2 assistant
剛才建了 `hello.txt`，內容是 `hi`。

$ aos agent say W bob "把 hello.txt 改成 hi again"
turn 3: 2 insts, 2119 ms
## turn 3 assistant
已把 `hello.txt` 的內容改成 `hi again`。
> pi 用了工具：edit hello.txt
$ cat W/hello.txt  →  hi again
```

同一個世界裡的 lmstudio agent `plain` 全程不受影響（`status: idle`）。
`find W` 確認 pi **沒有動過 `.aos/`**（`--no-context-files` ＋ system prompt 明講）。

## 關鍵事實（細節在 `pi-cpu.md`）

- `pi -p --mode json` 的 stdout 是 **JSONL**，不是單一 JSON。**最終回覆＝最後一個
  `turn_end` 事件的 `message.content` 裡所有 `type=="text"` 區塊接起來**；
  工具看 `tool_execution_start`。一次呼叫 1～4 秒，exit 0。
- **prompt 走 stdin**（隊長裁決）：實測連以 `--` 開頭的 prompt 都不會被誤判成選項。
- 第一次用某個 session id 時 stderr 印 `creating a new session with that id` 是正常的。

## 隊長裁決（4 條）

1. **prompt 走 stdin 不走 argv**——dash 安全，已實測。
2. **pi 分支整條放新檔 `engine_pi.cpp`**，`step.cpp` 只插 6 行早退分支
   （`read_engine` → `kind=="pi"` → `step_pi` → `return 0`）。這是為了讓隊 C 在
   `core/agent` 上的改動 rebase 時衝突最小。
3. **`engine.json` 不存在＝ lmstudio**，舊世界不用遷移、行為零變化。
4. **`history.json` 仍鏡射 user／assistant 文字**，讓 `listen`／`state` 保持可用，
   但真正的記憶在 pi 的 session——兩份真相這件事已寫進文件的取捨那節。

## 誠實補充：這條路最大的取捨

使用者的定義是「仍以 inst 為核心，只是有個 llm 程式可以被指令呼叫」。
engine=pi 時 `step` 這條 inst 仍然成立，**但 pi 的工具動作不是 inst**——
它在 pi 行程內部做完才吐結果，不會出現在 `batch/<turn>/`，
也不受 `tools.json` 白名單限制。**世界裡因此有一段 aos 看不見的行為。**
這是 pi 當 CPU 跟 `aos llm` 當 CPU 最根本的差別，不是實作偷懶，
需要使用者自己決定能不能接受。`pi-cpu.md` 最後一節有完整對照表與五條不順手處。

## 團隊

- **codex gpt-5.6-sol ×2 條線**：① engine 抽象＋pi 後端＋7 個測試；② 三份文件。兩線平行、檔案不重疊。
- **隊長**：先自己用 shell 把 pi 跑通（provider／JSONL 形狀／session 記憶／stdin／`.aos` 互撞
  四項實測），把結果寫成規格塞進任務書，讓隊員不必重跑；之後審 diff、重跑 build＋ctest、
  跑真 pi 的端到端驗收、commit。沒有親自寫實作。
