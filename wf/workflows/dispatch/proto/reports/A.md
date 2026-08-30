# 隊 A 回報：最小「機器」——core/exec → core/wire → core/loop

← [交接書 proto-A-machine](../proto-A-machine.md)｜[PROTOCOL](../PROTOCOL.md)｜[dispatch](../../README.md)

**終局 STATUS：`DONE`**（6 條驗收全部有證據，`ctest` 7/7 全綠）

## 做了什麼

三個新的核心小專案，按層切開、單向相依，舊的 `core/inst` 原地不動：

| 小專案 | 子命令 | 職責 |
|---|---|---|
| `core/exec` | （純函式庫） | 唯一碰 `fork`/`exec`/`waitpid` 的層。`start_all()` 一次把整批 fork 出去、`wait_all()` 統一等完 |
| `core/wire` | （純函式庫） | 唯一懂協定 JSON 形狀的層。§2／§3／§4 三種 struct ↔ JSON 文字 |
| `core/loop` | `aos run`／`aos deliver` | 資料夾的回合機：匯聚 → 並行執行 → 落檔 → 更新 `state.json` → `turn` +1 |

`loop → exec`、`loop → wire`；`exec` 與 `wire` 互不相識，也不知道 `loop` 存在。共 2,059 行，**單檔最大 191 行**（門檻 300）。

### 兩個關鍵形狀

- **`exec` 的兩階段 API 是刻意的**：上層要在「已 fork、還沒等完」的時間點把 pid 寫進 `state.json`——那是外面的人看得到「回合正在跑」的唯一證據。合成一個 `run_batch()` 就沒有這個接縫了。
- **stdout/stderr 走 `mkstemp` 暫存檔而不是 pipe**：一次 fork 一整批的時候 pipe 緩衝會互相卡死，避開它就不必為最小原型寫一個 poll 迴圈。

## 6 條驗收的證據

| # | 驗收 | 證據 |
|---|---|---|
| 1 | 根目錄建置＋ctest 全綠 | `100% tests passed out of 7`：舊的 `aos_inst_tests`／`aos_inst_capi_tests`／`aos_tooljson_tests`／`aos_llms_tests` continue 綠，新增 `aos_exec_tests`（7 案）／`aos_wire_tests`（5 案）／`aos_loop_tests`（6 案） |
| 2 | `aos --help` 列出 `run` 與 `deliver` | `run  推進一個資料夾 N 回合`、`deliver  把一條指令原子投遞進 inbox` 兩列都在 |
| 3 | 三條並行、總時長 < 2 秒 | `turn 1: 3 insts, 1015 ms`，外部量測 `elapsed_ms=1017`（三條各 `sleep 1`，序列跑會是 3 秒）。`batch/1/out/` 三個結果，stdout 皆含 `hi` |
| 4 | 3 個 idle 回合 | `turn 2: idle`／`turn 3: idle`／`turn 4: idle`；`.aos/turn` = `5`、`state.json.phase` = `idle`；`batch/2` **不存在**（idle 回合不建 batch） |
| 5 | 執行期間 `state.json` 有 pid | 跑 `sh -c 'sleep 2'` 期間另一個 shell 讀到 `"phase": "running"`、`running[0].pid = 1997709`、`"status": "running"`；跑完後同一筆變 `"status": "done"`、`"exit": 0` |
| 6 | 自我投遞 | 投 `sh -c 'aos deliver "$AOS_FOLDER" -- echo again'`，第一回合 `exit 0` 後 inbox 出現 `d-1788076726413-1999633-0.json`，第二回合 `turn 2: 1 insts` 真的執行到它，`out/` 有 `again` |

驗收 3–6 的煙霧腳本在 `/tmp/claude-1000/.../scratchpad/team-a/smoke.sh`（暫存物，不進 repo）。

## commit

| hash | 內容 |
|---|---|
| `fecbdac` | `core: exec / wire / loop 三個小專案——按層切乾淨的最小機器` |

51 個檔：三個小專案（含各自 README 與 tests）、`core/CMakeLists.txt` 三行 `add_subdirectory`、`core/README.md` 三列、`wf/workflows/common/code-map.md` 的登記。
**`git add` 全程只加明確路徑**，使用者未提交的 `wf/` 改動（30+ 個檔）原封不動。**未 push。**

## 隊形與分工

