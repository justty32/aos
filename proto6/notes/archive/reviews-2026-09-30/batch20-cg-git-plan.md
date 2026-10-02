> 封存 2026-10-02：09-30 審稿與第十八～二十批（含 cgroup／git）改寫計畫、交接、核對報告，批次已結束；結論已由 proto6/spec（settled/ 與 settled/deferred/）與裁定紀錄 proto6/notes/verdicts/09～11 吸收

# 把 cgroup 與 git 納入 tick／daemon 基礎：改寫計畫（待使用者裁定）

← [審稿索引](README.md)｜依據：[第二十批](../../verdicts/11-tick-as-unit.md)（追答 8、9，疑點裁定 1～8，進行順序）、[第十九批](../../verdicts/10-tick-minimal-core.md)（疑點裁定 8、9：cgroup 常沒 sudo、git 常不能用，採 a＋b）、[第十八批](../../verdicts/09-special-computing-os.md)（第 3、8、17 條，Q19～Q21、Q31）｜上一輪計畫：[batch20-plan](batch20-plan.md)｜落點表：[batch20-cg-git-map.json](batch20-cg-git-map.json)

**只寫計畫，spec 一字未動。**條文落點一律用條號（B-／P-／T-／V-），不寫路徑：tick／daemon 相關篇正在搬進整理區，條號不變。

## 摘要

- **核心不用改。**git 要的東西（每項結束碼紀錄、停格檔、`AOS_TASK_ID`）和 cgroup 要的東西，上一輪的基礎都已經有了；tick 核心仍然只做四件事。
- **git**：做成三個系統級任務 `aos-git open|mark|close`。範本順序：git 開格 → 收件 → 使用者任務（每組後面一個存檔點）→ 清理 → git 收尾 → 投件 → 發摘要。上一格沒正常收尾就還原到最近一次提交；每格最多一個 commit，訊息 `aos-tick <seq>`；每次呼叫 git 都帶 `core.fsync`，最低 git 2.36。
- **建議的簡化**：收件、投件、發摘要、清理**不必認得 git**。在新順序下，「上一格正常收尾」就等於「已經提交」，所以現行規則直接成立。git 開格不再刪原件、不再查擋板，投件也不用從 HEAD 取件（疑-4）。
- **cgroup**：node 框和資源上限歸 daemon；有 cgroup 就用，沒有就退回現行的程序群組。首推不用 sudo 的 systemd 使用者委派。格後收尾改用 `cgroup.kill`，每項一框交給普通程式 `aos-cg`。`cgroup_*` 動作在有 cgroup 時照做，沒有時照樣回 `unsupported`。
- **本機實測找到三個草稿沒想到的坑**（這台 WSL 上測）：
  - 一般 shell 在 root 的 `init.scope` 裡，拿不到自己的框；
  - `systemd-run --user --scope` 每次開出的 scope 名字都不一樣，daemon 重啟後找不到舊框，清不掉舊程序；
  - 框的檔案歸自己，不代表 systemd 真的委派了（沒加 `Delegate=yes` 的 scope 檔案也歸自己），只看擁有者會誤判。
- 疑點 12 題，放在第五節。最要緊的是：停格檔跟 git 收尾的衝突（疑-1）、失敗組在哪裡還原（疑-2）、下游要不要認得 git（疑-4）。

## 零、範圍與不動的東西

- **不動**：tick 核心四件事（B-602 鎖、B-620 照表跑、B-628 上下層、B-633 結束碼紀錄），以及停格檔、擋板檔（B-620、P-213）。daemon 看擋板不看結束碼（B-607），通道四件事（B-612～614）也不動。
- **本輪要做**：各篇「下一步納入」段的草稿（B-630、B-622、P-205、B-202 的 `aos-cg` 段、P-211、daemon 篇末 cgroup 段、V-03 的下一步小節）定稿、搬回正文，改寫各處「下一步納入時補」的句子。
- **跟上但不在本輪**：kernel、agent、LLM、CLI 各篇講到 git 或 cgroup 的地方，例如 A-102 手改後自己提交、P-814／P-715 範本、S-203／S-205 分上限、`aos node new` 建初始 commit。這些在落點表標「其他篇跟上」，等基礎定了再改。
- **保證怎麼寫**（沿 T-01）：整格原子要**同時**掛了 open、mark、close，而且 git 能用；每項後代清空要任務包了 `aos-cg`，而且 daemon 有 cgroup；資源上限要 daemon 有 cgroup。沒掛時會怎樣不逐條寫。

## 一、git

### 1.1 範本順序

| # | `id`（建議） | argv | 說明 |
|---|---|---|---|
| 1 | `open` | `aos-git open` | 還原上一格做一半的、打本格第一個存檔點 |
| 2 | `inbox` | `aos-inbox` | 不變（B-623） |
| 3 | `m-inbox` | `aos-git mark` | 收件自成一組 |
| … | 使用者任務 | 各自 | 每項（或每組）後面接一個 `aos-git mark` |
| n-4 | `clean` | `aos-clean …` | 移到 close 前，清理變動當格提交 |
| n-3 | `close` | `aos-git close` | 最後一組的成敗、提交 |
| n-2 | `outbox` | `aos-outbox` | 不變 |
| n-1 | `summary` | `aos-publish` | 不變 |

- 存檔點照疑點裁定 3（a），每組跑完打一個。「組」＝相鄰兩個存檔點之間的各項；最後一組是最後一個存檔點到 close 之間（通常就是 `clean`）。
- 範本在每項使用者任務後面各放一個存檔點，所以每項自成一組。要把幾項綁成一組，就拿掉中間的存檔點。第十九批的 `group` 欄位仍當陌生鍵，不復活。
- 任務表長度大約變兩倍，見疑-12（要不要多一種包裝寫法）。
- `aos-needs` 不變：被擋下的項記 `exit:125`，所在的組算失敗。

