# daemon-root：根 daemon 定義（只帶時鐘與清道夫，agent 之後再掛）

← [templates](../README.md)

給「一個定義資料夾本身就是根入口」的用法：起它＝起一台根 daemon，表上只有 `_clock`（每秒寫 `$AOS_STACK/clock`，`.env` 把 `AOS_CLOCK` 指過去，子項照繼承聽這個鐘）與 `_sweeper`（每 10 分鐘清這台自己的 stderr 封存、寫 `sweeper_report.json`）；agent 不寫進 `daemon.json`，由 `aos-agent ctl add` 經 `procs_requests` 掛上、記在 stack 的表裡。

| 檔 | 做什麼 |
|---|---|
| `_entry` | `aos-daemon --enable-logs daemon.json`（狀態變化印到 stdout） |
| `daemon.json` | `procs_requests` 信箱＋`_clock`、`_sweeper` 兩列，沒有身體 |
| `.env` | `AOS_CLOCK=${AOS_STACK}/clock`（殼裡已有 `AOS_CLOCK` 就不蓋，起之前 `unset`） |

## 用法

下面的 `defs`、`stacks/root`、`ann` **只是例子**：定義與 stack 可以叫別的名字、可以分散在 `defs_1`、`defs_2`、可以放在別的外部資料夾，也不必在同一層或同一個 repo——一切由 `aos-exec` 的參數與你給的路徑決定，範本與程式都不假設這些名字。

```sh
cd <你的專案>
<repo>/proto8/templates/copy-out daemon-root defs          # 根定義
<repo>/proto8/templates/copy-out agent-fsm defs/ann        # 一隻 agent 的定義
mkdir -p stacks && cp <repo>/proto8/cmd/aos-agent/stack.gitignore stacks/.gitignore   # stack 進 git 時擋掉不該帶的
export AOS_LLM_KERNEL=<llm kernel 專案的 stack>            # 在起根的殼設，子項照繼承
unset AOS_CLOCK AOS_DAEMON AOS_STACK
aos-exec --stack stacks/root defs                          # 前景起根；stacks/、stacks/root 不在會自己建
```

另一個殼掛 agent（`-w .`＝工作區是專案資料夾；表上存相對路徑，整包搬走照樣對）：

```sh
aos-agent -d stacks/root ctl add --auto-restart -w . defs/ann
aos-daemon-ctl -d stacks/root ls        # _clock、_sweeper、ann 都是 running
```

子項的 stack 預設在 `stacks/root/procs/<名>/`（例 `stacks/root/procs/ann/`）。

- **llm kernel** 是另外一個專案、自己起停（可用 `copy-out kernel/llm-kernel <那邊的定義>` 抄一份，再 `aos-exec --stack <那邊的 stack> <那邊的定義>`）；`AOS_LLM_KERNEL` 指它的 stack。它沒開時 agent 只是一直等、不會壞。
- **下班**：`aos-daemon-ctl -d stacks/root shutdown`（子項全睡下、記在表上），再 `git` 推。
- **換台**：`git` 拉過去、照上面設好環境變數後直接 `aos-exec --stack stacks/root defs`，睡下的 `ann` 自己醒、接著跑，不用其他指令。
- **指到 proto8 的路徑**：copy-out 預設寫成 `{"$env": "AOS_PROTO8", "$path": …}`，每台設一次 `AOS_PROTO8=<這台 proto8 的絕對路徑>` 即可；錨點 `.aos-proto8`（`copy-out --relink`）只是可選的另一種準備方式，不是必要步驟。本範本自己沒有指進 repo 的路徑。
- 子 daemon（領班、總機）不帶鐘列，只帶自己的 `_sweeper`；鐘只在根。
