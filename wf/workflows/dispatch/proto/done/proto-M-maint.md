# 任務：維護線 M——文件補齊、兩支壞掉的 repro、`inbox read` 前綴

> 交接書是唯一契約。現況：[docs/usage.md](../../../../docs/usage.md)、[docs/overview.md](../../../../docs/overview.md) 只寫到五個小專案；`core/tick`／`core/tool` 與隊 Y 的新指令沒進文件。[reports/Y.md](reports/Y.md) 末段指出 `trial/repro/L2-02.sh` 的第二個斷言預設了錯的實作、`L2-14.sh` 的 `wait` 用法讓判斷走不到；`aos inbox read` 只吃完整 id。

## 唯一目標

三件事，都在 **main** 做：
1. **文件**：`docs/usage.md` 與 `docs/overview.md` 補上 `core/tick`（`aos heartbeat init`／`aos tick`／`aos routine`／`aos schedule`）、`core/tool`（`aos tool add/ls/rm`、`--metainfo`、`aos contact add/ls/rm/status`）、以及隊 Y 的 `aos chat`、`aos run --daemon`／`aos stop`、`aos state` 的 `unread`／`last_error`、`aos inbox ls/read`。以各小專案 README 與 `--help` 輸出為準，**不發明行為**；每條指令附一個可貼的例子。
2. **repro**：把 `trial/repro/L2-02.sh` 第二個斷言改成驗「system prompt 含通訊錄」（對照 `core/agent/tests/test_agent_tools.cpp` 的做法，或直接跑一回合看 request 檔）；修 `L2-14.sh` 的 `wait` 用法讓判斷式走得到。兩支修完要 **PASS**，且其餘 26 支不從 PASS 變 FAIL。這是唯一允許改 L1／L2 repro 斷言的一次（隊 Y 建議、調度者批准）。
3. **`aos inbox read <id>`**：支援唯一前綴（歧義時列候選、exit 1）；空信箱／錯 id 回 exit 1。補 ctest。

## 團隊（你是 Opus 隊長）

codex ×2（`codex exec -m gpt-5.6-sol -C /home/lorkhan/repo/simple_tools/aos --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`；任務書寫「最終回覆即成品，另寫到 -o」）：一條文件、一條 repro＋inbox read。**工作量押給 codex**；你審 diff、跑 ctest 與全部 repro、commit。先 `cmake --build --preset default` 確認 main 的 build 是新的。

## 硬性限制

- 可改：`docs/usage.md`、`docs/overview.md`、`core/agent/`（只為 inbox read）、`trial/repro/L2-02.sh`、`trial/repro/L2-14.sh`、對應 code map。**禁區**：其餘 `core/*`、`app/`、`reference/`、`wf/` 其他檔、`ideas/`、`trial/findings-*.csv`。
- `git add` 只加明確路徑、絕不 `-A`（主工作樹有使用者未提交的 wf 改動，不要碰）；不 push；不 load／unload LM Studio；不開 GUI；不用 wf-lint；DeepSeek key 只從環境變數；測試用暫時 HOME／AOS_HOME；收工前 `pgrep -f "aos run"` 必須為空。
- 隊 L3 同時在 worktree 只寫 `trial/findings-L3.csv`、`repro/L3-*.sh`、`sandbox/`——你不碰那些。

## 驗收（就這 3 條）

1. `docs/usage.md` 每個子命令（`run/deliver/llm/agent/say/listen/talk/state/chat/inbox/stop/heartbeat/tick/routine/schedule/tool/contact`）都有一節＋一個例子；`docs/overview.md` 小專案表含 tick／tool。
2. `for f in wf/workflows/dispatch/trial/repro/*.sh; do bash $f; done` 28/28 PASS（附輸出）。
3. ctest 全綠，新增 inbox read 前綴案例 ≥ 2。

## 回報

最後一則訊息＝三條驗收的證據（≤ 20 行）＋commit hash＋STATUS。
