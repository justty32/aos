pack4 驗收完成：**10 項通過、1 項部分通過；未確認新的 B／G。** 受測 HEAD：`ad1dfa25`。舊 50 案全過；獨立核帳 99 份新快照、276 筆轉移全過，5 個負對照全抓紅。

證據目錄：`proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/pack4/`。

[主結果](results.json)、[新發現](findings.json)、[完整快照索引](archives.json)。

| 項目 | 結果＋證據 |
|---|---|
| 1. rc 3 接 unknown_codes | 通過：真 tick/tock＋step＋budget；a2 同 request、accepted=1、resends=1；持續故障用完額度才 unknown。`results.json: unknown-recover / unknown-exhaust` |
| 2. 不開 unknown_codes | 通過：halted failed；resume --resend 同 request 結算一次。`results.json: unknown-default` |
| 3. payload | 通過：EIO 回 3、單行 unknown、stage=payload、無 traceback；不存在／壞 JSON 回 2。`results.json: payload` |
| 4. 重播回條 | 通過：gateway EIO 回 3，--out 前後 SHA-256 相同；恢復後回 0、只受理一次。`results.json: replay` |
| 5. 過期 intent | 通過：receipt／resend／stop 三型均核對 frame、request、attempt、實跑次數。`results.json: intent-receipt / intent-resend / intent-stop` |
| 6. R8-14 | **部分**：讀表 EIO 後恢復，ran=2、halt.kind=unknown，額度未重設；實體 write EIO 則 ran=1 就停。另：拒寫消耗 attempt 號，實跑 a1、a3，沒有第三次執行。`results.json: resend-open-fail / resend-write-fail`、`repeat-write-results.json` |
| 7. R8-22 | 通過：after-intent 真 SIGKILL；跨回合走 unknown，可人工續送；同回合補加原 a1、ran=1。`results.json: intent-stop / intent-same-round` |
| 8. 加權成本 | 通過：amount=2＋預設 1，used=3、accepted=2、initial=10、available=7。`results.json: weighted` |
| 9. 舊案／核帳 | 通過：41＋9 案；99／99 快照、5／5 負對照。`crash/verified/results.json`、`crash/extra/results.json`、`audit-summary.json`、`negative-controls.json` |
| 10. C8-03 | 通過：工作資料夾、results、gateway 各連殺 writer 6 次；恢復後死 tmp=0，活 writer 的唯一 tmp 保留。results 的原子發布實際是 hard link。`tmp-results.json` |
| 11. 文件一致性 | 通過：README／spec／gate docstring 三處退出碼語意一致；加權單位與 step 規則均有對照證據。`doc-results.json` |

**NEW-pack4-1：X／低，R8-22 已知限制的延伸。** `write:*/tasks.json:EIO` 在加項前命中後，直譯器保留 intent；故障撤除，下一回合因 intent 過期且額度已用完，仍停 unknown。另跑 3 次均 ran=1；人工 `resume --resend` 均能同 request 完成。沒有多跑；此案是 step 派工探針，不涉及 budget 帳本。依據為 step spec §5.4／§5.6、代定清單 S 的縮窗決策；完整最小重現、影響與建議見 `findings.json`。建議文件與驗收分開描述讀表拒寫和實體寫入故障。

第 6 項「不得出現 a3」與 step spec:83「attempt 號照加」不一致：a2 派工失敗後，第二次實跑叫 a3。實體 write EIO 分支未能執行「殺第二次子工作」，因產品先停在 unknown；已照實列部分，沒有湊通過。

自由邊界亦完成：18 組 unknown_codes 值、3 種非 run 步驗證均符合契約；把 1／2 列為 unknown 並謊稱非冪等 append 工作為冪等，確會重複效果，分類 **M**，不列 bug。證據：`results.json: validation / misuse-code-1 / misuse-code-2`。

重跑：從 repo 根 `python3 <本目錄>/probe.py`、`tmp_probe.py`、`rerun_crash.py`、`repeat_write.py`、`doc_probe.py`、`audit_all.py`；各 driver 自動套用指定 systemd scope。`probe.py` 因保留第 6 項寫入 EIO 的未通過斷言，預期退出 1。舊探針斷言未改，只改重跑說明與暫存前綴；核帳器與 astra-6 原件 SHA-256 完全相同。`provenance.json` 留存來源。

清理通過：`ps-before.txt`／`ps-final.txt`、`cleanup.json`；自建暫存根已清、無本線受測程序殘留，tracked 檔零修改，無 commit／push／LLM 呼叫。大量快照已封裝 tar.gz，單檔均低於 300 KiB。首跑兩個探針自身錯誤已修正，舊紀錄保留於 `harness-initial.tar.gz`，未計為產品失敗。