| 誰 | 做了什麼 |
|---|---|
| Fable 規劃者 ×1 | 把 PROTOCOL 落成三份公開標頭草稿與檔案切分，寫進 `core/<name>/README.md`。**三份草稿的公開簽名最後都原封不動被實作採用** |
| codex gpt-5.6-sol #1 | `core/exec` ＋ `core/wire`，自己跑到 6/6 全綠，另做了外部 `find_package(aos)` 消費測試 |
| codex gpt-5.6-sol #2 | `core/loop`（對著標頭草稿寫，**全程沒建置**）。整合後**第一次編譯就過**，零修正 |
| codex gpt-5.6-sol #3 | `code-map.md` 與 `core/README.md` 的登記 |
| 隊長（我） | 標頭草稿定案、寫四份子任務書、三個 `add_subdirectory` 登記、審 diff、跑 build/ctest/smoke、修 `loop.hpp` 的註解、commit |

Sonnet 兩位沒有派上——調度者中途把人力調向 codex，測試與文檔都由 codex 一併做掉了。

## 隊長裁決（設計小選擇，都選了最簡單的一條）

1. **`exec` 抓 stdout/stderr 用 `mkstemp` 暫存檔，不用 pipe。** 一次 fork 一整批的時候 pipe 緩衝滿了就得寫 poll 迴圈；暫存檔沒這問題。代價是輸出整檔讀進記憶體、沒有上限。
2. **`exec` 做成兩階段 `start_all()` / `wait_all()`，`Running` 是欄位攤開的普通 struct**（不做 pimpl／opaque handle）。理由見上面「兩個關鍵形狀」。
3. **逾時直接 `SIGKILL` 整個 process group，不做舊碼的 SIGTERM → 2 秒寬限兩段式。** 協定 §3 只認 `signal: 9`。
4. **`wire` 的公開 API 一律 string 進 string 出**，`nlohmann::json` 不出現在公開標頭。這樣不必用 `PUBLIC_DEPS`／`PUBLIC_PACKAGES`，外部消費者的 `find_package(aos)` 也不會被要求先找得到 nlohmann。
5. **JSON 鍵維持協定原名，C++ 欄位改名避開巨集**：`stdin`→`stdin_data`、`stdout`→`stdout_text`、`stderr`→`stderr_text`。
6. **`aos deliver` 也呼叫 `ensure_layout`。** 協定只說 `run`／`agent init` 會建 `.aos/`，但驗收 3 是在空資料夾先 deliver 再 run。
7. **argv 形式投遞的 id 自動產生 `d-<epoch_ms>-<pid>-<seq>`。** 協定只定義了「檔名去掉 `.json`」這個預設，沒說 argv 形式的 id 怎麼來。
8. **`AOS_FOLDER`／`AOS_TURN` 覆蓋指令自帶的同名 env key**（而不是讓指令蓋掉它們）。
9. **inbox 裡解析失敗的檔案照搬進 `insts/`（留現場證據）但跳過不執行**，只在 stderr 留一行、`out/` 沒有對應檔。
10. **code map 不另立 `code-map/exec.md`／`wire.md`／`loop.md` 三份分冊。** 交接書的禁區只開放 `wf/workflows/common/code-map.md` 一個檔，所以三個小專案的逐檔表格留在它們自己的 `core/<name>/README.md`，`code-map.md` 只加路由與「常查的東西在哪」的條目並註明不另立分冊。**這條之後若要改回慣例（每個小專案一冊），是很便宜的搬移。**
11. **只開一個 commit 而不是分多個。** `core/CMakeLists.txt` 的三行 `add_subdirectory` 綁在同一個 hunk 裡，硬拆要走互動式 `git add -p`（本環境不支援），而且拆開後中間狀態建不起來。

## 已知不管（三個小專案的 README 各有一節，這裡只列最重要的）

- **沒有鎖**：兩個 `aos run` 同時推同一個資料夾會互搶 inbox、互蓋 `state.json`。
- **沒有崩潰恢復**：`run` 在 `wait_all` 途中被殺，`insts/` 已搬走但 `out/` 沒寫、`turn` 沒加，下次啟動不會補跑。
- **不 `fsync`**：`rename` 是原子的，但斷電後檔案內容可能是空的。
- **輸出無上限**：子行程印 GB 級 stdout 會吃光 RAM。
- **孫行程若自己 `setpgid` 脫離群組，逾時殺不到**。

## 給隊 B 的一句話

驗收 6 的自我投遞路徑（隊 B 靠它活）**已經通了**：指令拿得到 `AOS_FOLDER`（絕對路徑）與 `AOS_TURN`，`aos deliver "$AOS_FOLDER" -- ...` 投進去的東西下一回合會被執行。`agents/<name>/status.json` 的原樣鏡射也通了——寫進去就會出現在 `state.json` 的 `agents` 底下，loop 不解讀內容。
