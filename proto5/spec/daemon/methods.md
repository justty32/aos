← [daemon](README.md)｜[spec 總導航](../README.md)

# 3. method（`D/requests/`）

（2026-09-24 proto5-2 池式納入：拿掉 `spawn`，加 `scale`／`ls`，`kill` 改按池。）走法：往 `D/requests/` 放 JSON-RPC 單，回音在 `D/responses/` 同名，
收的人讀完放 ack（[cpu §3](../cpu/messages.md)）。回音、原單、ack 的處理照範式 §6.3；daemon 自己崩在中間，重啟照範式 §6.2 對帳（`current` 那格就是為這個）。

| method | 誰用 | 一句話 |
|---|---|---|
| `scale` | kernel、`aos-daemon scale` | 宣告「池 P 要這幾號」；池不在就建 |
| `kill` | 人（`aos-daemon kill`） | 把某幾顆砍掉重來 |
| `ls` | 其他程式 | 回池的摘要；人跟 kernel 平常直接偷看檔案 |
| `stop` | `aos-daemon halt` | 整個 daemon 停機（notification，檔名前綴 `stop-`；§5） |
| `ack` | 所有收回音的人 | 同範式 §3.3 |

**拿掉 `spawn`**：單顆孩子就是 `count: 1` 的池。第 1 版的 `spawn`（同名同目標回舊 pid）、`NameTaken` 的意思搬進 `scale`。
params 形狀不合＝`-32602`。錯誤回音照範式：`{"code": -32000, "message": …, "data": {"code": "NameTaken"}}`。

## `scale`

```json
{"jsonrpc": "2.0", "id": "k-1790000000000000000-4242-41-scale-llm", "method": "scale",
 "params": {"pool": "k1-llm", "owner": "/abs/K", "count": 3, "skip": [],
            "target": "/abs/K/pools/llm/cpus/{name}/inst.json",
            "home": "/abs/K/pools/llm/cpus/{name}", "decl": [1790000000000000000, 41]}}
```

| 鍵 | 型別 | 必填 | 意思 |
|---|---|---|---|
| `pool` | 字串（合法檔名） | 是 | daemon 這邊的池名（kernel 的 `dpool`） |
| `owner` | 字串 | 是 | 誰的池。kernel 用自己家的絕對路徑；人用 `aos-daemon scale` 建的池是 `cli` |
| `count`、`skip` | 同 [kernel §1.1 編號](../kernel/info.md) | `count` 是 | 要哪幾號；名字是十進位字串 |
| `target` | 絕對路徑樣板 | 池不在、`count`>0 時是 | 第 i 號孩子的 aos-exec 目標；`{name}` 恰好出現一次，換成號碼 |
| `dir_target` | 字串 | 否 | 資料夾目標裡的 inst 路徑（同 aos-exec） |
| `home` | 絕對路徑樣板 | 否 | 第 i 號 cpu 的家；只給 `ls` 數「忙」用（偷看那家的 `state.json` 的 `current`） |
| `decl` | 兩個非負整數的陣列 | 否 | 送件者的宣告序號，照字典序比大小。kernel 用 [chain 的 epoch ns, 格序號]（boot 用 0）。CLI 不給 |

**daemon 怎麼處理**（一律同步、做完才回）：
1. 形狀不合（`count` 不是非負整數、`skip` 有重複或負數、樣板沒有 `{name}` 或不只一個、不是絕對路徑、池名不合 kernel §1.1 的規則）＝`-32602`。
2. daemon 在 `stopping`＝`-32000`／`Stopping`。
3. 池已在、`owner` 不同＝`-32000`／`NameTaken`（`message` 說現在的 owner）。
4. **過期**：池已在、有給 `decl`、而且比 `pool.json` 記的 `decl` **小**＝`-32000`／`Stale`，什麼都不改（相等＝同一張重送，照常做）。
   擋的是「舊鏈放進來還沒處理的單，在新鏈的單之後才被處理」：`scale A → scale B → 重放 A` 會把 B 蓋掉。
   沒給 `decl` 的不擋，`pool.json` 的舊 `decl` 留著。池已經拿掉之後才到的舊單擋不住（保證外，[kernel §5](../kernel/daemon-link.md)）。
5. **池不在、`count` 是 0**：什麼都不建，直接回成功（`ver` 0）。所以 boot 可以放心先送「縮到 0」，不用帶樣板。
   池不在、`count`>0 卻沒給 `target`＝`-32602`。
6. 成員數超過 daemon 能管的（全 daemon 合計**宣告**數超過 `max_children` 與 `開檔上限 − 64` 取小）＝`-32000`／`TooMany`，什麼都不改。
   實際能同時活幾支另由 fd 預算管（§4）。同一份宣告換台機器可能被拒。
7. 寫 `D/pools/<pool>/pool.json`（新宣告、`decl`；`target`／`home`／`dir_target` 有給就換新的）→ 回音 → 刪原單。
   實際拉、收孩子是之後迴圈的事（節流），**回音只代表「收到宣告了」**，不代表 cpu 活了。

result：`{"pool": "k1-llm", "count": 3, "ver": 7}`。`ver` 是這池第幾版宣告，每次成員真的變了才加 1；同一份宣告重送不加（冪等）。

**`count: 0`**：成員清空。全部孩子收完之後 daemon 把整個池拿掉（[§1.2](pools.md)），池名就空出來，別的 owner 可以用。
**換 `target` 不重拉**：活著的孩子照舊，之後（重）拉的才用新樣板；這池所有 `failed` 的等待清掉、馬上可以再試。

## `kill`

```json
{"jsonrpc": "2.0", "id": "cli-1790000000000000000-77", "method": "kill",
 "params": {"pool": "k1-default", "names": ["3", "5"]}}
```

`names` 與 `"all": true` 二選一。語意是**砍掉重來**：宣告沒變，所以砍完 daemon 會再拉一顆（不算崩潰、不加 `streak`、不退避）。
用途：換環境（kill 全池讓每顆重讀 `envs.json`）、救卡住的 cpu。要真的少一顆用 `scale`（或 kernel 的 `cpu rm`）。

result：`{"killed": ["3"], "skipped": {"5": "pending"}}`。`running` 的開始走階梯；`dead`／`failed` 的清掉等待時間、儘快重拉（也算進 `killed`）；
`pending`／`killing` 的略過；不是成員的略過（`"not-member"`）。池不在＝`NotFound`。`stopping` 期間照常。

## `ls`

params `{}` 或 `{"pool": P}`。沒給 pool：`{"pools": {P: 摘要}}`；給了：`{"pool": P, "summary": 摘要, "children": {"<i>": 孩子檔的內容＋"busy"}}`。
摘要與孩子檔的格式在 [§1.2](pools.md)。帶 pool 的回音可能很大（上萬顆約 1 MB），是給人偶爾用的。
