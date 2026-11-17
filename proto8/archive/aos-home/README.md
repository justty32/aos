# aos-home：把五夾抄進樹的 copy_tree.py（env.sh 11-17 搬到 proto8/env.sh）

← [archive](../README.md)｜搭樹十七步：[ops-notes-to-aos ③](../../thinking/2026-11/12/ops-notes-to-aos.md#3-寫-envsh)｜11-13 搭的那棵：[aos-home](../../thinking/2026-11/13/aos-home.md)

11-17 封存（路徑-6 A）：樹裡的程式直接指 repo，不再抄樹；這裡不測、不維護。

`env.sh` 11-17 搬到 [`proto8/env.sh`](../../env.sh)（路徑規則一：`AOS_HOME`＝那個 proto8 本身，順便把那個家的指令放進 PATH），測試跟著搬到 [`cmd/aos-tree-start/tests/test_env_sh.py`](../../cmd/aos-tree-start/tests/test_env_sh.py)。這夾只剩 `copy_tree.py`。

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
