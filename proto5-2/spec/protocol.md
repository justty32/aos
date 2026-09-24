# kernel ↔ daemon 協定

← [spec 導航](README.md)｜kernel 怎麼用：[kernel-pools](kernel-pools.md)｜daemon 怎麼做：[daemon-reconcile](daemon-reconcile.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/daemon.md](../../proto5/spec/daemon.md) §3 的 method 表**與 [proto5/spec/kernel.md](../../proto5/spec/kernel.md) §5。
> 走法不變：往 `D/requests/` 放 JSON-RPC 單，回音在 `D/responses/` 同名，收的人讀完放 ack（[cpu.md §3](../../proto5/spec/cpu.md)）。

| method | 誰用 | 一句話 |
|---|---|---|
| `scale` | kernel、`aos-daemon scale` | 宣告「池 P 要這幾號」；池不在就建 |
| `kill` | 人（`aos-daemon kill`） | 把某幾顆砍掉重來 |
| `ls` | 其他程式 | 回池的摘要；人跟 kernel 平常直接偷看檔案 |
| `stop` | `aos-daemon halt` | 整個 daemon 停機（同 proto5，notification，檔名前綴 `stop-`） |
| `ack` | 所有收回音的人 | 同範式 §3.3 |

**拿掉 `spawn`**：單顆孩子就是 `count: 1` 的池。proto5 的 `spawn`（同名同目標回舊 pid）、`NameTaken` 的意思搬進 `scale`。

## 1. `scale`

```json
{"jsonrpc": "2.0", "id": "k-1790000000000000000-4242-41-scale-llm", "method": "scale",
 "params": {"pool": "k1-llm", "owner": "/abs/K", "count": 3, "skip": [],
            "target": "/abs/K/pools/llm/cpus/{name}/inst.json",
            "home": "/abs/K/pools/llm/cpus/{name}"}}
```

| 鍵 | 型別 | 必填 | 意思 |
|---|---|---|---|
| `pool` | 字串（合法檔名） | 是 | daemon 這邊的池名（kernel 的 `dpool`） |
| `owner` | 字串 | 是 | 誰的池。kernel 用自己家的絕對路徑；人用 `aos-daemon scale` 建的池是 `cli` |
| `count`、`skip` | 同 [kernel-info §3](kernel-info.md) | `count` 是 | 要哪幾號；名字是十進位字串 |
| `target` | 絕對路徑樣板 | 池不在時是 | 第 i 號孩子的 aos-exec 目標；`{name}` 恰好出現一次，換成號碼 |
| `dir_target` | 字串 | 否 | 同 proto5 `spawn` |
| `home` | 絕對路徑樣板 | 否 | 第 i 號 cpu 的家；只給 `ls` 數「忙」用（偷看那家的 `state.json` 的 `current`） |
| `decl` | 兩個非負整數的陣列 | 否 | 送件者的宣告序號，照字典序比大小。kernel 用 [chain 的 epoch ns, 格序號]（boot 用 0）。CLI 不給 |

**daemon 怎麼處理**（一律同步、做完才回）：
1. 形狀不合（`count` 不是非負整數、`skip` 有重複或負數、樣板沒有 `{name}` 或不只一個、不是絕對路徑、池名不合 [kernel-info §5](kernel-info.md) 的規則）＝`-32602`。
2. daemon 在 `stopping`＝`-32000`／`Stopping`。
3. 池已在、`owner` 不同＝`-32000`／`NameTaken`（`message` 說現在的 owner）。
4. **過期**：池已在、有給 `decl`、而且比 `pool.json` 記的 `decl` **小**＝`-32000`／`Stale`，什麼都不改（相等＝同一張重送，照常做）。
   擋的是「舊鏈放進來還沒處理的單，在新鏈的單之後才被處理」：`scale A → scale B → 重放 A` 會把 B 蓋掉（審查 R6）。
5. **池不在、`count` 是 0**：什麼都不建，直接回成功（`ver` 0）。所以 boot 可以放心先送「縮到 0」（審查 R2）。
6. 成員數超過 daemon 能管的（[daemon-home §1](daemon-home.md) 的 `max_children`，全 daemon 合計**宣告**數）＝`-32000`／`TooMany`，什麼都不改。
   實際能同時活幾支另由 fd 預算管（[daemon-reconcile §5](daemon-reconcile.md)）。
