# astra-7 重跑與證據

從副本根目錄使用 Python 標準函式庫即可。所有 product import 都停用 bytecode；只寫本證據目錄、指定報告與自建 `/tmp/astra7-*`。**不要並行同一個腳本**，結果檔會互相覆寫。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-7-infra-evidence/regression.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-7-infra-evidence/legacy.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-7-infra-evidence/edges.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-7-infra-evidence/jsonl_edges.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-7-infra-evidence/followup.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-7-infra-evidence/claim_batch.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-7-infra-evidence/probes.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-7-infra-evidence/longrun_clean.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-7-infra-evidence/verify.py
```

- `regression.py`：原版 astra5 28 項、astra6 18 項、owner_reload 9 項，共 55 項。沒有跑會呼叫 LLM 的 agent／real 全套。
- `legacy.py`：直接載入上一輪證據函式；common 指向本輪輸出，故障 hook 仍讀第五輪的 crash/sitecustomize.py。G04 原本等待「owner 被改成功」的 bug 條件改為定時觀察，另用 claim_batch 的同 node 既有鎖主做對照。F11 的舊測試暫存目錄包在當次 Space 下。
- `edges.py`：root symlink、chmod、rename 回原位、bind 身分檢查；runner fd；ctl-failed 累積／次級命名碰撞；G04 barrier；讀回失敗的手動及 daemon 對照。
- `jsonl_edges.py`：真 log／decision／send／audit 寫入入口的 ASCII／UTF-8 半行；runner I/O；晚期 node 搬移。
- `followup.py`：真 bind root 的 daemon 與 lazy detach；已觀測 root-gone 後搬回；runner out.log 故障後 keep；短寫讀回失敗後 daemon 缺 round。
- `claim_batch.py`：不改產品、不掛 barrier，12 次同 tick 雙任務搶同 subroot；另驗原同 node 第二請求在現役 daemon 已拿鎖時被拒。
- `probes.py`：僅跑 namespace、ledger；兩者只用固定結果模擬服務，沒有網路或模型呼叫。
- `longrun_clean.py`：正式 600 秒、11 個每分鐘快照，結束後再測 stop＋kill。取樣 live／zombie 分列，fd 讀取失敗記 pid；warm-up 可有短命程序的競態缺口。每 200 ms 用 waitpid 回收控制器收養的已退出程序。
- `audit_longrun.py`：在正式長跑接近結束、暫存根尚在時另跑一次；核對每條線已提交的 rounds、ended 去重、action／I/O 錯誤。它不是全樹原子快照，不能在長跑清場後重跑。
- `longrun.py`／`longrun.json`：初跑 600 秒紀錄，subreaper 直到 Space 結束才 waitpid，因此有測試器名下的 zombie；正式判斷使用 clean 版。保留初跑便於稽核，不用初跑 Z 數宣稱產品洩漏。
- `verify.py`：來源 hash、所有案例 cleanup、產品程序／AOS7_ROOT 與本輪暫存根核對；不殺別人的程序。

`common.py` 由上一輪 harness 複製，只改本輪暫存前綴；controller 設 Linux subreaper，只為收回自己的 orphan，**產品並未改成 subreaper**。正常先 SIGTERM 自己登記的 Popen，最後以明確 PID 收控制器後代並 waitpid，確認清空才刪自己建的目錄；沒有 pkill。每案 `cleanup.root_exists=false` 與 `remaining_children_before_delete=[]` 記錄清場。產品是否自己收乾淨，看 longrun 的 `product_live_survivors` 與 F11 等案例在 harness 介入前的觀察。

`recorded` 只表示有觀察資料，不代表 pass。`harness_error` 才代表案例沒跑完。bind 使用 `unshare --user --map-root-user --mount`，掛載／卸載皆只在該 namespace；環境不支援時應記未測，不以 mock 當真 mount。普通 umount 會因 daemon fd／任務 cwd 回 EBUSY，因此另測 lazy detach，不能把 busy 算產品 bug。

基線最初逐檔雜湊完整保存以供比對；收尾確認後，`baseline.json` 縮成完整受保護檔案集合的聚合 hash、檔案數與產品程式／規格逐檔 hash，不保留大份歷史清單。`verification.json` 保留比較結果。初版 fd 取樣遇程序退場 PermissionError、初版 bind 對 busy 判讀錯誤，均在 harness 修正後重跑，沒有算成產品失敗。
