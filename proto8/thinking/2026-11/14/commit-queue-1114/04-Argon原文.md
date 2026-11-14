# commit 排隊：Argon 審查原文

← [commit-queue-1114](../commit-queue-1114.md)｜涵蓋：Argon（Gemini 4 Argon High，plan 模式、無工具）對 01～03 的 (A) 審查 11 條、(B) 提案 4 條，原文照錄

指令：在 /tmp 跑 `agy -p <01+02+03 全文與要求> --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`，第一次就過（沒遇到 Authentication required）。

---

### (A) 審查：錯誤、漏洞與邊緣狀況

1. **[高] `journal.json` 寫在 `update-ref` 之前，但復原時沒驗 `NEW` 有沒有進 `main`（失敗復原／CAS 重試漏洞）**
   - **問題**：步驟 9 先寫 `journal.json` 再跑 `update-ref`。若 `update-ref` CAS 失敗（或跑之前被殺），`main` 根本沒指到 `NEW`；但跳回步驟 2 重試或下次有人呼叫時，步驟 1 看到有 `journal.json` 就會把**未生效的 `NEW`** 硬寫進共用 `.git/index` 與工作樹，造成幽靈污染。此外，若補寫前有人手動 commit 把 `main` 推到更新的 `NEW2`，直接拿舊 `NEW` 補寫會蓋掉 `NEW2` 的改動。
   - **改法**：
     1. `update-ref` CAS 失敗時，必須**先刪掉 `journal.json`** 再跳回步驟 2。
     2. 步驟 1（與 `doctor --repair`）看到 `journal.json` 時，先跑 `git merge-base --is-ancestor <NEW> refs/heads/main`：若回傳非 0，代表上次死在 `update-ref` 成功前，**直接刪掉 `journal.json` 不補寫**；若回傳 0 才補寫（若 `main` 已超越 `NEW`，僅對 `NEW` 與當前 `main` blob 相同的路徑補寫）。

2. **[高] 快取樹只靠 `read-tree --reset -u OLD` + `clean -fdq`，清不掉上次失敗殘留的髒生成物與 ignore 檔（Git 底層用法錯誤）**
   - **問題**：驗證 A3 提到 `index_gen.py` 報錯（rc=1）時「還是會寫其他份」到快取樹，且此時還沒跑 `update-index`，所以快取 index 裡的生成物仍是 `OLD` 版。下次別人執行步驟 4 跑 `read-tree --reset -u OLD` 時，因為「快取 index == `OLD`」，`read-tree -u` **不會覆寫快取樹裡已被改髒的 tracked 檔**；`clean -fdq` 也只清 untracked 檔（且不含 gitignore 檔）。結果上次失敗殘留的生成物會留到步驟 7 被 `status --porcelain` 誤收進別人的 commit。
   - **改法**：步驟 4 改為三步（都在快取環境變數下，**切勿跑 `git reset --hard` 以免動到真 repo 的 `HEAD`**）：
     1. `git read-tree --reset -u OLD`
     2. `git checkout-index -f -a`（強制把快取樹所有 tracked 檔還原成 `OLD`）
     3. `git clean -fdxq`（加 `-x` 連同被 ignore 的暫存檔一併清乾淨）

3. **[高] 步驟 10 先跑 `update-index --cacheinfo` 再寫工作樹，導致共用 `.git/index` 的 stat cache 全空（Git 底層用法錯誤）**
   - **問題**：`update-index --cacheinfo` 只寫入 mode 與 blob SHA1，不會填檔案的 `mtime/ctime/ino/size`（stat 全為 0）；且步驟 10 在步驟 11（寫工作樹）之前跑。這會害共用 `.git/index` 裡這批檔案全部處於 stat-dirty 狀態，後續任何工具跑 `git diff-files` 都會誤判為 modified，跑 `git status` 也得重算整批檔案雜湊。此外，逐檔呼叫 `update-index` 若有 30+ 個生成物就要搶 30+ 次 `index.lock`，極易撞鎖或做一半中斷。
   - **改法**：
     1. **步驟 10 與 11 對調**：先寫共用工作樹（原步驟 11），再更新共用 `.git/index`（原步驟 10）。
     2. 改用 `git update-index -z --index-info` **單次呼叫（只鎖一次 `index.lock`）**批次寫入所有變動（刪除項傳 mode `0` 與 40 個 `0` 的 SHA1）。
     3. 緊接著對這些路徑跑一次 `git update-index -q --refresh -- <paths...>`，把工作樹最新的 stat 填回共用 index（工作樹若有未 commit 修改，`-q` 會安靜略過不報錯，index 仍維持 `NEW` 的 blob）。

