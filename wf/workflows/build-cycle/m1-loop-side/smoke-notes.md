# M1 煙霧測試留存（實跑原文）

← [plan](plan.md)｜[spec](spec.md)｜[SPEC](../../../../docs/SPEC.md)

**用途**：S8 寫 `docs/usage.md` 時直接照抄——feature-dev 鐵律要求「文件裡的每條指令與
輸出都真的跑過」（spec 驗收 7）。**本檔的每一段都是實跑貼上的原文，不要手改**；命令
改了就重跑、重貼。

**跑法**（每一節開頭都標了世界的位置與日期）：

```text
WSL Ubuntu；世界開在 /tmp（ext4，renameat2 可用，不是 drvfs）
PATH 前面掛上 <repo>/build/bin，所以下面的 `aos` 就是 default preset 建出來的執行檔
每段的 `[exit N]` 是該命令的退出碼，stderr 與 stdout 一起收
```

---

## S4 `aos deliver`（2026-08-28，世界 `/tmp/aos-smoke-gFH92x`）

投遞、彙整、取件走完整一圈；含各種拒絕路徑與退出碼。

```console
$ aos --help
usage: aos <command> [args...]

commands:
  exec         推進一個 aos 資料夾的一回合
  init         初始化一個 aos 資料夾
  deliver      投遞一批 instruction 到 aos 資料夾的收件匣
  tooljson     讀取並檢查 tool JSON spec
  llms         呼叫 OpenAI 相容端點並查詢模型能力
[exit 0]

$ aos init .
[exit 0]

$ printf '{"argv":["touch","a"]}' | aos deliver
{"delivery":"694-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ printf '{"argv":["touch","b"]}' | aos deliver
{"delivery":"697-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ ls -1 .aos/inst.tempd/
694-0.json
697-0.json
[exit 0]

$ printf '[{"argv":["touch","c"]},{"argv":["touch","d"]}]' > batch.json; aos deliver . -f batch.json
{"delivery":"699-0.json","count":2,"target":".aos/inst.tempd"}
[exit 0]

$ aos deliver . -f /dev/null
aos deliver: invalid input: JsonSyntax
[exit 1]

$ printf 'not json' | aos deliver .
aos deliver: invalid input: JsonSyntax
[exit 1]

$ printf '{"argv":["touch","a"],"nope":1}' | aos deliver .
aos deliver: invalid input: record 1: UnknownKey
[exit 1]

$ printf '[{"argv":["touch","a"]},{"argv":[]}]' | aos deliver .
aos deliver: invalid input: record 2: EmptyArgv
[exit 1]

$ ls -1 .aos/inst.tempd/
694-0.json
697-0.json
699-0.json
[exit 0]

$ aos deliver /tmp/aos-smoke-no-such-world -f batch.json
aos deliver: cannot enter /tmp/aos-smoke-no-such-world: No such file or directory
[exit 1]

$ aos deliver . . -f batch.json
usage: aos deliver [folder] [-f FILE|-]
[exit 2]

$ aos exec .
[exit 0]

$ ls -1a . .aos
.:
.
..
.aos
a
b
batch.json
c
d

.aos:
.
..
inst-head.json
inst.tempd
version
[exit 0]

$ cat .aos/inst-head.json
{"version":1,"id":"63558783d7668c4f","origin":"aggregated","result":null}
[exit 0]
```

讀法：

- 三次投遞（`694-0`／`697-0`／`699-0`）＝三個不同 pid 的行程各投一次，序號都從 `0`
  起算（§D-2 的 `<pid>-<seq>`）。同一 process 連投 N 次得 N 份不同名這件事 CLI 演不了
  （一次投遞就一個行程），由 `core/inst/tests/test_run_deliver.cpp` 的第一案蓋住。
- 四種拒收都是**驗證階段**擋下來的：收件匣事後只有三個檔，連 `.temp` 都沒有殘留。
- 一回合 `aos exec .` 把三份投遞（共四筆 instruction）併成一批跑掉，`a b c d` 都在，
  投遞被清空，批旁邊留下 `inst-head.json`（§C-8 四欄位齊，S3 落地的那個）。

## S4 輸入來源的三種寫法與 canonical 位元組（2026-08-28，世界 `/tmp/aos-smoke-4sQSQJ`）

```console
$ printf '{"argv":["touch","z"]}' | aos deliver .
aos deliver: invalid ./.aos: No such file or directory
[exit 1]

$ mkdir world && aos init world
[exit 0]

$ printf '{"argv":["touch","e"]}' > one.json; aos deliver world -f one.json
{"delivery":"734-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ aos deliver world - < one.json
{"delivery":"736-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ aos deliver world -f - < one.json
{"delivery":"738-0.json","count":1,"target":".aos/inst.tempd"}
[exit 0]

$ ls -1 world/.aos/inst.tempd/
734-0.json
736-0.json
738-0.json
[exit 0]

$ cat world/.aos/inst.tempd/*.json
[{"argv":["touch","e"]}]
[{"argv":["touch","e"]}]
[{"argv":["touch","e"]}]
[exit 0]

$ aos exec world && ls -1 world
e
[exit 0]

$ aos exec world; ls -1 world/.aos
inst-head.json
inst.tempd
version
[exit 0]
```

讀法：

- 第一條：沒有 `.aos` 的資料夾**不是世界**，deliver 報錯、不自動建（§D-3）。
  （`aos init world` 也不建資料夾本身，所以前面要 `mkdir world`。）
- `-f FILE`／`-`／`-f -` 三種寫法都通；`-f one.json` 的路徑是相對**呼叫者的** cwd
  解析的（`one.json` 在 `world/` 外面），因為它是命令的輸入、不是世界的一部分。
- 投出去的位元組是 canonical 的（§D-3 裁-7）：投的是單一物件，落地是批陣列
  `[{"argv":["touch","e"]}]`＋一個 LF——`read_all`→`write_all` 往返後的樣子。
- 第二次 `aos exec world` 沒事可做（投遞已清空、沒有新批次），照樣回 0。

---

## 待補（後續步驟寫進來）

- S6：`aos init w && cat w/.aos/turn`（`0`）→ 投遞＋`aos exec w` → `cat w/.aos/turn`（`1`）。
- S7：`strace -c -e fsync` 對空轉 `--loop` 的計數（風險 3 的實測）。
