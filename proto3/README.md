# proto3 — 用 Janet 重寫骨幹

← [AGENTS](../AGENTS.md)｜前一代 [proto2](../proto2/README.md)｜Janet 參考 `~/projs/langlab-janet`

2026-09-08 開的。方向（使用者拍板）：**骨幹重寫、工具包與工作室 preset 之後沿用**。
骨幹用 Janet（1.41.2、jpm、spork，全裝在 `~/.local`）。**目前只在記憶體裡跑**，還沒存磁碟、
沒接 Python 工具包、沒有 team／agent 交流——這些都先不動，先把基礎架構搭穩。

## 核心想法：Janet 資料就是檔案系統

- 一個**世界**＝一個 table（`@{}`）。裡面放什麼都行：函式、資料、小孩世界。
- **跑世界＝對它求值**：`world/dotick` 走一遍元素，碰到 `:func-tick` 就叫它（把世界自己傳進去），
  碰到 `:kids` 裡借父時鐘的小孩就跟著求值一格。資料夾裡的資料夾，就是 list 裡的 list。
- **path 就是身分**：`world/all` 是整棵樹（path → 世界），`world/at` 用 path 找。
  小孩 path＝父 path＋`/`＋名字；`kill` 連子孫一起消失。
- **一個世界一個鐘**：`kernel/register` 登記；鐘每 interval 對世界求值一格。
  小孩 `:clock :shared`（預設）借父的鐘，`:own` 自己登記一個。
- **LLM 是另一個世界**：有自己的鐘和佇列，agent 把請求丟進去就走自己的格；
  結果以信寄回請求者 inbox（pending → running → done／failed 三態）。
- **等待和喚醒只有一個原語**：`agent/wait-for`——登記「等到什麼算數、等到了做什麼、等幾格放棄」，
  之後每格由時鐘替它檢查。誰叫醒它？永遠是時鐘。這是 proto2 補了三十幾條補丁才學到的那一課
  （見 [backbone-pains](notes/2026-09-08-backbone-pains.md)）。
- **格有會計**：每個世界 `:ticks` 記這格在幹嘛（busy／wait／idle／frozen）。

## 檔案

```
project.janet        jpm 專案宣告（依賴 spork）
src/world.janet      世界：make／dotick／at／spawn／kill；信箱 send／take-mail／say
src/kernel.janet     時鐘：register／unregister／pause／continue／ls；同步 step-all／run、非同步 start
src/llm.janet        LLM 世界：make／ask／tick；現成 engine：echo-engine、script-engine（測試用劇本）
src/agent.janet      agent（先勾輪廓，之後會改）：wait-for 原語；idle→think→wait→act 四態
src/main.janet       範例：報時世界、LLM、agent（借鐘小孩＋自己鐘的小孩）、旁觀者
test/basic.janet     36 條：求值／會計／小孩／信箱／鐘／LLM 三態／agent 一輪與逾時
notes/               設計前的盤點（packs-contract、backbone-pains）＋使用者口述想法（ideas）
variant-cl/          同一套骨幹的 Common Lisp 版（SBCL），一比一對照，見它的 README
```

## 怎麼跑

```sh
cd proto3
janet src/main.janet 8          # 同步走 8 格就停（interval N 的鐘每 N 格動一次）
janet src/main.janet async 5    # 非同步：每個鐘一條 fiber 各走各的，5 秒後收
jpm test                        # 跑測試
```

## 還沒做（刻意）

存磁碟（Janet 資料 ↔ 檔案）、接 proto2 的 Python 工具包、team／預算、agent 之間交流、
真的 LLM 引擎、agent 狀態機的完整版（重送／卡住／每題上限）。
