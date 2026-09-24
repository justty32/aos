# kernel 的家與 cpu 的家

← [spec 導航](README.md)｜池表：[kernel-info](kernel-info.md)｜帳本：[kernel-ledger](kernel-ledger.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/kernel.md](../../proto5/spec/kernel.md) §1 的目錄圖與「建家」段落**；家的規則一、主人／外人的分法不變。

## 1. 目錄

```text
K/
  info.json                 池表（kernel-info）；人寫，或 aos-kernel cpu add／rm 改
  state.json                帳本（kernel-ledger）
  requests/                 syscall、ack、stop，加上 cpu 丟來的回音通知 resp-*（cpu-notify）
  responses/
  pools/<P>/envs.json       這池的環境；kernel 照 info.pools.P.envs 寫
  pools/<P>/inst.json       這池的 cpu 模板（§2）
  pools/<P>/cpus/<i>/       一顆 cpu 的家：info.json、inst.json、state.json、requests/、responses/、cpu.log
  kernel.log
```

跟 proto5 的差別：`K/cpus/<name>/` 改成 `K/pools/<P>/cpus/<i>/`；kernel 池那顆固定是 `K/pools/kernel/cpus/0/`。

## 2. 池模板：每顆 cpu 的 `inst.json` 都一樣

```json
{"argv": ["/abs/proto5/cli/aos-cpu", "."], "cwd": ".",
 "stderr": {"$opt": "append", "$val": "cpu.log"},
 "envs": {"$ref": "../../envs.json"}}
```

`.json` 目標的 base 是檔所在的資料夾（[aos-exec](../../proto5/spec/aos-exec.md)），所以放在 `cpus/<i>/inst.json` 時，
`.`、`cpu.log` 都是那顆自己的家，`../../envs.json` 是池的環境檔。**每顆的 inst.json 內容一模一樣**，就是 `pools/<P>/inst.json` 的複本。
`argv[0]` 是 kernel 建模板時找到的 `aos-cpu` 絕對路徑（同 proto5 的做法）。

好處：改池的 `envs` 只要重寫一份 `envs.json`；daemon 每次拉（含重拉）都重讀 target（[daemon.md §2](../../proto5/spec/daemon.md)，不變），
所以**之後拉起來的 cpu** 就帶新環境。已經活著的不會變——要全池換新就 `aos-daemon kill --pool <dpool> --all`（[daemon-cli](daemon-cli.md)）。

`envs` 整格用 `$ref` 取進來是 [inst-posix](../../proto5/spec/inst-posix.md) 本來就允許的（先解再驗，`envs` 的 `clear` 選項照認）。
`$ref` 找檔的中心是解出來的 `cwd`（inst-posix §3.1）——這裡就是那顆 cpu 的家，所以 `../../envs.json` 指到池的環境檔；
`envs.json` 裡再有 `$ref`，中心仍是那顆的家，不是池目錄。`$ref:""` 指的是 `envs.json` 自己那份文件。（審查 R14）

## 3. cpu 的家怎麼建

「建家」＝**缺的補齊、不覆蓋**（同 proto5 §1.1 末）：`cpus/<i>/`、`requests/`、`responses/`、`info.json`、`inst.json` 各自不在才寫。

一顆工作 cpu 的 `info.json`：

```json
{"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 200, "timeout_ms": 0,
 "notify": "/abs/K/requests"}
```

`poll_ms`／`timeout_ms` 照 info 的 `cpu` 格；`notify` 是新欄位，叫 cpu 回完音就往 kernel 家丟一張通知（[cpu-notify](cpu-notify.md)）。
kernel 池那顆**不帶 `notify`**（它跑的是 tick，回音由 tick 自己收），`poll_ms` 20。

什麼時候建：
- tick 決定要長大時，只建**新加的那幾號**（[kernel-pools](kernel-pools.md)），O(新增數)。
- boot 時把每個池的每一號都「缺的補齊」一次（O(池大小)，只在 boot）。

模板與 `envs.json` 的寫法：kernel 在 boot 與「info 的 envs 變了」時重寫（`.tmp` 再 rename）；帳本記一個摘要（`envs_digest`）來判斷「變了沒」，每格不用讀檔比對。

## 4. 家不刪

縮小、`skip` 退休的 cpu，家留著：裡面可能還有沒 ack 的回音、`cpu.log` 要給人查。再長回來就用回同一個家。
所以磁碟上的家數＝**這個池曾經到過的最大號＋1**。要清得人手動刪（先確定那號不在任何池的成員裡、daemon `ls` 看不到它）。
清理指令這版不做，列在 [README 的要使用者拍的](../README.md)。

## 5. 主人與外人

- `K/` 的主人仍是「當下正在跑的那一格 tick」；`K/pools/<P>/envs.json`、`inst.json` 也是 kernel 的東西，只有 tick 與 boot 寫。
- `K/pools/<P>/cpus/<i>/` 各是另一個家，主人是那顆 `aos-cpu`；kernel 只在家缺東西時補，已經在的一律不改（同 proto5）。
- cpu 往 `K/requests/` 丟通知，是外人被允許的那一種動作（放一則 request，[cpu.md §1](../../proto5/spec/cpu.md) 規則一）。
