# 任務：刪舊三個小專案、`.aos/every/` 進 loop、一個資料夾一隻 agent（`aos say` 直接用）

> 交接書是唯一契約。協定 [PROTOCOL](PROTOCOL.md)（本任務會**修改**它，改法寫在下面）。前兩隊的報告在 [reports](reports/)。

## 背景與唯一目標

使用者 2026-08-30 三個裁決：(1) 採用 [self-delivery-in-loop](../../ideas/self-delivery-in-loop.md) 方案 A；(3) 舊 `core/inst`／`core/llms`／`core/tooljson` **現在刪**；(4) **一個 agent 佔一個資料夾**，待在 bob 的資料夾裡直接 `aos say ...` 就好。
**唯一目標**：main 上 ctest 全綠，且在一個資料夾裡 `aos agent init` → 另一視窗 `aos run --step 0` → `aos say "..."`／`aos listen` 能對話，agent 不再自我投遞而是靠 `.aos/every/`。

## 團隊（你是 Opus 隊長）

工作量押給 codex（`codex exec -m gpt-5.6-sol -C /home/lorkhan/repo/simple_tools/aos --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`，sol／terra／luna 皆可，最多 4 條、量力而為）。建議三條並行：① 刪除線、② every 線（core/loop）、③ 頂層指令線（core/agent）。②③ 都會碰 `core/agent/src/init.cpp`（init 改寫 every 檔）——把那個檔交給 ③，② 只做 loop 端並在任務書寫清 every 檔格式。Sonnet／Fable 可用可不用。隊長寫任務書、審 diff、跑 ctest、commit；不親自寫實作。

## 工作

1. **刪除**：`git rm -r core/inst core/llms core/tooljson`；`core/CMakeLists.txt` 去掉三行；`core/README.md`、`wf/workflows/common/code-map.md`、`docs/subprojects.md` 裡的對應條目刪掉或標「已刪 2026-08-30」；`docs/README.md`、`AGENTS.md` 開頭那句「目前只有一個核心小專案 `core/inst/`」改成指向五個新小專案。**其他 docs／wf 文件不重寫**（歷史文件提到 inst 沒關係）。確認 vcpkg.json 若有只給 llms 用的相依（curl 現在 `core/llm` 也用，留著）不必動。
2. **`.aos/every/`（方案 A）**：loop 每回合匯聚時，除了搬 `inbox/*.json`，也把 `every/*.json` **複製**成本回合指令（id＝`<stem>-<turn>`，檔案留在 every/ 不動）。PROTOCOL §1 加一列、§5 加一句。`aos deliver --every` 可選，不強求。
3. **agent 改用 every**：`aos agent init` 寫 `.aos/every/agent-<name>.json`（argv `["aos","agent","step"]`，見下一條的 cwd 語意）而不投 inbox；`step` **不再自我投遞**；工具呼叫仍走 inbox（三回合往返不變）。`status.json` 照舊。
4. **一個資料夾一隻 agent、cwd 即世界**：
   - 所有子命令的 `<folder>` 參數改為**可選**，預設＝從 cwd 往上找最近含 `.aos/` 的目錄（找不到就用 cwd）。`aos run`、`aos deliver`、`aos agent *` 都適用。
   - `aos agent init [--name N]`：N 預設＝資料夾 basename；同資料夾已有 agent 就報錯退出（一個資料夾一隻）。
   - 新增**頂層**子命令 `aos say <text...>`、`aos listen`、`aos talk`、`aos state`（登記在 `core/agent` 的 CMake），agent＝`.aos/agents/` 裡唯一那隻；`aos agent say/...` 舊形式可留作別名或直接刪，你裁。
   - step 在 loop 裡跑時 cwd＝`<folder>`（協定 §2），所以 argv 不必帶路徑；保險起見 step 也認 `AOS_FOLDER`。
5. 更新 `core/loop/README.md`、`core/agent/README.md`、code map、PROTOCOL；測試跟著改（every 至少一案、cwd 解析至少一案、init 重複報錯一案）。
6. commit 到 main（可分多個）。