### 1.2 開格 `aos-git open`

1. **看 git 能不能用**（1.8）。不能用時照 B-632 什麼都不做，stderr 印 `no_git`，回 0。
2. **上一格沒正常收尾就還原**：讀 `last.json`，`ended:false` 或有 `stopped_after` 都算沒正常收尾。
   - 還原前先把工作樹跟 HEAD 的差異存成 `refs/aos/rescue/<上一格 seq>`（疑-3），再把工作樹與 index 還原到 HEAD。範圍照 B-622。
   - 正常收尾，或沒有 `last.json` 時不還原。
3. **清殘留**：上一格留下的 `refs/aos/marks/*` 清掉。上一格是當機（`ended:false`）時，一併清掉 git 管理目錄裡 aos 自己可能留下的鎖檔（`index.lock`、`HEAD.lock`、`refs/**/*.lock`）。人手在格間跑 git 算外部世界，照疑點裁定 8 不管。
4. **巢狀排除**：掃出下層 tick 的資料夾，寫進 `info/exclude`（1.9）。
5. **打本格第一個存檔點** `refs/aos/marks/<本項 id>`。
- 任何一步失敗：寫擋板、建停格檔、回 1。

**跟草稿比，拿掉兩步：**

- 第 1 步「看到擋板就不碰工作樹」拿掉：核心取鎖後第一件事就看擋板，有擋板時根本不會跑到 open（B-620）。P-205 的 `tick_blocked` 代碼一起拿掉。
- 第 4 步「刪 HEAD 裡已提交的收件原件」拿掉，留給收件任務，理由見 1.6 與疑-4。

### 1.3 存檔點 `aos-git mark`

- **做什麼**：
  1. 讀 `current.json`，找出上一個存檔點之後各項的結束碼。上一個存檔點＝紀錄裡最近一個「有對應 `refs/aos/marks/<id>`」的項；只看紀錄與 ref，不重讀 `tasks.json`，免得任務在格內改了表造成錯位。
  2. **這組全是 `exit:0`**：把此刻的工作樹存成暫存提交，記在 `refs/aos/marks/<本項 id>`。
  3. **這組有失敗**（照疑-2 建議 b）：把這組改過的路徑（上一個存檔點跟現在的差異，含新增、刪除）還原回上一個存檔點，再打存檔點。後面的組就看不到失敗組寫的東西。
- **不動**：分支、HEAD 與正式 index（用暫存 index 檔。實作時先複製正式 index 再 `add -A`，才吃得到 stat 快取，不必每次重算全樹 hash）。
- **不 fsync**：存檔點只在本格有用，當機後 open 一律還原到 HEAD，所以帶 `-c core.fsync=none`，省成本。
- **ref 名**：`<任務 id>` 照 ID 格式可能含 `..` 或以 `.lock`、`.` 結尾，不是合法 ref 名。這種 id 回 1，stderr 印 `mark_id_invalid`，建停格檔（建議預設；也可以改成把 id 編碼，見 1.10）。
- 沒有紀錄可讀（`AOS_TICK_RECORD` 不在）時：寫擋板、建停格檔、回 1（`record_missing`）。

### 1.4 收尾 `aos-git close`

1. 照 mark 的做法，處理最後一組（成功就留、失敗就還原）。
2. 巢狀排除再掃一次（1.9）。
3. **提交**：剩下的改動 commit 一次，訊息 `aos-tick <seq>`；沒變動就不 commit。建議預設：訊息另加一行 `aos-failed: <存檔點 id…>`，列出失敗的組，只給人看、不參與計算。
4. 刪掉本格的存檔點，回 0。
5. 有 `gc` 需要時在前景跑（`-c gc.autoDetach=false`），見 1.7。
- 還原、commit 或 gc 失敗：寫擋板、建停格檔、回 1。核心看到停格檔，就不開後面的投件與發摘要。

### 1.5 跟核心紀錄、停格檔、擋板檔怎麼互動

| 情況 | 會怎樣 |
|---|---|
| 上一格 `ended:true`、沒有 `stopped_after` | 不還原；收件任務照 B-623 刪原件（這時一定已提交，見 1.6） |
| 上一格 `ended:false`（當機） | open 先存 rescue、再還原到 HEAD；收件任務不刪原件 |
| 上一格被停格檔停下 | 同上：停在 close 之前，這格等於沒提交，整格作廢（疑-1） |
| 本格某項建停格檔 | close 不跑、不提交；下一格 open 還原 |
| open／mark／close 自己失敗 | 寫擋板＋建停格檔；這格作廢，之後各格被擋，要人處理 |
| 有擋板 | 核心不跑任何項（現行）；git 任務不另外看擋板 |
| 格間人手改檔 | 上一格正常：被下一次 close 一起提交。上一格不正常：進 rescue ref、工作樹回 HEAD（疑-3） |

**核心要不要改：不用。**git 任務只讀 `current.json`、`last.json` 與 `AOS_TASK_ID`，失敗時建停格檔、寫擋板，這些都是現成的。疑-1 的選項 c 會讓核心變五件事，不建議。

### 1.6 下游任務不必認得 git（疑-4 建議 b）

在新順序下（close 在投件前，close 失敗會建停格檔），「上一格 `ended:true` 而且沒有 `stopped_after`」就表示上一格的 close 成功了，工作樹等於 HEAD（失敗組已經還原）。所以：

