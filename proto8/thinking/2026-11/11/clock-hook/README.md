# clock-hook：hook 加「起來／停下」與「照時鐘觸發」（11-11）

← [2026-11-11](../README.md)｜[thinking](../../../README.md)｜圖紙與來回 [01](01-圖紙與改向.md)｜施工結果 [02](02-施工結果.md)

## 使用者原話與裁定（照時間）

前半（先定的「時鐘登記＋專用信箱」做法，後來被改向取代，見下）：

1. hook 要加的事件：選「起來與停下」。
2. agent 被刪時時鐘登記不跟著清：「交給自檢吧。如果要順手清的話，就是aos-agent ctl rm與另一個功能有耦合了。」
3. 「啊，時鐘登記那塊，我想到了，就是我們在定義中，hook起來的時候，登記時鐘，hook結束的時候，拿掉時鐘。然後自檢這塊是保底」
4. 「Hmmm，幫我改成五分鐘叫一次吧。」
5. 「我覺得這樣不太好，可以幫我改成寄信到一個特別的信箱，然後agent的hook本身也會登記一個"若指定信箱有新信"這個」「不然這就是固定往agent history添加東西，不太好」
6. 「預設就是收到信後啥也不做。」「預設啥也不做，那就是信收走，但不做事。睡著或正在忙的時候...hook應該可以設定說，是否只取用最新的那個，我希望預設是這樣，所以期間的就會被忽略。」
7. 起來／停下掛哪一層：選「aos-loop 自己加」。
8. sleep 算不算停下：「算。然後hook這邊可以細分出更多細類。目前就先這樣就好。」
9. 專用信箱：選「hook 裡寫，範本用 clock」。
10. kill -9 後登記殘留：選「自檢加『積太多就拿掉』」。
11. 「登記表那個確實要加鎖。但登記名字要全樹唯一，這就是要自己承擔的風險，」
12. 事件名：選前綴風格那組（`after_start`、`after_stop`、`mail_arrived`）。
13. 「只取最新一封」選項名：`latest_only`。
14. 腦自己用 `clock_register` 沒給 box：選「改成必填」。
15. 「公司有lmstudio，但只有破爛小模型。所以建議都使用eca，實際的loop fsm agent需要回家測。」「eca這塊，除了claude haiku之外，也試試看code gpt luna」
16. hook 寫不寫進 CONVENTION：「先不寫」。after_queue 停下後晾著的信：「不補」。
17. 「登記的名字，就用範本的定義中的名字，啊，我想到了，看看能不能在登記的時候，看到有重名，就加上-1,-2」

改向（取代 5、6、9～14、17 那半）：

18. 「就是說，因為現在hook本來就綁在loop上，所以hook就可以添加一個類型，就是loop每次exec前和exec後。然後這個exec前觸發的，就可以添加一個aos函數，使其去看指定的clock proc(指定一個proc名稱或路徑，該proc必須有clock檔案佈局)，這個aos函數會讀取設定，並儲存一些東西，然後我們在其中寫一些：每隔十個cycle就幹嘛，或是透過cycle換算，若超過十秒就幹嘛」
19. 選項框：「改成新做法」（專用信箱、有新信事件、latest_only、登記表加鎖、撞名後綴、積太多保底都不做；起來／停下照做，但不再拿來登記時鐘）；「時間到了沒」的判斷＝「hook 格裡寫條件」。
20. 舊的時鐘登記／時鐘寄信／`clock_register` 工具：先選拿掉，隨即改口「啊，不要拿掉好了，先留著」「搞不好以後會用到」＝整組留著、完全不動（連 14「box 改必填」也不做）。

## 決定

- **起來／停下**：aos-loop 加通用鍵 `on_start`／`on_stop`（＋`on_timeout_ms`，預設 5000），不認得 hook；範本 loop.json 指到 `lib/agent/hook_fire`，由它發 `after_start`／`after_stop`（after_stop 多 `code`、`signal`）。sleep、rm、daemon 收工都算停下；kill -9 不跑；pause 不算。
- **照時鐘觸發**：新事件 `clock_due`，hook 格裡寫條件 `every_cycles` 或 `every_ms`（毫秒用 cycle × `AOS_CLOCK_INTERVAL` 換算），`clock`＝proc 名稱或路徑（省略＝`$AOS_CLOCK`）。判斷在行程內做：agent-fsm 每格、aos-eca-turn 每輪的最開頭呼叫 `hooks.clock_tick`，到了才起 handler；狀態在 `hooks/<名>/clock_due.json`。忙完、醒來只跑一次（`missed` 記錯過幾次），不補跑。
- **範本預設**：agent-fsm、eca-claude 的 hooks.json 帶一格 `timer`（`clock_due`、`every_ms` 300000、handler `lib/agent/hook_noop` 什麼都不做、`on_error: continue`）當掛點（照 4「五分鐘」、6「預設啥也不做」；代定，可翻）。
- **記錄、不做**：專用信箱 `<stack>/clock`、`mail_arrived`、`box`、`latest_only`、看信那一步、登記表加鎖、自檢「積太多」、撞名加 `-1`／`-2`、範本 after_start 登記／after_stop 拿掉時鐘、`clock_register` 的 box 改必填。時鐘寄信那組（aos-clock-register、`clock_register` 工具、登記表、自檢「箱子不在就拿掉」）照 20 原樣留著。
- hook 不寫進 CONVENTION（16）。

## 結論

已施工，見 [02](02-施工結果.md)：aos-loop `25825fc24`；hook 事件、看時鐘、範本與文件在後兩個 commit。待使用者裁的題目在 02 最後。
