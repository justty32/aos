# aos-home：一棵樹的環境檔 env.sh 正本

← [extras](../README.md)｜搭樹十七步：[ops-notes-to-aos ③](../../thinking/2026-11/12/ops-notes-to-aos.md#3-寫-envsh)｜11-13 搭的那棵：[aos-home](../../thinking/2026-11/13/aos-home.md)

[`env.sh`](env.sh) 是一棵樹（例如 `~/aos-home`）根上那份環境檔的正本：每個視窗先 `cd <樹> && source env.sh`。搭新樹時抄一份過去：`cp proto8/extras/aos-home/env.sh <樹>/env.sh`。

它做三件事：

- 清掉 `CLAUDECODE` 等三個 Claude Code 變數（在 Claude Code 裡起的 eca 才不會被當成巢狀）。
- **清掉全部 `AOS_*`**，再只設 `AOS_HOME`＝env.sh 所在的資料夾。agent 的 shell 帶著活樹的 `AOS_STACK`、`AOS_WS` 等；11-13 15:24 起樹事故就是舊寫法只清 `AOS_DAEMON`／`AOS_KERNEL`／`AOS_CLOCK`，根把那格 agent 的 stack 當成自己的。
- PATH 找不到 `aos-exec` 時提醒先跑一次 `proto8/install.sh`。

內容跟 11-13 15:35 活樹那份逐字相同（那份是 `eca_main` 照使用者「2. 可以，隨便」改的）。改了這份不會自己進活樹，要手抄過去。

**為什麼放 extras、不放 templates**：停樹重抄的是 `lib templates knowledge py kernel` 五夾；放 `templates/` 會在活樹的 `templates/` 多出一份 env.sh，`cp -r` 範本時也可能被一起抄走。extras 不進活樹。

測試 [`test_env_sh.py`](test_env_sh.py)：bash 與 zsh 各 source 一次（絕對路徑與 `./env.sh` 兩種），環境先放一堆 `AOS_*` 與 CLAUDE 變數，source 後只能剩 `AOS_HOME`＝那個資料夾；只 source、不起任何行程。跑法：`python3 -m unittest discover -s proto8/extras/aos-home`。