- **收件（B-623）**：現行「上一格正常收尾才刪 bytes 相同的原件」照用，不用改成比 HEAD。上一格當機時，消費副本已經被 open 還原掉，原件留著、重收；照 B-503 也不會重吃。
- **投件（B-624）**：本格走到 outbox，就表示 close 已經成功，待送區裡的檔都已提交，「先提交再送」自然成立。
- **發摘要（B-624）**：同理，目前的 `summary.json` 就是已提交的那一版。
- **清理（B-404）**：保留期起點留在「`aos-clean` 第一次看到的那一格」，不改成「首次提交的那一格」。在 tick 內不自己 commit，由本格 close 提交。
- **B-632**：改寫成「沒掛 git 任務，或 git 不能用時」。敘述不變：結束碼紀錄就是唯一的依據。

結果：git 只存在於 open、mark、close 三個入口。其他系統級任務在有 git、沒 git 時跑同一份程式，正好就是疑點裁定 5 說的「合成同一種模式」。

**有 git 才多出來的**：同 ID 重送時，補投的原回應從 git 歷史撈（B-503）。這由處理那個 method 的任務自己做，用 `git log -- .aos/outbox/responses/<id>.json` 找原 bytes；沒 git 時照現行「歷史裡找不到」處理。

### 1.7 git 參數與落盤

- **最低版本 2.36**，每次呼叫帶 `-c core.fsync=committed,reference`（第十八批第 17 條、Q31）。只有 commit 與 ref 更新需要；存檔點帶 `core.fsync=none`（1.3）。
- **一律另帶的參數**（建議預設，草稿沒寫到）：
  - `core.hooksPath=/dev/null`：不跑 hooks。
  - `commit.gpgSign=false`：使用者全域開了簽章時，不會卡住或失敗。
  - `gc.auto=0`、`maintenance.auto=false`：git 預設會在背景 `gc --detach`。背景程序會繼承鎖 fd，讓下一格回 75，也違反「不准背景程序繞過 tick」。gc 改由 close 視需要在前景跑。
  - `safe.directory=<node 根>`：多帳號時 node 根目錄的擁有者可以跟 tick 帳號不同（B-203 承認兩種主人）。git 預設會拒絕這種 repo，每格都會失敗。命令列 `-c` 算受保護設定，實作時要驗。
- **環境要清**：`GIT_DIR`、`GIT_WORK_TREE`、`GIT_INDEX_FILE` 等可能從上層環境繼承，會讓 git 操作到別的 repo。aos-git 呼叫 git 前清掉所有 `GIT_*`，只設自己要的。
- **作者**：用 repo 設定。repo 與全域都沒設時，git 會拒絕 commit、每格擋板。建議預設是固定用 `aos <aos@localhost>` 頂上，不擋。
- **固定排除**：不管 `.gitignore` 寫了什麼，aos-git 一律排除 `.aos/tick/`、`.aos/tick.lock`、`.aos/tick-blocked`、`requests/`、`responses/` 等核心檔（寫在 `info/exclude` 或每次帶 pathspec）。否則 `.gitignore` 漏了 `/.aos/tick/` 時，紀錄會被提交、被還原，`seq` 會倒退。
- **不在 tick 內**：`aos-git` 在 tick 外（沒有 `AOS_TICK_RECORD`、核對不到繼承的鎖）回 125，stderr 印 `not_in_tick`。人手要提交就直接用 git（草稿原本讓它自己取鎖，但 close 在格外沒有本格紀錄可讀，沒意義）。

### 1.8 git 不能用時（疑-5）

「沒掛 git 任務」維持現行做法（B-632：結束碼紀錄取代日誌）。「掛了但 git 不能用」建議分兩種：

- **沒裝、低於 2.36、不是 repo**：open、mark、close 都只印 `no_git`、回 0，照 B-632 走。第十九批說 git 常不能用，要能退回（a＋b）。
- **repo 在但壞了**（HEAD 讀不到、物件缺、aos 以外的鎖檔卡住、權限不夠讀）：寫擋板、建停格檔。這時如果默默退回，會失去還原而且沒人知道。
- **git 之後又能用了**：第一次能用的那格，open 看上一格正常就不還原，close 把累積的改動一次提交；repo 在但沒有 HEAD 時，由 close 建第一個 commit。

### 1.9 巢狀

- 下層 tick 的資料夾（有 `.aos/inst.json` 或 `inst.json`）寫進上層 repo 的 `info/exclude`，不改 `.gitignore`（沿上一輪暫定）。
- **草稿沒想到**：任務在格中建了子 node（例如 kernel 跑 `aos node new`），只在 open 掃的話，這一格的 mark／close 會把子 node 的檔案提交進上層；之後才排除也沒用，已追蹤的檔不會因為排除就不追。建議 mark 與 close 在存工作樹前都重掃一次（成本見 1.10）。
- 子 node 自己是 repo 時，git 會把它當成內嵌 repo；排除之後不碰它，還原也不進去（B-622「不遍歷子 repo」）。

### 1.10 其他沒考慮到的（git）

