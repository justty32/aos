← [agent-access 提案](README.md)

# 操作實例（完整版的樣子；最小版的差別標在各段尾）

擺設：`~/aos/amy/`（agent 家）、`~/aos/workspace/`、`~/aos/other-workspace/`、`~/aos/util-tools/`、`~/ws-A/`、`~/ws-B/`。

## 映射表長這樣：`amy/access.json`

```json
{"_metainfo": {"_type": "agent_access", "_version": 1},
 "mounts": {
   "ws":   "../workspace",
   "util": {"$opt": "ro", "$val": "../util-tools"}
 },
 "cwd": "ws",
 "net": false}
```

- `mounts` 的 key＝**amy 看到的名字**（牢裡是 `/work/<名字>`），值＝真的資料夾（相對 agent 家，或絕對路徑）。值可以是任何指示詞（`$env`、`$ref`、`$fmt`），選項 `ro`＝唯讀。
- `cwd`：工具從哪個名字開始（沒寫＝`/work`，看得到所有名字）。
- 沒列的資料夾，工具**看不到**——包括 amy 自己的家。
- aos-agent 每送一批工具就解一次這個檔、整批用同一份：**改完下一批生效，不用 stop／start**。已經送出去、排隊中、正在跑的那一批照舊的（[contract §1](contract.md)）。

## 例 1：今天不准碰 ./workspace，改碰 ./other-workspace

兩種意思，選一種：

**(甲) 換掉，amy 當作同一個地方**（她的工作邏輯不用換）——改一行：

```diff
-   "ws":   "../workspace",
+   "ws":   "../other-workspace",
```

或用指令：`aos-agent access set ws ../other-workspace --target ~/aos/amy`。

**(乙) 兩個不同地方，amy 知道換了**——拿掉一個、加一個：

```sh
aos-agent access set other ../other-workspace --cwd --target ~/aos/amy   # 加 other，同時把起點改成 other（一次原子寫）
aos-agent access rm ws --target ~/aos/amy                                # 先 rm 會被拒：ws 是目前的 cwd
aos-agent access ls --target ~/aos/amy
```

```
name   path                          mode  exists
other  /home/u/aos/other-workspace   rw    ok
util   /home/u/aos/util-tools        ro    ok
cwd: other   net: off   bwrap: ok
```

(乙) 記得 `aos-agent say "工作區換成 other/ 了，workspace 不能用了" --target ~/aos/amy`，不然她記憶裡還在找 `ws/`（找了會得到 `No such file or directory`）。

## 例 2：隔天又覺得 amy 可以碰自己

```sh
aos-agent access set self . --target ~/aos/amy        # 一律唯讀（§7 題 2 的預設），她看得到自己的設定與記憶
aos-agent access set notes ../amy-notes --target ~/aos/amy   # 要她能寫東西：映射一個家外面的資料夾
```

`self` 不給可寫：家裡有太多會決定權限與行為的檔（`info.json`、`access.json`、`tools/`、`state.json`、`.tick.lock`、`paused`…），蓋不完也蓋不住之後新建的（[contract §4](contract.md)）。

## 例 3：amy 永遠在 `ws/` 工作，實際從 ~/ws-A 換到 ~/ws-B

```diff
-   "ws": "/home/u/ws-A",
+   "ws": "/home/u/ws-B",
```

牢裡還是 `/work/ws`，`pwd`、錯誤訊息、工具輸出的路徑一個字都不變；記憶裡的路徑都是 `ws/…`，沒有舊路徑要清。
要不要清記憶：**不用**（路徑沒變）。但檔案內容變了——她記得的 `ws/a.txt` 在 ws-B 可能不在。要她知道就 `say` 一句；我們不自動投。

**好幾個 agent 一起換**：映射寫成指到一份共用檔，改那一份就全換：

```json
"ws": {"$ref": "../shared/current-ws.json#/path"}
```

## 例 4：共用工具夾 `./util-tools/`，amy 叫它另一個名字

`util-tools/bash-edit-a.json`（多個 agent 共用）：

```json
[{"type": "function",
  "function": {"name": "bash-edit-a", "description": "…", "parameters": {…}},
  "_meta": {"argv": ["/home/u/aos/util-tools/bin/edit-a"]}}]
```

amy 的 `info.json`：

```json
"tools": ["tools/base.json",
          {"$opt": {"as": {"bash-edit-a": "edit-a"}}, "$val": "../util-tools/bash-edit-a.json"}]
```

