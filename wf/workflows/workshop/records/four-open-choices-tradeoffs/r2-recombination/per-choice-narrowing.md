# R2：四題各自被收窄成什麼

> 〈成形的方向〉底下的其餘四節，分別收窄 R1 的第二題（kernel）、第一題（路徑／multiplex）、
> 第三題（A／B）、第四題（身分）。

## 每個世界保有完整 kernel，不向父層動態繼承

接住使用者「每個行程都可以有自己的 kernel」的傾向：每個 `procs/<name>/.aos/` 都保存完整
`kernel.json`，執行時只看自己，不沿目錄或 parent 欄位向上找。換到世界自足、可獨跑、可搬、可重播；
賠掉政策自動同步，升級責任改由 core 逐份處理。

**複用發生在寫入完整檔時，不在執行當下暗中合成。**寫入方式的候選：完全不繼承；core 在建立／升級時
物化完整 kernel，另以 `kernel.source.json` 記來源；父先明寫子 kernel 再呼叫；用模板建立。

這讓第二、第四題解綁：kernel 不用判斷「父」是目錄祖先還是 UUID parent，搬到別處也不會只因換父就
暗中換政策。代價從「合成規則」移成「誰負責把每份完整檔升級到正確版本」。

## 對外路徑規則可以不改；要改的是單一行程 multiplex 的內部 I/O

使用者問「一個 `aos exec` 推多世界，但路徑要改？」答案分兩層：

- 對 instruction、`$ref`、重導向與外部處理器，路徑仍以**各自世界的 folder** 為根，不改成相對總
  root，子世界也不必知道父路徑。
- 「一個 exec」指**同一個 OS 行程**同時持有多個世界時，內部才用 root fd／`openat`；啟動普通子命令
  前再 `fchdir(root_fd)`，管理者本身不反覆切全域 cwd。
- 「一個 exec」指**命令呼叫樹**時，每次 `aos exec <child>` 仍只推一個世界，原本 cwd 模型保留。

外部路徑語意都保住；「一個 `aos exec`」指哪一種實作（`advance_once(World&)`、`aos exec w1 w2`
逐 root fd 推進、命令樹）尚未對齊。

## 原本的 A／B 被重組成「完整子世界＋集中管理」

磁碟形狀：root 與 `root/procs/<name>` 各有完整的 `.aos/{kernel.json,inst.json,…}`；父端另有只給
core 看的 proc-table／manifest，記 path、generation、ready／join 等管理狀態。子世界沒有 parent 欄位，
queue 在自己的 `.aos`，不另設集中 `lanes/`。

這是 R1 A 的**儲存方式**（每個子行程是完整小世界）加 R1 B 的**管理方式**（root core 是唯一管理者），
但 queue 不搬到父層。共同 ABI 可縮成「自足的 world step」，proc-table 是 core 的索引，不是 `exec`
ABI；循序呼叫、多子行程，或日後在同一 OS 行程內呼叫 `advance_once(World&)`，磁碟上的子世界都不必
跟著搬。

**誰去推世界可以延後；子世界是否自足、queue 放哪裡、core 如何認領結果是磁碟契約，不能延後。**

## 不用 UUID，改用父域名稱／路徑加 generation

接受使用者「不該綁 UUID」的傾向，並排除 inode 與內容 hash：inode 經搬移／複製不可靠，內容 hash 又會
隨世界演化。替代形狀有兩種：

| 形狀 | 得到什麼 | 付出什麼 |
|---|---|---|
| 父域內的 `(name, generation)`／`<slot>@<generation>`，表內另記相對路徑 | 同名資料夾刪掉重建後，舊 receipt 不會誤投給新行程；不用全域 registry | 身分只在父域內成立；搬出父域要 detach／adopt，未完成關係不能自然續接 |
| 正規相對路徑就是地址，`.runi` 只代表本次 activation | 最少 metadata，`tree` 仍直接可讀 | rename 就是改址，copy 是新世界；若重用同一路徑，還要另靠回合資料避免收錯舊結果 |

共同界線：**不用 UUID 就不承諾「搬家後仍是同一個行程」。**搬移的收緊方式有三種候選：只允許沒有
`.runi`、沒有待收 receipt 時做同 filesystem rename；搬移＝detach＋新 attach、舊 receipt 失效；跨父域
時明做 `adopt`。generation 的用途不是模仿全域 UUID，而是防止「同名新目錄收到上一代的結果」。
