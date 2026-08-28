# M1 loop 側立法＋便宜機械件 — 規劃 spec

← [build-cycle](../../README.md)｜[roadmap M1](../../../roadmap.md)｜[SPEC](../../../../../docs/SPEC.md)

**閘門 ①／② 由使用者概括授權**（2026-08-28 roadmap 衝刺模式：做完整條他驗成品）。
先裁的問題照 roadmap 記載的建議方向由主線裁，記入 verdicts＋SPEC。

## 一句話

把 SPEC 的 B（命名與版面）、D（交接協定）、E（世界與 git）三區從佔位補成條款、
`docs/aos-folder.md` 整份降為說明；同時落地五樣機械件：**`aos deliver`（＋C ABI）、
投遞檔名唯一化、PC `.aos/turn`、header sidecar 的產生、fsync 與彙整崩潰窗口修補**。

## 本階段裁決（主線已裁，2026-08-28，記入 verdicts）

1. **§27 三小裁決**（照 roadmap 建議）：`.aos/turn` 由 **loop 持有**；**release 成功時
   遞增**；**進 git**。
2. **`.gitignore` 政策取代 aos-folder 十的「整包不進」**（使用者已在 roadmap 拍板）：
   `.runi`／`inst.tempd/`（含各 CPU 的 `*.tempd/`）／`.bad` 不進 git；`.aos/turn` 與
   `.aos/version` 進。E 區立法時寫成條款。
3. **`.bad` 誰清**：彙整者 **MUST NOT** 自動刪；清理歸人或 `aos recover`（M3 實作）。
   「crash 之後要人來處理」的哲學一以貫之。
4. **投遞檔名唯一化**：照 T5 `aos deliver` 規格；若 T5 未定，plan 提案（方向：pid 加
   單調序號或隨機後綴，維持 `<名字>.<副檔名>.<狀況>` 命名標準）。

## 做完之後長什麼樣

1. **SPEC B／D／E 區有條款**（佔位消失）：命名標準（含 `.bad`）、`.aos/` 版面樹、
   `.aos/turn`、版面版本完整條款（F-2 收攏）、三步交接協定、彙整規則、`deliver`、
   投遞檔名、路徑基準、footprint 宣告（SHOULD，§24）、`.gitignore` 政策、快照／回滾
   語意。`docs/aos-folder.md` 開頭聲明全檔為說明。
2. **`aos deliver`**：子命令（吃 stdin 或檔案）＋ C ABI，先 `.temp` 後 `rename`，
   檔名唯一；外部生產者不再手刻投遞協定。
3. **`.aos/turn`**：`aos init` 建立（`0`）；release 成功後遞增。回合編號從此存在
   （PC 誕生）。
4. **header sidecar 的產生**：彙整層寫 `inst-head.json`（`version:1`、`id`、
   `origin:"aggregated"`、`result:null`）。loop **讀** header 留 M2。
5. **修 bug**（gotchas D 表）：`core/inst/src/` 寫檔全補 `fsync`；彙整崩潰窗口用批
   id 去重兜底（同一批不會執行兩次）；`--loop 0`／節流那兩條**不動**（M2 的 loop 工作）。
6. SPEC「已知未決」#2（退出碼表）D 區收編時對齊實作消掉；#3（pid 不唯一）消掉；
   #1（SIGINT 斷點續跑）**原樣保留**——仍未拍板，不在本階段裁。

## 驗收條件

1. SPEC B／D／E 區逐條有編號、位階、來源；grep 無「planned, M1」殘留（已兌現或改標）。
2. `aos deliver` 行為與 SPEC D 區條款一致；同一 process 連續投遞 N 次得 N 份投遞。
3. 崩潰窗口測試：彙整完成、刪投遞前中斷，重啟後同一批**不會**被執行第二次。
4. `.aos/turn`：init 後為 `0`，跑一回合後為 `1`。
5. 彙整產出的批旁有 header sidecar，四欄位齊。
6. `ctest` 全綠（含新測試）；code map 同步；`docs/usage.md` 補 `deliver`。
7. 文件裡寫的每條指令與輸出都真的跑過（feature-dev 鐵律）。

## 明確不做

exec_loop 搬遷、loop 讀 header 分支、`timeout_ms` 搬遷、節流／退避（→ M2）；
`status`／`recover`／`check`（→ M3）；§25／§26／§29 裁決（各自階段）；SIGINT 續跑拍板。

## 動工前讀

[T5 subcommand-specs](../../../experiments/t5-agent-loop/subcommand-specs.md)、
[gotchas](../../../common/gotchas.md)、[debts §2](../../../ideas/machine-shape/debts.md)、
`docs/aos-folder.md` 二／三／六／九／十、`core/inst/src/handoff.cpp`、
[code map](../../../common/code-map.md)、SPEC 全文。
