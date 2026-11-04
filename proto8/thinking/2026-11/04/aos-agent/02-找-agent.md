← [入口](README.md)｜涵蓋：找 agent 的兩條路、`.aos/agent.json` 格式與規則、佔資料夾的衝突、哪個 daemon｜上一份 [01-子命令](01-子命令.md)｜下一份 [03-種類與契約](03-種類與契約.md)

## 找 agent：只有兩條路（使用者 11-04 定的，fable 補細節）

使用者 11-04：找 agent＝`AOS_DAEMON_STACK` → daemon 表上的名字 → 那列的 stack；擴充＝當前資料夾有 `.aos/agent.json` 就知道找誰。所以：

1. **給了名字**：查 daemon 表（`aos-daemon-ctl ls --json` 的 `procs`），表上有＝那列；`running`／`stopping`／`stopped`／`sleeping` 都算在（跟 `where` 一樣，11-03「一個proc在daemon中的狀態……除此之外就是不存在於daemon了」）；沒有＝`InstanceMissing`。
2. **沒給名字（或給的是資料夾）**：看 `<資料夾>/.aos/agent.json`（沒給資料夾＝cwd）。有＝讀出 `name` 與 `daemon_stack`，回到第 1 條去查**那個** daemon 的表。沒有＝`InstanceMissing`，訊息教兩句：「給名字（`aos-agent ls` 看有哪些）」或「讓一隻佔這裡：`aos-agent occupy 名字`」。

**不帶過來的第三條路**：aos-eca 現在會「再比工作區」（表上 `ws` 跟這個資料夾相同就算）。aos-agent 不做——使用者定的只有兩條，比工作區是第三條暗路（C-56），而且兩隻共用同一工作區時就猜不出來。要「cd 進去就能說」就 `occupy`。這是跟 aos-eca 行為不同的一點，記在 [04 過渡](04-過渡與邊緣.md)。

**`--stack S` 例外**：say／listen／state／pause／resume 給了 `--stack`（或設了 `$AOS_STACK`）就直接用那個 stack、不走上面兩條（給直接 `aos-exec` 跑的留的；使用者「先暫時忽略直接aos-exec出來的那些」，所以只留明路、不猜 `.stack`）。這時沒有 daemon、沒有名字：start／stop／rm 這些要 daemon 的子命令不收 `--stack`（給了＝`ArgumentsBad`「這隻不在 daemon 上」）。

## `.aos/agent.json`：佔資料夾的證據

**位置**：`<資料夾>/.aos/agent.json`（使用者的字；`.aos/` 是隱藏資料夾，C-51「隱藏檔一律略過」所以不會被當成程式的一部分）。只這一個檔；`.aos/` 裡以後要放別的再說。

**內容**（只放找到它要用的兩樣，其他都查表就有，C-56）：

```json
{"name": "bob", "daemon_stack": "/home/u/aos-daemon/.stack"}
```

- `name`＝daemon 表上的名字；`daemon_stack`＝那個 daemon 的 stack，**絕對路徑**（寫入時從 `--daemon-stack`／`$AOS_DAEMON_STACK` 轉絕對）。
- 不放 stack、ws、種類：都從表與 stack 推得出來（[03](03-種類與契約.md)），放了就會跟表上不同步（C-48「不認得的 key 一律忽略」照舊——多的 key 不報錯）。

**誰寫**：`aos-agent occupy 名字 [資料夾]` 寫、`aos-agent release [資料夾]` 刪（`.aos/` 空了順手刪）；`aos-agent rm` 把指著被拔那隻的標記一起拿掉。**agent 的身體（aos-eca-turn、idle.py）從不寫它**——身體只碰自己的 stack（P-42 三樣以外不碰工作區；C-65 工作區只放交辦的東西與成果）。這是[方向題 1](06-衝突與方向題.md#方向題-1aosagentjson-誰寫怎麼寫)的建議案；用 `add --occupy` 旗標或讓 agent 自己寫是另兩案。

**佔資料夾的衝突怎麼判**（使用者「如果有其他agent想要佔據資料夾，那就是看這個」）：

| `occupy X 資料夾` 時發現 | 判法 |
|---|---|
| 沒有 `.aos/agent.json` | 寫入 |
| 有，`name` 就是 X、`daemon_stack` 相同 | 已經佔著，說一句、退 0 |
| 有，指的那隻**還在**它那個 daemon 的表上（任何 phase，含 `stopped`／`sleeping`） | `WsOccupied`「這裡被 Y 佔著；要換先 `aos-agent release`」、退 1、不改檔 |
| 有，指的那隻**不在**表上（rm 過、自己結束下了表）、或 `daemon_stack` 不是資料夾／沒有 `procs_state.json` | 舊標記＝沒人佔，直接覆寫（11-03「拿下名單後……就不存在了」） |
| 有，讀不懂（不是 JSON、沒有 `name`／`daemon_stack`） | `MarkerBad`、退 1、不改檔；訊息指路徑，人自己刪 |

- `occupy` 的 X 要**已經在表上**（先 `add` 再 `occupy`）；不在＝`InstanceMissing`。
- 一個資料夾只被一隻佔；一隻可以佔好幾個資料夾（標記在資料夾那邊，agent 那邊不記）。agent 平常不佔任何資料夾（使用者「agent通常是不需要佔據資料夾的」）。
- `occupy` 不檢查資料夾是不是它的工作區（`--ws`）：佔資料夾只是「cd 進來能找到它」的捷徑，跟它在哪裡做事是兩件事（C-65 stack／工作區分開的精神）。
- `release` 不管標記指誰、不問 daemon，直接刪（人的資料夾人作主）；沒有標記＝說一句、退 0。
- `rm`／`stop`／`start` 之外沒有別的子命令會動標記；`stop` 的那隻仍佔著（它還在表上）。

## 哪個 daemon

順序：`--daemon-stack D` ＞（沒給名字時）標記的 `daemon_stack` ＞ `$AOS_DAEMON_STACK`。給了名字就不看標記（名字＝「我知道是哪隻」，daemon 照環境）。三個都沒有＝`DaemonMissing`。標記指的 daemon 跟環境的不同時以標記為準（它存的是絕對路徑、正是為了 cd 之後還找得到）；要明講就 `--daemon-stack`。daemon 沒在跑（`procs_state.json` 的 pid 對不上）：查表類（ls／state／where）照 aos-daemon-ctl 說一句注意、照表印；要動它的（add／rm／start／stop）＝`DaemonMissing`（跟 aos-eca 一樣）；say 照寄、提醒重開 daemon（aos_human 的 `run_hint` 已有：`sleeping`＝「重開 daemon 它會自己醒」）。
