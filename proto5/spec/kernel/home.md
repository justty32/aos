← [kernel](README.md)｜[spec 總導航](../README.md)

# 1. 家

（2026-09-24 proto5-2 池式納入：`K/cpus/<name>/` 改成 `K/pools/<P>/cpus/<i>/`，多了池模板與 `envs.json`。2026-09-24 one-boot：帳本換成 `ledger.sqlite`、多了 `.tick.lock`；kernel 池那顆拿掉。）池表見 [§1.1](info.md)，帳本見 [§1.2](ledger.md)。

```text
K/
  info.json                 池表（§1.1）；人寫，或 aos-kernel cpu add／rm 改
  ledger.sqlite             帳本（§1.2；sqlite 檔，旁邊可能有 sqlite 自己的 -wal、-shm 檔）
  requests/                 syscall、ack、stop，加上 cpu 丟來的回音通知 resp-*（[cpu §6.4](../cpu/notify.md)）
  responses/
  pools/<P>/envs.json       這池的環境；kernel 照 info.pools.P.envs 寫
  pools/<P>/inst.json       這池的 cpu 模板（見下）
  pools/<P>/cpus/<i>/       一顆 cpu 的家：info.json、inst.json、state.json、requests/、responses/、cpu.log
  kernel.log                有事件的格 append
  .info.lock                cpu add／rm 改 info 時拿的鎖（§6 cpu）
  .tick.lock                同時只准一格的鎖：tick 一開始拿、boot 寫帳本時拿（§3、§7）
  state.json.v2-old         舊版（第 2 版）帳本匯入 sqlite 後改的名；留著給人查，程式不再讀
```

沒有 `procs/` 資料夾：行程紀錄全在帳本裡。（第 2 版的 kernel 池那顆 `K/pools/kernel/cpus/0/` one-boot 起不再用；舊家留著的不刪。）

## 主人與外人

- `K/` 的主人是「當下正在跑的那一格 tick」（daemon 只開一格、再加 `.tick.lock`，保證同時只有一格，§7）；外人只能往 `requests/` 放單、讀 `responses/` 然後放 `ack`；帳本隨便看（只讀：用 `aos-kernel proc`／`ls`，或同一支 lib `lib/aos_kernel_store.py`，§1.2）。
- `K/pools/<P>/envs.json`、`inst.json` 也是 kernel 的東西，只有 tick 與 boot 寫。
- `K/pools/<P>/cpus/<i>/` 各是另一個家，主人是那顆 `aos-cpu`；kernel 對它們也是外人，**只在家缺東西時補**（初始化，不算動別人的家），已經在的一律不改。
- cpu 往 `K/requests/` 丟通知，是外人被允許的那一種動作（放一則 request，[cpu §1](../cpu/layout.md) 規則一）。

## 池模板：每顆 cpu 的 `inst.json` 都一樣

```json
{"argv": ["/abs/proto5/cli/aos-cpu", "."], "cwd": ".",
 "stderr": {"$opt": "append", "$val": "cpu.log"},
 "envs": {"$ref": "../../envs.json"}}
```

`.json` 目標的 base 是檔所在的資料夾（[aos-exec](../aos-exec/README.md)），所以放在 `cpus/<i>/inst.json` 時，
`.`、`cpu.log` 都是那顆自己的家，`../../envs.json` 是池的環境檔。**每顆的 inst.json 內容一模一樣**，就是 `pools/<P>/inst.json` 的複本。
`argv[0]` 是 kernel 建模板時找到的 `aos-cpu` 絕對路徑。

好處：改池的 `envs` 只要重寫一份 `envs.json`；daemon 每次拉（含重拉）都重讀 target（[daemon §2](../daemon/spawn.md)），
所以**之後拉起來的 cpu** 就帶新環境。已經活著的不會變——要全池換新就 `aos-daemon kill --pool <dpool> --all`（[daemon §6.3](../daemon/cli.md)）。
那份 inst 裡的 `$env` 讀的是**daemon 的環境**（是 daemon 在拉它）；在別的終端 `export` 不會影響已經在跑的 daemon。

`envs` 整格用 `$ref` 取進來是 [inst-posix](../inst-posix/README.md) 本來就允許的（先解再驗，`envs` 的 `clear` 選項照認）。
`$ref` 找檔的中心是解出來的 `cwd`（inst-posix §3.1）——這裡就是那顆 cpu 的家，所以 `../../envs.json` 指到池的環境檔；
`envs.json` 裡再有 `$ref`，中心仍是那顆的家，不是池目錄。`$ref:""` 指的是 `envs.json` 自己那份文件。

## cpu 的家怎麼建

「建家」＝**缺的補齊、不覆蓋**：`cpus/<i>/`、`requests/`、`responses/`、`info.json`、`inst.json` 各自不在才寫。
建到一半崩掉，下一格或下次 boot 會補齊，不會卡住。

一顆工作 cpu 的 `info.json`：

```json
{"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 200, "timeout_ms": 0,
 "notify": "/abs/K/requests"}
```

`poll_ms`／`timeout_ms` 照 info 的 `cpu` 格；`notify` 叫 cpu 回完音就往 kernel 家丟一張通知（[cpu §6.4](../cpu/notify.md)）。
通知丟進 `K/requests/`，daemon 看到有新檔就馬上開一格（[daemon §10](../daemon/ticks.md)），所以回音不用等到下一次 `tick_ms`。

什麼時候建：
- tick 決定要長大時，只建**新加的那幾號**（[§3.1](pools.md)），O(新增數)。
- boot 時把每個池的每一號都「缺的補齊」一次（O(池大小)，只在 boot）。

模板與 `envs.json` 的寫法：kernel 在 boot、新池、「info 的 envs 變了」時重寫（`.tmp` 再 rename）；帳本記一個摘要（`envs_digest`）來判斷「變了沒」，每格不用讀檔比對。
每顆 cpu 的 `inst.json` 只在缺時寫。

## 家不刪

縮小、`skip` 退休的 cpu，家留著：裡面可能還有沒 ack 的回音、`cpu.log` 要給人查。再長回來就用回同一個家。
所以磁碟上的家數＝**這個池曾經到過的最大號＋1**。要清得人手動刪（先確定那號不在任何池的成員裡、daemon `ls` 看不到它）。
這版不做清理指令（09-24 Q9 照草稿）。
