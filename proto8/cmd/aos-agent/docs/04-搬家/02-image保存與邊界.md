# image 的保存、git 食譜與不隨 image 搬走的邊界

← [搬家入口](../04-搬家.md)｜上一份：[六段食譜](01-六段食譜.md)

**別信、別帶的**：

- 表與 state 窗的 `pid`、`started_at_ticks`、`boot_id` 是上一台（上一次）的；新 daemon 對不上就當「沒在跑」，照起、照醒。
- eca（claude／codex 當 agent）的對話本體在那台的 `~/.claude/projects/…`，image 裡只有 `session.txt` 的 id；換一台 `--resume` 找不到就從頭開（`history.jsonl` 還在、看得到以前聊什麼）。`transcripts/` 的 symlink 到別台是斷的，無害。畫面的 `tty.sock` 是死的，醒來 `aos-agent open` 重開。
- git 不收空資料夾（信箱的 `tmp/ new/ cur/`、工具小格）：第一圈 daemon、aos-post、aos-tools 會自己建回，不用管。
- **只在 Linux 檔案系統 checkout**：Windows 端 checkout 會丟 `+x`（定義裡的 `_entry`）、`core.autocrlf` 會在 `stage.txt`、`_entry` 尾巴加 `\r`；`/mnt/c` 底下又每個檔都 `+x`（aos-exec 會把 JSON 當執行檔）。真的要過 Windows，pull 完 `chmod +x` 那幾個 `_entry`，並放下面的 `.gitattributes`。
- **`ws/.stack` 是捷徑**（指到別的磁碟）：就地照常跑（daemon 的基準點取 stack 的真實路徑，11-05 B 線）；但 `cp -a` 只帶走捷徑、新舊兩份會共用同一個實體 stack——搬家要把捷徑指到的實體一起帶走、換成真資料夾（自擔）。
- 同一份 image 一次只在一台醒著：pull 前先 Ctrl-C；同一個 stack 已有 daemon 在跑，再 `aos-exec ../daemon` 會 `DaemonExists` 退 1。

**範本**（這個資料夾裡）：

| 檔 | 放哪 | 做什麼 |
|---|---|---|
| [`stack.gitignore`](../../stack.gitignore) | `cp stack.gitignore ws/.stack/.gitignore`（每台 daemon stack 各一份） | 擋暫存、鎖、可重建檔與 log（[完整規則與理由](../../../../thinking/2026-11/06/git-image/04-gitignore建議.md)），包含 `think/request.json`；保留 state、procs 表、history、stage、pending、在途 `new/`／`cur/`／問腦回信、設定覆蓋層與額度帳 |
| [`stack.gitattributes`](../../stack.gitattributes) | `cp stack.gitattributes <git repo 根>/.gitattributes` | `* -text`：一律不轉換行（放根＝定義的 `_entry` 也管到） |

`.gitignore` 放 `.stack` 裡而不是 ws 根：放 ws 根也擋得對 image，但 `**/tmp/`、`**/.*` 會連你 ws 裡自己的 `tmp/`、`.env` 一起擋。

11-05 WSL 實測（試驗場）：Ctrl-C → `cp -a` 整份到 `/tmp` 另一處 → 新位置 `aos-exec ../daemon`：三列都在新位置醒、fsm_ann 接著答，舊位置的檔沒被碰；拿走定義再起＝那列 `stopped`＋原因、放回去 `start` 就回來；放兩份範本 `git init`＋commit＋`git clone` 到第三處再起：同樣醒、接著答。git 擋掉的只有三份 `stderr.txt` 和 kernel 信箱（裡面只剩 `.flock` 與空資料夾）。

## git image：專門 repo、只留最新一份（11-06 使用者裁定）

