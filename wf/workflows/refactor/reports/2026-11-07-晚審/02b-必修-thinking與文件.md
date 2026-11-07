# 晚審必修 19～25：11-07 thinking、不足清單、交棒、第二輪設計與 knowledge 文件落後於程式和裁定

← [入口](README.md)｜上一份 [02](02-必修-memory與條文.md)｜下一份 [03 設計問題](03-設計問題.md)

路徑沒特別寫的，都相對於 `proto8/thinking/2026-11/07/`。

## 19. 當天索引缺列、狀態寫成「未 commit」

- **檔:行**：
  - `README.md:7-10`：沒列 edge-1107、kb-ideas；`:9` 把 daemon-prune 寫成「未 commit」，其實已經在 `9edcf15d5`。
  - `../README.md:15`：份數寫 1。
  - `daemon-prune/README.md:1`、`:9`：寫「未 commit」。
  - `arknights-kb/README.md:3`（knowledge-write「未實作」）、`:58`／`:61`（同一件事寫兩次，「三題待裁」和「6 題」打架）、`:64-78`（分檔目錄缺 04～10，也缺 07）。
  - `arknights-kb/03-W1到W4施工結果.md:5`、`:100`：寫「未 commit」「未列入生成冊」，但生成冊已經收了。
  - `proto8/thinking/2026-11/05/knowledge-write/README.md:5`：寫「只規劃、沒改程式」。
  - `proto8/thinking/2026-11/06/os-impl/README.md:41`：沒寫 09 的 A 已經被 B 翻掉。
- **建議**：補列、改狀態，目錄補齊；os-impl README 句尾加上「已被 11-07 B 翻」並連到 07。

## 20. 不足清單和交棒落後於 P1～P5 與 B

- **檔:行**：
  - `arknights-kb/不足清單.md:11`（#3）、`:16`（#8）、`:19`（#11）、`:20`（#12）、`:26`（#18）、`:27`（#19）、`:30`（#22）：都還寫「未處理」。`61a7ed360` 和 B 已經修了，`10-第二輪設計.md:13-17` 自己也寫了哪條對應哪條。
  - `arknights-kb/交棒.md:30-36`：整段是第一輪結束時寫的；`:32` 引錯三個不足編號（#1→#3、#4→#1、#2→#4）。
  - `交棒.md` 另有前後打架：`:15` 對 `:10`、`:19` 對 `:39`。
- **建議**：不足清單逐條標「已修（commit）」或「部分修」（#3 的內建 forward 還沒做）；交棒刪掉舊段、統一說法。

## 21. 第二輪設計還是舊圖，gpt 會照它施工

- **檔:行**：
  - `arknights-kb/10-第二輪設計.md:27`：links 還是一處提及一條、用 `at`。代定 15 已經改成一個目標一條、位置放進 `spans`。
  - `:37`：降級階梯寫「luna→本機」；`:46` 的代號沒有 terra。代定 9 已經改成 sol→terra→luna→本機。
  - `:34`：還寫「namer 先取名」。得失 `:22` 已經改成建節點時才命名。
- **為什麼必修**：第 5 行自己寫著「本檔是 Claude 的設計決定，gpt 照做」。
- **建議**：改正文，或在這幾處註明「已由代定 N 取代」。

## 22. 07、daemon-prune、edge-1107 留著被推翻的方案、過程和過時狀態

- **檔:行**：
  - `arknights-kb/07-停不下與消失.md:1`：還寫「待使用者裁」。`:22-40` 的 A/B/C 選項表已經被 B 取代。`:42-46` 和 `:48-58` 是同一個裁定寫了兩段。
  - `daemon-prune/README.md:61-126`：原始指令輸出，證據指到 `/tmp/aos-daemon-prune.*`，重開機就沒了。
  - `edge-1107/README.md:3`：寫「沒修」，但 `00a0a1b14` 已經修了。`:18-57` 是逐個實驗的過程；整檔 10 KB，超過 8 KB。
- **對照**：user/03「只留原文、決定、結論」；STRUCTURE 觸發 A。
- **建議**：只留使用者原話、裁定與落實、還沒修的限制，其餘濃縮。要搬走或刪掉的整份內容另見 [裁定 11](04-要使用者裁定.md)。

## 23. 使用者六題的裁定沒落實到試驗場與設計檔

- **檔:行**：`~/code/playground-ak/defs/llm_team/kernel.json:8`、`:12`，`defs/llm_main/kernel.json:7`、`:11`（`max_calls: 3000`）；`arknights-kb/代定清單.md:10`（代定 4 沒標已裁）；`arknights-kb/02-設計.md:35`、`02-設計-修正.md:10`、`:25-28`
- **對照**：`arknights-kb/README.md:82` 使用者原話「5.不限制」。
- **建議**：試驗場拿掉 `max_calls`；如果 kernel 一定要這個值，就寫明理由。代定 4 和兩處「要使用者裁」都補上已裁註記。

## 24. 不足清單是同質記錄表，該改走資料檔

- **檔:行**：`arknights-kb/不足清單.md:7-33`（8,964 B、27 列；wf-lint 報 BIGLIST）
- **對照**：鐵律 6；[data-files](../../../common/data-files.md)。
- **建議**：轉成 `wf-table/1` 的 json，md 只留導語。代定清單是給使用者回來聽報告用的，可以留在 md。

## 25. knowledge 文件跟程式對不上

- **檔:行**：
  - `proto8/knowledge/README.md:29`：寫葉節點只有 `.md`，但 `memory_fs.py:9` 也收 `.json`，P3 還加了 `#/指標`。
  - 同檔 `:3`：沒列 memory_write。
  - `proto8/knowledge/aos/cli/daemon.md`：完全沒提 prune。
- **建議**：補 `.json` 葉、`#` 指標、memory_write 和 prune 一節（給 agent 讀的部分用英文寫）。
