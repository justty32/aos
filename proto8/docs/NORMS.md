# proto8 規範

← [proto8](../README.md)｜概念層：[CONCEPTS.md](CONCEPTS.md)｜慣例：[CONVENTION.md](CONVENTION.md)｜程式：[impls/](../impls/README.md)（C++，唯一實作）、[cmd/](../cmd/README.md)（Python：aos-tick、aos-tools、aos-daemon-ctl 等）、[templates/](../templates/README.md)

**比起實作，更重要的是規範**（C-45）。四層：

| 層 | 是什麼 | 在哪 |
|---|---|---|
| 概念 | aos 怎麼看世界（例：時空＝tick-tock＋資料夾；資料夾＝程式） | [CONCEPTS.md](CONCEPTS.md) |
| 規範 | 從概念推出來、大家都要守的 | 本檔（條文按主題放在 NORMS/ 分檔） |
| 慣例 | 我們自己人寫 aos agent 時照抄的標準形狀（P-05～P-44），**不要求別人守** | [CONVENTION.md](CONVENTION.md) |
| 程式 | 符合規範的實作與範例，**不要求一定用** | [proto8/impls](../impls/README.md)（C++，唯一實作：[aos-exec](../impls/aos-exec/README.md)、[aos-loop](../impls/aos-loop/README.md)、[aos-fsm](../impls/aos-fsm/README.md)、[aos-daemon](../impls/aos-daemon/README.md) 等命令列（全表見 impls README），inst 是 C lib [inst](../impls/inst/README.md)、指示詞是 [aos-directive](../impls/aos-directive/README.md) 庫；刻意沒有 aos-inst 命令列）；例外 [proto8/cmd](../cmd/README.md) 是 Python（aos-tick、aos-tools、aos-daemon-ctl、aos-eca-turn 等）；[proto8/templates](../templates/README.md)（兩個範本：eca-claude、agent-fsm）。Python 版的其他幾支刪了（使用者 10-23「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++、tick 先留 Python），舊的 lib 在 git 歷史 |

本檔（含分檔）只收使用者親口定下的規範（條號 N-）；AI 提的、還沒定的放在最後「待定」，不算數。作廢的條號只留在條號表；沒有實作的條文標「現無實作」。「+x 沒 `#!`」的檔三處（可執行檔入口、argv 陣列入口、單子 `argv[0]`）一律用 `/bin/sh` 跑（使用者「乙」，N-59 第 5 件、N-60）。各條的出處見[附錄2 各批出處](NORMS/附錄2-各批出處.md)；舊名 → 現名見[附錄3 舊名對照](NORMS/附錄3-舊名對照.md)。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按標題（再按條號／頂層清單項）拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [命名](NORMS/命名.md) | 命名的規則：10-23 命名統合、要跑什麼＝exec、10-23 晚入口改名、計數一律 counter_*、時間點一律 _at、上限一律 max_*、控制自身的窗叫 ctl／state，管子項的叫 procs_* |
| [附錄3 舊名對照](NORMS/附錄3-舊名對照.md) | 舊名 → 現名（程式、環境變數、檔名、JSON key） |
| [主題](NORMS/主題.md) | 主題（10-15 使用者定：概念、規範、實作之外，再用主題分）；條號表與各批出處 |

<a id="主題10-15-使用者定概念規範實作之外再用主題分"></a>
<a id="條號表與各批出處"></a>
