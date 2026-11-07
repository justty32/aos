git-image 調查數據、gitignore 建議與 Z 隊落地（`04185730c`、`cf5799221`）：總結與發現 1～3
← [入口](../04-設計規劃.md)｜上一份 [01-續2-special-cases決策表](01-續2-special-cases決策表.md)｜下一份 [02-續-git-image發現4到5](02-續-git-image發現4到5.md)

## 這區白話總結

三題裁定的落地大致照字面：wait 格的「找不到請求就回 think 重組」就是使用者點的那個選項的原文，不是 sol 自己發明的。
最大的問題在搬家食譜：它關掉了 git 的自動清理，又沒有手動清理那一步。結果「只留最新一份」只在新 clone 上成立，每天凍住的那台機器自己的 `.git` 照樣越長越快（我實測 20 次凍住，本機 `.git` 72 MB，一份 image 才 4.8 MB）。
第二個問題是 `push --force` 沒有防呆：兩台機器搞混時，舊的那份會靜靜蓋掉新的，而且因為只留最新一份，蓋掉就救不回來。
另外，調查的「一週 70 GiB」是用一個做不到的情境算的。agent 每輪都把整份 history 送給腦，大約跑 260 輪就會撞到 200K 的上限，根本跑不到 10080 輪。結論的方向還是對的，但數字嚇人過頭了。

## 最該先處理的 3 條

1. 錯誤行為（已實測）：搬家食譜 `gc.auto 0`，又沒有 `reflog expire`＋`gc --prune`，本機 `.git` 照樣按平方成長。
2. 錯誤行為（推論）：`push --force` 沒帶 lease（先核對遠端還是不是你上次看到的那份）。兩台搞混時，舊 image 會蓋掉新的，而且沒有歷史可救。
3. 方向性代定：log 與 `**/archive/` 擋掉、只留在原機器，使用者沒被問過；換機器時的 `clean -fdX` 還會把這台的紀錄刪掉。

---

### 1. 「只留最新一份」的食譜，本機 `.git` 照樣平方膨脹
- **類別**：設計（食譜）｜**嚴重度**：錯誤行為（已實測）
- **檔:行**：`proto8/cmd/aos-agent/docs/04-搬家/02-image保存與邊界.md:34,46-52`；量測腳本 `proto8/thinking/2026-11/06/git-image/scripts/gitimage_bench.py:368-373`
- **commit／哪隊**：`cf5799221`（Z 隊，sol）寫的食譜，`57e55e650`（P8，sol）把它搬進分檔
- **問題**：
  - 03 說「squash 後 `.git`＝一份 image」，但那個數字是量測腳本另外跑了 `reflog expire --expire=now --all`＋`gc --prune=now` 才量出來的。
  - 食譜沒有這兩步，反而叫你 `git config gc.auto 0`（關掉 git 的自動清理）。舊版本還被 reflog（git 自己的「上一版在哪」備忘）抓著，自動清理也關了，所以永遠不會釋放。
  - 我照食譜原樣實測（20 隻 agent、每次凍住前跑 10 輪、凍住 20 次，遠端是本機的 bare repo）：本機 `.git` 從 0.7 MB 長到 72 MB，自建的遠端也一樣大；補上兩步清理之後只剩 4.8 MB。食譜說的「要等 git 清理」，在 `gc.auto 0` 底下永遠等不到。
  - 另外，`rm --cached .` 每次都把整份 image 重新雜湊一遍。小事，但 add 的時間會跟著整份 image 長。
- **使用者原話**：「只留最新一份 (Recommended)」（`proto8/thinking/2026-11/06/git-image/README.md:48`，選項框原文）；調查原題「是否會導致膨脹無法遏止」（同檔:7）
- **建議**：可以直接修。push 之後加 `git reflog expire --expire=now --all && git gc --prune=now`（tag 指著的版本照樣留著）。自建遠端的話，遠端也要定期 gc。

### 2. `push --force` 沒防呆，搞混兩台時會無聲丟掉新的 image
- **類別**：設計（當機復原、人工介入）｜**嚴重度**：錯誤行為（推論，沒實測）
- **檔:行**：`proto8/cmd/aos-agent/docs/04-搬家/02-image保存與邊界.md:49,12`
- **commit／哪隊**：`cf5799221`（Z 隊，sol）
- **問題**：
  - 「一次只在一台醒著」只靠人記得。情境：B 機忘了先 fetch，就在舊的工作樹上醒來、凍住，再 `push --force`，A 機剛推上去的新 image 就被蓋掉。
  - 只留最新一份＝沒有歷史可以撈回來。除非剛好打過 tag，不然 A 那段的記憶就沒了。
  - 另一個人工介入的洞：image repo 會把整個 ws 推到遠端，ws 是 agent 寫的成果，裡面可能有金鑰或私人檔。食譜沒有提醒「遠端要設成私有」。
- **使用者原話**：沒找到原話，這是推論（user/02「審的範圍」要求查當機復原、人工介入，`wf/workflows/common/user/02-交接與收工.md:21`）。
- **建議**：可以直接修。改成 `git push --force-with-lease=main:<上次 fetch 到的 commit>`，遠端不是你以為的那份就拒絕；食譜再加一句「image repo 用私有的」。

### 3. log 與 archive 擋掉＝紀錄只留原機器，沒問過使用者；換機器時還會被刪
- **類別**：代定｜**嚴重度**：方向性代定（輕）
- **檔:行**：`proto8/cmd/aos-agent/stack.gitignore:39-45`；`proto8/thinking/2026-11/06/git-image/05-其他手段與衝突.md:28`（N-16 衝突「只列不判」）；`02-image保存與邊界.md:59`
- **commit／哪隊**：`04185730c` 建議、`cf5799221` 落地（都是 sol）
- **問題**：
  - 方向題只有三題（歷史、request、垃圾桶）。「stderr、live.jsonl、turns、transcripts、archive 都不進 image」這件事沒有單獨問。05 自己也說擋 `archive/` 跟 N-16（信箱可以選擇留歸檔）會衝突，只是「今天沒人用 `--keep`」。
  - C-79 說的是「stack＝記憶體」，像 lisp image 那樣整份存。哪些東西算「只給人看、可以丟」，是使用者對 image 範圍的判斷。
  - 食譜在新機器跑 `clean -fdX -- ws/.stack/`，會把這台原有的被擋檔（也就是「只留原機器」的那些紀錄）一起刪掉。來回搬兩次，紀錄就兩邊都沒了。
- **使用者原話**：「daemon就像是硬體，各stack就是各程序所佔據的記憶體空間」（`proto8/docs/CONCEPTS/02-設計理念-時空.md:13`，C-79）；擋 log 這件事沒找到原話。
- **建議**：問使用者。
  - A（推薦）：維持擋，但 `clean -fdX` 改成只清 `**/think/request.json`，log 留在各自那台機器上。
  - B：`archive/` 改成不擋（照 N-16，選了留就是要留）。
  - C：全部帶走，接受 image 變大。
