# 隊 Y 回報：四項改進落地

← [dispatch](../../README.md)｜交接書 [proto-Y-improve](../done/proto-Y-improve.md)｜設計 [ux-round-1](../../../../../core/agent/docs/ux-round-1.md)｜判準 [usability-target](../../../ideas/usability-target.md)

2026-08-30。Opus 隊長 ＋ Fable 規劃者一輪 ＋ codex（gpt-5.6-sol）四條線，循序執行、隊長逐條審 diff。
分支 `worktree-agent-a1fa1602017a3657c`，已 rebase 到含隊 X 全部 25 條 bug 修正的 main。

## 做了什麼

| 項 | 指令面 | 一句話 |
|---|---|---|
| 1 少打指令 | `aos chat`、`aos run --daemon`、`aos stop` | 空資料夾一個指令 1.7 秒拿到回覆；背景 loop 有 pid 檔可停；投遞即喚醒 |
| 2 狀態可見 | `aos state` | `unread` 現場數、失敗回合 `status=error` 並帶 `last_error`；LLM 失敗不吃訊息 |
| 3 通訊錄 | system prompt、`say` 工具、`aos contact status` | agent 開機就知道隊上有誰、開箱就會投遞、一個指令看全隊 |
| 4 不燒 LLM 的信箱 | `aos inbox ls`／`read`、`aos listen` | 讀自己的信不必先呼叫一次 LLM |

## 五條驗收

| # | 結果 | 證據 |
|---|---|---|
| 1 | **PASS** | rebase 後 build 成功、ctest 8/8；X 的 repro 26/28 PASS（兩條例外見下） |
| 2 | **PASS** | 空資料夾 `aos chat "你叫什麼名字"` → `已建立 agent demo（…，lmstudio）` ＋ `我是 demo。`，1.7 s、exit 0；`aos stop` 後 `pgrep aos run` 空、`run.pid` 已刪 |
| 3 | **PASS** | 說三句不跑回合 → `"status":"pending"`／`"unread":3`；假端點跑一回合 → `"status":"error"`、`last_error` 是連線失敗原文、`say/` 仍有 3 封；換回真端點推 3 回合 → 被回答、`unread` 歸 0 |
| 4 | **PASS** | A 的 step 投出 `["aos","say","--to","B","請告訴我現在的時間"]`（log 可見，工具結果 `ok:true`）；`aos contact status` 印出 `B  B  pending  0  1` |
| 5 | **PASS** | `AOS_LLM_URL=http://localhost:19999/v1` 下 `aos inbox ls`／`aos inbox read` 都正常、exit 0 |

投遞即喚醒另量了一次：daemon `--interval 5000`，從 `aos deliver` 到下一回合開跑 **67 ms**。

## 兩條沒有 PASS 的 repro

**`L2-14`**——隊 X 已在 [reports/X.md](X.md) 判定「沒有任何實作能讓這支腳本 exit 0」（腳本自己的
`wait` 用法讓判斷式走不到），不是我這邊的回歸。

**`L2-02`**——第一個斷言（預設工具要有投遞能力）現在 **PASS**（`say` 在預設工具裡）。
失敗的是第二個斷言：它 `grep -rq "contact"` **agent 自己的資料夾**，也就是預設了「通訊錄會被
複製進 `agents/<name>/`」這種實作。本輪的做法是組 request 時才從 `.aos/contacts.json` 讀進
system prompt，agent 資料夾裡不留副本（少一份會過期的複本）。
規則不准改斷言，所以照隊 X 處理 L2-14 的方式，用等價證據結案：實際問 agent
「你的通訊錄上有誰？」，它答 `~` 與 `w1`——**需求本身是滿足的，壞的是那條腳本的實作假設**。
建議下一棒把該斷言改成驗 system prompt（`core/agent/tests/test_agent_tools.cpp` 已有對應的 ctest）。

## 隊長裁決

設計文件 [ux-round-1](../../../../../core/agent/docs/ux-round-1.md) 末節有六條核稿裁決，這裡只記要點與後續調整：

