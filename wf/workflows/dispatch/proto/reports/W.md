# 隊 W 回報——補兩個已裁決的缺口（step 取槽、使用者住 `~`）

← [交接書 proto-W-gaps](../proto-W-gaps.md)｜[隊 V 回報](V.md)｜[ideas/tools/contacts](../../../ideas/tools/contacts.md)｜[PROTOCOL](../PROTOCOL.md)

**分支**：`main`（直接在主 working tree 做，未 push）
**隊形**：Opus 隊長＋codex gpt-5.6-sol ×3（**循序**，因為三條線都碰 `core/agent/`；
隊長寫任務書、審 diff、跑建置與驗收、commit，不親自寫實作）

## 做了什麼

三個 commit，一條線：step 取槽 → 使用者是一格 agent → 端到端 smoke。

| commit | 內容 |
|---|---|
| `93484d4` | `step` 走 lmstudio 也取槽；`engine.json` 帶 `priority`；等不到 exit 75 |
| `1d0e677` | say 訊息帶 `from`；`~` 的扁平信箱與 `say --to ~`／`listen`；通訊錄天然一格 `~` |
| `fdb590f` | `core/agent/tests/smoke_user.sh`：四條驗收的可重跑證據 |

### 一、step 的 lmstudio 那條取槽

隊 V 只在 `aos llm` 的 CLI 層取槽，agent 內嵌呼叫 `aos::llm::complete()` 那條沒取——
上限對 agent 不成立。現在照 `engine_pi.cpp` 的形狀補上：

- **時機**：pending 工具結果照舊先收，接著把 `say/` 掃成清單（**只掃不吃**），
  `will_call = received_tools || !messages.empty()` 為真才 `acquire()`；
  取到槽之後才進「讀檔 → history → remove」的迴圈。逾時退回時 `say/*.md` 原封不動。
- **CPU 名**：`engine.json` 的 `provider` → `AOS_LLM_ENGINE` → `lmstudio`。
- **優先度**：`engine.json` 的 `priority` → `AOS_LLM_PRIORITY` → 0，
  由 `detail::llm_priority()` 統一，pi 那條改用同一份。
  `aos agent init --priority N` 把它寫進 `engine.json`（0 不寫檔，維持既有檔案外觀）。
- **退回語意**：`step()` 回傳 75、status 寫 `waiting-llm`；`aos agent step` 對 75
  在 stderr 只印一行 `waiting-llm`。pi 那條也一併從「回 0」統一成回 75。

### 二、使用者也是一格 agent，住 `~`

- **say 帶 `from`**：訊息檔變成 `from: <寄件世界絕對路徑>\n\n<文字>`；
  格式只有一份（`detail::message_body()`）。`from` 空＝維持原樣（函式庫呼叫者向後相容）。
  寄件人由 `say_from()` 算：`AOS_FOLDER` → 從 cwd 往上找世界 → 都不在就是 `~`。
- **`~` 的版面是扁平的**：`~/.aos/say/` 與 `~/.aos/log.md`，沒有 persona／history／status／engine
  ——使用者不是真的 agent，不要幫他建那些。新檔 `core/agent/src/user.cpp` 收全部：
  `user_folder()`／`is_user_folder()`／`say_from()`／`ensure_user_layout()`／
  `say_to_user()`／`drain_user_say()`／`read_user_log()`。
- **`aos say --to ~ …`** 投到 `~/.aos/say/`；在 `~` 底下 `aos say` 是寫給自己的便條；
  在 `~` 底下 `aos listen` 先把 `say/` 搬進 `log.md` 再印（跟讀模式每 200 ms 再搬一次）。
- **通訊錄天然一格 `~`**：`aos::tool::user_contact()` 合成 `{~, $HOME}`，
  `find_contact()` 與 `aos contact ls` 注入它，`ls` 排第一列。
  `read_contacts()`／`write_contacts()`／`add_contact()` **完全沒動**——所以 `~` 永遠不會落進
  `contacts.json`，也可以被檔案裡的同名條目覆寫。

## 4 條驗收的證據

| # | 驗收 | 證據 |
|---|---|---|
| 1 | build＋ctest 全綠 | `cmake --build --preset default -j8` 無 warning；`ctest --preset default` **8/8 全過**（隊長在三個 commit 後各跑一次） |
| 2 | 兩隻 agent 同回合 step → 一隻成功、一隻 exit 75／`waiting-llm` | `smoke_user.sh` [1/3]：`AOS_HOME` 暫存、`cpus.json` 設 `lmstudio {max_inflight:1, wait_ms:100}`、本機假端點睡 2 秒。輸出 `w1: exit=0 status=idle say=0` / `w2: exit=75 status=waiting-llm say=1`，敗方 stderr **剛好一行** `waiting-llm`，且**它的 `say/` 訊息還在**（`say=1`）。另有單元測試 `agent step keeps say when the lmstudio slot is unavailable` |
| 3 | `from` 標頭、`say --to ~`、在 `~` `listen` | `smoke_user.sh` [2/3]：`W/.aos/agents/w/say/*.md` 第一行是 `from: <W 絕對路徑>`；`aos say --to '~' "回報完成"` 後 `<HOME>/.aos/say/` 恰一封、含同一個 `from`；`cd <HOME> && aos listen --once` 印出 `回報完成` |
| 4 | `aos contact ls` 第一列是 `~` | `smoke_user.sh` [3/3]：空通訊錄時第一列 `~ <HOME> 使用者（頂層信箱）`；`contact add bob` 之後 `~` 仍在第一列、`bob` 在後，且 `contacts.json` 文字裡沒有 `"~"` |