- **失敗組還原時，殘留後代還在寫**：沒包 `aos-cg` 的任務留下的程序，要等格後才被 daemon 收掉。還原之後它們可能又寫回來。只有包了 `aos-cg` 而且有 cgroup，才能保證還原時沒人在寫。建議在 B-630 寫明：保證跟著掛了什麼走。
- **成本**：每個存檔點都要掃全樹（`add -A` 加巢狀重掃）。範本每項後面一個，大 node 每格要掃 n 次；實作時用 stat 快取。檔案很多的 node 可以把組綁大一點，減少存檔點。
- **多帳號**：`aos-as` 開的程序寫出的檔，擁有者是別的帳號。權限是 0600 時 tick 帳號讀不到，mark 會失敗、寫擋板。建議寫明：跨帳號任務寫進 node 的檔要讓 tick 帳號讀得到（B-609 的共享群組）。還原時靠上層資料夾的寫權換檔，通常沒問題。
- **任務 id 當 ref 名**：見 1.3。另一條路是改用 `refs/aos/marks/<AOS_TASK_INDEX>`，把 id 寫進提交訊息；使用者指定的是 `<任務 id>`，所以先照指定做、不合法的 id 報錯。
- **沒有 git 時的落盤**：核心紀錄與消費副本都不 fsync，斷電可能同時丟掉副本和已刪的原件。這是上一輪 B-632 就接受的，不是本輪新問題；有 git 時 commit 已落盤，才刪原件。

## 二、cgroup

### 2.1 什麼算「有 cgroup」（疑-6）

三個條件都成立才用：Linux ≥ 5.14、`/sys/fs/cgroup` 是 cgroup2（純 v2）、拿得到**委派給自己**的子樹。否則照現行的程序群組做（B-601、B-604）。stdout 印一行 `cgroup=on` 或 `cgroup=off`。

**「委派給自己」怎麼認**（草稿只看擁有者，實測不夠）：

- 設定明寫 `cgroup_root`，或開了 `create_cgroup`，就算。
- 省略時，看自己所在的單位是不是 `Delegate=yes`：用 `systemctl [--user] show -p Delegate <單位>` 問，單位名取 `/proc/self/cgroup` 最後一段。問不到（沒有 systemd）就算沒有。
- 實測（這台 WSL，systemd 255）：沒加 `Delegate=yes` 的 `systemd-run --user --scope`，`cgroup.procs` 一樣歸自己；兩種 scope 都沒有 `user.delegate` xattr。只看擁有者，會把沒委派的 scope 當成可以寫，違反 systemd「一個框只有一個寫入者」的約定。

**cgroup v1、混合模式**（v2 掛在 `/sys/fs/cgroup/unified`）：自動偵測一律算沒有。混合模式可以明寫 `cgroup_root` 指進去，但 controller 多半在 v1 那邊，上限會回 `unsupported`，只剩殺程序與看空不空能用。

### 2.2 子樹從哪來（首推不用 sudo）

依序推薦：

1. **systemd 使用者委派**（不用 sudo，首推）：`systemd-run --user --scope -p Delegate=yes aos daemon --config …`。實測這台 WSL 拿得到 `cpu memory pids`。
2. **使用者層 service**：固定單位名、`Delegate=yes`、`loginctl enable-linger`。開機自動啟動用這個；它的框路徑固定，重啟時 systemd 也會先殺舊程序。
3. **系統層 service**：root 開，`Delegate=yes`，有 helper，文末附錄那份。
4. **沒有 systemd**：root 事先 mkdir 並 chown，或 sudo 開加 `--create-cgroup`。
5. 都沒有：`cgroup=off`，照程序群組跑。

**限制要寫明**：

- **不用 sudo 就只能單帳號**：沒有 root helper，就不能把框交給別的帳號，也不能以別的帳號開程序。多帳號部署一定要 sudo（3 或 4）。
- **WSL**：
  - 實測 wsl.exe 開的 shell 在 root 擁有的 `/init.scope`，直接跑 daemon 只會是 `cgroup=off`；要先在 `/etc/wsl.conf` 設 `systemd=true`，再用 1 或 2。
  - VM 閒置被關時，所有東西一起死，照 B-603 處理。
  - 這台是純 cgroup2 並開了 `nsdelegate`。

### 2.3 框的樹

沿草稿：

```
<子樹根>/daemon                daemon 與 helper
<子樹根>/n-<h>                 頂層 node（分支，上限寫這層）
          ├─ tick              這格的 tick 與沒包 aos-cg 的任務
          ├─ task-<seq>-<pid>  aos-cg 開的每項一框
          ├─ mount-<h>         本 node 掛的掛載行程
          └─ n-<h'>            子 node
```

- **建框**：daemon 在 node 第一次開格前建 `n-<h>` 與 `tick`，不寫上限；上限由上層 kernel 用 `cgroup_limits` 寫（2.6）。
- **交框**：`n-<h>` 的資料夾與 `cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads` 交給 node 的執行帳號，因為 `aos-cg` 要在裡面開框、搬自己；上限檔仍歸 daemon。帳號不是 daemon 自己時經 helper。
- **連帶**：交框之後，node 帳號**技術上**就能在 `n-<h>` 下開自己的子框，所以疑-7 一定要定。node 也能對自己框裡別的帳號的程序寫 `cgroup.kill`（`aos-as` 開的），這是預期行為，不是漏洞。

### 2.4 開格、格後收尾、重啟清空

