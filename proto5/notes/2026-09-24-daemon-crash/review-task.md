# 任務書：審查 daemon 崩潰窗口測試 C-2／C-3（唯讀）

你是審查員，只讀不改、不 commit；不碰 LM Studio／lms／ollama（這條線不需要模型）。

## 背景

- 規範：`proto5/spec/daemon.md` §2（go 握手順序）、§6.1（啟動接手：等上一任孩子死透 → 對帳 current → 寫新 state，孩子表從空開始）。
- 原始審查題目：`proto5/notes/2026-09-23-rearch/impl-review-report.md` 的 C-2、C-3。
- 實作：`proto5/lib/aos_daemon.py`（`run()`、`_previous_children()`、`Daemon._launch()`、`process_request()`）。
- 新測試：`proto5/lib/test/test_daemon_crash.py`（HUB＝subreaper，用 WNOWAIT 先記再收屍；GATED＝在測試 driver 裡替換函式當閘門，產品程式沒改）。

## 要你看的

1. 閘門點是否真的落在宣稱的窗口（spawned／before_go／go_sent／responded／prev_term／prev_kill／prev_done／reconcile_interrupted／reconciled）。有沒有落錯位置、或 GATED 的替換沒被產品路徑用到（例如模組屬性查找方式）。
2. 斷言是否足以抓到真錯：例如新任在舊孩子死透前就公布 state、提前清表、回音被重寫兩次、多拉一顆孩子。HUB 的「WNOWAIT 先記再收屍」是否真讓「state 公布那一刻 → 已收屍名單」的比對沒有競態。
3. flaky 風險：固定 sleep、6 秒 wait_for、pid 重用、HUB 與 unittest 主行程的收屍衝突、清理是否一定不留行程。
4. daemon 在這兩個窗口有沒有真會壞的地方（測試沒抓到的）：例如 `_previous_children` 的 PermissionError 當活著、接手期間收到 SIGTERM、state.json 半寫、current 對帳與舊孩子未死的順序。
5. 規範歧義：§2 說「崩在寫表之後、回音之前……客戶重送 spawn → 回它的 pid（冪等）」，但 §6.1 說新任清表不收養。你怎麼讀？

## 回報

照嚴重度列（真 bug／測試漏洞／flaky 風險／建議），每條附檔案:行號與一句理由。沒有就說沒有。中文、精簡。
