templates 三分明早要用的補丁材料：機械層的搬遷腳本與對照表、手改層的六個補丁、怎麼在新 main 上重做，以及 11-23 晚在家機 scratch 複本上測試與預演交件的結果（線 tri-split-1123，Claude 子 agent 代核心程式、範本、知識庫三個位子施工）。

# 06-switch：三分的補丁怎麼重做、測了什麼

← [06 入口](../06-三分的施工設計.md)｜做法照 [06d](../06d-補丁怎麼做怎麼套.md)｜切換清單 [06e](../06e-切換步驟.md)｜改表腳本與預演改表是另一隻 agent 的：[stack_paths.py](stack_paths.py)、[rehearsal.md](rehearsal.md)（這份不寫它們的內容）

## 底與做出來的

- **底**：main `0f7c19c6820659b0b69c670b6f44df338a670db9`（11-23 21:15 clone）。
- **複本**：`~/.aos/scratch/tri-split-1123/aos`（`git clone --no-hardlinks`，push 指到 `no-push`），在它自己的 main 上疊了 M＋H1～H6 共 7 個 commit，HEAD `be8b36f568c431aa10b5ae4e1168010a772664c3`。
- **出的東西**（`~/.aos/scratch/tri-split-1123/out/`）：`tri-split.patch`（底到 HEAD，不含 `wf/knowledge/code-map/` 與知識庫以外的 `_index.json`）、`files.txt`（新增與修改 403 個）、`rm.txt`（刪掉與搬走的舊路徑 214 個）、`pre-switch.txt`（底與 HEAD）。

## 這個夾有什麼

| 檔 | 是什麼 |
|---|---|
| `split.py` | 機械層 M：照 `moves.tsv` 做 06c 的 R1～R5；`--dry-run` 只列、`--apply` 改、`--check` 抓剩下的舊路徑；跑兩次結果一樣 |
| `moves.tsv` | 06a 的路徑對照表（`舊<TAB>新`，先檔後夾），`split.py` 與 R2 共用 |
| `H1-core.patch`～`H6-docs.patch` | 手改層 H：`git format-patch` 出的六個 commit，接在 M 後面 `git am` |
| `run_all.sh` | 全套測試：`git archive` 抄一份、清掉 `AOS_*`、在那份裡 `install.py`、逐夾跑，寫 `summary.tsv` 與 `fails.tsv` |
| `run_frontend.sh` | `proto8/frontend/tests` 要走它自己的 `run.sh`（連 `AOS_HOME` 都不能有），`run_all.sh` 跑完再補這一夾 |
| `01-M與H.md`、`02-測試與預演交件.md`、`03-還沒解的問題.md` | 這份 README 的三段細節 |

## M 與 H（細節在 [01](01-M與H.md)）

- **M**＝`split.py --apply`：R1 `git mv`（九個檔進 `py/aos/apps/agent_fsm/`、14 個夾進類別夾）→ R2 相對連結 → R3 格與宣告的路徑 → R4 字面路徑 → R5 拼出來的路徑；不碰的範圍照 06c 再加三處。11-23 動了 380 個檔，跑第二次 0 處。
- **H**＝六個補丁：H1 核心程式、H2 範本、H3 前端、H4 知識庫、H5 生成設定、H6 文件與共用工具；接在 M 後面 `git am`。

## 明早怎麼在新 main 上重做（停樹之後）

複本的 main 已經疊了 11-23 的 commit，明早**另開一份新的 clone**最省事（11-23 晚已照這段在 `t-drift` 對當時的 main `492e2c3fc`（底之後又進了 5 個 commit）實跑過：M 重跑、六個補丁 `git am` 全過、`--check` stale 0，結果跟測過的那份只差那 5 個 commit 動的 11 個檔）。

```sh
S=~/.aos/scratch/tri-split-1123
D=~/repo/aos/proto8/thinking/2026-11/23/org範本與templates分層-1123/06-switch
git clone -q --no-hardlinks ~/repo/aos $S/aos-1124 && git -C $S/aos-1124 remote set-url --push origin no-push
B=$(git -C $S/aos-1124 rev-parse HEAD); echo "base $B" >> $S/out/pre-switch.txt
git -C $S/aos-1124 log --stat 0f7c19c68..$B          # 漂移動了什麼
python3 $D/split.py --repo $S/aos-1124 --apply
git -C $S/aos-1124 add -A && git -C $S/aos-1124 commit -q -m "M"
git -C $S/aos-1124 am $D/H*.patch                     # 衝突就停，人解完 git am --continue
python3 $D/split.py --repo $S/aos-1124 --check        # stale 要是 0
bash $D/run_all.sh $S/aos-1124 HEAD $S/t-1124          # 漂移碰到 proto8/py 或 templates 才跑全套；frontend 另跑 run_frontend.sh
EX=(':(exclude,glob)wf/knowledge/code-map/**' ':(exclude,glob)**/_index.json')
git -C $S/aos-1124 diff --binary -M $B HEAD -- . "${EX[@]}" > $S/out/tri-split.patch
git -C $S/aos-1124 -c core.quotepath=off diff --no-renames --name-status $B HEAD -- . "${EX[@]}" > $S/out/name-status.txt
awk -F'\t' '$1!="D"{print $2}' $S/out/name-status.txt > $S/out/files.txt
awk -F'\t' '$1=="D"{print $2}' $S/out/name-status.txt > $S/out/rm.txt
```

之後照 06d「帶回 repo」第 2～6 步：工作樹那些檔是乾淨的才 `git apply --check`／`git apply`，清掉舊夾的 `__pycache__` 與空夾（`git apply` 搬不走沒追蹤的檔），逐檔比雜湊，再 `commit-request submit --line tri-split-1124 --files $(cat files.txt) --rm $(cat rm.txt) --msg-file … --dry-run`，看過再正式交。**`--rm` 要使用者本人的視窗打**（agent 的權限模式會整條擋）。

## 測試與預演交件（細節在 [02](02-測試與預演交件.md)）

- **全套測試**：底與複本 HEAD 各 83 夾、3,362 支，逐夾結果一樣，**新出現的紅 0 條**；`frontend/tests` 兩邊 52 支 OK；兩支 `check.py` 兩邊都紅、原因一樣（底就紅）。
- **預演交件**：`commit-request submit --dry-run` 在另一份退回底的 clone 上 `DONE DryRun`、exit 0；沒有 `DescMissing`；生成器重生 11 個檔；被搬的夾裡本來就沒有 `_index.json`，不會留下沒人管的生成檔；只有 `not claimed` 警告。

## 還沒解的問題（細節在 [03](03-還沒解的問題.md)）

1. `switch.sh` 沒寫
2. 條文的句子跟不上
3. 歷史紀錄裡的連結會斷
4. 逐字抄本的相對連結
5. 06c 沒列、我照「全 repo」的字面也改了的
6. 06c 沒列、我加進不碰的範圍的
7. 測試裡有 4 種寫法 R5 抓不到
8. `--rm` 214 個舊路徑
9. 規劃夾的 README 與日索引沒加這個夾的連結
10. 兩支 `check.py` 在底上本來就紅
11. 知識庫 `cli/agent.md` 沒有掛範本的例子，沒改