- **開格**：runner 開在 `n-<h>/tick`（用 `CLONE_INTO_CGROUP`，或 exec 前寫 `cgroup.procs`），照舊 `setsid`。
- **格後收尾**（B-601）：runner 回報之後，對 `n-<h>` 底下**除了子 node 的 `n-*` 與本 node 的 `mount-*` 以外**的每個框寫 `cgroup.kill`，看 `cgroup.events` 等 populated 變 0，再 rmdir `task-*`（框已交給別的帳號時由 helper 刪）。等不到歸零（例如 D 狀態程序）就照 B-607 停格。有 cgroup 時，不再另外對程序群組送 SIGKILL。
- **收尾**（B-604，重啟、停機、解除、`node.kill`）：TERM → 等 `shutdown_grace_ms` → `cgroup.kill` → 確認全空。範圍同上，再加上子 node 與掛載行程。
- **重啟清空**（B-603）。草稿說「省略 `cgroup_root` 就用自己所在的框」，但首推的 `systemd-run --user --scope` 每次開出的 scope 名字不同（實測 `run-r<隨機>.scope`），新 daemon 看不到舊 scope 裡的舊程序。建議（疑-8 a）：
  - `state.json` 記上次用的子樹根；
  - 啟動時舊根跟新根不同、而且舊根還在，就先取舊根的鎖（取不到表示另一個 daemon 在用，不碰），再對舊根走一次收尾；
  - 清空後舊 scope 沒有程序，systemd 會自己回收。
- **空框清理**：照草稿，逐層重建完、仍沒人登記的 `n-*` 才刪。

### 2.5 一棵資源樹只准一個 daemon（B-611）

- 有 cgroup 時，對子樹根另外取一把 flock，並往上試鎖到掛載點、往下掃子孫。實測 cgroup 目錄可以 open 後 flock，第二個 fd 會被擋（EAGAIN）。
- 用 1 開的兩個 daemon 各在自己的 scope，彼此是兄弟、不重疊，只有 `state_dir` 那把鎖會擋。
- **巢狀 daemon**（例如某個 tick 用 `node.mount` 掛了另一個 daemon）：內層自動偵測到的根，在外層的 `mount-<h>` 底下；外層鎖著祖先，照草稿內層會拒絕啟動（疑-11）。

### 2.6 上限與佈建動作

| 動作 | 有 cgroup 時 | 沒 cgroup 時 |
|---|---|---|
| `cgroup_limits` | 寫 `n-<h>` 的 `cpu.max`、`memory.max`、`pids.max`，隨時改、不等全空；調低超過的交給 Linux，下指令的 kernel 自己記一筆 | `unsupported`（不變） |
| `cgroup_create` | 照草稿：在上層框下建本 node 的框；疑-10 建議併進 daemon 自動建框 | `unsupported` |
| `cgroup_delegate` | 照草稿：inst 的 `user` 換了時把框交給新帳號；疑-10 建議改成 daemon 開格前發現擁有者不對就自動交 | `unsupported` |
| `spawn_as` 帶 `frame` | helper 核對它是本 node `n-<h>` 的直接子框、存在且沒有程序，把 runner 放進去 | 帶了回 `unsupported`（不變） |
| helper 內部「刪殘留框」 | 只給 daemon 用，不開放給 `node.provision` | 不用 |

- **controller 往下開**：要在子 node 上寫上限，上一層的 `cgroup.subtree_control` 要開 `+cpu +memory +pids`。每層都已交給該 node 帳號，所以上層 node 帳號關掉它，就等於撤了自己子 node 的上限。這在上層的權限內，不是逃脫；祖先對整棵分支的上限照樣有效。
- **這些動作算不算通道事務**：`node.provision` 不在追答 5 的四件事裡，但在格內用自己的帳號呼叫，算「在某一格裡做」，不違反唯一逃生口；它不在格外開任何程序。建議預設：`cgroup_limits` 跟 `node.register`、`node.wake` 一樣，**可帶可不帶**本格憑證，讓 kernel 的資源任務用 tick 身分核權。
- controller 不在（例如沒委派 `cpu`）時，那一項上限回 `unsupported`，其餘照用。

### 2.7 `aos-cg`（B-202、P-211）

- 草稿照留：在 `n-<h>/tick` 裡時開 `task-<seq>-<pid>`，搬自己進去，fork＋exec 原指令；主程序結束後還有程序就直接 `cgroup.kill`，等空了 rmdir。清不空回 1，stderr 印 `frame_not_empty`，建停格檔。
- **沒 cgroup 時**：退回 subreaper 加程序群組（上一輪疑-9 暫定 a，跟「沒有就退回程序群組」一致），stderr 印 `cgroup_unavailable`。人手或 cron 跑的格不在 `n-<h>/tick`，一律走這條。
- **拿掉**「開框前先清同框下 `seq` 較小的舊 `task-*`」：只有 daemon 開的格才會有 `task-*`，daemon 每格格後都會收掉，重啟時也會清，這一步是多餘的。
- 跟 `aos-as` 一起用時寫 `aos-cg -- aos-as <帳號> -- 原指令`（B-303、P-212 帶 `frame`），不變。

### 2.8 node 自己開的子框（疑-7）

第十八批 Q19 說「可調設定，預設不管」；第二十批追答 5 說「唯一逃生口是通道」；上一輪疑-13 暫定成「撤，改用 `node.mount`」，使用者還沒答。**這三句互相衝突。**建議照追答 5：

- 不提供逃生口；
- 格後收尾範圍寫成「`n-<h>` 底下除了子 node 與掛載行程以外的一切」，node 自己開的框也在內；
- 撤掉 `kill_escape_cgroups`；
- 這樣也不用再維護保留名清單（`tick`、`task-*`……），只剩 `n-*`、`mount-*` 要認。

### 2.9 中途失效、跑不出框

- **只影響某些 node**：daemon 啟動時 `cgroup=on`，之後某個 node 建框失敗（上層關了 controller、權限被改、`max.descendants` 滿了），建議那個 node 退回程序群組跑，寫一件事項，別的 node 照常；不整個 daemon 降級，也不停那個 node。這就是「有就用、沒有就退回」落到單一 node。
- **任務自己跑出框**：用 `systemd-run --user`、`at`、cron 這類外部服務開程序，就會跑出 `n-<h>`，逃過收尾與上限。`setsid`、double fork 逃不出 cgroup，只有外部服務能。aos 不擋這條路（B-626 說管轄權是約定），在 B-202 寫明「經外部服務開的不歸 aos 管」即可。

