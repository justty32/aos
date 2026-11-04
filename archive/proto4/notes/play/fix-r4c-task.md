# fix-r4c：kernel 側（只改 `proto4-3/`）

r3 試玩清單 #6 的 kernel 那一半、#9（`proto4/notes/play/README.md` 的 r3 表）。執行器那一半（等檔沒到退 **101**）由另一本 fix-r4b 在 `proto4-6/`、`proto4-4/` 做，你這邊只認號碼。

## 共通規矩（三本任務書都一樣）

- 你在 repo `/home/lorkhan/repo/simple_tools/aos`。先讀 `AGENTS.md` 開頭三軸與 `wf/workflows/dev-env.md`，再讀你要改的那個 proto 的 README 與原始碼。**不要讀 `proto4/notes/`** 以外的設計筆記；這本任務書引用的試玩報告在 `proto4/notes/play/2026-09-13-r3-opus.md` 與 `2026-09-13-r3-gptsol.md`，可以看。
- 動手前先跑 baseline 並記下數字：`proto4-3`：`cd proto4-3 && python -m unittest discover -s test`（226）；`proto4-4`：`cd proto4-4 && for t in aos step cpu; do janet test/$t.janet; done`（42／45／12，`janet` 在 `~/.local/bin`）；`proto4-6`：`cd proto4-6 && python -m unittest discover -s test`（71）。做完三邊都要重跑，數字只能變多不能變少。
- **只改任務書點名的資料夾**。另外兩本任務書同時在別的 codex 手上改別的資料夾，你碰了會撞。
- 程式碼與 README 單檔 **不超過 300 行**（`aos_kernel_tick.py` 285、`aos_kernel.py` 286、`aos-step-lua` 275 都在邊上）；要破就把一塊完整功能搬到新檔，行為不變。
- 每個行為變更都要有測試；README／`docs/` 同步改，大白話、繁體中文。
- LLM 真打只准本機 LM Studio（`http://localhost:1234/v1`，模型 `google/gemma-4-e4b`，已載好）；**不要碰 DeepSeek、不要讀任何 `*_API_KEY`**。單元測試用假的 OpenAI server（`proto4-5/test/_fake_openai.py` 已有）。
- **不 commit、不 push、不開 agent。** 最後用 markdown 回報：改了哪些檔、每條怎麼做、三邊測試數字、沒做或做不到的說清楚。

## 要做的

1. **`config.json` 多一個 `wait_exit`（預設 101）與 `bad_after`（預設 10）**（#6）。`aos-kernel-init` 加 `--wait-exit`、`--bad-after` 旗標，寫進 config；舊的 config 沒這兩個 key 時用預設（`KHome.config` 讀出來要補預設）。
2. **看到 `wait_exit` 就標 waiting**（#6）。cpu 上的行程最近一次退出碼等於 `wait_exit` → 在 kernel state 記 `waiting: true`（連續幾次 `wait_runs` 也記），`aos-kernel ls` 的狀態欄印 `waiting`（不是 `running`），並多一欄或在同列尾巴印「等了 N 回合」。退出碼變回別的就清掉。
3. **等的人有人排隊就讓出 cpu**（#6）。cpu 上的行程在 waiting 且佇列裡有別人 → 像 quantum 到了那樣換下去（回佇列，**不進 done、不進 bad**），讓別人跑；佇列空就讓它繼續佔著（反正沒人要）。回到佇列裡的行程 `ls` 也要看得出它上次是在等（狀態欄 `queued (waiting)` 之類）。
4. **連續非零退出進 `bad/`**（#6）。退出碼不是 0、不是 `done_exit`、不是 `wait_exit`、也不是 125 的，連續 `bad_after` 次（同一支 aos-run 內、用現有 `runs_at` 那套算）→ 搬到 `procs/bad/`，原因寫「連續 N 次退 <code>」，cpu 換 idle；`bad_after` 設 0 ＝ 關掉這條、永遠重跑（保留「壞了也活著」的選項）。125 那條（連續 2 次）維持不變。`ls` 的 `bad:` 那行原因要看得出是這條。
5. **`ls` 分開講「找不到 daemon 家」與「daemon 死了」**（#9）。`AOS_DAEMON_HOME` 沒設或那個家不存在／沒 state → 印 `daemon ?（找不到 daemon 的家：AOS_DAEMON_HOME 沒設？）`；有家、有 pid 但不活 → 才印 `daemon dead`。
6. **README 與 `docs/kernel.md`**（#9 ＋ 上面）：範例裡的 `K` 改成絕對路徑（例如 `/tmp/K` 或 `~/aos/K`，不要長在 repo 裡）；指令一律 `./aos-kernel…` 或開頭一句「以下假設你把 proto4-3 加進 PATH」二選一、全篇一致；`aos-kernel-init` 那行加註解「module 要在 init 時就 `--module` 掛，之後補只能手改 `config.json` 的 modules」（順便讓 init 對已存在的家印這句提示，而不是只說「已經有這個資料夾了」）；寫 101／`wait_exit`、`bad_after`、waiting 狀態與讓出 cpu 的規則；`docs/files.md` 的 config 欄位表補上。

## 測試

`proto4-3/test/` 加：假行程退 101 → ls 顯示 waiting；佇列有人時被換下去、佇列空時留著；連續 `bad_after` 次退 3 → 進 bad、原因對；`bad_after: 0` 永遠不進；101／100／125 不算進連續失敗；沒設 `AOS_DAEMON_HOME` 時 ls 的字。舊 config（沒有新 key）照跑。
