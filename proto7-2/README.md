# proto7-2 — 照使用者建議重做 daemon／tick 的第二次試做

← [proto7](../proto7/README.md)｜要合的：[核心 spec](../proto7/spec/core.md)（條號 S-）｜上一次試做：[proto7-1](../proto7-1/README.md)

**proto7-1 之後的第二次試做：照使用者 10-04 的建議（[user-advice](../proto7/user-advice.md)）重做 daemon 與 tick。這一步只有 spec 草稿，還沒有程式。**

## 入口

- **[spec.md](spec.md)**：細部 spec 草稿，每節標 S- 條號。
- **[notes/changes-from-7-1.md](notes/changes-from-7-1.md)**：跟 proto7-1 的對照表（怎麼做 → 改成怎麼做 → 為什麼），最後是**要你決定的 Q 清單**（每題附推薦）。

## 一句話看改了什麼

node 改成登記、不再掃資料夾；tock 預設照固定 interval，提前 tock 變成可選；只剩 tasks.json 一個任務表（一次性任務是裡面 `mode: "once"` 的一項）；任務資料夾照名字重用，不再每回合新增；核心只留「上一次」，更前面的歷史交給可選的歷史 module。