## 三、接點（條號、schema、範例、V-03）

逐列看 [batch20-cg-git-map.json](batch20-cg-git-map.json)，每列有條號、動作、內容摘要、依哪一題疑點。以下只列各篇重點。

- **名詞與入口**：T-01（保證條件句加「掛了 git 三件」與「daemon 有 cgroup」）、T-10 表（系統級任務加 `aos-git`，普通程式加 `aos-cg`）、「收尾」詞條（有 cgroup 時用 `cgroup.kill`）、「標準任務表範本」詞條（新順序）、spec 入口的依賴段。T-07 不改。
- **tick 篇**：
  - 篇首「本篇先假設」段改成現行規則；
  - B-626 第 2、3 點；
  - B-602、B-633 的「git 還原也不碰」改成固定排除（1.7）；
  - B-628 巢狀 git；
  - B-629 範本改寫；
  - B-621 組與還原段；
  - B-623、B-624 只改「下一步納入時補」那幾句（疑-4 取 b 時，行為不變）；
  - B-625 當機恢復；
  - B-632 改寫；
  - B-630、B-622 定稿搬進正文；
  - 刪篇末段。
- **daemon 篇**：
  - 篇首段；
  - B-601 開格與格後收尾；
  - B-603 清空、舊根、空框；
  - B-604 收尾；
  - B-605 偵測、子樹、命名、交框、逃生口；
  - B-606 換父與解除時的框；
  - B-608 `cgroup_root` 要重開；
  - B-609 動作表；
  - B-611 cgroup 鎖；
  - B-613 `mount-<h>`；
  - 附錄；
  - 刪篇末段。
- **base**：B-202（`aos-cg` 定稿、拿掉清舊框、寫明外部服務）、B-204（OOM 證據要有框）、B-303（`aos-as` 帶 `frame`）、B-404（在 tick 內由 close 提交；起點不改）、B-503（補投從 git 歷史撈）、inst 篇「撤回範圍」一句。
- **protocol**：
  - P-200 布局（`.gitignore` 最低清單、`info/exclude`、`refs/aos/marks/`、`refs/aos/rescue/`）；
  - P-203 介面表；
  - P-205 定稿（argv 加 `mark`，拿掉 `tick_blocked` 代碼，加 `not_in_tick`、`mark_id_invalid`）；
  - P-206 消費副本一句；
  - P-211 定稿；
  - P-212 `frame`；
  - daemon 協議：P-101 兩欄生效；P-102 `cgroup=on|off`；P-106 `node.show` 的 `cgroup`；P-107 動作與 `frame`；P-108 helper 的 `cgroup_remove` 與 spawn 的 `frame`；P-116 `state.json` 加上次子樹根。
- **schema**：
  - 要改的：`daemon-state`（加欄）、`daemon-provision` 與 `daemon-registration` 的動作列舉（疑-10 取 b 時刪兩個）、`daemon-rpc`（`node.show` 的 `cgroup` 說明）、`daemon-config`（描述改成生效、撤 `kill_escape_cgroups`）；
  - 不改的：`node-tasks`、`node-tick-record`。
- **範例**：
  - 新增「掛了 git 的範本任務表」valid、「mark 的 id 以 `.lock` 結尾」invalid（若採報錯）；
  - `get_result` 的 `cgroup` 非 null 範例已有，核對即可；
  - 疑-10 取 b 時，刪 `provision_cgroup_create`／`_delegate` 兩組範例。
- **V-03**：「下一步納入：git 與 cgroup」小節的句子搬進正文、依本計畫改寫，另加下列新場景（每句正本條號見 map）：
  - **git**：
    - 失敗組在它的存檔點被還原，後一組讀不到它的改動；
    - 停格檔讓整格作廢、下一格重收；
    - 當機四個窗口：使用者任務中、close commit 前、commit 後、投件中；
    - 格間手改進 rescue ref；
    - `.gitignore` 漏了 `/.aos/tick/` 時 `seq` 仍連續；
    - git 沒裝、太舊、不是 repo 時照 B-632，repo 壞了寫擋板；
    - 格中新建的子 node 不被上層提交；
    - 格結束後沒有背景 git 程序握著鎖；
    - node 根目錄擁有者跟 tick 帳號不同時照常提交；
    - 別的帳號寫了 0600 檔時寫擋板；
    - close 失敗時不投件；
    - 滿碟時 commit 失敗、不刪原件。
  - **cgroup**：
    - WSL 的 `init.scope` 與沒委派的 scope 都印 `cgroup=off`，委派 scope 印 `cgroup=on`；
    - `setsid` 加 double fork 的殘留在格後被 `cgroup.kill`；
    - scope 名換了，重啟仍清得到舊框；
    - 某個 node 建框失敗時只有它退回程序群組；
    - 巢狀 daemon；
    - node 自開的子框在格後被收；
    - 同一個 `cgroup_root` 後啟動的回 125；
    - `aos-cg` 在沒 cgroup 時退回；
    - `aos-cg -- aos-as` 別帳號的程序在同一框。
- **V-02**：「下一步納入時補」那段轉正。V-01 正本表的列：B-630、B-622 拿掉「下一步納入」字樣，P-205、P-211 同。

## 四、審：設計原則

### 4.1 冗餘（建議拿掉）

