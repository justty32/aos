← [回入口 README.md](../README.md)｜段落：tools 覆蓋層（11-05）｜上一份：[02-已知限制](02-已知限制.md)｜下一份：[04-搬家](04-搬家.md)

<a id="tools-覆蓋層"></a>

## tools 覆蓋層（11-05，只存差異）

使用者 11-05：「stack存定義副本...建議是不要，使用者想弄可以自己弄，但我們自己在做的時候盡量不要」、「tools只存差異那塊可以先做，我直覺上這是好方法。等實作出來後我再看看」（[portable-flow 衝突 2](../../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)、[06 步 4](../../../thinking/2026-11/05/portable-flow/06-實作步驟草稿.md)）。以下是實作時照原則定的（可翻案）。

### 存什麼

`aos-agent tools add／rm` 不再把定義的 `tools.json` 整份抄進 stack，只在 `<stack>/tools.json` 記**這一隻自己加的、拿掉的**：

```json
{"add": {"math": {"path": "../../../../agents/lib/math"}}, "rm": ["clock"]}
```

- `add`：名字 → 登記內容（跟 aos-tools 登記檔裡一項一樣：`path`，可執行檔另有 `cache`）。**`path` 存相對覆蓋層這份檔所在的資料夾**（就是這隻的 stack），字串算、不 realpath——整份 image（`ws/.stack/`）搬家時跟著走。選「相對覆蓋層」而不是「相對 daemon stack」：aos-tools 本來的規則就是「手寫的相對路徑從這份檔的資料夾算」，覆蓋層照同一條，aos-tools 不用知道 daemon；覆蓋層在 stack 裡，兩種基準點一起搬，效果一樣。
- `rm`：拿掉的名字（只記定義裡有的；覆蓋層自己 add 的再 rm＝直接從 `add` 刪）。
- 沒改過＝沒有這份檔＝就是定義那份。`tools reset`＝刪掉這份。
- `llm` 本來就只存改過的鍵（`<stack>/llm.json`），不動。

### 怎麼合併（誰讀）

每次要用時現疊，不存結果：**定義的 `tools.json` → 拿掉 `rm` 裡的名字 → 放上 `add` 的（同名蓋過定義）**。疊法只寫在一處：`aos-tools --file <定義>/tools.json --overlay <stack>/tools.json …`（[aos-tools](../../../bin/docs/01-逐支說明.md)；`ls`／`get`／`call` 都看疊好的那份，`add`／`rm` 只寫覆蓋層、不碰定義）。用它的：

- `aos-agent tools ls／get／add／rm`（stderr 一行說用的是「定義」還是「定義疊覆蓋層」）。
- agent-fsm 的身體 `brain.py`（給腦看的工具清單）、`act.py`（叫工具）：沒給 `--tools` 時，`$AOS_STACK/tools.json` 在就加 `--overlay`；每格重讀＝下一題生效。
- eca agent：`lib/agent/cli_session.py` 的 `stack_copies`（cli.json 沒明寫 `tools` 時）把它交給 `aos-mcp --overlay`，aos-mcp 原樣轉給 aos-tools；每次起 CLI 重接。

### 定義後來改了怎麼辦

照疊，不用 reset：

- 定義**多了**工具＝這隻也看得到（除非名字在 `rm` 裡）。
- 定義**拿掉了** `rm` 裡的名字＝那個名字疊的時候找不到，忽略（不報錯、檔裡留著也無害）。
- 定義**多了一個跟 `add` 同名的**＝覆蓋層的 `add` 贏（這隻自己加的優先）。

### 已知的邊

- **覆蓋層壞掉或 `add` 的工具不見了＝整隻停下**（11-05 [edge-agent](../../../thinking/2026-11/05/edge-agent/README.md) 實測）：brain／act 每格 `aos-tools ls`，覆蓋層 JSON 壞、或 `add` 指的路徑不在，aos-tools 報 `RegistryBad`／`PathMissing`、身體報 `ToolsBad` 退 1，那隻自己結束、**下了 daemon 表**——這時 `aos-agent tools rm／reset` 也找不到它（`InstanceMissing`）。救法：手動刪或改 `<stack>/tools.json`（stack 留著），再同名 `aos-agent ctl add`，從停的那格接著答。照 aos-tools「不猜不跳過」，不改成略過壞的那個。
- **跟定義同名的**：`tools add 名 路徑` 撞到定義裡已有的名字＝aos-tools `ToolExists`；要這隻改用自己的就 `tools add --override 名 路徑`（寫進覆蓋層的 `add`，疊的時候蓋過定義）。
- 指到 image 外面的工具（例 repo 裡的 `lib/base/clock`）存的也是相對路徑（`../../../../../../home/…`）：整份搬到另一層深度或別台、那邊沒有同樣相對位置的檔＝那個工具找不到（aos-tools 報 `PathMissing`）。照 [portable-flow 03 原則 5](../../../thinking/2026-11/05/portable-flow/03-絕對路徑盤點.md)「指到 daemon 外面自擔」；要帶著走就把工具放進定義旁的 `lib/`。
