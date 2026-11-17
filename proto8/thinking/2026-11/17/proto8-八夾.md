# 11-17 proto8 頂層 17 個夾能不能精簡到 8 個：三個方案、推薦與要你裁的題（只規劃、沒動手；AI 寫的方案，還沒裁）

← [proto8](../../../README.md)｜分檔：[01-事實表](proto8-八夾/01-事實表.md)、[02-方案細節](proto8-八夾/02-方案細節.md)、[03-要裁的題](proto8-八夾/03-要裁的題.md)

使用者原話（11-17）：「proto8/底下好多個資料夾。我在想，是否能精簡到只剩下八個？去想想，規劃一下給我看」

## 先講結論

- **做得到。** 推薦方案甲：留下 `impls cmd lib templates knowledge docs thinking archive` 八個。
- **分三步走**：第一步只併六個小夾（17 → 11），便宜、不碰活樹，現在就能做；第二步把 `py` 併進 `lib`、`kernel` 併進 `templates`（11 → 9），這步會動到活樹的夾名和「靠位置找模組」那批地雷，建議跟你 11-16 說的路徑規劃一起做；第三步 `extras` 解散（9 → 8），等 aos-view 改名時一起搬。
- **代價**：第一步小工；第二步中工（約 30 處程式路徑、換樹腳本 3 處夾名表、兩棵活樹各換一次）；第三步小～中工。
- **只要不想動活樹，最少只能到 9 個**（方案丙）。`thinking` 和 `docs` 不建議搬：`thinking` 一搬，裡面約 5300 行連結的相對路徑全要重算。

「八個」我算的是頂層**資料夾**；`README.md`、`_index.json`、`install.sh` 三個檔不算、留原地（題 1）。

## 現在的 17 個，分五類

| 類 | 夾 | 搬它貴不貴 |
|---|---|---|
| 會被抄進活樹的（`~/aos-home` 裡同名） | `lib templates knowledge py kernel` | 貴：換樹腳本寫死這五個名字，`$AOS_HOME/lib` 這種寫法到處都是 |
| 只在 repo 跑、`install.sh` 連進 PATH 的 | `impls cmd` | 貴：`install.sh`、建置腳本、22 支指令的 `../../../py` |
| 程式用的小資料 | `cases schema feedback` | 便宜：各只有一兩處程式在找它 |
| 文件與紀錄 | `docs thinking notes user-advice archive` | `docs`、`thinking` 很貴（連結多），其餘便宜 |
| 其他 | `extras`（還沒定位的嘗試）、`bin`（空的，只剩沒進 git 的快取） | `extras` 中等；`bin` 直接刪 |

每夾的大小、檔數、誰靠它的路徑，在 [01-事實表](proto8-八夾/01-事實表.md)。

## 三個方案

### 甲：順著分層併（推薦）

```
proto8/
  impls/      C++ 的基礎層與標準庫（不動）
  cmd/        人打的指令（不動；之後收 aos-view、換樹工具）
  lib/        腦叫的工具 ＋ py（共用 Python 模組）＋ schema ＋ cases
  templates/  agent 範本 ＋ kernel 範本
  knowledge/  給 agent 讀的知識庫（不動）
  docs/       條文 ＋ notes
  thinking/   討論紀錄 ＋ user-advice
  archive/    封存（＋ extras 裡不再做的嘗試）
```

- 為什麼：C-74 最上層本來就是「agent／kernel」並列，`kernel/` 的 README 自己說放的是「可以直接抄去用的 kernel 範本」；`py` 是 Python 共用模組，跟 `lib` 的差別只是「誰 import」。併完活樹從五夾變三夾，換樹要顧的名字變少（順著 11-15「換樹不該要跑一堆腳本」）。
- 代價：動到活樹夾名，家機、公司兩棵都要換一次樹。

### 乙：會進活樹的收成一夾

```
proto8/
  impls/  cmd/
  home/       ＝ $AOS_HOME 指的那一包：lib py kernel templates knowledge 原樣放進來
  docs/  thinking/  archive/  extras/
```

- 只剩 7 個。為什麼：repo 跟活樹之間寫死的名字從五個變一個（C-51「固定名字要限縮」），換樹＝抄一個夾。活樹裡的夾名完全不變。
- 代價最大：約 820 個檔往下一層，這些檔裡往外的相對連結全要重算；22 支指令與上百支測試的路徑要改；而且改掉你 11-13 定的「`AOS_HOME`＝proto8 本身或它的抄本」（變成 `proto8/home`）。大工。