**驗收腳本**：`bash core/agent/tests/smoke_user.sh`（可重跑、離線、只打 127.0.0.1 的假端點，
全程 `HOME` 與 `AOS_HOME` 指 `mktemp -d`，跑完自清）。隊長獨立跑過一次，
並另外手動走過一遍驗收 3／4；跑完確認 `~/.aos/` **不存在**（真的沒碰到使用者的家）。

## 隊長裁決

| # | 裁決 | 理由 |
|---|---|---|
| 1 | lmstudio 取槽放在「掃完 `say/` 但還沒吃」之間，而不是 step 一開頭 | 一開頭取＝閒置回合也搶槽，會餓死別人；掃完才取＝沒事做就不佔。工具結果那段不呼叫 LLM，照舊先收 |
| 2 | 取槽失敗時已收下的**工具結果**不回滾 | 收完 `history.back().role == "tool"`，下回合 `received_tools` 自然還是 true，會重試；只有 `say/` 訊息一旦 remove 就沒了，所以只保護它 |
| 3 | `step()` 回 **75**（不是回 0），pi 那條一併改 | 交接書驗收 2 明寫 exit 75；也對齊 `slot.hpp` 寫死的呼叫者約定（stderr 一行 `waiting-llm`、exit 75）。隊 V 的 pi 回 0 是那時沒人要求 exit 碼 |
| 4 | 優先度 = `engine.json` 的 `priority` **非 0 就用它**，否則 `AOS_LLM_PRIORITY` | 交接書要 `engine.json.priority`，隊 V 已經放了環境變數那條；「明確寫 0 又想被環境變數覆蓋」是邊緣，跳過（0 也不寫檔） |
| 5 | say 的 `from` 標頭**連著文字一起進 agent 的 history**，step 不解析 | 最小原型：agent 本來就該看得到誰寄的；step.cpp 這輪已被另一條線改過，不想再動它 |
| 6 | `~` 的信箱是**扁平**的 `~/.aos/say/`＋`log.md`，不是 `agents/<name>/` | 交接書驗收 3 明寫 `<tmp>/.aos/say/`。使用者不是真 agent，沒有 persona／history／status／engine 可言 |
| 7 | `~` 沒有 loop 在跑，所以**由 `aos listen` 自己把 `say/` 搬進 `log.md`** | 不然信永遠停在投遞匣。搬過就不重複，跟 agent 的 listen 語意一致 |
| 8 | `~` 這一格**只在 `find_contact()` 與 `contact ls` 合成**，不碰 `read_contacts()` | 若在 read 層合成，`add_contact()` 的「讀→改→寫」會把 `~` 寫死進 `contacts.json`——那就變成過期的絕對路徑 |
| 9 | 在 `~` 底下 `aos say <文字>`（沒有 `--to`）＝寫給自己的便條 | 否則 `resolve_name()` 會因為 `~` 沒有 agent 而爆掉，難看又沒用 |
| 10 | smoke 不掛進 ctest | 會起 HTTP server、會睡秒級；比照隊 V 的 `smoke_slots.sh` 維持手動腳本 |

## 沒做、留給下一棒

- **`aos state`／`aos talk` 在 `~` 底下**沒處理（會走 `resolve_name()` 那條而報錯）。邊緣，跳過。
- **`aos contact rm ~`** 回「沒有聯絡人 ~」（合成的刪不掉）；`aos contact add ~ …` 會落檔覆寫，
  這是刻意留的覆寫途徑。
- **`~` 的信沒有回合機**：使用者的信箱只有 `listen` 會搬，沒有 loop、沒有 status、沒有回信路徑
  （agent 想「回信」就是再 `aos say --to ~`）。
- **`wf/workflows/ideas/tools/contacts.md` 末段那句「尚未實作：say 的 `from`、`~/.aos/` 的初始化、
  `aos say --to ~`」現在已經做完了**，但那個檔在本輪禁區裡，沒有改。請調度者順手劃掉。
- `HOME` 沒設時 `user_folder()` 直接 throw（`user_contact()` 則回空 folder 並被當作沒這一格）；
  沒有走 passwd 的 fallback。

## 收線狀態

三個 commit 都在 `main`，**未 push**。`git add` 全程只加明確路徑，
使用者未提交的 `wf/`／`docs/`／`AGENTS.md` 改動一律沒碰。
