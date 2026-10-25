# 轉交提案（未拍板，不自行改規格）

使用者本輪已明說：

> **我這邊還在思考，這幾個 choice 我都懸而未決。**

下列是要使用者拍板才能改規格的提案：

1. **是否採納「扁平 `exec`、階層 `core`」這條邊界。**採納則 `aos exec` 永遠只推一個
   self-contained world，不讀 parent；`aos core` 管 proc-table、建立／收割、join 與 commit。
   另要拍板 root 權力先只靠協定守約，還是現在就要求 POSIX 權限／fd／sandbox 強制。

2. **「一個 `aos exec` 推多世界」是哪一種。**命令樹中的多次單世界 exec、單一命令接多個 world，
   或同一 OS 行程內的 `advance_once(World&)`。只有後兩種需要改成 root fd 型內部 I/O；instruction
   與外部處理器看見的路徑仍相對自己的 folder。先保留命令樹的話，**可以延到之後再定**。

3. **是否採納「每世界一份完整 kernel，不動態繼承」。**採納則要定由 core 用模板、
   `kernel.source.json` 或其他方式建立／升級，以及 `.runi` 如何指認本地 kernel 現場。它取代 R1 的
   動態分層選項，不再需要用 parent 解出有效 kernel。

4. **是否採納「完整 `procs/<name>` 世界＋core proc-table」的磁碟形狀。**還要拍板 queue 留在
   各子世界、取消集中 `lanes/`，以及 proc-table 哪些欄位可重建、哪些 generation／join／receipt
   狀態是耐久真源。誰實際推進子世界可以之後再換，不必跟磁碟版面一起定死。

5. **不用 UUID 之後，handle 用相對路徑，還是 `(name, generation)`。**同時拍板 rename、copy、
   detach／adopt 的語意，以及有 `.runi`、待收 receipt 或未結 join 時是否一律禁止搬移。兩種都不
   承諾透明搬家；差別在要不要用 generation 阻擋同名新世界收錯舊結果。

**agent loop 的實作架構不在這批轉交內**（使用者指定留到 R3）。