### 丙：活樹與程式路徑都不動

```
proto8/
  impls/ cmd/ py/ lib/ kernel/ templates/ knowledge/   （七個程式夾原樣）
  docs/       條文 ＋ notes
  thinking/   討論紀錄 ＋ user-advice
```

- **到不了 8，最少 9**，而且要 `archive` 搬去 repo 根的 `archive/proto8/`、`extras` 解散。硬要 8 得把 `thinking` 搬出 proto8，不划算。
- 為什麼列它：只改文件連結，活樹零風險。

## 對照

| | 甲 | 乙 | 丙 |
|---|---|---|---|
| 最後幾個夾 | 8 | 7 | 9 |
| 活樹夾名 | 5 → 3（要換樹） | 不變 | 不變 |
| 程式路徑大約改幾處 | 約 30＋測試 | 上百 | 不到 10 |
| 換樹腳本 | 夾名表 3 處改短 | 3 處加一層，之後可簡化成抄一夾 | 不改 |
| 歷史紀錄裡會過時的連結行 | 約 410 | 約 1150 | 約 310 |
| 工 | 中（分三步） | 大 | 小～中 |

數字是 grep 估的，算法與細節在 [02-方案細節](proto8-八夾/02-方案細節.md)。

## 推薦

**甲，分三步，每步單獨交、單獨退得回。** 理由：`thinking`、`docs`、`impls`、`cmd` 這四個最貴的都不動；併的兩對（`py`→`lib`、`kernel`→`templates`）都對得上你定的分層；活樹變簡單。

**只想先拿最便宜的改善**：只做第一步，17 → 11，不碰活樹、不碰換樹腳本：

| 現在 | 去哪 | 要改的程式 |
|---|---|---|
| `bin/` | 刪（空的） | `.gitignore` 一行 |
| `schema/` | `lib/schema/` | 0～1 處（找法本來就是往上找；順便讓活樹裡也找得到） |
| `cases/` | `lib/aos/measure/cases/` | measure 的測試 2 處 |
| `feedback/` | `wf/advices/feedback/` | `storage.py` 一個函式＋測試 |
| `notes/` | `docs/notes/` | 無 |
| `user-advice/` | `thinking/user-advice/` | 無 |

## 要你裁的題（選項與後果在 [03](proto8-八夾/03-要裁的題.md)）

1. 頂層三個檔算不算在八個裡——推薦不算、留原地。
2. `thinking` 留在 proto8 嗎——推薦留、原地不動。
3. `archive` 留在 proto8 還是搬去 repo 根 `archive/proto8/`——推薦留。
4. `extras` 解散還是留著；aos-view 何時搬——推薦解散，等 aos-view 改名那次一起。
5. `user-advice` 去哪——推薦 `thinking/user-advice/`。
6. `feedback` 去哪——推薦 `wf/advices/feedback/`（你 11-17 說過「也幫我弄進 wf/advices」）。
7. `notes` 去哪——推薦 `docs/notes/`。
8. `py` 要不要併進 `lib`——推薦併，但跟路徑規劃同一次做。
9. `kernel` 要不要併進 `templates`——推薦併成 `templates/kernel/`。
10. 跟 11-16 的「路徑規劃」要不要併成同一次——推薦第一步不等，第二步等路徑規則定了再搬。
11. 舊紀錄裡指到舊夾的連結怎麼辦——推薦照 11-06 的前例：舊紀錄不改，在 thinking README 的改名表加一段。
12. 空的 `bin/` 刪不刪——推薦刪（刪檔要你點頭）。

## 沒查到、沒把握的

- 連結數是 grep 估的「行數」，不是精確連結數；乙案「往外的相對連結要重算幾條」沒量。
- 家機那棵樹沒看到，只看了公司 WSL 的 `~/aos-home`（五夾：`kernel knowledge lib py templates`，11-17 08:47 抄自 `d5f47c890`）。
- 活樹裡 `lib/aos/comm/check.py` 現在找不找得到 `schema/`：照程式讀是往上找、活樹沒有這個夾，應該會報 `SchemaMissing`；沒實跑。
- `.vscode/settings.json`、`.claude/settings.json` 沒有寫死 proto8 的子夾名（grep 過）；`wf/public`、家機上的個人腳本有沒有寫死，沒查。
