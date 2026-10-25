# R2：還沒收攏的

> 還在生長的想法、大家問出來的問題、明顯的坑。

## 還在生長的想法

- **「一個 `aos exec` 推多世界」仍有三種形狀**：同一 OS 行程內 `advance_once(World&)` multiplex、
  同一命令 `aos exec w1 w2` 逐 world root fd 推進、父批次呼叫多個普通 `aos exec <path>` 的命令樹。
  三者都讓 `exec` 不懂親緣，但啟動成本、全域 cwd、總退出碼與故障隔離不同，尚未收成一個介面。
- **proc-table 是真源還是可重建索引，還沒對齊**：一說可由自足 worlds 重建；一說 manager manifest
  保存 generation／join 等只存在父端的狀態。有未結 join、配額或上一代 receipt 時，哪些欄位能重建、
  哪些必須耐久，還要分清。
- **root 權力的「有權」尚未變成「別人做不到」**：core 是唯一 writer 目前只是控制協定；強制機制
  （POSIX 權限、僅 core 持有的 dirfd／authority handle、降權執行，或完整 OS sandbox）未定。所有程式
  仍用同一 UID 且 instruction 可跑任意命令時，至高權力只是守約，不是安全隔離。
- **完整 kernel 的升級來源有數種**：模板、`kernel.source.json`、父先物化再呼叫，都保住執行時自足；
  來源檔是不是規格、core 升級失敗時怎麼留下現場，尚未成形。
- **agent loop 刻意留給 R3。**使用者原話：

> 這些東西其實頗多，我會建議 **agent loop 可以延到下一輪**。

## 大家問出來的問題

| 問題 | 它卡住什麼 |
|---|---|
| 「一個 exec」是單一 OS 行程、一條命令樹，還是同一命令接多個 world？ | 決定現在是否需要 `World&`／root fd，也決定多世界的錯誤與退出語意 |
| root 的唯一寫權靠守約、POSIX 權限／fd，還是 sandbox？ | 決定「至高權力」只是排程規則，還是真的安全邊界 |
| 一個世界 busy／失敗時，其餘世界是否照跑？總退出碼怎麼算？ | 多世界若進同一次 `aos exec`，就必須有批次失敗語意 |
| 父 `.runi` 未清而子已完成，父 crash 後 receipt 算哪一回合？ | core 收結果與父回合 commit 的原子邊界仍未定 |
| 搬移是否保留未結 join？ | 不用 UUID 後，detach／adopt 能否延續等待關係仍未回答 |
| 外部處理器能否繞過 core，直接 claim 子世界？ | 若可以，core 的唯一管理權是建議；若不行，就需要可強制的權限機制 |

## 明顯的坑

- **把「core 是唯一 writer」直接當成安全隔離。**同 UID、又允許任意 POSIX 指令時，沒有權限分離或
  sandbox，外部程式仍能繞過 core 改檔。
- **同一 OS 行程推多世界，卻繼續靠全域 `chdir`。**要用 root fd／`*at`；否則一個世界切 cwd 時，其他
  世界的相對路徑會跟著變。
- **不用 UUID，就假設不必處理舊身分。**要加 generation，防止刪除重建後同名新行程誤收上一代 receipt。
- **拿 inode 或內容 hash 當替代 ID。**inode 經複製／跨檔案系統不可攜，hash 會在世界正常演化時改變。
- **讓活著的世界透明搬家。**搬移要收緊為新地址、detach／adopt，或只准沒有 `.runi` 與待收 receipt
  時 rename；承諾活搬，舊 join、能力與 receipt 的歸屬就重新變成未解的交易。
- **proc-table 一面說是可重建索引，一面又把唯一的 generation／join 寫在裡面。**哪些是 cache、哪些是
  耐久真相要分開；不分就會重新出現表與目錄雙真相。