7. 寫 `D/pools/<pool>/pool.json`（新宣告、`decl`；`target`／`home`／`dir_target` 有給就換新的）→ 回音 → 刪原單。
   實際拉、收孩子是之後迴圈的事（節流），**回音只代表「收到宣告了」**，不代表 cpu 活了。

result：`{"pool": "k1-llm", "count": 3, "ver": 7}`。`ver` 是這池第幾版宣告，每次成員真的變了才加 1；同一份宣告重送不加（冪等）。

**`count: 0`**：成員清空。全部孩子收完之後 daemon 把整個池拿掉（先刪 `summary.json`，再刪 `pool.json` 與資料夾），池名就空出來，別的 owner 可以用。
kernel 把「`summary.json` 不在」當成「池已完全拿掉」（搬池、halt 都靠它）。

**換 `target` 不重拉**：活著的孩子照舊，之後（重）拉的才用新樣板。

## 2. `kill`

```json
{"jsonrpc": "2.0", "id": "cli-1790000000000000000-77", "method": "kill",
 "params": {"pool": "k1-default", "names": ["3", "5"]}}
```

`names` 與 `"all": true` 二選一。語意是**砍掉重來**：宣告沒變，所以砍完 daemon 會再拉一顆（不算崩潰、不退避，[daemon-reconcile §3](daemon-reconcile.md)）。
用途：換環境（kill 全池讓每顆重讀 `envs.json`）、救卡住的 cpu。

result：`{"killed": ["3"], "skipped": {"5": "pending"}}`。`running` 的開始走階梯；`dead`／`failed` 的清掉等待時間、儘快重拉；
`pending`／`killing` 的略過；不是成員的略過（`"not-member"`）。池不在＝`NotFound`。

## 3. `ls`

params `{}` 或 `{"pool": P}`。沒給 pool：`{"pools": {P: 摘要}}`；給了：`{"pool": P, "summary": 摘要, "children": {"<i>": 孩子檔的內容＋"busy"}}`。
摘要與孩子檔的格式在 [daemon-home §3](daemon-home.md)。帶 pool 的回音可能很大（上萬顆約 1 MB），是給人偶爾用的。

## 4. 崩潰窗口

| 誰崩、崩在哪 | 會看到什麼 | 怎麼收 |
|---|---|---|
| kernel：記了 `pending`、還沒放單 | 單在 `sends` | 下一格出貨補放 |
| daemon：收了單、寫 `pool.json` 之前 | 新 daemon 開機對帳回 `Interrupted` | kernel 清 `pending`、重算重送 |
| daemon：寫了 `pool.json`、回音之前 | 同上（`Interrupted`），但宣告已生效 | 重送同一份，`ver` 不加 |
| daemon 沒在跑 | 單留在 `D/requests/` | 等；daemon 開起來就處理。`cpu ls` 印「單在路上，daemon 沒在跑」 |
| kernel：讀了回音、還沒寫帳本 | 回音還在 | 下一格重讀重判（冪等） |
| 兩個 kernel 用同一個 `dpool` | 後來的收到 `NameTaken` | kernel 記進 `pools.P.error`、`ls` 大聲印；人改 `dpool` |
| 人刪了 `D/pools/<pool>/` 或換了 daemon 家 | kernel 的 `sent` 還在、daemon 沒這池 | kernel 平常不知道（不送單就不會發現）；`ls` 看摘要不在就報 `池不見了（跑 aos-kernel boot）`，boot 會重送全部宣告 |
| 人用 `aos-daemon scale --force` 改了 kernel 的池 | daemon 宣告跟 kernel 的 `sent` 不同 | kernel 下次送單就蓋回去；中間派到被收掉的號會卡住，所以 `--force` 只給救急（[daemon-cli](daemon-cli.md)） |

## 5. 單的檔名

kernel 放的：`k-<chain>-<seq>-scale-<P>.json`（一格一池最多一張）；boot 放的：`k-<chain>-boot-scale-<P>.json`（kernel 池縮到 0 那張加 `-down`）。
ack 照 proto5 §1.3 的 `ack-<chain>-<seq>-<家名>-<digest>.json`。CLI 放的照範式慣例 `cli-<epoch ns>-<pid>.json`。
