← [回入口 README.md](../README.md)｜段落：tools 覆蓋層（11-05）｜上一份：[02-已知限制](02-已知限制.md)｜下一份：[04-搬家](04-搬家.md)

<a id="tools-覆蓋層"></a>

## tools 覆蓋層（11-05，只存差異）

使用者 11-05：「stack存定義副本...建議是不要，使用者想弄可以自己弄，但我們自己在做的時候盡量不要」、「tools只存差異那塊可以先做，我直覺上這是好方法。等實作出來後我再看看」（[portable-flow 衝突 2](../../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)、[06 步 4](../../../thinking/2026-11/05/portable-flow/06-實作步驟草稿.md)）。以下是實作時照原則定的（可翻案）。

### 存什麼

`aos-agent tools add／rm` 只在 `interfaces.json` 的 `aos-agent.tools` **宣告的相對路徑**記這一隻自己加的、拿掉的（11-06 K-6）：定義讀 `<定義>/<tools 路徑>`，這隻自己那份寫 `<stack>/<同一 tools 路徑>`。例如宣告 `"tools": "cfg/my_tools.json"`，自己那份就是 `<stack>/cfg/my_tools.json`。`tools`／`llm` 宣告都只能是定義內的相對檔名；不可絕對、不可含 `..`、不可指資料夾。不複製定義，只存差異。**11-10 起長得跟一般登記檔一樣**（[aos-tools-cli](../../../thinking/2026-11/10/aos-tools-cli/README.md) 步 4；使用者 N1「跟一般清單同形狀。想要rm的話，就是指定的key : null」（11-10 改口：「null就是null，我們不做rm功能」「寫成 null，讀的人當它不是工具」）、K1「現在就寫 $override」）：

```json
{"$override": "../../defs/bob/tools.json",
 "tools": {"math": {"path": "../../../../agents/lib/math"}, "wall_clock": null}}
```

- `$override`：底檔（定義那份）。第一次 `tools add／rm` 由 aos-agent 寫（`aos-tools --file 自己那份 override …`），寫法照當初 `ctl add` 給定義的寫法（使用者 N2「跟你加 agent 時的寫法走」）：daemon 表 `as_written.def` 是 `$env` 指示詞＝原樣接上宣告的 tools 路徑（例 `{"$env": "DEFS", "$path": "/bob/tools.json"}`）；其餘（表上只有解好的絕對路徑，分不出原寫法）＝相對自己那份的資料夾。定義那份不存在時不寫 `$override`，`add` 直接建一般登記檔。
- `tools`：加的（跟登記檔裡一項一樣：`path`，可加 `env`／`env_file`／`cache: false`）與不要的（`"名": null`——值是 null 的那格不算工具）。`path` 保留使用者的寫法（11-10 午 TC）——給絕對＝存絕對、給相對＝存相對自己那份所在資料夾（字串算、不 realpath）；要寫指示詞直接 `aos-tools --file <stack>/<tools 路徑> add --path-json …`。
- 疊法是照順序疊，後面蓋前面（補丁式往下合，合併沒有刪除、`null` 只是值）：只寫 `{"env": {…}}` 的同名格會沿用定義那格的 `path`；`tools add --replace` 要整格換時，aos-tools 用 `null` 蓋過定義那格有、這次沒給的欄位（值是 null 的欄位＝當沒設）。`tools rm` 定義也有的名字＝寫 `"名": null`，只有自己那份記的＝刪那個 key。
- 沒改過＝沒有這份檔＝就是定義那份。`tools reset`＝刪掉這份。
- `llm` 也按它自己的宣告相對路徑放覆蓋層，只存改過的鍵（例宣告 `"llm": "cfg/brain.json"` 就寫 `<stack>/cfg/brain.json`）。
- **要重建什麼**（11-10）：舊形狀 `{"add": {…}, "rm": […]}` 的檔讀不了（`RegistryBad … top-level add / rm are not registry keys`）：`aos-agent tools reset` 後重新 `tools add`／`rm`。

### 怎麼合併（誰讀）

每次要用時現疊，不存結果，疊法只在 aos-tools 一處（[aos-tools](../../aos-tools/README.md)）：呼叫者的共同規則是「`<stack>/<tools 路徑>` 是檔就只傳它（`aos-tools --file 它`，它的 `$override` 指回定義那份），否則傳定義那份」；`ls`／`get`／`call` 都看疊好的那份，`add`／`rm` 只寫自己那份、不碰定義。用它的：

- `aos-agent tools ls／get／add／rm`（stderr 一行說用的是自己那份還是定義那份；自己那份的 `$override` 解出來不是這隻定義的那份時多印一行 warning——stack 被 cp 去配另一個定義時指標不會跟著變）。
- agent-fsm 的身體 `brain.py`（給腦看的工具清單）、`act.py`（叫工具）：沒給 `--tools` 時照上面的共同規則選一份；每格重讀＝下一題生效。
- eca agent：`proto8/lib/agent/cli_session.py` 的 `stack_copies`（cli.json 沒明寫 `tools` 時）同樣依宣告，自己那份在就把它當登記檔交給 `aos-mcp`；每次起 CLI 重接。
- `aos-agent ctl state` 的 tools 那行：`own: N listed, M set to null (+名, null:名…) over <$override 原樣值>`。

### 定義後來改了怎麼辦

照疊，不用 reset：

- 定義**多了**工具＝這隻也看得到（除非自己那份把它寫成 `null`）。
- 定義**拿掉了**自己那份寫成 `null` 的名字＝疊的時候本來就沒有，忽略（不報錯、檔裡留著也無害）。
- 定義**多了一個跟自己那份同名的**＝自己那份的那格合上去、它寫到的 key 贏（這隻自己加的優先）。

### 已知的邊

- **自己那份壞掉或它加的工具不見了＝整隻停下**（11-05 [edge-agent](../../../thinking/2026-11/05/edge-agent/README.md) 實測）：brain／act 每格 `aos-tools ls`，自己那份 JSON 壞、`$override` 指不到、或它加的路徑不在，aos-tools 報 `RegistryBad`／`PathMissing`、身體報 `ToolsBad` 退 1，那隻留在表上 `stopped`＋`reason`（11-05 使用者裁「留表標 stopped (Recommended)」）；修好後 `aos-agent tools reset`（或 `tools rm` 那個、手動改 `<stack>/<宣告的 tools 路徑>`）再 `aos-agent ctl start`，同一個 stack 從停的那格接著做；不要了 `aos-agent ctl rm`。照 aos-tools「不猜不跳過」，不改成略過壞的那個。
- **跟定義同名的**：`tools add --name 名 路徑` 撞到定義裡已有的名字＝aos-tools `ToolExists`；要這隻改用自己的就 `tools add --replace --name 名 路徑`（使用者 11-10 N3「旗標改叫 --replace」；寫進自己那份，定義那格有、這次沒給的 key 寫成 `null`）。
- 指到 image 外面的工具（例 repo 裡的 `lib/base/wall_clock`）存的也是相對路徑（`../../../../../../home/…`）：整份搬到另一層深度或別台、那邊沒有同樣相對位置的檔＝那個工具找不到（aos-tools 報 `PathMissing`）。照 [portable-flow 03 原則 5](../../../thinking/2026-11/05/portable-flow/03-絕對路徑盤點.md)「指到 daemon 外面自擔」；要帶著走就把工具放進定義旁的 `lib/`，或改用 `--path-json` 的環境變數寫法。