4. **[高] 符號連結（symlink）用一般讀檔與寫檔處理會壞掉或變成普通檔（邊緣狀況）**
   - **問題**：計劃允許收 symlink（mode `120000`），但步驟 5 若直接對路徑跑 `git hash-object -w <path>` 或 `open()`，會去讀連結指向的**目標檔**（若目標不存在更會直接報錯）；寫進快取樹若用一般寫檔會變成 `100644`，到了步驟 7 `status --porcelain` 就會出現 typechange (`T`)，觸發「白名單外變動 → FAILED」。
   - **改法**：檢查 `os.path.islink(p)`。若為 symlink，用 `os.readlink(p)` 取得目標路徑字串，透過 `git hash-object -w --stdin` 算 blob、mode 設 `120000`，並在快取樹用 `os.symlink()` 建立連結。

5. **[中] 步驟 3 與步驟 5 分兩次讀共用工作樹，且等鎖期間檔案可能被改（並行／TOCTOU 漏洞）**
   - **問題**：步驟 3 檢查「`blob ≠ HEAD`」讀一次工作樹，步驟 5 寫入快取樹又讀一次工作樹；若兩次讀取之間該線還在改檔，快取樹與快取 index 的內容就會不一致，導致步驟 7 報「白名單外變動」。
   - **改法**：在進入處理時，**只讀一次**共用工作樹上的 `files` 到記憶體（記下 bytes / link target、mode、算好 blob SHA1），步驟 3 的比對與步驟 5 寫入快取樹全部使用記憶體裡這同一份快照，絕不二次讀取工作樹。

6. **[中] 日索引在「新的一天」允許放進 `--files`，會讓換日時多條線搶改同一檔的問題復發（並行與語意漏洞）**
   - **問題**：換日時若兩條線同時交當天第一筆，都手寫 `14/README.md` 放進 `--files`，就會再次發生混寫或第二條線因「日索引在 HEAD 已存在，不准在 `files`」而被擋；相反地，若第一條線乖乖只傳 `--op day_upsert`，快取樹裡還沒有那天的 `README.md` 就會讀檔失敗。
   - **改法**：**一律禁止日索引出現在 `--files`**。當 `day_upsert` 發現快取樹裡該日的 `README.md` 尚不存在時，由排隊程式自動以標準日索引模板（含第一行一句話與表頭）建立新檔並插入該列。

7. **[中] 共用檔在工作樹 `≠ OLD` 時「只重套本次 ops」，可能洗掉前人已 commit 的列（共用工作樹寫回漏洞）**
   - **問題**：步驟 11 若發現工作樹的共用檔 `≠ OLD`，只在工作樹那份上重套「本次的 ops」。但若某個 agent 編輯器開著舊版工作樹存檔，讓工作樹落後 `OLD`（漏了前一次 commit 的 ops），只套本次 ops 就會讓前一次已進 `HEAD` 的列在工作樹上消失。
   - **改法**：當工作樹那份 `≠ OLD` 時，先在快取裡拿 `OLD` 版、工作樹版、`NEW` 版做三方合併（`git merge-file --union -p <工作樹檔> <OLD檔> <NEW檔>`），再對結果跑一次本次 ops（因 ops 冪等，有就不會重複加），最後原子寫回工作樹。

8. **[中] `month_bump` 用「子字串包含」判斷冪等會誤吞短摘要；`day_upsert` 改用 `[name](link)` 認列會在改名時重複插列（冪等漏洞）**
   - **問題**：
     1. `month_bump` 若用 `segment in summary_col`，當既有摘要有 `"commit 排隊設計"`，新交的 segment 是 `"commit 排隊"`，會被當成已存在而吞掉（份數也不加）。
     2. `day_upsert` 若以 `| [name](link) |` 認列，同一檔案 `link` 修改標題 `name` 重交時會認不到舊列，變成重複兩列。
   - **改法**：
     1. `month_bump` 將摘要欄以 `；` 切開 strip 成陣列，用 `segment.strip() in segments` 做**整段精確比對**。
     2. `day_upsert` 維持以第一欄內的 `](link)` 為唯一鍵認列；所有 ops 參數驗證不得含換行或未跳脫的 `|`。