| 草稿裡的 | 為什麼多餘 |
|---|---|
| open 看擋板、`tick_blocked` 代碼 | 核心有擋板時一項都不跑，open 碰不到擋板 |
| open 刪 HEAD 裡已提交的原件 | 新順序下「上一格正常收尾」＝已提交，收件任務的現行規則等價（疑-4） |
| 投件只投 HEAD、發摘要從 HEAD 取 | 同上，走到投件就表示 close 已成功，工作樹等於 HEAD |
| 保留期起點改成「首次提交那格」 | 現行「`aos-clean` 首次看到那格」有沒有 git 都對，只會晚不會早 |
| close 的「後組改到同路徑一起還原」 | 失敗組在自己的存檔點就還原，後組根本看不到（疑-2 b） |
| `aos-cg` 開框前清舊 `task-*` | 只有 daemon 開的格有 `task-*`，daemon 每格收、重啟也清 |
| 受管框的保留名清單 | 收尾範圍寫成「除子 node 與掛載行程以外全收」就不必列（疑-7） |
| `cgroup_create`、`cgroup_delegate` 兩個手動動作 | daemon 開格前本來就要建框、本來就讀 inst 的 `user`，可以自動做（疑-10） |
| 有 cgroup 時仍對程序群組 SIGKILL | `cgroup.kill` 已涵蓋；`setsid` 留著只為了送訊號方便 |
| `aos-git` 在 tick 外自己取鎖 | close 在格外沒有本格紀錄，改成回 125 |

### 4.2 沒考慮到的狀況

逐條見第一、二節，這裡集中列：

- **git**：
  - 停格檔讓 close 不跑（疑-1）；
  - 失敗組的改動被後面的組讀到（疑-2）；
  - 格間手改被還原（疑-3）；
  - 當機在 close 途中留下 git 鎖檔（1.2 第 3 步）；
  - `.gitignore` 漏列核心檔（1.7 固定排除）；
  - git 自動 gc 在背景跑、握著鎖 fd（1.7）；
  - hooks、簽章、`GIT_*` 環境、沒設作者（1.7）；
  - 多帳號的 `safe.directory` 與 0600 檔（1.7、1.10）；
  - 格中新建子 node（1.9）；
  - 任務 id 不是合法 ref 名（1.3）；
  - 沒包 `aos-cg` 的殘留在還原後又寫回來（1.10）；
  - 每個存檔點都掃全樹的成本（1.10）。
- **cgroup**：
  - 擁有者 ≠ 委派（2.1，實測）；
  - WSL 的 shell 在 `init.scope`（2.2，實測）；
  - systemd 不在（2.2 第 4 項）；
  - cgroup v1 與混合模式（2.1）；
  - 不用 sudo 只能單帳號（2.2）；
  - scope 名每次不同，重啟找不到舊框（2.4，實測）；
  - 巢狀 daemon 被鎖擋住（2.5）；
  - 建框中途失敗（2.9）；
  - D 狀態程序讓框一直不空（2.4）；
  - 任務經外部服務跑出框（2.9）；
  - 上層關 controller 等於撤子 node 上限（2.6）。

### 4.3 跟三條原則有沒有衝突

- **tick 核心只做四件事**：沒有衝突。git 與 cgroup 都不需要核心多做事。唯一會衝突的是疑-1 選項 c（核心加「收尾項照跑」），不建議。
- **唯一逃生口是通道**：
  - 逃生口子框直接衝突（疑-7，建議撤）；
  - git 背景 gc 是隱性衝突（1.7 已修）；
  - 外部服務開程序是 aos 擋不住的漏洞，寫成約定（2.9）；
  - `cgroup_limits` 等佈建動作是格內呼叫，不算繞過（2.6）。
- **保證跟著掛了什麼走**：
  - 投件「只投已提交」要靠 close 排在投件**前面**，是順序帶來的保證。範本對了就成立，使用者自己把投件排到 close 前面時就沒有；照 T-01「沒掛（沒排對）的後果不逐條寫」。
  - open、mark、close 只掛其中一部分時，保證各自縮水：只掛 open 有當機還原、沒有失敗組還原；只掛 close 會提交、但當機不還原。不另外檢查。

## 五、疑點（請你裁定）

最重要的放前面。每題的「建議」是記錄者的預設，不代表已定。

**疑-1 任務建了停格檔，git 收尾就不會跑，這格的改動怎麼辦？**
停格檔會讓後面各項都不跑，包括排在後面的 git 收尾，所以這格什麼都沒提交；下一格開格看到「上一格沒正常收尾」就整格還原。前面已經成功的組也一起丟掉，收件要重收。
- a：接受。有 git 時，停格檔的意思就是「這格作廢」。想提早結束又保住結果的任務，不要用停格檔，改讓後面的項讀紀錄自己跳過。（建議）
- b：下一格開格時補做上一格的收尾：照上一格留下的存檔點，把已經做完的成功組補提交，只還原沒做完的部分。當機也適用，損失最小，但開格變複雜，也要靠沒落盤的存檔點。
- c：核心多一條：任務表可以標某項「停格也照跑」，讓收尾一定跑。核心會變成五件事。

**疑-2 失敗組的改動在哪裡還原？**
照裁定 3 每組後面有存檔點。問題在時機：等收尾再還原的話，後面的組已經讀過失敗組寫的東西，可能拿壞資料做出「成功」的結果。
- a：照草稿，收尾時一次算、一次還原；後面的組改到同一個檔就一起算失敗。
- b：每個存檔點當場檢查剛結束那組，失敗就立刻還原再打點；後面的組看不到失敗組的改動，收尾只要提交。（建議）
- c：兩者都做。