1. **pid 檔**：先定 `.aos/daemon.pid`，收到調度者的 home-daemon spec 後改回
   `.aos/run.pid`，且**寫 pid 的責任放進 `aos run` 迴圈本身**——任何 `--step 0`（前景或 `--daemon`）
   都寫、都能被 `aos stop` 停；`--daemon` 只負責脫離終端與導 log。本輪不做 `daemon.json`／`aos daemon`。
2. **失敗回合的 status 用 `error`**（不是騙人的 `idle`）。與隊 X 獨立做出同一個判斷，rebase 後採用 X 的版本。
3. **不把 `step.cpp` 中段抽成新檔**。X 同時在改同一個檔，搬走幾十行只會讓 rebase 更難解。
4. 砍掉規劃稿的 `last_ok_at` 與 `aos say --to <絕對路徑>`（後者是 `L2-11`，不在這四項裡）。
5. 砍掉 `refresh_unread`：`say()` 不回頭改 `status.json`，未讀一律由讀的一方**現場數**，少一個競態。
6. **`inbox read` 會消費訊息**（搬進 `read/`，step 就掃不到）。只想看不想消費用 `aos inbox ls`。

## rebase 怎麼解的（跟隊 X 的重疊）

四條線是在 X 落地前的 main 上做的，rebase 時四個 commit 全部撞到。原則是**同一件事採 X 的版本，
只留我這邊獨有的**：

| 檔 | 處置 |
|---|---|
| `agent/src/step.cpp` | 全採 X（X 已做同樣的「先問到答案才動信箱」重排），只補回失敗時多帶一個 `last_error` |
| `agent/src/run.cpp`／`run_top.cpp` | 全採 X 的 `state_text()` 單一實作點，把 `last_error` 加進去；`listen` 用 X 的 `print_unread`，只補「兩邊都空」時的指路與一行 `aos inbox read` 提示 |
| `loop/src/run.cpp` | 全採 X（flock 鎖世界 ＋ SIGINT/SIGTERM 收孫行程），再疊上 `--daemon`、pid 檔、空回合改走 `wait_for_delivery` |
| `tool/src/contact_cli.cpp` | 兩邊的 usage 合併 |

**丟掉的重複工**：我這邊自己寫的訊號處理與「用 pid 檔擋重複啟動」——X 的 `flock` 是更對的做法，
pid 檔在合併後只剩「地址簿」這一個職責（給 `aos stop` 與未來的 home daemon 用）。

## 順手修的兩件事（不在四項裡）

- `core/agent/tests/test_agent_store.cpp` 的 `every` argv 斷言寫死成 `{"aos","agent","step"}`，
  但 X 修 L1-01 之後那裡是絕對路徑——這條測試會隨測試行程的 `PATH` 上有沒有 `aos` 而**時好時壞**
  （照 README 把 `build/bin` 放進 PATH 就 FAIL）。改成只驗形狀。
- `wake.cpp` 的停止旗標在 rebase 後沒有人設（形同虛設，靠 `nanosleep` 被 EINTR 打斷才碰巧正確）。
  接上 X 的 handler，並補 `AOS_API`（跨 `aos_loop`／`aos_loop_cli` 兩個 target）。

## 已知不管

- `aos inbox read` 只吃完整 id，不支援唯一前綴；空信箱時給錯 id 回 0 而不是 1。
- `state.json.agents.<name>` 的 `unread` 是**上一次 step 當下**的快照（PROTOCOL §4 規定那是
  `status.json` 的原樣鏡射，loop 不解析內容）。要即時值就看 `aos state` 或 `aos contact status`，
  兩者都現場數。
- `say` 工具的 `argv[0]` 沿用 X 修 L1-01 的絕對路徑解析；把世界搬到別台機器要重寫 `.aos/tools/say.json`。
- pi 引擎只補了 system prompt 的通訊錄段，`step_pi` 吃訊息的時序本輪沒動。
- 兩條 loop 同時搶一個世界由 `.aos/run.lock` 擋住；`run.pid` 沒有自己的鎖，極窄的競態下可能寫到舊 pid。
