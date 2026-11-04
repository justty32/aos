← [入口](README.md)｜涵蓋：要使用者用 root 做的；用例怎麼套；邊緣狀況（還沒問使用者）｜上一份 [02-決定-照推薦定-可翻案-使用者-10-2](02-決定-照推薦定-可翻案-使用者-10-2.md)

## 要使用者用 root 做的

```
sh proto8/extras/sandbox/root/setup.sh            # 先乾跑看要做什麼
sudo sh proto8/extras/sandbox/root/setup.sh --apply
sudo -n /usr/local/bin/s6-setuidgid aos-run id      # 驗：uid 是 aos-run
```

做了四件：s6 四支（`s6-setuidgid`、`s6-applyuidgid`、`s6-envuidgid`、`s6-softlimit`）從試驗場放進 `/usr/local/bin`（或改裝 AUR 的 s6）；建 `aos-run`；開 `/srv/aos-run`；加 `/etc/sudoers.d/aos-run`（先 `visudo -c` 驗過才放）。拆掉的指令在腳本最後一行。之後要用身分層：`sudo -n s6-setuidgid aos-run aos-sandbox 設定檔 prog…`（身分在最外面，設定裡不寫 `user`），或由 root 起的 daemon／kernel 在設定裡寫 `"user": "aos-run"`。

## 用例怎麼套

| 用例 | 怎麼關 | 擋什麼、不擋什麼 |
|---|---|---|
| 自我改進 | 預設就關（S11）；工作區放 `sandbox.json` 換設定或寫 `false` 不關 | 擋：讀判準、碰家目錄、連網、吃爆記憶體／CPU。不擋：判準是檢查程式時，檢查程式自己跑函數（要關得檢查程式作者自己接） |
| pi-tools／工具庫的 bash | 工具資料夾 `_entry` 寫 `["aos-sandbox", "sandbox.json", "aos-exec", "inner"]`，`inner` 指原本的工具（[examples/bash-boxed](../../../../extras/sandbox/examples/bash-boxed)） | 擋：出工作區、連網。原本工具一行不改 |
| claude／codex CLI 工具 | [examples/cli-tool.json](../../../../extras/sandbox/examples/cli-tool.json)：要網、要寫 `~/.claude`、`~/.codex` | 只擋「讀寫工作區以外」；CLI 自己的沙盒（`--tools`、`sandbox_mode`）照舊 |
| agent 當工具 | [examples/agent.json](../../../../extras/sandbox/examples/agent.json)：斷網、信箱綁進來（`rw`＋`env` 的 `AOS_KERNEL`）、kernel 那邊要寫 `accept` | 擋：任意單子（S18）。換帳號跑時信箱照 `setup.sh --mailbox` 設 |

## 邊緣狀況（還沒問使用者）

- **kernel 信箱**：`accept` 名單裡的腦照信裡的 `AOS_WS`、`AOS_STACK` 動檔（agent-ivy 的 brain.py 會搬 `$AOS_WS/new/` 的題目、寫 `$AOS_STACK/current.txt`），寄信的人把它們指到別的 agent 的工作區就能借 kernel 的手去動；同一個信箱的人看得到彼此的信（含整份環境）——要分開就分信箱、分群組；同一個帳號、只靠 bwrap 時，綁了信箱的上層資料夾（例：信箱放在綁進來的 `$AOS_STACK` 底下）就等於給了信箱。
- **`sender.lock`**：寄得進信箱的程式自己建一封信、拿著鎖不放，kernel 就當它是活著的寄信人——鎖只說「人還在」、不是身分（身分只有 Linux 的 uid）。閘門被 SIGKILL 時鎖自動放掉；kernel 讀不到鎖檔（權限不給）＝當人不在、丟信。
- **`procs`（`-p`）是整個使用者的行程數**：用自己的帳號跑時，瀏覽器等行程都算進去，設小了一開跑就失敗；只有專用帳號（`aos-run`）時才有意義。
- **`mem_mb` 是虛擬記憶體上限**：會先預留大塊虛擬記憶體的程式（Go、Java、Node、某些 LLM 函式庫）可能一起跑就失敗；Python 小程式沒事。
- **綁進來的路徑會帶出上層資料夾的名字**：綁 `/home/lorkhan/repo/…/x`，沙箱裡 `ls ~` 看得到 `repo`（空殼、看不到內容）。
- **cwd 不在沙箱裡**：bwrap 靜靜改到 `/`；相對路徑的 prog 會找不到。
- **符號連結指出去**：`ro`／`rw` 裡的連結會照指到的地方綁；函數在 `rw` 裡自己做的連結指到外面，沙箱裡看不到（指到的地方沒綁）。
- **身分層的權限**：換成 `aos-run` 之後，它進不了 700 的家目錄、也進不了 `mkdtemp` 開的 700 暫時資料夾——self-improve 的暫時資料夾要改到 `/srv/aos-run` 底下才能配身分層用（現在只配命名空間層）。`sudo` 預設清環境，`PATH`、`AOS_*` 要另外帶（`sudo --preserve-env=…`）。
- **stack 也得綁**：包住 `aos-exec` 時，它會在沙箱裡建 `$AOS_STACK`；stack 沒列進 `rw` 就建不了（或建在沙箱的 `/tmp`、跑完就沒了）。
- **巢狀的沙箱**：沙箱裡再叫 `aos-sandbox`：bwrap 在 user namespace 裡再開一層可以，但 `user` 換不了（不是真 root）。
- **只在 Linux、要開 user namespace**：有的發行版或容器關了 unprivileged userns，bwrap 就起不來（`aos-sandbox` 不會降級成不關，直接是 bwrap 的錯）。
- **`/etc` 整個唯讀綁進來**：`/etc/passwd`、`/etc/hosts` 看得到（本來就是誰都能讀的）；`/etc/resolv.conf` 指到 `/run` 的機器上 `net: true` 也解析不了名字（`/run` 沒綁）。
