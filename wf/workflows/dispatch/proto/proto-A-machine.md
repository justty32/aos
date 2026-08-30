# 任務：做出 aos 的最小「機器」——core/exec → core/wire → core/loop，讓 `aos run` 跑得起來

> 交接書是唯一契約。協定見 [PROTOCOL](PROTOCOL.md)（**以它為準**）。派線規則 [dispatch](../README.md)、隊形 [aos-teams](../aos-teams.md)。

## 背景與唯一目標

使用者要一個能用的最小原型：以 POSIX 執行為底，疊最必要的序列化，再疊最簡易的 loop（含**匯聚**與 **loop state**）。
`main` 上舊的 `core/inst` 把這些揉在一起、且已被使用者裁定「打掉重來」——**這次開新小專案、按層切乾淨**。舊的原地不動。
**唯一目標**：從 repo 根目錄 `cmake --build --preset default && ctest --preset default` 全綠後，使用者能在任一資料夾用 `aos deliver` 投指令、`aos run --step N` 看到它們被匯聚、並行執行、結果落檔、`state.json` 反映現況。

## 團隊（你是 Opus 隊長）

- **Fable 規劃者 ×1**：`Agent(model="fable")`。開工前先讓它花一輪把 PROTOCOL 落成三個小專案的公開標頭草稿（`include/aos/exec.hpp`、`wire.hpp`、`loop.hpp` 的函式簽名）與檔案切分，寫進 `core/<name>/README.md`。**只規劃，不寫實作。**
- **gpt-5.6-sol ×2**：`codex exec -m gpt-5.6-sol -C /home/lorkhan/repo/simple_tools/aos --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`。任務書從 stdin 餵、要自給自足（貼上 PROTOCOL 與標頭草稿）。建議：一位做 `core/exec`＋`core/wire`，一位做 `core/loop`（可先對著標頭草稿寫、等 exec/wire 落地再接）。codex 可自行再派生 codex／terra／luna，不限。**codex 不 commit。**
- **Sonnet ×2**：`Agent(model="sonnet")`。一位寫 ctest（每個小專案 3–6 個案例，用「讓批次自己動手」的手法、不 sleep）；一位補 code map 與 README、跑最後的 smoke（下方驗收 4–6）。
- 隊長自己：寫子任務書、審 diff、跑 ctest、commit。**你不親自寫實作。**

## 工作

1. 讀 [PROTOCOL](PROTOCOL.md)、`core/inst/CMakeLists.txt`（小專案範本）、`wf/workflows/add-subproject.md`、`wf/workflows/common/conventions.md`、`wf/salvage/05-程式碼哪些值得抄.md` §三（setpgid 雙保險、fork 後只做 async-signal-safe）。
2. Fable 出標頭草稿 → 你核一遍 → 派 codex。
3. `core/exec`：`spawn(argv, env, cwd, stdin, timeout_ms) → {exit|signal, stdout, stderr, started/ended}`；回合內並行＝多個 child 同時 fork、統一 wait。抄舊 `exec.cpp`／`spawn_prep.cpp`／`wait.cpp` 可以，但**不帶** `$ref`／`$env`／resolve 那整層。
4. `core/wire`：nlohmann::json ↔ 協定 §2–§4 的三個 struct。就這樣，不多。
5. `core/loop`：`deliver()`、`aggregate()`、`run_turn()`、`write_state()`；CLI `aos run`／`aos deliver`。
6. 每個小專案 `README.md` 一頁；`wf/workflows/common/code-map.md` 加三個小專案的條目（鐵律 3）。
7. commit 到 `main`（可以分多個 commit）。

## 硬性限制

- **禁區**：`core/inst/`、`core/llms/`、`core/tooljson/`、`core/llm/`、`core/agent/`、`reference/`、`app/`、`wf/` 除 `wf/workflows/common/code-map.md` 與本資料夾的「隊長裁決」段之外一律不碰。
- **`git add` 只加明確路徑**（working tree 有使用者未提交的 wf 改動，**絕不** `git add -A`／`git commit -a`）。**不 push。**
- 不取任何鎖、不開 GUI／瀏覽器、不裝系統套件、不 unload／load LM Studio 模型。
- 不做 C ABI、不做 `$` 指示詞、不做 fsync 耐久鏈、不做 `.runi`／崩潰恢復——**邊緣狀況一律跳過**，最多在 README「已知不管」列一行。
- 卡在設計選擇 → 選最簡單的一個、記進本檔尾「隊長裁決」段、繼續。**不要停下來等人。** 只有協定本身要改才回報 BLOCKED。
- 暫存物放 `/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/8f4f80fb-1793-4431-92e8-09478f666f76/scratchpad/team-a/`。

