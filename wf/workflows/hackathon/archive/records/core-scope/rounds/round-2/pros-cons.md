# 第 2 輪紀錄 — 好處／壞處

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1](../round-1/pros-cons.md)｜[R3 →](../round-3/pros-cons.md)

## 3. 好處／壞處

### 好處

- 第 1 輪要人搬檔或盲目重開的差異都變得可觀察：Publish 收成 1 份實作；每種事故場各用一條高階恢復命令，人工 rename 為 0。命令名稱不當安全保證：明示 retry 仍真的留下兩筆 provider ledger。
- no-replace 原型讓 same-target 競爭明確回 Already／Conflict；Deliver 先驗 key／JSON／schema／world，壞投件成為可見拒絕。
- 雙 producer 對照把遺失歸到命名與覆蓋競爭，不是負載或 aos 執行；「同時有 writer」與「同時有第二個耐久工作」是兩回事。

### 壞處

- 私有原型明顯增厚：一份 Publish／Deliver／Effect／Recovery 327 行，另一份私有 CLI 618 行；成功基線就留下 12 個 transaction 目錄與 12 張 receipt，清理與保留期未定。Effect 要 phase、stable key、attempt、decision、receipt 與 recovery transition，仍回答不了 provider 到底做沒做。
- no-replace 只處理 target commit，沒解 transaction directory、receipt 與 consumer acknowledgment 的並行邊界；`renameat2` 是 Linux-only；沒有可外推的斷電結果。
- 私有 validator 不是現有 instruction schema 的唯一真源，會長出第二套規則。現有 aos 仍安靜忽略錯名、child exit 137 時仍可能回 0，也沒有通用 status 一次列出 `.runi`、temp、instruction exit 與 result 缺口。
