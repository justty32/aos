hook 總文件的入口：aos 的 hook 到底怎麼一回事，給人和 agent 看；細節分在同夾七份。

← [aos-hook 指令](../README.md)｜[py/docs/05 指令](../../../../docs/05-commands.md)｜寫於 11-21（線 top-1121-hookdoc），以 hook 整套換新格式＋極簡引擎之後的程式為準

## 骨幹（使用者 11-21 原話）

- 「hook體系的唯一約定，就是要在interfaces.json中宣告，有宣告就能用，至於怎麽實作的，就是各家自己的事情。」
- 「hooks表示有哪些鉤子，hookeds表示有哪些被勾着」
- 「宣告這東西只是參考」（「沒宣告的照樣跑，其他的也是」）
- 「發事件的程式自己決定 <- 沒錯，我們提供的hook fire本身會參與這個過程，所以也算在其中。如果有人不想用我們的aos-hook fire，那就弄他自己的。」
- 「總之hook這邊就保持極簡」

## 三句話版

1. 一個程式在某個時刻「發事件」，就照**被勾清單**（`hookeds.json`）把掛在那個事件上的 handler 一個一個叫起來，事件 JSON 從 stdin 給它。
2. 引擎只交回每個 handler 的**退出碼與 stdout**；退 10 算不算攔、stdout 能不能改東西、失敗要不要停，是**發事件的那一家**自己定的規矩。
3. **宣告**（`hooks.json`：有哪些點、handler 收到什麼）只是給人和工具看的參考，沒有程式照它擋人；兩份檔都在 `interfaces.json` 最外層用 `hooks`／`hookeds` 指出來。

## 分檔

| 份 | 內容 |
|---|---|
| [01-一頁看懂](01-一頁看懂.md) | 三樣東西、一條流程、一張圖、最短的例子 |
| [02-宣告格式](02-宣告格式.md) | `hooks.json` 的格式：硬性只有 id 與 `input`；aos 自己的宣告用了哪些自由鍵、誰讀 |
| [03-寫handler](03-寫handler.md) | handler 收到什麼、怎麼回、退出碼（引擎層與各家規矩分開講）、工作夾、逾時 |
| [04-掛hook](04-掛hook.md) | `aos-agent hook`、`self_hook`、直接改 `hookeds.json`、編譯時 `hooks=`；只攔某支工具；loop 點要重新編譯並重起 |
| [05-各家的點與規矩](05-各家的點與規矩.md) | agent 一家、aos-loop 四點、eca／mcp、kernel：有哪些點、能不能攔、失敗停不停 |
| [06-自己發事件](06-自己發事件.md) | 自己的程式提供 hook 點：用 `aos-hook fire`（兩種退出碼）、直接叫 Python 引擎、或完全自己來；非 Python 的程式 |
| [07-限制與還沒做的](07-限制與還沒做的.md) | 已知限制；今天定了但還沒做的 |

## 其他地方

- `aos-hook` 指令本身（旗標、輸出、結束碼、實跑例子）：[../README.md](../README.md)。
- agent 這邊的完整說明（每個事件的欄位、時鐘 on_clock、eca 的差別、指令）：[apps/agent/docs/06-hook](../../agent/docs/06-hook.md)。
- kernel 三點的細節（判決、代回、預算拒絕）：[tools/aos/kernel/README「hooks」](../../../../tools/aos/kernel/README.md#hooks)。
- 給 agent 看的知識庫：`aos/me/self_hook.json`（自己掛）、`aos/cli/hook.json`（`aos-agent hook`）、`aos/cli/offer_hooks.json`（自己的程式提供 hook 點）。
- 施工紀錄與替使用者做的選擇：[hook-新格式施工-1121](../../../../../thinking/2026-11/21/hook-新格式施工-1121/README.md)。
