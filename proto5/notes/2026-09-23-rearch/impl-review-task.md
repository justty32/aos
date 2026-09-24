你可以開自己的 subagent 平行做事。這是**唯讀審查**任務：不改任何檔、不跑測試（測試我已跑過：883 條全綠、無殘留行程）。用繁體中文。最後一則訊息就是報告，我會原樣存進 repo。

# 任務：審 proto5 的 cpu／daemon／kernel 實作是否照三份規範

repo `/home/lorkhan/repo/simple_tools/aos`。先讀：
- 規範（真理）：`proto5/spec/cpu.md`、`proto5/spec/kernel.md`、`proto5/spec/daemon.md`；底層 `proto5/spec/aos-exec.md`、`inst-posix.md`。
- 實作：`proto5/lib/aos_home.py`、`aos_client.py`、`aos_exec_cpu.py`、`aos_daemon.py`、`aos_kernel.py`、`aos_exec.py`（只加了 `run_target_full`／`spawn_target`）、`proto5/cli/aos-cpu`／`aos-daemon`／`aos-kernel`。
- 測試：`proto5/lib/test/test_home.py`、`test_client.py`、`test_exec_cpu.py`、`test_daemon.py`、`test_kernel.py`、`test_kernel_integration.py`、`test_kernel_recovery.py`、`test_rearch_e2e.py`、`_kernel_util.py`。
- 實作者自己記的 12 條歧義：`proto5/notes/2026-09-23-rearch/impl-findings.md`。
- 當初的任務書：`proto5/notes/2026-09-23-rearch/impl-task.md`。
- 背景（卡住再翻）：`proto5/notes/2026-09-23-rearch/review4-report.md` 尾巴「定稿前必改」。

## 要答的四件事

**A. 規範 vs 程式的偏差。** 逐節走 cpu.md §3～§7、daemon.md §3～§6、kernel.md §1～§6（含 CLI 節），找出程式行為與規範**不一致**的地方。每條給：規範位置（檔:行）、程式位置（檔:行）、一句話差在哪、嚴重度（擋＝會壞掉或違反已拍板的保證／要修／可先放）。**規範沒寫、程式自己選的**另列一小節，不算偏差。

**B. 12 條 impl-findings 逐條裁。** 每條三選一：(a) 規範要補寫——給可以直接貼進規範的一段話（≤ 4 行）；(b) 程式要改——說改哪裡；(c) 照現況接受、頂多在規範加一句「保證外」。要說理由，一條 ≤ 6 行。

**C. 測試沒蓋到的崩潰窗口與競態。** 對照三份規範裡明寫的順序（例如 kernel §3 十步、cpu §6.2 五列對帳、daemon §6.1 交接），列出**程式有做但測試沒驗**、或**程式與規範順序不同**的地方。最多 10 條，每條給時序＋後果＋建議測法。

**D. 測試品質。** 有沒有測試只在驗自我宣告（例如只驗 log 有寫、不驗行程真的死了）、有沒有靠 sleep 賭時序的（會在慢機器上 flaky）。最多 8 條。

## 格式

四節 A／B／C／D，條目編號 A-1、B-1…；每條有檔:行。總長 ≤ 7000 字。開頭一段「總評」≤ 8 行：能不能算「照規範落地」、最該先修的三件。不要重述規範內容，不要客套。
