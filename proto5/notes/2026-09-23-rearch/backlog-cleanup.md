# backlog 清理（2026-09-23 重架構後）

← [本輪 README](README.md)｜backlog 索引：`backlog/README.md`（資料夾已於 09-24 拿掉，見 [2026-09-24-backlog-cleanup](../2026-09-24-backlog-cleanup.md)）

新規範：[cpu.md](../../spec/cpu.md)、[kernel.md](../../spec/kernel.md)、[daemon.md](../../spec/daemon.md)。一件一列：檔名（或檔內條目）、原問題、結論、對到哪節。

## 刪掉的（整個檔）

| 檔／條目 | 原問題 | 結論 | 新規範 |
|---|---|---|---|
| `cpu-simpler.md` | cpu 佇列三資料夾＋短鎖＋收屍＋inode 核對太厚，想精簡 | 整套拿掉了：沒有鎖、沒有 `running/`、沒有收屍，放單靠 `link`、做到哪靠 `state.current` | cpu §1、§6.2 |
| `kill-tree-exceptions.md` | aos-run 開 kill_tree 停機時，某些長期服務想例外存活 | aos-run 跟 kill_tree 都沒了；現在只砍子程式那一組（process group），想活下來的工具自己脫離那組就砍不到 | cpu §5.2、daemon §5 |

## 檔留著、但裡面刪掉的條目

### kiss-holes.md

| 檔／條目 | 原問題 | 結論 | 新規範 |
|---|---|---|---|
| `kiss-holes.md` 第 3 條 | 收屍不等於殺掉原工作、HTTP 慢慢回會超時 | 沒有收屍了；逾時由 aos-exec 砍子程式那組，問模型也只是普通程式 | cpu §1、§4.1、§5.2 |
| `kiss-holes.md` 第 5 條 | daemon 不收養崩潰留下的 runner | runner 沒了；daemon 啟動先等上一任的孩子死透、孩子表從空開始（拍板不收養） | daemon §9 第 6 條 |
| `kiss-holes.md` 第 6 條 | 排程只看最後結果、漏中間退出碼 | 每次派工恰好一則回音，每則都判 | kernel §4 |
| `kiss-holes.md` 第 1 條（cpu／kernel 那半） | 沒有請求對帳、跨檔交易 | cpu 有開機對帳＋ack 才刪回音，kernel 有帳本＋出貨箱；剩 agent 那半，留在該條並指 request-identity | cpu §6.2、§3.3，kernel §1.2、§3 |

### review-leftovers.md

| 檔／條目 | 原問題 | 結論 | 新規範 |
|---|---|---|---|
| `review-leftovers.md` R10 | cpu 收到 TERM 主動寫 `ok:false`，免等收屍期限 | 第二次訊號就砍子程式、回音照寫 `stopped:true`；也沒有收屍期限了 | cpu §5.2 |
| `review-leftovers.md` R12 | 閒置 cpu 每秒起 `python -c pass` | 沒有 idle.json；沒單就睡 `poll_ms`，不起任何程式 | cpu §6.3 |
| `review-leftovers.md` R13 | 收屍用 running 檔 mtime 對時鐘，NTP 跳時會錯 | 沒有收屍、沒有 running 檔 | cpu §1 |

## 留著的

- `request-identity.md`、`agent-fail-state.md`、`tool-call-order.md`：agent 線，檔頭加了「等 agent 規範重寫後再判」。
- `llm-cpu-fallback.md`：換手需求還在，但 llm cpu 已不是 cpu 種類，改成「問模型的程式」的事；誰管 `models` 表要看 agent 重寫，也加了檔頭。
- `kiss-holes.md`：剩第 1（agent 那半）、2、4、7 條。
- `review-leftovers.md`：剩 R4（換成新形狀，仍在保證外）、R11（見下）。

## 不確定（留著讓人判）

| 檔／條目 | 原問題 | 結論 | 新規範 |
|---|---|---|---|
| `review-leftovers.md` R11 | 工作 cpu 跟 kernel tick 間隔分開、要先有 `last_target` | 這兩件都不成立了（cpu 自己 `poll_ms`、kernel `tick_ms` 本來就分開，`last_target` 拿掉了）。但 once 工作要等 kernel 一格派、下一格收，一次問答的延遲還是綁在 `tick_ms` 上——這算不算還要做，要人判 | cpu §2、kernel §3 第 3 步、§10 第 7 條 |
| `kiss-holes.md` 第 2 條 | 排隊與等待沒期限、半批沒送完永遠等 | 「排隊沒期限」在 kernel 這層還是真的（`queue` 裡的行程沒有期限，pool 沒 cpu 就一直等；只有 `timeout_ms` 管跑的時間）；「半批沒送完永遠等」是 agent 那層。要不要給 kernel 加排隊期限，要人判 | kernel §3 第 8 步、§4 |
