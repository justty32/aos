# wf/public/gate與鎖 — 帶 kernel_gate 的樹怎麼少撞逾時，自己有死活的獨佔資源怎麼上鎖

← [wf/public](README.md)｜gate 本身怎麼用見知識庫 `aos/kernel.md#/Being a kernel yourself: kernel_gate`

## 帶 gate 的樹：主導把每一輪做短，下屬逾時等十幾秒再重試

主導（eca）開了 `kernel_gate`、下屬帶 `AOS_KERNEL` 經它起、收、查行程時：gate 的站靠主導的 on_clock 推進，主導正在跑一個長回合時站不跑；下屬經 gate 的請求等不到，3 秒就回 `KernelFailed`。

1. 主導盡量把每一輪做短：長的工作派給下屬，不要自己在一輪裡跑很久。
2. 只查表的請求（只有 `procs_state_path: true`）gate 會直接放行、不 hold，但一樣要等站跑；急著看表就直接點名 daemon（`aos-agent --daemon D ctl ls`）。
3. 下屬遇到 `KernelFailed` 先當成「gate 正忙」：等十幾秒重試，重試幾次還不行才當真錯誤回報。

## 自己有死活的獨佔資源（遊戲、桌面），不要只靠 aos-lock

好幾隻 agent 要輪流用一個同時只能一人用、而且自己會活著或掛掉的東西（跑著的遊戲、桌面、一個 GUI 程式）時，aos-lock 判不出這種資源的持有者還在不在用：

- 命令列 `aos-lock acquire` 拿完就退出，名牌不寫 flock，不做死亡回收；只能靠 release 或 `--lease-cycles` 的租約。租約一到就換人，原持有人起的遊戲行程可能還在跑。
- 名牌只記一個身分（有 `AOS_WS` 就只記 WS），同一個工作區的另一隻 agent 也 release 得掉。

做法：由主導點名給鎖：下屬寄 REQUEST 要用，等主導回信點名才取；底層照舊用隊伍自己的鎖。主導收回時自己確認原持有人的行程已經收掉。持有者死活的細節見 `proto8/cpp/aos-lock/README.md`。
