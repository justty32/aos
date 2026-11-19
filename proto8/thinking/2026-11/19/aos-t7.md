two-machines T7 第 8、9 步公司機代跑（線 aos-t7-1119）：第 8 步 /mnt/c 起一棵假腦全過；第 9 步公司這一半跑到 `~/code/rv` 本地 commit `bfec146`，bob 真 claude 回 ok；建 repo、push 與家機那一半留給使用者；步驟單已照現況補兩節。

← [2026-11-19](README.md)｜步驟單 [14-真機驗證](../10/two-machines/14-真機驗證.md)

出處：使用者 11-19 下午「你直接幫我把能做的都做吧，步驟單也修一下。」（頂層轉）

## 怎麼跑的

- 版本：aos repo `5fa447e2b`，`git archive` 抄到 `~/.aos/scratch/aos-t7-1119/src`，在複本 `proto8` 跑 `install.py`（退 0）；每句 aos 指令經 bash 腳本清掉 `AOS_*`、`AOS_HOME` 指複本、`cd` 進樹再 `source env.sh`。`~/aos-home` 沒碰。
- 兩個 `aos-exec` 放背景、記 pid；收尾都是 `aos-daemon-ctl … shutdown`，之後 pid 都不在。

## 第 8 步：/mnt/c 起一棵（假腦）

`W=/mnt/c/Users/WG-Guanyu/AppData/Local/Temp/aos-t7-rv`。全過：`FAKE ANSWER to: hello (tool said: …)`；`ls` 三列 `running`；`error:` 0 行；**`time say` 0.287 秒、`time listen` 5.836 秒**（11-10 約 8 秒）。兩台 shutdown 退 0，`$W` 已刪。指令照原文仍能用，只有頁頂「開始前」過期。

## 第 9 步：公司這一半

- 公司 WSL 沒有 `~/code`，先 `mkdir -p ~/code`（原文沒寫）。
- ann 假腦回 `hello from office`；bob（eca-claude，`claude` 2.1.328 已登入，`llm.json` 改 haiku）只問「The password is kiwi. Reply ok.」一次，回 `ok`。
- shutdown 兩台、睡著時寄 `left in the mailbox`（退 0、印 queued 提示）、`git init -b main`、`git add .`、`git commit -m "rv day 1"` → `bfec146`，86 檔，`git status` 乾淨，沒有 remote。
- 路徑：表與 bob 小格都是相對的；沒有指到暫存複本的路徑。有兩處記了 `/home/guanyu/code/rv` 進 git：信箱那封信的 `sender`、llm kernel `ledger.jsonl` 的 `sender`。
- 在暫存夾 `git clone` 一份、換位置起兩台演家機那一半（只假腦、沒叫 bob）：ann 答了 `left in the mailbox`，`git status --short` 只有 stack 狀態檔、沒有 `stderr.txt`／`cooldown.json`／`.session_home`。演完已刪。
- 公司 machine-id `c58505f7…`。

## 沒驗到的

- machine-id 不同的那道比對（A16）、bob 換台後答不答得出 kiwi、`sender` 絕對路徑到家機會不會出事：都要家機那一半。
- 家機指令只照現在版本對過文字，未實跑。

## 留給使用者

公司機（`gh` 已裝已登入）：

```sh
cd ~/code/rv
gh repo create rv --private
git remote add origin git@github.com:<你的帳號>/rv.git
git push -u origin main
```

push 前別在公司再起這兩台（會先答掉信箱那封）。家機那一半照步驟單「第 9 步 11-19 更新」；注意家機 `install.py` 會一起換掉 `~/aos-home` 跑的版本。
