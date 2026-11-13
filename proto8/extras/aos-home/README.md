# aos-home：一棵樹的環境檔 env.sh 正本，與把五夾抄進樹的 copy_tree.py

← [extras](../README.md)｜搭樹十七步：[ops-notes-to-aos ③](../../thinking/2026-11/12/ops-notes-to-aos.md#3-寫-envsh)｜11-13 搭的那棵：[aos-home](../../thinking/2026-11/13/aos-home.md)

[`env.sh`](env.sh) 是一棵樹（例如 `~/aos-home`）根上那份環境檔的正本：每個視窗先 `cd <樹> && source env.sh`。搭新樹時抄一份過去：`cp proto8/extras/aos-home/env.sh <樹>/env.sh`。

它做三件事：

- 清掉 `CLAUDECODE` 等三個 Claude Code 變數（在 Claude Code 裡起的 eca 才不會被當成巢狀）。
- **清掉全部 `AOS_*`**，再只設 `AOS_HOME`＝env.sh 所在的資料夾。agent 的 shell 帶著活樹的 `AOS_STACK`、`AOS_WS` 等；11-13 15:24 起樹事故就是舊寫法只清 `AOS_DAEMON`／`AOS_KERNEL`／`AOS_CLOCK`，根把那格 agent 的 stack 當成自己的。
- PATH 找不到 `aos-exec` 時提醒先跑一次 `proto8/install.sh`。

內容跟 11-13 15:35 活樹那份逐字相同（那份是 `eca_main` 照使用者「2. 可以，隨便」改的）。改了這份不會自己進活樹，要手抄過去。

**為什麼放 extras、不放 templates**：停樹重抄的是 `lib templates knowledge py kernel` 五夾；放 `templates/` 會在活樹的 `templates/` 多出一份 env.sh，`cp -r` 範本時也可能被一起抄走。extras 不進活樹。

測試 [`test_env_sh.py`](test_env_sh.py)：bash 與 zsh 各 source 一次（絕對路徑與 `./env.sh` 兩種），環境先放一堆 `AOS_*` 與 CLAUDE 變數，source 後只能剩 `AOS_HOME`＝那個資料夾；只 source、不起任何行程。跑法：`python3 -m unittest discover -s proto8/extras/aos-home`。

## copy_tree.py：抄五夾，每夾記下抄自哪個 commit

活樹的 `lib`／`templates`／`knowledge`／`py`／`kernel` 是 repo 的複本，原本看不出抄自哪一版（[agents-feedback T05](../../thinking/2026-11/13/agents-feedback-1113-題目.md#t05-知識庫複本落後正本看不出新舊)）。這支照 [aos-teams/06 停樹換檔的做法](../../../wf/workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#停樹換檔的做法)抄（來源是 `git archive <commit>`，不抄工作樹；每夾先解到樹裡的暫存夾、寫好來源檔，再改名換上），每夾留一份 `.aos-source.json`：

```json
{"description": "Where this folder was copied from: ...", "commit": "<完整 hash>", "ref": "HEAD", "copied_at": "2026-11-13T22:03:36+08:00", "from": "/home/…/repo/aos/proto8/knowledge", "how": "git archive"}
```

```sh
python3 ~/repo/aos/proto8/extras/aos-home/copy_tree.py --ref <hash> ~/aos-home              # 五夾全抄
python3 ~/repo/aos/proto8/extras/aos-home/copy_tree.py ~/aos-home knowledge lib             # 只抄兩夾（HEAD）
python3 ~/repo/aos/proto8/extras/aos-home/copy_tree.py --stamp-only --ref <hash> ~/aos-home  # 已用別的腳本從 <hash> 抄好，只補來源檔
```

- `--dry-run` 只印；工作樹有沒 commit 的改動＝每夾一行提醒（那些改動不會進樹）。樹在 repo 裡、ref 不是 commit、夾名不在五夾裡都報錯不動。
- 不停樹、不碰行程：樹跑著時換 `py`、`templates` 的後果由呼叫者負責；只重抄 `knowledge`、`lib` 可以不停（[ops-notes-to-aos ⑯](../../thinking/2026-11/12/ops-notes-to-aos.md#16-repo-更新後只重抄-lib-或-knowledge)）。
- `--stamp-only` 寫的 `how` 是 `stamp-only`：內容沒經這支核對，只是照呼叫者說的記。
- 檔名以點開頭，`index_view` 與 `_index.json` 都不列它；agent 從知識庫 `aos/_description.json` 那句知道去看 `knowledge/.aos-source.json`。沒有這個檔＝手抄的、版本不明。

測試 [`test_copy_tree.py`](test_copy_tree.py)：暫存夾自建小 git repo 與小樹，驗五夾內容與來源檔、舊內容整夾換掉、暫存夾收乾淨、髒工作樹提醒、`--stamp-only`、`--dry-run` 與幾種錯；不起任何行程。跑法同上（`discover -s proto8/extras/aos-home`）。
