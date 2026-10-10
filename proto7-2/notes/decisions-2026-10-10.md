# 2026-10-10 頂層代定清單

← [前一天](decisions-2026-10-09.md)｜[catch-up](catch-up.md)

一行一條，格式比照 [decisions-2026-10-09](decisions-2026-10-09.md)：級別（A＝大、B＝中、C＝小）或結果／決定／出處。

## 結果

- 證明｜AP5：學徒自我改進 A／B 對照（luna 6×2、sol-low 5×2，4 題郵局慣例題、每題最多 5 輪；293 次真 AI、約 197 萬 token）→ 讀自己技能書的 B 組第 2～4 題平均輪數 luna 2.78→1.33、sol-low 2.33→1.40，大於題 1 雜訊（0.83、0.20）；一次過 A 0/33、B 21/33；兩模型 B 每一次都比 A 每一次好（排列檢定 p＝0.001／0.004）。限制：4 題的坑相同，證的是「同一種坑記得住」。分支 loop13/AP5 已 rebase、全套綠 → [apprentice-5](play/2026-10-09-real-ai/apprentice-5.md)

## loop14 FX1（修 astra-8 建議順序前四項）

- C｜A10-01：核心起任務的環境照舊只帶核心六個 `AOS7_*`，另**明列放行 `AOS7_LITELLM_KEY`** 一個（`lib/aos7_task.py` `TASK_ENV_ALLOW`）；不走「up.json 存金鑰」，因為秘密不能落地。金鑰只跟起 daemon 的環境走，要換金鑰得 stop 後從新環境重起 → `modules/up/ADVANCED.md`「要真 AI」段
- C｜A10-01 延伸：llmcall litellm 傳輸送出前驗金鑰字元，不合法就不送、當 rejected 退 1；其他傳輸例外的 why 只留例外型別名、不含原訊息（避免經例外 repr 進 out.log）→ `packs/llmcall/spec.md`
- C｜A10-02：`owe` 存不進 paused.json 就不開這一回合，等 POLL 回頂端重試（不確定寧可少跑）；`round_done`、`op_pause`／`op_resume`、`_save_paused_quiet`、`reap`／`sweep_leftovers` 的同型「存失敗照記憶體繼續」只盤點未修，留下一輪
- C｜A10-03＋B10-11：新增 `packs/llmcall/aos7_llmcall_exit.py` 當呼叫方共用的退出碼對照；退 4 只表示帳未清，答沒答成看回條 `outcome`。compact：答到（0／4＋answered）收摘要、確定失敗（1／2 或 4＋非 answered）退 1、3／未知退 3，pending 都留著
- C｜B10-11：author 收到 llmcall 1（模型拒答）或 2（作者自己組的請求被拒）都歸「確定沒做成」退 1，不再退 2；拒答不自動升級模型重送；本地用法錯仍退 2
- C｜brain／skills／author 一律用共用 `answered(rc, receipt)` 判斷「答到了」；brain 遇 llmcall 未知退出碼（不在 0～4）當不確定，保留同一筆請求等接續，不當失敗
- C｜A10-09：`aos7-ctl` 用法錯退 2 附例子、讀寫故障／Unknown／未預期例外退 3 一行（以前 1）；`notes/problems.md` G1 那列已加註；restart 失敗回條加 `outcome: unknown|refused` 欄位（只加不改），ctl 據此未知退 3、確定拒絕退 1
- C｜A10-11：照 10-09 L4 決定，前導零索引照收（4301 個 0＝索引 0），去前導零後仍超長才退 125
- C｜B10-01：error_path.json 補齊 12 支入口（共 29 支現役入口全登記）；凍結核心 tock／daemon／run／wait-tock 與退出碼透傳的包裝器用 exempt 寫理由；新增防漏列檢查
- C｜B10-02：error_path 檢查器把 HOME、XDG_*_HOME、TMPDIR 隔離到暫存區並納入不留檔快照，`--help` 也檢查不留檔；`__pycache__` 不例外（檢查器設 PYTHONDONTWRITEBYTECODE）

## loop14 FX2（daemon 存檔失敗不推進，接 FX1 A10-02 盤點）

- C｜`round_done` 改交易式：用複本算新 owe／steps／paused，paused.json 寫成功才換進記憶體；失敗記憶體全不動、回 False（磁碟留舊 owe，重開照 N-06 結算一次，不會雙扣）
- C｜時間線：結算失敗記 `settle_pending`（記住該扣或不扣），回頂端先重試、落盤前不走 `mark_owe`／tick（否則新回合號蓋掉舊 owe＝少扣多跑）；tick 失敗的半回合恢復時沿用 pending 的「不扣」
- C｜`mark_owe` 寫失敗改還原原值（以前一律 pop，會丟掉未結算的舊 owe）
- C｜`op_pause`／`op_resume` 交易式：寫不進回條 ok:false「沒有改；請重送」、記憶體不動、resume 不 wake（以前丟例外→無回條、效果卻已在記憶體生效）；上一回合結算還沒落盤時也先拒（免得重試扣到新額度）
- C｜`_save_paused_quiet`（unregister、node 消失拿掉倒數）失敗設 `_paused_dirty`，`check_nodes` 每圈補寫、停機前再補一次
- C｜`reap`：回收意圖沒寫進 nodes.json（或還有待補寫）就不起收任務的 thread、記 `reap-deferred`，已知 pgid 保留；補寫成功後回收迴圈照起，舊時間線還沒結束也照起（舊線結束後照舊再掃一次）。停機帶 kill 仍照身分掃全部 node
- C｜`sweep_leftovers`：held 意圖寫不進時每 0.1 秒重試、最多約 2 秒，仍失敗印一行 stderr＋事件後照常退出（不卡、不改退出碼）
- 留著｜起動時 `save_paused`／`save_nodes`／`gen.json` 寫失敗仍是未捕捉例外（traceback、退 1）：要改就得定新退出碼，屬退出碼契約，不在本輪範圍
- 留著｜停機時回收意圖重試 2 秒仍寫不進＝重開後不會續收（只剩 stderr 一行）；沒有別的落盤處可放，要不要「寫不進就不退出」是方向問題
