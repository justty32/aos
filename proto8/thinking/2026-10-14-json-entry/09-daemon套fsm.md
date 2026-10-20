# 2026-10-14 daemon 套 fsm 的紀律

← [JSON 入口](../2026-10-14-json-entry.md)｜上一份：[08-fsm拍板與改寫](08-fsm拍板與改寫.md)｜下一份：[10-lisp組合子](10-lisp組合子.md)

## 17. 使用者原話

> daemon那邊也可以用fsm的概念...嗎？

## 18. 研究結論

daemon 借 fsm 的紀律，但不變成一張 fsm 表。真正多狀態的是**每個子 loop 的生命週期**（像 supervisord／systemd：容器＋每子項一台小狀態機＋可換的 on-exit 策略）。daemon 留長壽程式，因 Popen／waitid 收屍／整群訊號是單次執行程式做不到的。Lisp 視角：daemon 是唯一的「並行」組合子，`(daemon :on-exit restart (loop A) (loop (fsm …)))`。

## 19. 五題拍板（全照推薦）

1. **形態**：長壽程式＋fsm 紀律。Popen／收屍／訊號留在程式內；表落窗、子項 phase 明寫、策略格可換。「daemon 整個變 fsm 資料夾、被 loop 拍」記為之後可做的實驗。
2. **子項 phase** 六態：`starting／running／exited／backoff／stopping／removed`，寫進 `table.json` 窗（N-14 一種，只有 daemon 寫）。
3. **daemon 重起：接回孤兒**——pid＋啟動時間（/proc）＋心跳對得上就認領、不重起；對不上當 `exited` 走策略格。
4. **策略格**：只有 `policies.child_exit`。stdin `{id, code, exits, last_state}`，stdout `{action: restart|leave|remove, after_ms}`；沒設＝`leave`（現行為）。
5. **`children` 陣列當初始表**：起來時等同逐個 add，控制資料夾仍可增減。

## 20. 風險（研究員點出）

- add 寫表與 Popen 之間被殺：先寫表、再 Popen（重起時表裡 `starting` 的要查證）。
- /proc 是 Linux 專屬，接回孤兒在別的平台要另想。
- 崩潰迴圈要內建退避上限（例如 `exits≥5` 強制 `leave`），不能全交策略格。
- 原始碼：`proto8/lib/aos_daemon.py`、`aos_daemon_table.py`；`restore()` 的 Exists 檢查是「只認 Popen」的根源，要改。（proto8/lib 已在 10-19 刪）

## 21. 未決

- **save 檔與 table 窗合一**：今天 save 存 `[{loop, ctl}]`，與新 `table.json` 會漂移；建議合成一份（table 窗就是 save 檔、load 就是接回）。已記 [NORMS 待定](../../NORMS/08-待定.md)。
