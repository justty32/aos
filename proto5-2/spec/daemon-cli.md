# daemon 的指令

← [spec 導航](README.md)｜協定：[protocol](protocol.md)｜存檔：[daemon-home](daemon-home.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/daemon.md](../../proto5/spec/daemon.md) §6 的命令列**，並推翻 §7、§9 第 7 條「沒有 ls、沒有 ctl」。

```sh
aos-daemon boot  [--target D]                                     # 開 daemon（照 fix-r4）
aos-daemon halt  [--target D] [--wait-ms N]                       # 停 daemon（照 fix-r4）
aos-daemon ls    [--target D] [--pool P] [--json]                 # 看池
aos-daemon scale [--target D] --pool P --count N [--skip I,J...] [--inst PATTERN] [--home PATTERN] [--force]
aos-daemon kill  [--target D] --pool P (NAME... | --all)
aos-daemon -h ／ aos-daemon <子命令> -h
```

家：`--target D`，省略找 `AOS_DAEMON_HOME`，再省略用 `./`（fix-r4 的慣例）。`boot`／`halt` 的細節以 fix-r4 落地的為準，這份只補「池」帶來的差別。
退出碼同 proto5：0 成功；1 讀驗／I/O／daemon 回錯，stderr 一行 `aos-daemon: <代號>: <白話>`；2 用法錯。

## `boot`

跟 fix-r4 一樣開 daemon；啟動步驟多了「照 `pool.json` 把孩子拉回來」（[handoff §2](handoff.md)）。
**跟 proto5 最大的差別**：daemon 重開之後 cpu 會自己回來，kernel 的鏈多半接得上，不一定要 `aos-kernel boot`。

## `halt`

同 fix-r4／proto5 的 `stop`：daemon 不活就不放單、印 `not running`；活著就放 `stop-*.json`、等 flock 探測不到、印 `stopped`。
停機走批次階梯（[daemon-reconcile §6](daemon-reconcile.md)）；`pool.json` 留著。

## `ls`

**偷看檔案、不放單**：daemon 沒在跑也看得到最後的摘要（第一行會說 daemon 沒在跑）。

沒給 `--pool`：一池一行，讀 `pools/*/summary.json`：

```text
daemon running  pid 100  pools 3  children 10011
k1-kernel   owner /abs/K  want 1      running 1      busy 1     restarting 0  pending 0  dead 0  failed 0  killing 0
k1-default  owner /abs/K  want 10000  running 9990   busy 8123  restarting 3  pending 7  dead 3  failed 0  killing 0
k1-llm      owner /abs/K  want 2      running 2      busy 0     restarting 0  pending 0  dead 0  failed 0  killing 0
```

- `busy`＝活著的孩子裡，家（宣告的 `home` 樣板）的 `state.json` 有 `current` 的。**要逐顆偷看**，是 O(活著的數量)；
  池沒給 `home` 就印 `busy -`。加 `--no-busy` 可以跳過（上萬顆時省一點）。
- 這就是使用者要的「按狀態數活／忙／dead／重拉中」：活＝`running`、忙＝`busy`、dead＝`dead`、重拉中＝`restarting`（外加 `pending`／`failed`／`killing`）。

給了 `--pool P`：先印那池的摘要行，再一顆一行（讀 `kids/*.json`，O(池大小)）：

```text
0     running  pid 2345  gen 3  busy   exits 2  streak 0  since 09:12:03
1     dead     pid 2350  gen 5  -      exits 4  streak 4  next 09:15:40  last_exit 1
2     pending  -
```

`--json` 印同樣的東西（摘要、`children`）成一份 JSON。

## `scale`

放 `scale` 單（[protocol §1](protocol.md)）、等回音（10 秒）、印 `pool P count A -> B (ver N)`。
- 池不在：要給 `--inst`（`target` 樣板，含一個 `{name}`）；`owner` 記成 `cli`。
- 池在、owner 是 `cli`：直接改。
- 池在、owner 是別人（例如某個 kernel）：拒絕，`Owned`、退 1，提示改用 `aos-kernel cpu add／rm`。
  `--force` 才照改（owner 不變）——kernel 不知道這件事，下次它送單會蓋回去；中間它派到被收掉的號的工作會卡住。只給救急用。

## `kill`

放 `kill` 單、等回音、印 `killed 3 5`、`skipped 7 (pending)`。宣告沒變，所以被砍的會再拉起來（砍掉重來，[protocol §2](protocol.md)）。
`--all`＝整池每顆都重來：常用在改了池的 `envs` 之後。上萬顆的池會被 `spawn_per_sec` 節流，要一段時間才全部換完。
