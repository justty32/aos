# `knowledge/aos/cli/_description.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/_description.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# 給人類與外部 agent 用的指令

用這些 shell 指令來管理 agent、工具與 daemon 的 proc。

在 aos 裡面，優先用你已註冊的工具。這套 CLI 是給人類的 shell 或外部的 coding agent 用的。每個指令都有 `--help`，而 help 才是最準的依據。

選 daemon：`--daemon D` > `$AOS_DAEMON`，之後 aos-agent 和其他指令就不一樣了。aos-agent：從它在目前資料夾找到的 agent stack 往上兩層（`aos/cli/flags.json#/target`）；樹根的 `./.stack` 絕不會被當成 daemon。aos-daemon-ctl、aos-mailbox 與其他指令：目前資料夾裡的 `./.stack`，不往上找。`AOS_DAEMON` 請用絕對路徑。D 是 daemon 的 stack，不是它的定義。

選 agent：`--target NAME` > `$AOS_AGENT` > 目前資料夾（`./.stack`，再來是 `./`，條件是它是 daemon 的表上某一列的 stack；aos/cli/flags.json#/target）。`ctl add` 用 `--name`；`ctl rm` 一定要給一個位置參數的名字；`ctl ls` 列出全部；`ctl who` 用一個 stack。

大部分 aos-* 指令在下面都有一頁（index 裡也有指標列，指向那些在別頁裡講的指令）；低階的零件在 `aos/cli/parts/`。先讀 `aos/cli/flags.json`（旗標放哪裡）和 `aos/cli/errors.json`（出錯時怎麼辦）。
