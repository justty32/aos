# aos-exec

`aos-exec - 在工作區裡執行一個資料夾程式`（NAME，C-54 R1）

**一句話：`aos-exec [--ws WS] [--stack S] [--stack-lazy] [--dotenv-override] XXX [ARGS...]`——在工作區 WS 執行 XXX 這個程式：定好工作區、走進 XXX（cd、讀那裡的 `.env`）、挑出入口、備好環境變數、開跑。**
一個 lib（`lib/libaos-exec.a`，公開標頭 `aos/exec.hpp`）加一支薄薄的命令列（`bin/aos-exec`，只叫 `run_cli`）。連 aos-util、aos-directive（解單子、argv 陣列與 JSON `.env` key 的指示詞）、aos-inst（C，靜態版 `aos-inst-static`）。全家慣例見 [impls/README.md](../README.md)。
aos-inst 是 C lib、沒有命令列，inst 單子由 aos-exec 在行程內跑。[aos-loop](../aos-loop/README.md)、[aos-fsm](../aos-fsm/README.md) 的每一次、[aos-daemon](../aos-daemon/README.md) 的子 loop，都是在 fork 出來的子行程裡呼叫這個庫的 `run_cli`（等同起一支 `aos-exec -- 目標 參數...`）。

像在門口換好鞋再進屋：它只負責帶路和換鞋，進屋之後做什麼是入口的事。`.env` 就是門口那張「進來先把這些設好」的紙條。入口是可執行檔或 argv 陣列時它不留在屋裡（exec，結束碼就是入口的碼）；
入口是 inst 單子時它留在門口當監工：在行程內交給 aos-inst 起子程式（自成行程群組）、把收到的訊號轉給整群、等它結束，再以子程式的碼結束。單子的 `timeout_cycles` 與 `timeout_ms` 擇一：有樹時鐘比格數、沒時鐘換成毫秒；到期後以牆鐘 `grace_ms` 收尾（[欄位](docs/03-環境變數.md)）。

```sh
aos-exec --ws ws agent        # 跑 agent/_entry（或 agent/_entry.json），工作區 ws
aos-exec cfg.json#/tools/stamp a b   # 跑 cfg.json 裡 /tools/stamp 那個值，沿用 $AOS_WS，參數 a b
echo hi | aos-exec tool              # tool/_entry.json 是 {"argv": ["cat"]}：單子沒寫串流＝接呼叫者的，印 hi
```

語意以規範為準：環境變數 N-57、命令列 N-58、只做哪幾件事 N-59、錯誤 N-60、找入口與種類 N-61、`#/` 尋址 N-62 在 [NORMS/10](../../docs/NORMS/10-基礎設施-定義與工作區.md)；指示詞 N-45 在 [NORMS/06](../../docs/NORMS/06-基礎設施-命令列與指示詞.md)；inst 在 [NORMS/03](../../docs/NORMS/03-基礎設施-inst.md)。下面寫的是這支程式的用法與實作上的細節。

**轉交的碼**（stdio-unify R8）：退非 0 時 stderr 有 `aos-exec: error:` 這行＝我錯（退 1）；沒有＝入口自己的碼。`aos-exec --help`＝英文說明印 stdout、退 0。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法](docs/01-用法.md) | 用法：開頭、一跳（hop）：走進去、讀 .env、挑入口 |
| [02-種類](docs/02-種類.md) | 用法（續）：種類（classify）、.env |
| [03-環境變數](docs/03-環境變數.md) | 用法（續）：環境變數（定義在 N-57；照 P-39 分三類；六個 AOS_* 加 PATH）、inst 單子 |
| [04-元素與實作注意](docs/04-元素與實作注意.md) | 元素；實作注意 |
| [05-錯誤代號等](docs/05-錯誤代號等.md) | 錯誤代號；跟規範／慣例的已知差異；建置與測試 |

<a id="用法"></a>
<a id="一跳hop走進去讀-env挑入口"></a>
<a id="種類classify"></a>
<a id="env"></a>
<a id="環境變數定義在-n-57照-p-39-分三類六個-aos_-加-path"></a>
<a id="inst-單子"></a>
<a id="元素"></a>
<a id="實作注意"></a>
<a id="錯誤代號"></a>
<a id="跟規範慣例的已知差異"></a>
<a id="建置與測試"></a>
