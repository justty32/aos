# 三條鐵律與明確不做的事

← [roadmap 導覽](README.md)｜[文件索引](../README.md)

> 這個檔裝的是：從 `agent-machine` 借來的三條鐵律，以及明確不做的事——這份 roadmap 的邊界。

## 五、三條鐵律

從 [`../agent-machine`](../../../agent-machine/START-HERE.md) 借的——**只借這三條**，不借
它整套 Task tree／Receipt／中央 store：

1. **先寫下意圖，再造成外部作用；證據不完整就停住，不自動重跑。** 回合模型的「先取走
   再執行」已經是這條的一半；缺的是「停住不自動重跑」要寫進 T2 的驗收。
2. **可攜的語意，和「這台機器上正在跑什麼」，要分開放。** `.aos` 若之後要進 git，
   `running/`、PID、鎖這類東西**一定不能**跟著進去，否則 clone 到別台機器會以為舊
   process 還活著。T2 建立 `running/` 的同時就要把它 gitignore 掉。
3. **原型的檔名、JSON 欄位、目錄名都不是 ABI。** T1–T3 的版面可以改；真的要凍結是
   之後另外一次決定。

## 六、明確不做的事

寫在這裡免得被當成漏做：

- **不做中央 store、scheduler、Task tree、Receipt、crash recovery 的完整矩陣。**
  那是 `../agent-machine/full/` 的重量級設計；aos 目前的模型刻意輕。
- **不做 `core/daemon` 這個小專案。** 持續執行是 `aos exec --loop 0` 這個旗標。
- **不做全域 LLM daemon 與跨資料夾排程。** 那要等「一個資料夾跑得動」之後才有意義。
- **不做 Git checkpoint、FUSE、VFS。**
- **不繼續 llmkit 移植的 S2／S5**（見 [`reference/PORTING.md`](../../reference/PORTING.md)）。
  [D4](decisions.md#d4) 已定：`core/llms`／`core/tooljson` 先不動，要排在 agent loop 之後。
  **`reference/` 仍然不要刪**：之後改造時還要拿 llmkit 原文對照。
- **不碰 `core/llms`／`core/tooljson`。** 它們現在的形狀不符合模型，但那是**擱置**，
  不是待修——別急著重寫，也別再往裡面投資。
- **不先改 `docs/overview.md`。** 等 T1 能跑再改。
