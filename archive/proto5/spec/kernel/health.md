← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：ls 第一行 health

（原本在 cli-ops.md 的 ls 段；2026-09-24 proto5-2 池式納入：cpu 不再逐顆查，改看池摘要。2026-09-24 one-boot：`cpus`（kernel cpu 不在）拿掉，加 `legacy`、`tick`，`stall` 改看帳本的 `last_tick_at` 與 daemon 登記的連敗。）

`aos-kernel ls` 文字版**第一行** `health <一句>` 說整體正不正常，把「停住」跟「正常忙碌」「會自己好」分開；`--json` 的 `health: {code, message}` 是同一句。
同一套判定在 `lib/aos_kernel_health.py`，[`aos-agent status`](../aos-agent/cli-status.md) 也用它（code 是 `ok` 以外、也不是 `recovering` 就印 `kernel 家有問題：…`）。

**先中先印**：

| code | 什麼時候 | 句子 |
|---|---|---|
| `dirs` | 缺 `requests/`、`responses/`、`pools/` | `K 家缺目錄：…（跑 aos-kernel check --target <K>）` |
| `legacy` | 帳本還是舊的 `K/state.json`（one-boot 之前的 kernel 寫的） | `帳本還是舊的 K/state.json（跑 aos up 或 aos-kernel boot --target <K>，換成 sqlite）` |
| `stopped` | `phase` 是 `stopped` 或從沒 boot | `停機中（aos up 或 aos-kernel boot --target <K>）` |
| `daemon` | 開 tick 的 daemon 沒活（或解不出來） | `daemon 沒在跑：<D>（aos up；或 aos-daemon boot --target <D> 之後 health 還不是 ok 再 aos-kernel boot …）` |
| `daemon` | 其他已宣告池的 daemon 沒活 | `daemon 沒在跑：<D>（先 aos-daemon boot --target <D>）` |
| `tick` | daemon 活著，但沒登記這個 kernel（`D/kernels/` 沒這格）：沒人開 tick | `daemon <D> 沒在替這個 kernel 開 tick（跑 aos up 或 aos-kernel boot …）` |
| `stall` | `phase` 是 `running` 或 `stopping`，daemon 登記的連敗次數 > 0 | `tick 連敗 N 次（最後退出 X；看 daemon 的 stderr，例如 D/daemon.log；跑 aos-kernel check …）` |
| `stall` | `phase` 是 `running`（`stopping` 不判），帳本 `last_tick_at` 超過 max(10 秒, 10×`tick_ms`) 沒前進 | `tick 停住：N 秒沒前進（跑 aos-kernel check --target <K>）` |
| `pools` | 某工作池 `error` 不是 null、或摘要不在但 `sent` 不空（正在縮到 0 的不算） | `池 P：<代號>（<message>）`／`池 P：池不見了（跑 aos-kernel boot …）`；多池用「；」接 |
| `bad` | （09-24 tick-gap）帳本裡有反覆行程被判 `bad`（停了、不會自己好） | `反覆工作 N 個 bad：名字、…（kernel 不再派它；看 aos-kernel ls 的 look 欄，修好後 rm 再 add 或重跑登記它的指令）`；最多列 5 個名字 |
| — | 上面都沒中、`phase` 是 `stopping`（停機收尾中，池本來就在縮） | `ok` |
| `recovering` | 有池在搬 | `搬池中：池 P（舊位置 <D> <dpool> 收完才換）` |
| `recovering` | 某工作池摘要 `running` 少於 `sent` 的成員數（縮小的 scale 單在途時改比 `pending` 的 count，取較小的；`cpu rm` 剛下不報少顆） | `池 P 少 N 顆（daemon 在補；看 aos-daemon ls --target <D> --pool <dpool>）`——**會自己好，不是停住** |
| `ok` | 其他 | `ok` |
| `broken` | 帳本或 info 讀不到 | `kernel 家讀不到：…`（這時 `ls` 退 1、stdout 空） |

**agent 的暫停也上第一行**：上面判完是 `ok` 時，`ls` 再看帳本裡的 agent（名字 `agent-` 開頭、不是 once、target 是某個家的 `tick.json`；讀那個家的 `paused`、`resumed`、
`state.json` 的 `errors` 與沒到的 `continue-*.json` 門，不讀記憶、不拿鎖）：
有暫停的＝`agent 暫停中：agent-bob（連敗）、agent-amy（手動）（修好原因後 aos-agent continue --all）`（code `agents_paused`）；
否則有連敗 1、2 次的＝`重試中：agent-bob（連敗 1/3）`（code `retrying`）；否則有 `resumed` 的＝`已解除暫停，等下一次成功：agent-bob`（code `resuming`）。
這三個 code 只在 `ls`，`aos-agent status` 不用（它有自己的一套）。每個 agent 的行程在 proc 表的 `備註` 欄也標同樣的字（[cli-ls.md](cli-ls.md)）。

跟第 1 版的差別：
- 「cpu missing」「恢復中（cpu dead）」拿掉——daemon 沒有孩子表了。工作池少了是 `recovering`（warn），不逐顆列名字。（第 2 版看 kernel 池摘要的 `cpus`，one-boot 拿掉，換成 `tick`。）
- 新增 `pools`（池出錯、池不見了）。
- daemon 沒在跑的提示改成「aos up；或先 aos-daemon boot，之後 health 還不是 ok 再 aos-kernel boot」：daemon 重開後池會自己拉回來、照登記接著開 tick（[§6 boot](boot.md)）。

（09-24 tick-gap）`bad` 以前不上第一行（還是 `ok`），T5 真跑郵差壞了十幾分鐘沒人發現。`aos up` 最後一行印的也是這句（但不因此退 1：kernel 本身沒壞）。
`aos-agent status` 把 `bad` 當 `ok` 看（是別的反覆工作壞了，不是 kernel 家壞了；這個 agent 自己 bad 另有一行）。