## 交付

| 產物 | 路徑 |
|---|---|
| 三個小專案 | `core/exec/`、`core/wire/`、`core/loop/`（各含 README、tests） |
| 登記 | `core/CMakeLists.txt` 加三行 `add_subdirectory` |
| code map 條目 | `wf/workflows/common/code-map.md` |
| 回報 | `wf/workflows/dispatch/proto/reports/A.md`（做了什麼、驗收逐條證據、commit hash 列表、隊長裁決） |

## 驗收（就這 6 條）

1. 根目錄 `cmake --build --preset default && ctest --preset default` 全綠（舊測試也要繼續綠）。
2. `aos --help` 列出 `run` 與 `deliver`。
3. 在空資料夾 `W`：`aos deliver W -- sh -c 'echo hi; sleep 1'` ×3 後 `aos run W --step 1`，三條**並行**跑（總時長 < 2 秒），`W/.aos/batch/1/out/` 有三個結果、stdout 含 `hi`。
4. `aos run W --step 3 --interval 50` 在空 inbox 下跑完 3 個 idle 回合，`W/.aos/turn` 變成 5，`state.json.phase` 為 `idle`。
5. 執行期間（用 `sh -c 'sleep 2'`）另一個 shell 讀 `state.json`，`running[]` 有那條、`pid` 非空；跑完後 `status` 為 `done`。
6. 投一條 `argv: ["aos","deliver","$AOS_FOLDER","--","echo","again"]`（用 `sh -c` 展開 env）跑一回合後，inbox 出現新投遞、下一回合會執行它——**這是「自我投遞」的基礎路徑**，隊 B 靠它活。

## 回報

最後一則訊息＝ `reports/A.md` 的內容摘要（≤ 30 行）＋終局 STATUS（`DONE`／`BLOCKED`／`FAILED`）。

## 隊長裁決

**完成於 2026-08-30，STATUS `DONE`，commit `fecbdac`。逐條證據與完整裁決列表見 [reports/A.md](reports/A.md)。**

1. **`exec` 抓 stdout/stderr 用 `mkstemp` 暫存檔，不用 pipe**——一次 fork 一整批時 pipe 緩衝會互相卡死，避開它就不必寫 poll 迴圈。
2. **`exec` 做成兩階段 `start_all()` / `wait_all()`**，`Running` 是欄位攤開的普通 struct——上層要在「已 fork、還沒等完」時拿到 pid 寫 `state.json`（驗收 5）。
3. **逾時直接 `SIGKILL` 整個 process group**，不做舊碼的 SIGTERM → 2 秒寬限兩段式（協定 §3 只認 `signal: 9`）。
4. **`wire` 公開 API 一律 string 進 string 出**，nlohmann 不進公開標頭——省掉 `PUBLIC_DEPS`／`PUBLIC_PACKAGES`。
5. **JSON 鍵維持協定原名，C++ 欄位改名避開巨集**（`stdin`→`stdin_data` 等）。
6. **`aos deliver` 也呼叫 `ensure_layout`**——驗收 3 是在空資料夾先 deliver 再 run。
7. **argv 形式投遞的 id 自動產生 `d-<epoch_ms>-<pid>-<seq>`**。
8. **`AOS_FOLDER`／`AOS_TURN` 覆蓋指令自帶的同名 env key。**
9. **inbox 裡解析失敗的檔案照搬進 `insts/` 但跳過不執行**（留現場證據），只在 stderr 留一行。
10. **code map 不另立三份分冊**——禁區只開放 `code-map.md` 一個檔，逐檔表格留在各小專案自己的 `README.md`，`code-map.md` 加路由並註明。**要改回慣例是很便宜的搬移。**
11. **只開一個 commit**——`core/CMakeLists.txt` 的三行 `add_subdirectory` 綁在同一個 hunk，硬拆後中間狀態建不起來。