**疑-3 上一格沒正常收尾、下一格開格要還原時，格間人手改了還沒提交的東西怎麼辦？**
例如上一格當機，接著你手改了設定、還沒 commit；下一格開格一還原，手改就沒了。
- a：照草稿直接還原，沒提交就丟；修的人要記得自己提交。
- b：還原前先把差異存成 `refs/aos/rescue/<seq>`，工作樹照樣還原；丟了可以撈回。只留最近幾份（例如 10 份）。（建議）
- c：上一格沒正常收尾時不自動還原，改成寫擋板等人處理。

**疑-4 收件、投件、發摘要、清理要不要認得 git？**
追答 8 說「下一格開格時刪已提交的原件」；草稿還讓投件「只投 HEAD 裡的」、發摘要「從 HEAD 取」。但在新順序下，上一格正常收尾就等於已提交，走到投件就表示已提交。
- a：照草稿，刪原件搬到 git 開格，投件與發摘要改讀 HEAD；有 git、沒 git 各一套寫法。
- b：都不改。刪原件留在收件任務，規則仍是「上一格正常收尾才刪」；git 只活在開格、存檔點、收尾三處。（建議）
- c：刪原件搬到 git 開格，投件與發摘要不改。

**疑-5 掛了 git 任務，但 git 不能用時怎麼辦？**
- a：一律退回沒 git 的做法（照 B-632），只印 `no_git`。
- b：沒裝、版本太舊、不是 repo 就退回；repo 在但壞了（HEAD 讀不到、物件缺、權限不夠）就寫擋板等人。（建議）
- c：一律寫擋板：既然掛了，就是要 git。

**疑-6 daemon 怎樣才算「有 cgroup 可以用」？**
實測：沒委派的框，檔案也歸自己，只看擁有者會誤用別人管的框。
- a：看得到 cgroup v2、框的檔案歸自己就用（草稿做法）。
- b：明寫 `cgroup_root`，或 systemd 說自己所在的單位有 `Delegate=yes`，才用；其餘一律算沒有。（建議）
- c：只有明寫 `cgroup_root` 才用，不自動偵測。

**疑-7 node 在自己框裡另開子框、留住常駐程序，還准不准？**
第十八批 Q19 說「可調、預設不管」，第二十批追答 5 說「通道是唯一逃生口、不准背景程序繞過 tick」，兩句衝突。上一輪暫定撤掉，你還沒答。
- a：照 Q19，預設不管，設定可以改成要殺。
- b：不准。每格結束把 node 框裡除了子 node 與掛載行程以外的全部收掉；要常駐就用 `node.mount`。（建議）
- c：不殺，但每格發現就寫一件事項。

**疑-8 daemon 重啟後找不到舊框（首推的做法每次開出的框名字都不同），舊程序怎麼清？**
- a：`state.json` 記上次用的框，重啟時舊框還在、沒被別的 daemon 鎖住，就先清空它。（建議）
- b：首推改成固定名字的使用者層 service，讓 systemd 重啟時殺舊程序；`systemd-run --scope` 只當試用。
- c：接受清不到，跟沒 cgroup 時一樣（下一格靠鎖回 75）。

**疑-9 設定明寫了 `cgroup_root`，開機時卻準備不好，daemon 怎麼辦？**
- a：報錯退出（草稿）：明寫就是要，默默不用會少了上限。（建議）
- b：照樣退回程序群組跑，印警告、寫事項。
- c：由設定另開一欄決定。

**疑-10 建框、把框交給帳號，要手動佈建還是 daemon 自動做？**
daemon 開格前本來就要建框，也本來就讀 inst 的 `user`。
- a：照草稿保留 `cgroup_create`、`cgroup_delegate` 兩個佈建動作，daemon 也會自動建。
- b：兩者都由 daemon 開格前自動做（要 root 的經 helper 內部動作），佈建只留 `cgroup_limits`。第十八批第 3 條的「helper 把框交給某帳號」仍在，只是不對外開放。（建議）

**疑-11 daemon 開在另一個 daemon 管的框裡（巢狀 daemon）怎麼辦？**
照草稿的鎖，內層會發現祖先被外層鎖住而拒絕啟動。
- a：內層自動偵測時碰到外層鎖，就當成沒有 cgroup（`cgroup=off`）照跑；它仍被外層的框和上限包住。（建議）
- b：拒絕啟動（草稿）。
- c：允許內層在外層的掛載框裡用 cgroup。

**疑-12 每個存檔點都要在任務表占一項，表會長一倍，要不要多一種寫法？**
- a：照裁定，存檔點就是獨立一項。（建議，最單純）
- b：另外允許包裝寫法 `aos-git mark -- 原指令`，跑完原指令順便打點，一項頂兩項；兩種寫法並存。

## 六、分工與順序（建議）

1. 先等疑-1～4 的答案（決定 B-630、B-623～625、B-632 怎麼寫），同時可以先寫 cgroup 側。
2. **git 隊**：tick 篇、P-200、P-203、P-205、B-404、B-503、V-03 的 git 句。
3. **cgroup 隊**：daemon 篇、B-202、B-204、B-303、P-101、P-102、P-106、P-107、P-108、P-116、P-211、P-212、V-03 的 cgroup 句。
4. **協議隊**：schema 與範例。
5. **主編**：T-01、T-10、spec 入口、V-01 與 V-02，以及落點表裡「其他篇跟上」的列，排進下一輪。
6. 落完跑 `check_ids.py` 與 schema 範例驗證，並在 WSL 實機驗第二節的三項實測。
