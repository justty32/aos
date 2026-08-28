# 這台機器的形狀：指令的地位、loop 的職權、資料夾與規範

← [ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

使用者**迫切想確定**的三件事：`inst` 作為 CPU 指令的地位、稍微外圈的 loop、以及承載整套
體系的資料夾結構／所需程式／規範。這一組逐項拷問這三塊。

## 若只挑事情做

1. **給「批」名字與 header**（instruction 第 1、2 條 ＋ loop 第 6 條是同一個決定）——同時
   解決 ISA 版本、指令來源、loop 分支所需的旗標。想確立的「inst 作為 CPU 指令的地位」，
   缺的正是這個。
2. **補 `deliver`**（layout-and-spec 第 11 條）——最便宜，擋掉最多真實故障。

內容已拆進 [`machine-shape/`](machine-shape/README.md)。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [instruction](machine-shape/instruction.md) | 真正的指令是「批」而批沒有名字、ISA 沒有版本、有指令沒有程式（`$ref` 若能引指令就是副程式）、沒有架構狀態只有檔案系統、von Neumann 但沒有 W^X | 要確立 inst 的 ISA 地位之前 |
| [debts](machine-shape/debts.md) | **已下裁決的欠帳**（不是待辦）：GPU 模型讓兩顆 CPU 共寫一份記憶體卻沒有記憶體模型；git 當快照撞上 `.aos/` 的暫態，回滾含 `.runi` 的 commit 會讓世界死鎖 | 想知道哪些問題是自己選出來的 |
| [loop](machine-shape/loop.md) | loop 沒有可分支的狀態（旗標暫存器缺席）、**官方寫法 `--loop 0` 是忙碌輪詢**、**失敗算「有做事」所以關掉唯一的節流閥**、除了 3 以外的回傳值全被忽略、loop 現在住在 `core/inst` 裡跟分層規劃相反、一世界一 loop 沒有排程器、沒有 reset line | 要動 `exec_loop` 之前 |
| [layout-and-spec](machine-shape/layout-and-spec.md) | 命名標準延伸不到 events／status、版面也沒有版本、沒有 `status`／暫停等控制介面、**最該有的 `deliver` 正好沒有**、規範已有三份真相且在漂 | 要動 `.aos` 版面或規格之前 |
