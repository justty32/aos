← [入口](README.md)｜涵蓋：llm kernel 自己一台 daemon 的佈局、`AOS_LLM_KERNEL` 的值、信箱固定名、多台 agent daemon 共用、「設 daemon 都是指其 stack」三個選項、要轉給改名隊的語意改動｜上一份 [06-實作步驟草稿](06-實作步驟草稿.md)｜下一份 [08-實作結果](08-實作結果.md)

# llm daemon 的佈局（fable 照使用者 11-05 的用法定的細節，可翻案）

使用者的用法（原文見 [README](README.md)）：定義放 `~/llm_kernel/def`（放哪都行，`def/` 只是方便），`cd ~/llm_kernel && aos-exec --stack . def` 把 llm 的 daemon＋kernel 叫起來；另開視窗起跑 agent 的 daemon（可以好幾台），起之前 `export AOS_LLM_KERNEL=~/llm_kernel`；全部共用一個 llm kernel，統一管理這台電腦出去的 endpoint 呼叫。

## 1 `~/llm_kernel` 長什麼樣

```
~/llm_kernel/                 ← 那台 llm daemon 的 stack＝那台機器（AOS_LLM_KERNEL 指這裡）
  def/                        ← 原始碼（放哪都行；例子放這裡一個資料夾帶走）
    _entry                    ["aos-daemon", "daemon.json"]
    daemon.json               {"exec": {"argv": ["aos-llm-kernel", "kernel.json"]}, "interval_ms": 300}
    kernel.json               slots、budget、timeout_ms、exec、endpoint、endpoints（金鑰 $env／$ref）
  state.json  procs_state.json  procs_ctl_mailbox/  procs/      ← daemon 自己的（aos-daemon 現狀）
  mailbox/                    ← kernel 的收件箱（固定名；tmp/ new/ cur/、ask 的 reply/、.flock）
  queue.json  used.json  daemon_reply/                           ← kernel 自己的
```

- 身體＝kernel（[02 § 1](02-兩種模式.md) 繼承式第一個實例）；`procs` 不寫，表上只會出現身體掛上來的 `llm_<id>` 問腦列（`aos-daemon-ctl --daemon ~/llm_kernel ls`＝正在飛的腦呼叫；統一管理就是這張表＋`used.json`）。
- `aos-exec --stack . def`：`AOS_STACK`＝`~/llm_kernel/`、cwd＝`def/`（kernel.json 的相對 `exec` 從 `def/` 算）、`AOS_WS`＝`~/llm_kernel`（沒給 `--ws`＝cwd）。daemon 寫的檔都在 stack 根、問腦 proc 在 `mailbox/cur/<id>/`，跟 `def/` 不撞（只要原始碼資料夾不叫 `mailbox`、`procs`、`state.json`…）。
- 整個資料夾一起搬＝定義＋狀態一次帶走；portable-flow 的「存相對 daemon stack」在這裡自然成立（`def/` 就在 stack 底下）。跟 portable-flow 預設的 `ws/.stack` 並存：使用者「這就只是一種用法而已，沒啥好糾結的」。

## 2 `AOS_LLM_KERNEL`＝llm kernel 的 stack，信箱固定在 `<stack>/mailbox/`

- **值的語意改了**（要轉給改名隊）：今天 `AOS_KERNEL`＝**信箱**資料夾；改名後 **`AOS_LLM_KERNEL`＝llm kernel 的 stack**（合一時＝llm daemon 的 stack；kernel 當 proc 掛在別台時＝那個 proc 的小格 `…/procs/llm/`）。aos-llm 的 `send`／`ask`／`regret` 寄到 **`$AOS_LLM_KERNEL/mailbox/`**，`ask` 的回信箱 `$AOS_LLM_KERNEL/mailbox/reply/`；kernel 這邊 `kernel.json` 的 `mailbox` key 拿掉、固定 `$AOS_STACK/mailbox/`（[03 § 6](03-問腦改掛daemon.md)）。
- 為什麼固定名：寄信的人手上只有 stack；同一招 aos-daemon-ctl 早就在用（daemon 的 stack 裡固定讀 `procs_state.json` 找信箱）。固定名只這一個、是這個 hub 的唯一入口（10-31「固定名字可以但限縮範圍」）。另一條（不推薦）：kernel 寫一扇 `llm_kernel_state.json` 回報信箱名——多一扇窗、多一個旋鈕，沒人要改信箱名。
- 沒設＝`LlmKernelMissing`（N-63 ②；問腦沒有 daemon 可退，跟 `AOS_KERNEL` 沒設＝daemon 不同）。**人設、不自動傳**（使用者）：agent daemon 起之前 export；要讓某台 agent daemon 的所有子項都拿到，寫進那台定義的 `.env`（`{"AOS_LLM_KERNEL": "/home/me/llm_kernel"}`，絕對路徑，portable-flow 題 5 同一招）。

## 3 「設 daemon 都是指其 stack，有好辦法嗎」（使用者的問題；推薦放第一）

- **(a) 維持指 stack（推薦）**：使用者自己的比喻就是答案——daemon 是硬體、stack 就是它本身（11-05「所以才說 AOS_DAEMON」），**指 stack＝指那台機器**，`--stack .` 之後「資料夾＝機器」更直觀；`AOS_DAEMON`、`AOS_LLM_KERNEL`、以後的 `AOS_KERNEL` 全是同一種東西（N-63 ① 值是資料夾）。後果：搬家＝搬一個資料夾、變數改一行（跨電腦一定要改，哪種做法都躲不掉）；啟動四步的 ③ 每台要說話的 daemon 一個變數、不多；不加任何新東西。
- (b) 名字登記處（`~/.aos/daemons/<名>` → stack，變數只寫名字）：多一個固定位置與一步「登記」（⚠第五步）、違 N-63 ①／②（值不是資料夾、要去猜登記處）、搬家還得改登記；跨電腦登記處本來就不同，沒省到。
- (c) 用定義資料夾代替（`AOS_LLM_KERNEL=~/llm_kernel/def`）：定義「放哪都行」（使用者），而且一份定義可以起好幾台；指定義指不到那一台。不成立。

結論：(a)。「指 stack」不是毛病，是這套體系裡「一個資料夾就是一台機器」的直接結果。
