← [daemon](README.md)｜[spec 總導航](../README.md)

## 6.3 `ls`、`scale`、`kill`

（2026-09-24 proto5-2 池式納入，新節；推翻第 1 版「沒有 ls、沒有 ctl」。2026-09-24 one-boot：`ls` 多印登記的 kernel。）用法總表在 [§6](lifecycle.md)。

### `ls`

**偷看檔案、不放單**：daemon 沒在跑也看得到最後的摘要（第一行會說 daemon 沒在跑）。只看有 `summary.json` 或 `pool.json` 的池。

沒給 `--pool`：一池一行，讀 `pools/*/summary.json`：

```text
daemon running  pid 100  pools 2  children 10010  kernels 1
k1-default  owner /abs/K  want 10000  running 9990（含 restarting 3）  busy 8123  pending 7  dead 3  failed 0  killing 0  draining 0
k1-llm      owner /abs/K  want 2      running 2（含 restarting 1）     busy 0     pending 0  dead 0  failed 0  killing 0  draining 0
kernel /abs/K  每 1000 ms 開一格 tick
```

- 第一行 `children`＝各池 running＋pending＋dead＋failed＋killing＋draining 的和（不含 tick）；`kernels`＝登記了幾個 kernel（one-boot）。
- 池表下面每個登記的 kernel 一行（讀 `kernels/*.json`，[§10](ticks.md)）：`kernel <K>  每 N ms 開一格 tick`，連敗時行尾加 `  連敗 N（最後退出 X）`。
- **`restarting` 是 `running` 的子集**，所以印成 `running 2（含 restarting 1）`，不另開一欄——避免被讀成「running 2 加 restarting 1 比 want 2 多一顆」（09-24 裁定，實作 D-126）。
  `dead`＝死了在等重拉，`restarting`＝已經重拉、還沒活過 `stable_ms`。
- `busy`＝活著的孩子裡，家（宣告的 `home` 樣板）的 `state.json` 有 `current` 的。**要逐顆偷看**，是 O(活著的數量)；
  池沒給 `home` 就印 `busy -`。加 `--no-busy` 可以跳過（上萬顆時省一點）。
- 這就是「按狀態數活／忙／dead／重拉中」：活＝`running`、忙＝`busy`、dead＝`dead`、重拉中＝`restarting`（外加 `pending`／`failed`／`killing`／`draining`）。

給了 `--pool P`：先印那池的摘要行，再一顆一行（宣告的成員逐號列，有 kids 檔的讀檔、沒有的印 `pending`；再列不是成員但還在收的 `draining`。O(池大小)）；
那池沒有 `summary.json` 也沒有 `pool.json`＝`NotFound` 退 1：

```text
0     running  pid 2345  gen 3  busy   exits 2  streak 0  since 09:12:03
1     dead     pid 2350  gen 5  -      exits 4  streak 4  next 09:15:40  last_exit 1
2     pending  -
```

`busy` 欄：活著且忙＝`busy`、活著不忙＝`idle`、其他＝`-`。kids 檔的 `streak` 可能比記憶體的舊（活滿 `stable_ms` 不寫檔）。
`--json` 印同樣的東西成一份 JSON：形狀同 [§3 `ls`](methods.md) 的回音，多一格 `daemon: {running, pid}`。沒給 `--pool` 時還多一格 `kernels`：**陣列**，每格是一個登記檔的內容（照檔名排）——跟 `ls` method 回的 `kernels`（以 id 為鍵的物件、多 `running`）形狀不同，因為 CLI 是偷看檔、daemon 沒在跑也看得到。

### `scale`

daemon 沒在跑就不放單、`NotRunning` 退 1（放了會在下次開機才生效，人看不懂）。否則放 `scale` 單（§3）、等回音（10 秒）、印 `pool P count A -> B (ver N)`。
- 池不在：`count`>0 要給 `--inst`（`target` 樣板，含一個 `{name}`；沒給＝用法錯 2）；`owner` 記成 `cli`。`--inst`／`--home` 相對路徑先轉絕對。
- `--skip` 省略＝沿用 `pool.json` 現在的（送 `[]` 會把退休的號叫回來）。
- 池在、owner 是 `cli`：直接改。
- 池在、owner 是別人（例如某個 kernel）：拒絕，`Owned`、退 1，提示改用 `aos-kernel cpu add／rm`。
  `--force` 才照改（送的 owner 是池現在的 owner，不帶 `decl`）——kernel 不知道這件事，下次它送單會蓋回去；中間它派到被收掉的號的工作會卡住。只給救急用。

### `kill`

daemon 沒在跑＝`NotRunning` 退 1。否則放 `kill` 單、等回音、印 `killed 3 5`、`skipped 7 (pending)`。宣告沒變，所以被砍的會再拉起來（砍掉重來，§3）。
`--all`＝整池每顆都重來：常用在改了池的 `envs` 之後。上萬顆的池會被 `spawn_per_sec` 節流，要一段時間才全部換完。
