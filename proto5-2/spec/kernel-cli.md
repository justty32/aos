# kernel 的指令：`init`、`cpu`、`ls`、`halt`

← [spec 導航](README.md)｜池表：[kernel-info](kernel-info.md)｜boot：[handoff](handoff.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/kernel.md](../../proto5/spec/kernel.md) §6 的 `init`、`stop`、`ls`、`check` 的池相關部分**；
> `add`／`rm`／`ack`／`tick` 行為不變，只是家改用 `--target`（fix-r4 的慣例）。

```sh
aos-kernel init  [--target K] [--config FILE] [--daemon D]
aos-kernel boot  [--target K] [--wait-ms N]                       # handoff.md §1
aos-kernel halt  [--target K] [--wait-ms N] [--no-wait]
aos-kernel cpu add [--target K] --pool P [--count N] [--env KEY=VALUE]... [--daemon D] [--dpool NAME]
aos-kernel cpu rm  [--target K] (P/<i> | --pool P --count N)
aos-kernel cpu ls  [--target K] [--pool P] [--json]
aos-kernel ls    [--target K] [--pool P] [--procs] [--json]
aos-kernel add／rm／ack／check／tick   # 同 proto5 §6，K 改 --target
```

家：`--target K`，省略找 `AOS_KERNEL_HOME`，再省略用 `./`。退出碼同 proto5（0／1／2）。

## `init`

- `--config FILE`：一份 JSON，內容就是 [kernel-info](kernel-info.md) 的格式（`_metainfo` 可省，會補上）。
  **只放 kernel 參數＋池定義，cpu 可以一顆都沒有**（`pools` 可以是 `{}`，或每池 `count: 0`）。讀驗照 kernel-info §2；不過＝退 1、不建家。
- 沒給 `--config`：預設 `{"pools": {"kernel": {"count": 1}}}`，其他全用預設。之後用 `cpu add` 加。
- `kernel` 池沒寫就補 `{"count": 1}`。
- `daemon`：`--daemon D` 優先，否則 config 裡的，否則 `AOS_DAEMON_HOME`（轉絕對路徑），都沒有就不寫——boot 時才報 `NoDaemon`。
- 建 `requests/`、`responses/`、`pools/`；不建任何 cpu 的家（boot／tick 建）。`K/info.json` 已在就拒絕（同 proto5）。
- 印 `initialized <K>`。

proto5 的 `--cpu`、`--env NAME:KEY=VALUE` 拿掉，改用 `cpu add`。

## `cpu add`

改 `K/info.json` 的池表，就這樣——**不放任何單、不用 boot**，kernel 在跑的話下一格就照新數字做（[kernel-pools](kernel-pools.md)）。

- 池不在：新增 `{"count": N}`（`--count` 省略＝1），`--env` 可重複（字面字串 `KEY: VALUE`，同 proto5 的 `--env`），
  `--daemon`／`--dpool` 有給就寫。
- 池在：`count` 加 N。這時給 `--env`／`--daemon`／`--dpool`＝用法錯 `PoolExists`（改既有池的環境或位置請直接編 info，影響見 [kernel-info §4](kernel-info.md)）。
- `P` 是 `kernel`＝用法錯（kernel 池永遠 1 顆）。
- 印 `pool P count A -> B`；kernel 沒在跑再多印一行「下次 boot 生效」。

## `cpu rm`

- `cpu rm P/<i>`：那號必須是現在的成員（不是＝`NotFound`、退 1）。把 i 加進 `skip`、`count` 減 1（[kernel-info §3](kernel-info.md)）。
- `cpu rm --pool P --count N`：`count` 減 N；N 大於現在的 `count`＝用法錯。收的是最大的那幾號。
- 被收的號手上有工作的，會做完才真的收（[kernel-pools §3](kernel-pools.md)）。印 `pool P count A -> B`。

**`cpu add／rm` 怎麼寫 info**：讀 → 改 → 寫 `.tmp` → rename 之前再讀一次原檔，跟一開始讀到的不同就重來（最多 3 次，再不行＝`Busy`、退 1）。
這擋得住兩個 `cpu add` 撞在一起的多數情況，擋不住「剛好在比對與 rename 之間」有人改；人手改 info 與 CLI 同時跑是保證外。
改完的 info 一樣要能過讀驗；過不了就不寫。info 裡的指示詞（`$env`…）會被保留原樣，CLI 只改 `pools.P.count`／`skip`／新池那一格。

## `cpu ls`

一池一行，讀帳本＋daemon 的 `summary.json`（O(池數)）：

```text
default  want 8  sent 8  busy 3  idle 5  draining 0   daemon k1-default: running 8 restarting 0 pending 0 dead 0 failed 0
llm      want 3  sent 2  busy 1  idle 1  draining 0   daemon k1-llm: running 2 …   scale 單在路上（ver 等回音）
gpu      want 3  sent 0  -                             daemon /abs/D2 gpu: 錯誤 NameTaken（owner /abs/K9）
```

`draining`＝已經不是成員、還在做事的號數。`--pool P` 再一顆一行（O(池大小)）：`P/<i>  idle｜busy <行程名>｜draining <行程名>  daemon <state> gen <n>`（daemon 那欄讀 `kids/<i>.json`）。
`--json` 同樣內容。

## `ls`

第一行 `health`（同 proto5 的做法，先中先印），接著**按池摘要**（同 `cpu ls` 的池行），然後行程：
- 預設只印各狀態的數量（`queued 12  running 8120  done 3  bad 1`），再把 `bad` 的一個一行（附 `看 <路徑>`，同 proto5）。
- `--procs` 才印每個行程一行（上萬個時很長）；`--pool P` 只看那池的 cpu 與行程。

health 判定改的地方（其他同 proto5）：
- 「cpu missing」改看 kernel 池：`k1-kernel` 的摘要 `running` 是 0＝`kernel cpu 不在（daemon 沒在跑或還在拉；跑 aos-kernel boot）`。
- 工作池不再逐顆查：某池 `running`＜`sent` 的成員數＝`池 P 少 N 顆（daemon 在補；看 aos-daemon ls --pool <dpool>）`，是 warn 不是停住。
- 某池 `error` 不是 null、或摘要檔不在但 `sent` 不空＝`池 P：<錯誤>（…）`。

## `halt`

放 `stop` syscall（method 名沿用 proto5 的 `stop`；fix-r4 若改名就跟著）。預設等到 `phase=stopped` 且**這個 kernel 的每個池**在 daemon 的摘要都 `running 0`、`killing 0`，印 `stopped`。
停機時 kernel 把每個池（含 kernel 池）縮到 0（[handoff §3](handoff.md)），所以停完 daemon 那邊只剩空池、會自己消失。
`not running`、`--no-wait`、逾時的處理同 proto5 的 `stop`。

## `check`

`pools` 項改看池表：沒有 `llm` 池、或 `llm` 池 `count` 是 0＝bad。`llm` 項看 `pools.llm.envs`（家已建就看 `K/pools/llm/envs.json`）有沒有 `AOS_LLM_CONFIG`。
`cpus` 項改看各池摘要（同上面 health）。`daemon` 項：池表裡提到的每個 daemon 家都查。其餘同 proto5。