9. **[中] 步驟 1 復原或步驟 10 `index.lock` 逾時提前結束時，漏了釋放 `claims.json`（失敗復原漏洞）**
   - **問題**：步驟 10 若遇 `index.lock` 逾時會直接回 `DONE + 警告` 並保留 `journal.json` 給下次步驟 1 補；但步驟 1 只寫「補步驟 10、11，刪日誌」，忘了補跑步驟 12 的「釋放 claim 與寫 `log.jsonl`」，會導致已 commit 檔案的 claim 永遠卡死。
   - **改法**：`journal.json` 內一併記錄 `line`、`keep_claim` 與要釋放的 `files`；或者在步驟 9 `update-ref` 一成功後就先釋放 `claims.json`（因為 commit 已經進 `main` 了）。

10. **[低] 純改執行權限（`chmod +x`）或純 `--op` 提交會被步驟 3 誤擋；刪空目錄後舊 `_index.json` 的去留未定（邊緣狀況）**
    - **問題**：
      1. 步驟 3 檢查「`blob ≠ HEAD`」，若某檔案只改了 `+x`（mode `100644` → `100755`，blob 沒變）會被當成沒改動而 BLOCKED。
      2. 若只有 `--op` 而沒有 `--files`／`--rm`，步驟 3 需允許空檔案清單。
      3. 備料提過「刪檔後資料夾空了，舊 `_index.json` 留著」，假設驗證漏測了這題。
    - **改法**：
      1. 步驟 3 改比對 `(mode, blob) != (head_mode, head_blob)`，並允許只傳 `--op`（改在步驟 8 驗證 `NEW_TREE != OLD_TREE`）。
      2. 實測 `index_gen.py` 在目錄檔案被 `--rm` 刪光時的行為；若它不會自動刪空目錄的 `_index.json`，在步驟 7 主動检查被 `--rm` 影響的目錄，若已無其他受控檔則在快取樹將該 `_index.json` 一併 `--force-remove`。

11. **[低] 環境變數污染風險（實作細節）**
    - **問題**：`GIT_DIR`、`GIT_WORK_TREE`、`GIT_INDEX_FILE` 若設在 `os.environ` 或使用相對路徑，會讓 `git -C` 找錯目錄，或在步驟 10 操作共用 index 時誤寫回快取 index。
    - **改法**：三個路徑一律轉成 `os.path.realpath` 絕對路徑，且只在呼叫快取樹 subprocess 時透過 `env=` 區域傳入，絕不修改全域 `os.environ`。

---

### (B) 提案：更好或該加的做法

1. **以 `git diff-tree -r -z OLD NEW` 作為步驟 9～11 的唯一真相來源**
   - 在步驟 8 建出 `NEW` 後，直接跑一次 `git diff-tree -r --no-commit-id --raw -z OLD NEW`，就能拿到 `OLD` 到 `NEW` 所有真正發生變動的路徑、新舊 mode/blob 與狀態（A/M/D）。
   - 直接把這份陣列存進 `journal.json`，步驟 10（餵給 `update-index -z --index-info`）與步驟 11（決定哪些生成物與共用檔要寫回工作樹）全部照這份陣列走，不必在步驟 5、6、7 手動東拼西湊路徑清單，也能自動濾掉套了冪等 op 後實際沒變的共用檔。

2. **把檔案快照移到「等 `flock` 之前」擷取，抓出等鎖期間的偷改**
   - 申請者呼叫 `commit-request submit` 時，在進 `flock` 等待前先把 `--files` 讀進記憶體算好快照；等拿到鎖後再比對一次工作樹檔案的當前雜湊。若等鎖的這幾秒內檔案又被動過，代表該線在背景等鎖時還在改同一支檔案，直接 BLOCKED 擋下，避免交出半成品。

3. **支援「同命令重送」的冪等回傳（Idempotent Retry）**
   - Agent 在 Bash 執行指令偶爾會因 timeout 重跑同一條 `submit`。若步驟 3 發現 `--files` 的 `(mode, blob)` 已經全部等於 `HEAD`，且套完 `--op` 後的樹也與 `HEAD` 完全相同、commit 訊息首行也與 `HEAD` 一致，不要回 `BLOCKED (無改動)`，直接回 `DONE` 並附上 `HEAD` 的 commit hash 與 `"warnings": ["already committed at <hash>"]`，並順手釋放該線殘留的 claim。

4. **`claims` 加上過期警示（Stale Claim Hint）**
   - 雖然 claim 不自動過期，但若某條線掛掉忘了 release，別條線被擋時很難判斷對方是「正在改」還是「早就死了」。在 `claims.json` 記錄 claim 時間與最後活動時間，當持有超過例如 2 小時，於 `BLOCKED` 回傳與 `doctor` 輸出中標註 `"stale": true` 及經過分鐘數，提示可直接請頂層 `--force` 釋放。