image 放**專門的 repo**；每次整棵 daemon 睡著後，建立沒有父 commit 的 **orphan commit**，用 `push --force-with-lease` 更新 `main`。要留下的版本先打 tag；定義與 ws 成果照樣一起帶，原始碼 repo 的歷史不跟著改。三題裁定見 [git-image](../../../../thinking/2026-11/06/git-image/README.md)。

第一次在 image 根設定（以下 `P` 是 proto8 的絕對路徑；根下有 `ws/`、定義資料夾；遠端用專門的 image repo，將 `IMAGE_REPO_URL` 換成其網址）：

```sh
git init -b main
git remote add origin 'IMAGE_REPO_URL'
git config gc.auto 0
cp "$P/cmd/aos-agent/stack.gitignore" ws/.stack/.gitignore
cp "$P/cmd/aos-agent/stack.gitattributes" .gitattributes
printf 'ws/.trash/\n' >> .gitignore
```

其他 daemon stack（例如 kernel 的 stack）也各放一份 `stack.gitignore`。**image 根只擋 `ws/.trash/`**，不套 stack 的寬規則到 ws；垃圾桶不搬、由人定期清，搬完無法還原原機丟進垃圾桶的檔。

每次凍住後存最新一份：

```sh
# 想留「上一份」時，先 git tag image-20261106-1200 main，再 git push origin 該tag名
git rm -r --cached --ignore-unmatch .
git add -A
git update-ref refs/heads/main "$(printf 'Frozen image\n' | git commit-tree "$(git write-tree)")"
git push --force-with-lease origin main
git reflog expire --expire=now --all && git gc --prune=now
```

`rm --cached` 只清索引、檔案留在原地，讓已追蹤但現在該擋的 request／log 也退出 image。`commit-tree` 不帶 `-p` 就是 orphan commit，不產生其他分支。tag 仍指向要保留的版本。

- **`--force-with-lease`**（11-07 sol 審查 #17，原本 `--force`）：遠端 `main` 不是你上次 fetch／push 看到的那份就拒絕（`! [rejected] main -> main (stale info)`）。兩台搞混時——例如 B 機忘了先 fetch 就在舊工作樹醒來、凍住再推——不會無聲蓋掉 A 機剛推的新 image（只留最新一份＝蓋掉就救不回）。被拒時先停下來弄清楚哪台的才是最新的；確定要用這台的，`git fetch origin main` 後再推。
- **push 後清掉舊版**（11-07 sol 審查 #16）：`gc.auto 0` 關了自動清理，舊版本又被 reflog 抓著，不手動清的話本機 `.git` 會一版一版疊上去（實測 20 次凍住 72 MB，清後 4.8 MB）。`reflog expire`＋`gc --prune=now` 只丟沒有參照的舊版，tag 指著的照留。自建的遠端（bare repo）也要定期在那邊跑 `git gc --prune=now`。
- image repo 會把整個 ws 推上去（agent 寫的成果，可能有金鑰或私人檔），遠端用私有的。

另一台已有這份 image clone 時，先 Ctrl-C 睡整棵，再取最新版本（這會捨棄該 clone 的本機改動，應先凍住並存好要留的成果）：

```sh
git fetch origin main
git reset --hard origin/main
find ws/.stack/ -type f -path '*/think/request.json' -delete
```

只刪指定 stack 裡各個 `think/request.json`，避免沿用上一份 image 的 request；其他被忽略的 log、快取與暫存都留著，其他 daemon stack 也各做一次（11-07 使用者裁定 sol 審查 #20-3）。歸檔信 `archive/` 跟著 image 走；stderr、live、turns、transcripts 等紀錄仍只留原機（11-07 使用者裁定 sol 審查 #20-1、#20-2）。

因為每版都沒有上一版，不能用一般 `git pull` 合併。醒在 wait 的 agent 若沒 pending、也沒 request，會先回 think 重組再寄；同樹已寄出的可靠 pending＋回信繼續收；跨樹在飛請求照搬家食譜作廢重寄，不沿用舊回信地址。