- 模型看到的工具清單裡叫 `edit-a`；它叫 `edit-a`，aos-agent 找回 `bash-edit-a` 那條去跑。記憶裡記的也是 `edit-a`。
- **模型看不到檔名**：它只看到每條工具的 `function.name`。所以「amy 看到 `edit-a.json`」實際是「amy 看到 `edit-a` 這個工具」。
- 整個資料夾也行：`{"$opt": {"as": {…}}, "$val": "../util-tools"}`（資料夾＝裡面所有 `*.json`，照檔名排序，現行規則）。只要其中幾條：`{"$opt": {"only": ["bash-edit-a"]}, …}`。
- 衝突：改名後跟別條同名＝`ToolInvalid`，訊息列兩邊的檔、位置、原名與改成的名字（現行「同名」規則，只多講一句是改名造成的）。`as` 裡寫了檔裡沒有的原名＝`ToolInvalid`（打錯字要早點知道）。
- 工具檔不用寫 `aos-jail`：amy 有映射表，aos-agent 送件時自動包；程式所在的資料夾由 aos-jail 唯讀掛到牢裡的 `/opt/tool`（[contract §1](contract.md)）。程式路徑寫絕對路徑或放 PATH（`_meta.argv[0]` 的相對路徑是相對 agent 家，共用檔用不上）。

## 例 5：共用工具夾本身搬家（`util-tools/` → `tools-shared/`）

先讓每個 agent 都**透過一份共用檔**找它（一次性設定），之後搬家只改那一份：

```json
// ~/aos/shared/where.json（信任資料：別映射成可寫）
{"util_tools": "/home/u/aos/util-tools"}
// 每個 agent 的 info.json
"tools": ["tools/base.json", {"$ref": "../shared/where.json#/util_tools"}]
// 每個 agent 的 access.json（要讓工具看得到這個夾子才需要）
"util": {"$opt": "ro", "$val": {"$ref": "../shared/where.json#/util_tools"}}
```

搬家：`mv util-tools tools-shared`、改 `where.json` 一行。工具檔裡的程式路徑若寫死絕對路徑也要跟著改——所以共用工具的程式最好放 PATH。
（`tools` 元素用 `$ref` 取**路徑字串**現在就行，實測過；取工具陣列不行。）

## 每種情境實際要改幾處

| 情境 | 要改的 |
|---|---|
| 例 1 (甲)、例 3：名字不變、換資料夾 | 映射表一行（或一個 `set`） |
| 例 1 (乙)：ws 換成 other | 一個 `set … --cwd`＋一個 `rm`；手編則同一檔改 `mounts` 與 `cwd`；要她知道再 `say` 一句 |
| 例 2：開放 self | 一個 `set` |
| 例 3 多個 agent 一起換 | 第一次：每個 agent 的映射表改成 `$ref` 共用檔；之後：共用檔一行 |
| 例 4：工具改名 | 每個要改名的 agent 各改一次 `info.json`（**要規範新增選項後才有**） |
| 例 5：共用夾搬家 | 第一次：每個 agent 改成 `$ref` 共用檔；之後：`mv`＋共用檔一行（程式路徑寫死的另改） |
| 最小版加一個資料夾 | `tools/base.json` 七條 argv 都要加一段、可能還要改 base 的 root——不划算，等完整版 |

## 最小版（現在的 proto5，不改 aos 程式）差在哪

- 生效時機一樣是下一批（寫 inst 時就把 `$ref` 解成字面）。
- 映射表只有字串：`amy/access.json` ＝ `{"ws": "/home/u/ws-A"}`；每支工具的 `_meta.argv` 直接是一串 bwrap 參數，其中一格 `{"$ref": "access.json#/ws"}`（[實驗 4](experiment.md#4-只靠現有指示詞bwrap走真的送件路徑exp4py)）。
- **只有一個 ws**。例 1 (甲)、例 3 是改一行；例 1 (乙)、例 2、例 4 的 `util` 要改每支工具的 argv（七支各一次），太麻煩＝等完整版。
- 拿掉 `ws` 那一行＝每次叫工具都「跑不起來：ReferencePointerInvalid」，模型看得到；要「暫時不准碰」改指向一個空資料夾比較乾淨。
- 沒有 `aos-agent access` 指令，直接編檔；沒有改名；只有 base 七支關牢，自己加的工具沒關。
