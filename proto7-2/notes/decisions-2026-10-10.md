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