## 硬性限制

- **禁區**：`reference/`（不刪不改，使用者另裁）、`app/`、`wf/` 除 code-map、本資料夾、`wf/workflows/ideas/self-delivery-in-loop.md`（可加一行「已採用 A，2026-08-30」）之外不碰。
- **`git add` 只加明確路徑**；`git rm` 只針對上面點名的三個目錄。**不 push。**
- 不取鎖、不開 GUI、不 load／unload LM Studio 模型（`qwen/qwen3.5-9b` 已可 JIT）。
- 邊緣狀況照舊跳過；小裁決記本檔尾「隊長裁決」。

## 交付

| 產物 | 路徑 |
|---|---|
| 刪除與登記 | `core/`、`docs/subprojects.md`、`docs/README.md`、`AGENTS.md` 一句 |
| every | `core/loop/`、`PROTOCOL.md` |
| 頂層指令與 cwd | `core/agent/`、`core/loop/` |
| 回報 | `wf/workflows/dispatch/proto/reports/C.md` |

## 驗收（就這 6 條）

1. `cmake --preset default && cmake --build --preset default && ctest --preset default` 全綠；`ls core` 只有 `exec wire loop llm agent`（＋CMakeLists、README）。
2. `aos --help` 沒有 `exec`／`init`，有 `run deliver llm agent say listen talk state`。
3. 空資料夾 `W` 內：`aos agent init`（不帶參數）→ `.aos/every/agent-W.json` 存在、inbox 為空、agent 名＝資料夾名。
4. `W` 內 `aos run --step 3`：三回合每回合 1 條 step 指令（來自 every），inbox 始終沒有 step 檔；`state.json.agents.<name>` 有值。
5. `W` 內 `aos say "你叫什麼名字"` → `aos run --step 1` → `aos listen`（或 log.md）有 LLM 回覆；`aos state` 印 idle。
6. `W/sub/` 內執行 `aos state` 也找得到（往上找 `.aos`）；`W` 內再跑一次 `aos agent init` 報錯、退出碼非 0。

## 回報

最後一則訊息＝ `reports/C.md` 摘要（≤ 30 行）＋終局 STATUS。

## 隊長裁決

（隊長追加）

1. **三條線循序跑，不並行**——共用同一個 working tree 與 `build/`，①刪 `core/inst` 會炸掉正在建置的 ②。
2. **`find_folder`／`current_folder` 放 `core/loop` 公開 API**，`core/agent` 私有相依 `aos::loop`；`.aos/` 版面的知識只留一份。
3. **`aos deliver` 靠「第一個參數是不是存在的目錄」判斷 folder**；`aos run` 靠「是不是 `--` 開頭」。
4. **舊形式 `aos agent say|listen|talk|state <folder> <name>` 全部保留、參數不改可選**（`say` 的 `<text...>` 會歧義）；要省參數就用頂層 `aos say/listen/talk/state`。
5. **`every/` 檔自帶的 `id` 一律覆蓋成 `<stem>-<turn>`**——不覆蓋每回合都撞名，工具往返讀不回結果。
6. **`aos deliver --every` 沒做**（交接書列為可選）。
7. **`fake_loop.py` 留著**（讓 agent 測試不依賴 PATH 上的 `aos`），跟著加了 every 支援。
8. **`code-map/inst.md`／`tooljson.md`／`llms.md` 三冊不刪**，只在路由表註明「已刪 2026-08-30，本冊為歷史存檔」——別的歷史文件連著它們。
9. **`docs/` 只改 `README.md` 與 `subprojects.md`**，參考範本從 `core/inst/` 換成 `core/llm/`。
10. **禁區裡的 22 條死連結刻意不修**（`wf/` 5 條、`docs/` 17 條，全指向已刪的 `core/inst/docs/`），詳見 [reports/C.md](reports/C.md) 的「已知不管」。
