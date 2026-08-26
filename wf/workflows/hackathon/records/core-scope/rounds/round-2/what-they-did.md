# 第 2 輪紀錄 — 各人這輪改了什麼

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1](../round-1/what-they-did.md)｜[R3 →](../round-3/what-they-did.md)

四位這一輪各自改了什麼、改在哪裡、成果放到哪個路徑，逐人一段。

## 1. 各人這輪改了什麼

**Carmack persona。** 沿用上一輪方向，但把混在一起的第一個數字拆成固定四欄：1 份原始碼實作、9 個靜態呼叫點、每案 8 次實際 commit、0 次人工 rename，題目的第一個數字只取實作份數。上一輪散落的發布改由一支 publish.py 處理，另加薄的 deliver.sh、記錄 unknown 的 effect.sh，以及把每種事故收成一條具名 action 的 recover.sh。修正後跑完 baseline、SIGINT、provider accepted／dropped、Effect response rename 前五案；兩個 unknown 案在不看 oracle 的情況下都下同一條 recover.sh abandon-unknown，rename 前完整 temp 則用 recover.sh adopt-temp。原場地本輪不可寫，成果放在 /tmp/aos-core-scope-p1-r2/round2/。

**Armstrong persona。** 把上一輪單一 temp + mv helper 加成 stable key、immutable intent／payload／receipt、stable temp、file fsync、directory fsync 與 Linux renameat2(RENAME_NOREPLACE)；Effect 改成 pending → done | unknown，恢復命令只接受 adopt | retry | abandon。這輪逐點砍在 Publish target／receipt 邊界與 Effect 的 pending／accepted／result／done 邊界，也重測 Ctrl-C；九個事故場都用一條高階恢復命令走到 final，shell mv 與手造半批 instruction 都是 0。另測同 target 雙 producer 競爭，第一次撞到自己的 mkdir race，修正後用 fresh world 重跑。上一輪場地不可寫，因此先以相同 SHA-256 複製到 /tmp/aos-p2-round2.kTrhIV/p2-agent-loop 再做本輪實驗。

**Cantrill persona。** 修正上一輪拿不到獨立 aos exit 的 SIGINT harness，統一 crash matrix 欄位，補測合法／非法 delivery 名稱、same-target race 與雙 producer 各 1,000 份，並把原本有 TOCTOU 的 Publish v1 換成私有 renameat2(RENAME_NOREPLACE) Publish v2。Deliver v2 由自己產生合法 <key>.json，先拒絕壞 key、JSON、schema、world，再回 published／already／conflict。本輪固定把第一個數字數成成功三回合的 Publish transaction 數。指定場地不可寫，成果放在 /tmp/p3-core-scope-round2/，另留 tarball 與 SHA-256。

**Thompson persona。** 撤回上一輪「三行 shell 已反證 Deliver」的結論，讓 no-aos 鏈承受同樣的 SIGINT、SIGKILL、rename 前中止，且事故後只能重跑同一條命令。effect 後重開在 SIGINT 與 SIGKILL 兩案都把 effect 從 1 次做成 2 次；舊 delivery helper 在 rename 前死亡後也無法以原參數重叫。另讓兩個 producer 各投 1,000 件：共用本地序號時遺失 1,000 件，改用全域唯一 ID 時遺失、重複、覆蓋、明確失敗皆為 0。最後以 hard link 寫窄 no-replace 原型，測過 crash 前 exact retry、Already 與 Conflict，但留下孤兒 temp。原場地被沙盒拒寫，成果放在 /tmp/p4-round2。
