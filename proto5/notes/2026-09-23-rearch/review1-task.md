你可以開自己的 subagent 平行做事（multi_agent 已開）。全程唯讀，不要改任何檔案。用繁體中文回報。

# 任務：審查兩份新規範草稿

repo 是 aos（`/home/guanyu/projs/aos`），今天 2026-09-23 使用者正在重新架構 proto5 的 daemon→kernel→cpu 這條線。
兩份新草稿：

- `proto5/spec/cpu.md`——「cpu 範式」與 exec cpu：一個資料夾＋一個主人行程、info／state／requests／responses、JSON-RPC 2.0 信封走檔案與 pipe、只有一種被排程的 cpu（exec cpu，一則 request＝跑一份 inst 一次）、停下來的三級、開機對帳。
- `proto5/spec/kernel.md`——kernel 不是長命行程，是一格一格的 `aos-kernel tick`，每格是一則 aos-exec request 跑在專用 exec cpu 上，開頭先把下一格放進隊裡（尾遞迴）；syscall＝往 K/requests/ 放 JSON-RPC；派工＝往各 cpu 的 requests/ 放 aos-exec、從 responses/ 收；跟 daemon 也走資料夾。

## 背景（要讀）

- 底層規範不變：`proto5/spec/directives.md`（指示詞）、`proto5/spec/inst-posix.md`（inst.json 格式）、`proto5/spec/aos-exec.md`。
- **舊版**（將被這兩份取代，拿來對照哪些痛點有沒有真的解掉）：`proto5/spec/run-home.md`、`aos-run.md`、`daemon-home.md`、`aos-daemon.md`、`kernel-home.md`、`aos-kernel.md`、`cpu-queue.md`、`aos-cpu.md`、`llm-cpu.md`、`tool-cpu.md`。
- 舊版程式在 `proto5/lib/`（aos_run.py、aos_daemon.py、aos_kernel.py、aos_cpu.py），舊版的已知問題在 `proto5/backlog/`、`proto5.1/notes/findings.md`、`proto5.1/notes/review-fable.md`。
- 使用者已經拍板的方向（不要質疑這些，是前提）：
  1. 規則一「一個資料夾一個主人」是軟性約定（硬性以後走 FUSE）。
  2. runner 聽命執行不自己迴圈，迴圈在 kernel。
  3. IPC 用 pipe（多機以後再 socket）。
  4. 用 JSON-RPC 2.0。
  5. 所有 request 都是 aos-exec：問模型、跑工具、agent 走一格全是 inst／程式；llm、tool 兩種 cpu 消失，變成程式。專門打 LLM 的 cpu 靠 kernel 開專用池（pool）。
  6. exec cpu 會解 params 裡的指示詞，中心是 cpu 的家。
  7. daemon 那份還沒寫；agent 那份之後才改。

## 要你回答的兩件事

### A. OK 不 OK（正確性、一致性、洞）

- 兩份之間有沒有互相矛盾（名詞、method 名、資料夾名、回音格式、§ 編號引用）。
- 跟 directives.md／inst-posix.md／aos-exec.md 有沒有對不上（例如 params 當 inst 解、timeout_ms 並列、`$ref:""` 指 request 本身、load_obj 的 base）。
- 競態與崩潰窗口：逐一過 cpu.md §6 的寫入順序＋開機對帳三種組合、kernel.md §3 的九步（先接鏈再做事、--seq 守門、重複 boot、cpu 死掉重生、once 的 add 延後回音、rm 正在跑的）、§5.1 溫和停的四個來源。找出「兩步之間崩了會怎樣」還沒被說清楚、或說錯的地方。
- 舊版 backlog／findings／review-fable 列的痛點，哪些新設計解了、哪些沒解、哪些**新引入**。
- 有沒有明顯做不到或跟 Linux 語意不符的假設（link 的 EEXIST、rename 原子性、pipe EOF、process group、訊號在 Python 裡的行為）。

### B. 說明清不清楚（給人讀的品質）

- 假設讀者是使用者本人（懂程式、但不想猜）：哪一段第一次讀會卡住、哪個詞沒解釋、哪個例子跟表格對不上、哪裡要先讀別段才看得懂但沒有指引。
- 兩份各自的「一句話」有沒有真的講到重點。
- 名詞表（cpu.md §0）夠不夠、有沒有多餘的。

## 回報格式

寫成一份 markdown，結構：
1. 總評（三到五行：OK 不 OK、最大的兩三個問題）。
2. A 的發現：一條一個編號 **C-n**（cpu.md）／**K-n**（kernel.md）／**X-n**（兩份之間或跟底層規範），每條寫「在哪（§）／問題／建議怎麼改（一兩句）／嚴重度：擋／要修／可先放」。
3. B 的發現：同樣編號 **R-n**，每條「在哪／哪裡看不懂／建議怎麼寫」。
4. 痛點對照表：舊 backlog／findings／review-fable 的項目 → 解了／沒解／新引入。
5. 不用重講規範內容，不用客套。
