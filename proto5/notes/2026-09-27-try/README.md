# 2026-09-27 proto5 實跑

← [notes 索引](../README.md)

照 tutorials 01–04 的基本路徑跑通：開機、kernel 工作、真模型工具回合、暫停恢復與關機。未修改原始碼，也未操作既有 runtime。

環境：repo 根目錄、Python 3.14.7、獨立家 `/tmp/aos-proto5-try-20260927-5klrm6cy`；default 2 顆、llm 1 顆。模型走既有 `http://localhost:4000/v1` 的 `deepseek-chat`，是實際端點回應，未使用 mock；代理背後的供應商未另查。資料留在暫存家，重開機可能清除；關鍵輸出已複製於本筆記旁。

| 試項 | 實測 |
|---|---|
| `init → check --probe → aos up` | probe 通，開機 `health ok`，3 顆 cpu 閒置 |
| once/date | 回音 `code: 0`；輸出 `2026-09-27T15:37:09+0800` |
| once/不存在的 argv | 回音 `code: 127`；這是工作失敗，CLI 收單本身不因此失敗 |
| 反覆工作 | 第 3 次 exit 100，狀態 `done`、runs 3、fails 0；產物恰好三行 tick |
| agent 問時間 | 記憶確有 `date` 呼叫，工具回 `2026-09-27 15:37:10`，模型回答下午 3 點 37 分 |
| pause/say/continue | 暫停時 say 已投遞但退 101，input 留 1；continue 後收到「暫停測試恢復成功」，health ok、errors 0 |
| stop/down | daemon not running、children 0；第二次 down 安全重入；掃 /proc 無本次 runtime 殘留 |

原始命令與輸出：[開機及工具回合](transcript.log)、[工作結果及暫停恢復](pause.log)、[關機](shutdown.log)、[殘留檢查](process-check.json)。

要接回本次家（暫存尚在時），從 repo 根目錄執行：

```sh
. /tmp/aos-proto5-try-20260927-5klrm6cy/env.sh
aos up
aos-agent start --target "$W/bob"
aos-agent say '現在幾點？請用工具查。' --target "$W/bob" --wait 60
# 收工
aos-agent stop --target "$W/bob"
aos down
```

本次未遇到功能阻塞。觀測到的易誤讀處是「CLI 成功 ≠ 工作 code 成功」，以及 pause 中 say 退 101 仍已收話；目前提示都能明確說明，不需要重送。尚未涵蓋壓力測試、crash recovery、team、CLI agent、權限逃逸或端點連敗恢復，不由這次煙霧測試推論其可靠性。
