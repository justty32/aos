# 開機即世界：`~` 是主世界，agents／pus 是子世界，`aos daemon` 統管多個 run

← [ideas](README.md)｜相關 [nested-worlds](nested-worlds.md)、[scheduling](scheduling/README.md)、[contacts](tools/contacts.md)、[usability-target](usability-target.md)

**使用者 2026-08-30 原話（節錄整理）**：

> 之後的使用場景很可能是我剛開機，然後就直接在 `~/` 開 `aos run`。我的 `~/agents/botA`、`~/agents/botB` 因為都被登記在
> `~/.aos` 下作為會被一同 tick 的子世界，所以…。而且這件事很可能會被我弄成 systemd。
> 除此之外，很可能我會有 `~/pus/llms`，其下有 `~/pus/llms/pi-ds`、`lm-local`… 這些，同樣被我 `~/` 的 `aos run` 運行，
> 然後一些 agent loop 就是把相關要求投遞到這邊。
> 再還有，我會希望 agent loop 運行中的時候，可以不指定特定 llm pu，而是說明想要 tier A 聰明的 llm pu。
> 還有，如果直接在 `~/` 開 `aos run`，會導致所有子世界都要等其他子世界的指令做完才能進入下個 tick，所以我會希望各子世界
> 可以有自己的循環——想要跟主世界同步 tick 沒問題，想要自己有自己的 tick 也可以。所以 `~/` 底下很可能是 `aos daemon start`，
> 其中包含多個要 `aos run` 的目標資料夾，並且會防止多個 `aos run` thread 互相影響。

## 拆成六件事（方向是使用者的；括號是跟現況的對應）

| # | 要的東西 | 現況對應 | 狀態 |
|---|---|---|---|
| 1 | `~` 是主世界，開機（systemd）就 `aos run`／`aos daemon start` | `~/.aos/` 已有最小版面（隊 W）；`aos run` 有 `--step 0` | 未做 daemon／systemd unit |
| 2 | `~/agents/*` 登記在 `~/.aos` 下，**一同 tick** 的子世界 | `every/sub.json` → `aos run sub --step 1` 已可做（[nested-worlds](nested-worlds.md)） | 登記方式未定：`every/` 手寫 vs `aos daemon add` |
| 3 | `~/pus/llms/{pi-ds,lm-local,…}` 是 **LLM PU 世界**，agent loop 把請求投到那裡 | 排程研究方案 A（「LLM PU 是另一個世界」）——裁決 11「A 留作 B 的投遞介面」 | 未做；D 保底只管槽 |
| 4 | agent 不指定 PU，只說「要 **tier A** 聰明的」 | 排程裁決 7「固定綁 engine＋可選 tier」；team-model 的 S/A/B/C 分級 | tier→PU 的對照表住哪未定（`~/.aos/cpus.json`？） |
| 5 | 子世界可以**跟主世界同步 tick**，也可以**有自己的 tick** | 同步＝`every/`；獨立＝各自 `aos run` | 兩種都要能在同一個 daemon 裡宣告 |
| 6 | `aos daemon start`：一個行程管多個 `aos run` 目標，**互不影響**（一個世界慢不拖住別的） | 無 | 隊 Y 正在做單世界 `--daemon`／`aos stop`；設計要留多目標餘地 |

## 使用者裁決（2026-08-30）

- home daemon **先只規劃**（Fable＋一頁 spec），實作等隊 X／Y 落地後再說。
- 第 3、4 件（LLM PU 世界、tier 選 PU）**先不做**，排程保底 D 夠用一陣。
- **systemd 先不做**：「風險略大，初期我還是傾向於手動啟用 `aos daemon start`」。

## 交接

- **隊 Y**（改進）：`aos run --daemon` 的 pid／設定形狀要能長成 `aos daemon start`（多目標清單），先不擴 scope。
- **下一隊（待使用者點頭）**：「home daemon」——`~/.aos/daemon.json`（目標清單：路徑、模式 `sync|own`、interval）、`aos daemon start/stop/status`、每目標一條獨立 loop（thread 或子行程）、systemd unit 範本；LLM PU 世界（第 3、4 件）走排程方案 B 時一起做。
- 這份跟 [top-down-cli §三](top-down-cli.md) 是同一個直覺的落地版。
