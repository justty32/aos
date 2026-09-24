# 定期喚醒 flavor 包（heartbeat）

← [repo README](../../README.md)（導航中樞）

**定位：本包不是排程器。** 它唯一的價值是把「該定期做的事」寫成**放在 repo 裡、跟著版控、agent 讀得懂**的清單；**執行引擎一律外借**——你的 agent 工具的循環／排程功能，或 OS 的 cron / 工作排程器 / CI 排程。清單與引擎分離，換引擎不用改清單。

## 與執行引擎的分工

| 誰 | 負責 | 不負責 |
|----|------|--------|
| 你的 agent 工具的循環／排程功能（Claude Code 為例：session 內的 `/loop`、雲端 routines 的 `/schedule`）| 每隔 N 分鐘重新喚醒同一個 agent | session 內循環：關掉就停、睡眠 / 關機期間不補跑；雲端排程：讀不到你本機未 push 的清單改動 |
| OS cron / systemd timer / 工作排程器 / CI 排程 | 開機常駐、跨 session 定時觸發任何指令 | 不知道「要做什麼」 |
| 其他 agent 工具（Codex CLI、Gemini CLI、Cursor 之類）| 沒有內建循環就在外面包一層：**每隔 N 分鐘叫 agent 跑一次 [tick](workflows/tick.md) 工作流**，語意完全一樣 | 同上，觸發歸觸發 |
| **本包（heartbeat）** | **要做什麼**：清單（routines / schedule）、到期判斷、授權邊界 | **不負責觸發**：自己不會醒 |

一句話：上面幾種引擎決定「什麼時候醒」，本包決定「醒來要做什麼」。**主體是 tick 工作流**，任何能定時叫 agent 的東西都能當引擎。

## 這個包有什麼

| 路徑 | 角色 |
|------|------|
| [WORKFLOWS.heartbeat.md](WORKFLOWS.heartbeat.md) | 派發表片段（貼進 kernel 的 WORKFLOWS.md）|
| [workflows/tick.md](workflows/tick.md) | **tick**：單次心跳，極薄派發器——叫起 routines 與 schedule，回一句摘要 |
| [workflows/routines.md](workflows/routines.md) | **routines**：固定循環的常規事務（時機分區 + 間隔登記表）＋ 執行規則 |
| [workflows/schedule.md](workflows/schedule.md) | **schedule**：臨時、一次性的行程（絕對時刻表），到點做完刪列 |
| [.claude/commands/wf-tick.md](.claude/commands/wf-tick.md) | Claude Code 的 slash 指令適配層（可選）：`/wf-tick [週期]` 循環跑 tick 工作流。其他工具沒有對應機制就忽略這個目錄 |

三個工作流互相獨立：tick 只做派發，清單與判斷各歸 routines / schedule 自己。

## 怎麼合進 kernel

```
bash tools/wf-init.sh --target <專案> --flavor heartbeat
```

通用步驟見 [IMPORT.md](../../IMPORT.md)（多個 flavor 就多帶幾個 `--flavor`，派發表依序插入）。本包特有的三點：

1. 片段檔只有一個 `WORKFLOWS.heartbeat.md`；`workflows/*.md` 併進 `<專案>/workflows/`。
2. `.claude/commands/wf-tick.md` 落到**專案根**的 `.claude/commands/`——以 Claude Code 為例，它只讀專案根那個目錄，**非侵入式佈局也一樣**（其餘檔進 `wf/`，指令仍留在根，腳本會把指令內指向 `../../workflows/tick.md` 的連結改寫成實際路徑）。用別的工具就忽略這個目錄。
3. 填完 `{{時區}}` 後**決定引擎**（見上面分工表）——不管哪一種，語意都是「每隔 N 分鐘叫 agent 跑一次 tick 工作流」——並把 routines / schedule 的清單換成自己的。

## 踩坑

- **Windows 的 git-bash 下 `TZ=… date` 可能回 GMT**（MSYS 不吃 IANA 時區名，靜默失敗、不報錯，時間會整個偏掉）。改用 PowerShell 取當地時間：
  ```powershell
  [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date), '<時區 ID，如 Taipei Standard Time>').ToString('yyyy-MM-dd dddd HH:mm')
  ```
  時區 ID 用 `Get-TimeZone -ListAvailable` 查。平台差異只講在這裡——工作流檔裡只留一行 `TZ='{{時區}}' date '+%F %A %H:%M'`，導入到 Windows 專案時把那行換成上面這句。
- **錯過的心跳不會補**：session 內的循環在 session 關閉、睡眠、關機期間不跑，cron 預設也不補。醒來後可能一次撞上好幾個到期項——`schedule` 的執行段有「錯過很久」的處理規則，routines 的間隔型天生容忍延遲（比對「上次執行」而非固定時刻）。

## 移除某個工作流要動的地方

| 移除 | 刪什麼 | 同步改什麼 |
|------|--------|-----------|
| routines | `workflows/routines.md` | 專案 `WORKFLOWS.md` 派發表 routines 那列；`workflows/tick.md` 流程第 1 步 |
| schedule | `workflows/schedule.md` | 專案 `WORKFLOWS.md` 派發表 schedule 那列；`workflows/tick.md` 流程第 2 步 |
| tick（連整包）| `workflows/{tick,routines,schedule}.md`、專案根 `.claude/commands/wf-tick.md`（若有）| 專案 `WORKFLOWS.md` 派發表整段「定期喚醒 flavor」 |

改完跑 `tools/wf-lint.sh`（Claude Code 可用 `/wf-lint`）確認沒有指向已刪檔的連結。
