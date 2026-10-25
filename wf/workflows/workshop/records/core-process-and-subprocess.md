# 主題：核心行程、子行程，與外部處理器的契約

← [workshop](../README.md)

本場紀錄在資料夾 **[core-process-and-subprocess/README.md](core-process-and-subprocess/README.md)**（檔頭、續場 session id、導航）。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [使用者拍板的三條](core-process-and-subprocess/decisions.md) | 已拍板的三條（`kernel.json` 收、`func` 拆成 job 與 lane、多核學 Linux）與使用者注入的「行程有自己的資料夾」 | **要知道哪些已是前提** |
| [R1 想法池](core-process-and-subprocess/r1.md) | 核心系統指令、匯聚歸屬、行程定義、`dofuncs`、多核、零 lib 契約、exe／lib 切線 | 要找外部處理器契約清單時 |
| [R2 想法池](core-process-and-subprocess/r2.md) | 巢狀拓樸 A／B、job→lane 升格、root 的權力清單、kernel 分層合成 | 要談子行程佈局、親緣綁路徑還是 UUID |
| [轉交提案](core-process-and-subprocess/handoff.md) | 四條**未拍板**、要使用者決定才能改規格的事 | 要拍板改什麼規格時 |
