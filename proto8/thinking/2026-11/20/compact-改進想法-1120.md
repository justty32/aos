# compact 改進想法（使用者 11-20 晚，逐字）：清工具輸出納入 agent-fsm 的 compact，壓完補回用 hook、各自的 compact 方式之後再規劃

← [2026-11-20](README.md)

## 來由

使用者在家機重建 `~/aos-home`、接真模型、試過 `/compact` 之後問原理，再問 Claude Code 的 compact 怎麼做。頂層答的對照（頂層憑對 Claude Code 行為的了解說的，沒讀它的原始碼）：骨幹一樣是叫模型寫摘要取代舊對話；Claude Code 多做「壓之前先把舊的工具輸出清掉」「壓完重新附上最近讀的檔、待辦、重讀 CLAUDE.md」「壓前壓後各有 hook」。

## 使用者原話

「oh...很...樸實無華，你知道claude code的compact是怎麼做的嗎？」

「噢噢，聽起來值得改進，清工具輸出這個看起來確實該納入我們的這個朴實compact。至於壓完後補回這塊，我們可以用hook實現，之後可以實現大家各自的compact方式，比如aos特色的一些東西或是...反正之後再來規劃。」

## 決定

- 清工具輸出：要納入 agent-fsm 的 compact。
- 壓完補回：用 hook 做；之後可以各自實現自己的 compact 方式。
- 都是「之後再來規劃」，沒派線、沒改程式。

## 註（記錄者加，不是使用者的話）

- 今天 `/compact` 是 body 指令，不過 `before_queue`／`after_queue`，也沒有壓前壓後的 hook 點（[02-agent-fsm「寄 /compact 會怎樣」](../../../templates/docs/02-agent-fsm.md)）；要用 hook 補回得先有點可掛。
