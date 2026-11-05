# archive — repo 根的封存處

← [INDEX](../wf/INDEX.md)

repo 根層級的過時資料夾放這裡，照 [STRUCTURE archive 規則](../wf/STRUCTURE.md#archive-規則)：不刪、不在維護鏈、內容不改、不維護內部連結；本表只准追加列。

| 項目 | 封存日期 | 取代者／原因 |
|------|----------|--------------|
| [proto/](proto/README.md) | 2026-11-04 | 舊原型（proto），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto2/](proto2/README.md) | 2026-11-04 | 舊原型（proto2 — 從零重來的 aos），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto3/](proto3/README.md) | 2026-11-04 | 舊原型（proto3 — 用 Janet 重寫骨幹），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto3-1/](proto3-1/README.md) | 2026-11-04 | 舊原型（proto3-1（Janet）— 世界是 list，求值走 eval），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto3-2/](proto3-2/README.md) | 2026-11-04 | 舊原型（proto3-2 — 使用者寫偽碼、我補全），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto4/](proto4/README.md) | 2026-11-04 | 舊原型（proto4 — 資料夾模擬 lisp（Janet）），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto4-1/](proto4-1/README.md) | 2026-11-04 | 舊原型（proto4-1 — kernel 直接執行 `.aos/inst`（Python）），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto4-2/](proto4-2/README.md) | 2026-11-04 | 舊原型（proto4-2 — inst.json ＋ cpu ＋ daemon ＋ kernel（Python）），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto4-3/](proto4-3/README.md) | 2026-11-04 | 舊原型（proto4-3 — aos-exec 單發、aos-run 連續、aos-daemon 管一堆、aos-kernel 排程（Python）），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto4-4/](proto4-4/README.md) | 2026-11-04 | 舊原型（proto4-4 — 逐步 lisp（Janet）），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto4-5/](proto4-5/README.md) | 2026-11-04 | 舊原型（proto4-5 — 一次呼叫與 LLM 排程），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto4-6/](proto4-6/README.md) | 2026-11-04 | 舊原型（proto4-6 — 逐步 JSON、Python、Lua），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto4-7/](proto4-7/README.md) | 2026-11-04 | 舊原型（proto4-7 — 簡單的 agent），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto5/](proto5/README.md) | 2026-11-04 | 舊原型（proto5），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto5-2/](proto5-2/README.md) | 2026-11-04 | 舊原型（proto5-2（已納入 proto5，只剩歷史）），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto5.1/](proto5.1/README.md) | 2026-11-04 | 舊原型（proto5.1 — 拿 proto5 的規範去「先做做看」的實驗場），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto6/](proto6/README.md) | 2026-11-04 | 舊原型（proto6 — Linux agent 架構規劃），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto7/](proto7/README.md) | 2026-11-04 | 舊原型（proto7 — aos 時空架構），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto7-1/](proto7-1/README.md) | 2026-11-04 | 舊原型（proto7-1 — 照 proto7 核心 spec 一路做到 kernel／agent 的試做），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [proto7-2/](proto7-2/README.md) | 2026-11-04 | 舊原型（proto7-2 — 照使用者建議重做 daemon／tick 的第二次試做），由 [proto8](../proto8/README.md) 取代；使用者 11-04「舊的proto1~7都封存」 |
| [aos-v1/](aos-v1/) | 2026-11-05 | 甲代 C++（08～09 月的單一執行檔 `aos`：根 `CMakeLists.txt`／`CMakePresets.json`／`vcpkg.json`、`cmake/`、`common/`、`app/`、`core/`、`modules/`、`docs/`、`.aos/`、`playground/`、`brief/`、`reference/`，原樣搬來），由 [proto8](../proto8/README.md) 取代；使用者 11-05「大重構七題都照推薦吧，我覺得OK」（[arch-refactor 方向題 1](../proto8/thinking/2026-11/05/arch-refactor/README.md)） |
