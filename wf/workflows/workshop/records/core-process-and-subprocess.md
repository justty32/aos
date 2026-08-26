# 主題：核心行程、子行程，與外部處理器的契約

← [workshop](../README.md)

這場紀錄已拆成資料夾：**[core-process-and-subprocess/README.md](core-process-and-subprocess/README.md)**（檔頭資訊、續場 session id 與導航都在那裡）。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [使用者拍板的三條](core-process-and-subprocess/decisions.md) | R1 之後使用者當場拍板的三條（`kernel.json` 收、`func` 拆成 job 與 lane、多核學 Linux），以及他同一輪注入的新概念「行程有自己的資料夾」 | **要知道哪些已經是前提、不必再議** |
| [R1 想法池](core-process-and-subprocess/r1.md) | R1（各自發想）的四段：核心系統指令、匯聚歸屬、行程定義、`dofuncs`、多核、零 lib 契約、exe／lib 切線 | 想知道那三條拍板是從哪些理由長出來的 |
| [R2 想法池](core-process-and-subprocess/r2.md) | R2（延伸／組合／變體）的四段：巢狀拓樸 A／B、job→lane 升格、root 的至高權力清單、kernel 分層合成 | 要談子行程佈局與親緣綁路徑還是 UUID |
| [轉交提案](core-process-and-subprocess/handoff.md) | 四條**未拍板**、要使用者決定才能改規格的事 | 要拍板下一步改什麼規格時 |
