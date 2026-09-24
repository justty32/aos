← [spec 總導航](../README.md)

# aos-agent：走一格、登記、取消登記

← [proto5 README](../../README.md)｜資料夾：[agent.md](../agent/README.md)｜問模型：[aos-llm.md](../aos-llm/README.md)｜送件：[kernel.md §2](../kernel/syscall.md)、[cpu.md §3](../cpu/messages.md)

> 第 2 版，2026-09-24 定稿，同日 fix-r4 改命令列、fix-r5 改日常輸出（health 不再樂觀、continue 兩階段與 `--all`、listen 講中間句）；已實作（`lib/aos_agent.py`＋`cli/aos-agent`）。輪次、審查與實作沿革在檔尾〈沿革〉（09-24 試玩 r3 搬）。

一句話：**`aos-agent tick` 每次只送出或接回一批工作，更新記憶與進度後就退出；結果還沒到就保留進度，留給下一次。**
問模型、跑工具都是往 kernel `add --once` 的普通工作；反覆叫 `tick` 是 kernel 的事——`aos-agent start` 把它登記成一個反覆行程。

## 14. 已拍板的前提（使用者定的，不重問）

1. **沒有同步工具**：問與跑都是 kernel `add --once`。取捨：最快等一格 tick；同批工具可能平行，有先後依賴的合成一個工具或拆兩輪。
2. **agent 先進現有的池**：`start`／`stop`＝替人 `aos-kernel add`／`rm` 反覆行程 `agent-<資料夾名>`；K 由 `AOS_KERNEL_HOME` 給（09-24 fix-r4 由 `AOS_K` 改名），沒設＝用法錯 2。
3. **llm.json 放 llm cpu 那邊**：agent 只給代號；外圈逾時 `info.llm.timeout_ms`、HTTP 逾時在 llm.json（[aos-llm.md §6](../aos-llm/timeouts.md)）。
4. （09-24 fix-r4，使用者定）**命令列**：家一律 `--target`（省略＝目前資料夾）；`last` 改成 `listen --last／--wait／--follow`；`say --wait [秒]`；加 `pause`、`continue` 兩種暫停都解；tick 上 flock。

## 13. 保證外與這份沒管的

- **一個 agent 家同時只有一個 tick 在做事**（09-24 fix-r4 改）：tick 鎖（§2.1）擋掉第二個，第二個退 101、不動檔。仍別用兩個名字登記同一個家——不會壞，但每格有一邊是白跑。
  外人改 `state.json`（例如加門）會跟正在跑的那格互相蓋掉——要改就先 `stop`，等 `aos-kernel ls` 看不到 `agent-<資料夾名>` 了再改，或借 tick 鎖（§2.1 末）。
- 人刪了 K 的檔、工作真的丟了：當批一直等；要放棄就 stop 後手動把 `batch` 設 `null`（工作檔自己清）。
- **問模型讀的是執行當下的 agent 家**：`aos-llm call` 跑起來才讀人格、記憶、工具（[aos-llm.md §3](../aos-llm/request.md)）；
  在途時人改了這些，會影響那一問。aos-agent 只保證**當前還沒取消的** think 批在途時不寫記憶；被 `Removed` 的舊問可能在重問、記憶變長之後才讀家，
  但它的回音 kernel 會丟掉、不會接進記憶（要連殘留也保證輸入不變，得等它的 `procs` 消失再重問，這版不做）。
- kernel `stop`：還在排隊的 once 回 `Stopping`（think 下次重問、工具告訴模型「沒跑」），在跑的照常跑完；
  agent 自己的那格在 stopping 時不會被派，當批留到下次 boot 之後收（kernel 跨 boot 保留 `procs`／`replies`）。
- 放單崩在 `link` 之後、刪 `.tmp` 之前：`K/requests/` 留一個 `.` 開頭 `.tmp` 結尾的殘檔；主人只收 `.json`，不會誤收；**沒人自動清**（保證外），人在都停著時刪。
- **日常 CLI 是最小版**（09-24 試玩 r2 補）：`init`（單一內建預設）、`say`、`status`、`continue` 有了（§1.1～§1.4）；（09-24 fix-r4 補）`listen`、`pause`（§1.5、§1.6）；（09-24 fix-r5 補）`continue --all`、`init --force`（§1.4、§1.1）。
  **這份沒管的**：`init --template`／`--config`（template 從哪來使用者還沒定）、`tools`／`llms` 子命令、專屬 cpu、`say` 投到 `input` 第一條以外的地方；構想在 [thinking/aos-agent.md](../../../thinking/aos-agent.md)。記憶太長也沒管。

## 各節

原文裡「檔尾〈沿革〉」「檔尾〈實作補記〉」「見下」這類方位詞是拆檔前的位置，拆後照下表找對應檔（`history.md`、`impl-notes.md`、`rulings.md` 等）。

| 檔 | 內容 |
|---|---|
| [essentials.md](essentials.md) | 使用者只需要懂的：日常會用到的子命令 |
| [terms.md](terms.md) | §0 名詞（白話） |
| [cli.md](cli.md) | §1 用法總表；§1.1 `init` 生一個最小可跑的家 |
| [cli-talk.md](cli-talk.md) | §1.2 `say` 投一則話；§1.5 `listen` 看回話 |
| [cli-status.md](cli-status.md) | §1.3 `status` 現在怎樣了；§1.4 `continue` 解除暫停；§1.6 `pause` 手動暫停 |
| [tick.md](tick.md) | §2 一次 `tick` 的順序；§2.1 同時兩個 `tick`；§12 `tick` 的退出碼與 stderr |
| [gate.md](gate.md) | §3 門；§4 `batch` 是 `null` 時照 `state` 走 |
| [send.md](send.md) | §5 送出一批：§5.1 建批、§5.2 送件、§5.3 act（工具的 inst）、§5.4 think（問模型的 inst） |
| [collect.md](collect.md) | §6 收回：§6.1 think 的 `done`、§6.2 act 的 `done` |
| [settle.md](settle.md) | §7 結清 |
| [idle.md](idle.md) | §8 idle：收輸入 |
| [pause-clean.md](pause-clean.md) | §9 連敗暫停；§10 清工作檔 |
| [register.md](register.md) | §11 `start`／`stop`：登記進 kernel |
| [rulings.md](rulings.md) | 調度者裁決（第 2～3 輪，實作層級） |
| [history.md](history.md) | 沿革 |
