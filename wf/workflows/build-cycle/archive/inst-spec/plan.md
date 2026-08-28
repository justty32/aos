# inst 與序列化定案 — 實作 plan

← [spec.md](spec.md)｜[build-cycle](../README.md)

> **閘門 ② 由使用者放棄書面審**（2026-08-28「都OK，然後開分支去做」）。同日定下團隊
> 模式：主線（Fable）規劃與立法、plan 可開 Fable agent、實作開 Opus（可指揮 sonnet）、
> 審核另開 Opus；本項目（M0）純文件且判斷密度高，由主線直接執行。分支：`roadmap-run`。

## 步驟

1. **寫 `docs/SPEC.md`**（主線親寫，憲法不外包）：地位三段（唯一 normative／裁決進入
   流程／三向標記）＋六區骨架＋ inst 側條款（A、C、F 區）＋「已知未決」附錄。
2. **`core/inst/docs/format.md` 降級**：欄位表與驗證狀態表**搬走**（指向 §C-3／§C-6），
   開頭加主從聲明；敘事、理由、範例保留。
3. **`docs/aos-folder.md`** 開頭加一行：回合語意與 instruction 格式的 normative 在
   SPEC；版面與交接協定的收編在 M1。
4. **入口與舊自稱清理**：`docs/README.md` 加 SPEC 一列；全 repo grep「唯一真源」──
   `wf/INDEX.md` 與 `wf/SESSION-LOG.md` 對 aos-folder 的「唯一真源」稱呼改指 SPEC。
5. **裁決記錄**：verdicts A 表加五條（§30／§22／header sidecar＋B1 v1／$ref 不取指令／
   三向標記）；B 表第 1、3、10、11、12 條補裁決註記；`machine-shape/instruction.md`
   §3／§22 與 `layout-and-spec.md` §30 各補一行裁決。
6. **roadmap M0 標完成、SESSION-LOG 更新、本項目夾移 `archive/`**。
7. **驗收**：spec 九條逐條過（含 grep、`git diff --stat` 只有 `.md`、WSL 全綠 build）。

## 條款對照表（spec 驗收 2，收尾時核）

| spec 條款表 | SPEC 編號 |
|---|---|
| 批＝真正的指令；一回合＝一整批 | §A-1（原子接受 §A-2） |
| 一回合內沒有資料流 | §A-3 |
| 嚴解析、鬆執行 | §C-1 |
| 欄位表／指示詞／驗證狀態表 | §C-3／§C-4／§C-6 |
| 沒有任何上限＋不可信輸入 | §C-7 |
| 沒有 inst.json＝停留本回合 | §A-4 |
| 批 header（planned, M1） | §C-8 |
| 格式版本 vs 版面版本 | §F-1／§F-2 |

## 風險與退路

- **搬表手滑改字**：搬家用複製貼上不重打；搬完 diff 目視核對。
- **SPEC 寫出未裁條款**：三向標記規則兜底——未拍板矛盾一律進「已知未決」。
- **WSL 建置不可用**：docs-only 改動，若 WSL 壞掉則記 WAIT_USER 請使用者跑一次，
  不阻塞 commit（`git diff --stat` 已證零程式改動）。
