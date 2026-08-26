# 第 2 輪紀錄 — 好處／壞處

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1](../round-1/pros-cons.md)｜[R3 →](../round-3/pros-cons.md)

書記對上面那批坑的正反兩面整理：這一輪什麼有效、私有原型付出了什麼代價。

## 3. 好處／壞處

### 好處

四條路都把上一輪只能靠人搬檔或盲目重開的差異做得可觀察。Carmack persona 把 9 個靜態 Publish 呼叫點收進 1 份實作，五個乾淨案例都以 8 次 commit 收尾，人工 rename 為 0。Armstrong persona 的九個事故場各只用一條高階命令，rename 前 temp、target 後缺 receipt、Effect result-ready、done 後缺 continuation 與 Ctrl-C 現場都有各自的恢復輸出；明示 retry 也真的留下兩筆 provider ledger，沒有把命令名稱當成安全保證。

Cantrill persona 修正 SIGINT harness 後，golden、SIGINT、SIGKILL、delivery rename 前四案有一致欄位；Publish v2 的 same-target 競爭實際跑出同內容 Already、異內容 Conflict，Deliver v2 也讓錯 key、JSON、schema、world 成為可見拒絕。Thompson persona 用同一命令重開 no-aos 對照，實際推翻上一輪只有 happy path 的三行論；雙 producer 的 shared-slot／global-ID 對照把遺失歸到命名與覆蓋競爭，而不是 2,000 件負載或 aos 執行。

三份 multi-producer 回報把「同時有 writer」與「同時有第二個耐久工作」分開記錄：同 target 需要原子排他，不同全域 key 的 2,000 件路徑可全數處理；三份答案仍都把 concurrent logical agent jobs 記為 0。

### 壞處

私有原型已明顯增厚。Carmack persona 的 Publish／Deliver／Effect／Recovery 共 327 行；Armstrong persona 的私有 CLI 618 行，成功基線留下 12 個 transaction 目錄與 12 張 receipt，清理與保留期未定。Effect 仍要 phase、stable key、attempt、decision、receipt 與 recovery transition，卻不能回答 provider 到底做沒做。

Publish 的 no-replace 只處理 target commit，沒有一併解掉 transaction directory、receipt 與 consumer acknowledgment 的並行邊界。Armstrong persona 的 mkdir race 與 consumed-before-receipt 現場、其餘三份 aggregate 後同 key 可再次發布的結果，都留下額外帳本或 acknowledgment 尚不存在的狀態。三份 renameat2 實作是 Linux-specific；四份原型都沒有可外推的斷電結果。

Deliver 的私有 validator 也不是現有 instruction schema 的唯一真源。Armstrong persona 只支援本輪的 string argv；Cantrill persona 的 Python validator 是窄原型；Thompson persona 的 hard-link 原型沒有 JSON／schema 驗證。現有 aos 仍會安靜忽略錯名，child exit 137 時仍可能讓 aos exec 回 0，也沒有通用 status 一次列出 .runi、temp、instruction exit 與 result 缺口。
