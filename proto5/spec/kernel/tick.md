← [kernel](README.md)｜[spec 總導航](../README.md)

# 3. 一格 tick 做什麼

```sh
aos-kernel tick --target K --chain C --seq N
```

每一步標了 **讀**／**寫帳本**／**放檔**；「崩在這裡」的後果寫在步驟後面。cpu 那邊的順序是
「先發回音、再刪原單」（範式 §6.3），這裡查檔一律**先查原單、再查回音**，才不會看錯。
第 5～9 步新增的四類出貨待辦（ack／回音／stop／刪原單）不在當步做，統一在第 10 步；崩在中間下格第 4 步補。
第 6 步補放、第 7 步 spawn、第 8 步派工不是出貨箱的東西，各在自己那步當場放。

1. **讀** info、帳本。`--chain` ≠ `chain` → 舊鏈的殘格：退 0、什麼都不做。
2. `phase=stopped` → 出貨（第 4 步的方式，含 `stops`）、不接鏈、退 0。否則**放檔**：把下一格 `link` 到
   `cpus/<kcpu>/requests/k-<chain>-<N+1>.json`（`aos-exec`：`target`＝帳本的 `cli`，是普通檔，
   `args`＝`["tick", "--target", K 的絕對路徑, "--chain", C, "--seq", "N+1"]`（09-24 fix-r4 改），全是字串；**明寫 `timeout_ms: 0`**，不吃 cpu 的預設）。EEXIST＝上一格已放過
   （它崩在放檔之後、寫帳本之前，這格被重跑）——只有第 N 格會放第 N+1 格，所以 EEXIST 不會是別人。
   然後**寫帳本** `last_seq=N`。**先放後記**：這格之後崩了，下一格照跑。崩在放檔之前＝鏈斷，daemon 的
   `restart` 救不了（cpu 沒死、是沒單），`ls` 看得出（§6），人重新 boot。
3. 睡 `tick_ms`（下一格已在隊上，但 kernel cpu 正被這格佔著，睡完退出它才開始；實際週期＝睡＋這格做事的時間）。
4. **出貨**：四張出貨箱每筆放檔（`link`，EEXIST 當已放；`deletes` 是刪檔，ENOENT 當已刪）、每放完一筆**寫帳本**拿掉。
   順手把 kernel cpu 的 `responses/` 全部 ack 掉——這是唯一不進帳本的出貨（都是舊 tick 的回音；`code≠0` 的記 log 一行）。
5. **讀** `requests/`，收 syscall（§2；`ack-` 照範式 §3.3、`stop-` 只改 `phase`）。放在 daemon 操作之前。
6. **收回音**：每顆 `req` 非 null 的工作 cpu，先**讀** `cpus/<c>/requests/<req>` 在不在——
   - 在：在途，跳過。
   - 不在，再看 `cpus/<c>/responses/<req>`：**在** → 判定（§4），把結果（計數、status、queue、pending 的回音進
     `replies`、這則的 ack 進 `acks`、`req`／`proc`／`discard` 清掉）**一次寫帳本**。崩在寫帳本之前＝下格重讀
     同一份回音、重判一次，冪等（回音要 ack 才會消失，而 ack 在帳本之後才放）。
   - 兩個都不在：從沒放出去（上格崩在寫帳本之後、放檔之前）→ **再放一次**（`link`，EEXIST 就當已在）。
     這個推論成立是因為 cpu 只在回音發出之後才刪原單，而回音只有 kernel 放 ack 才消失、ack 又在帳本之後。
7. **daemon**（§5）：偷看 `D/state.json` 的孩子表。對 info.cpus 裡每顆 c（含 `kcpu`）：
   - 表裡有 c、`alive=true`、`target` 是 `K/cpus/<c>/inst.json` → 好。
   - 表裡有 c 但 `target` **不是**我們的 → 別的 kernel 的孩子：stderr `NameTaken`、退 1，不派工。
   - 表裡沒有 c、或 `alive=false` 且 `state` 不是 `dead`（不是在等重拉）→ 家不在就建（info、inst，`envs` 照 info），
     `spawn`（`name`＝c、`restart:true`），等回音。`state=dead` 的讓 daemon 自己重拉。
   cpu 非 0 死掉是 daemon 自動重拉，這裡不用管（daemon 自己重啟過則要人重 boot，§6）；重生那顆手上若有 `req`，它的開機對帳會回 `Interrupted`
   （原單還沒開始的它照做，不是每件都 `Interrupted`），下格在第 6 步照常收。
8. **派工**（`phase=running` 才做）：每顆 `req` 為 null 的工作 cpu，從 `queue` 頭找第一個 pool 相符且
   `not_before` 已到的行程 → 從 queue 拿掉、`status=running`、`req`＝`k-<chain>-<N>-<c>.json`、`proc`＝NAME、
   **寫帳本** → **放檔**（`aos-exec`，params 照行程紀錄：`target`／`dir_target`／`args`（有才放）／`timeout_ms`）。
   崩在寫帳本之後、放檔之前＝第 6 步補放。**先記後放**，所以永遠不會同一行程派兩顆。
9. **停機**（`phase=stopping`）：先把 `queued` 的 `once` 全部拿掉、各回 `-32000`／`Stopping`（進 `replies`）。
   然後所有工作 cpu `req` 為 null、四張出貨箱空、沒有任何 `pending` → `stops`＝所有 cpu（含 `kcpu`）、
   `phase=stopped`、**寫帳本** → 第 10 步出貨。kernel cpu 收到 stop 就不會再跑已排的下一格，那份殘格留著，
   下次 boot 換了 chain 它會自滅。崩在寫帳本之後、放完之前＝下格（若還跑得到）第 2 步補放；跑不到
   （kernel cpu 已停）就算了——boot 會把舊的 `stops` **丟掉**不重放（§6），因為那些 stop 是給上一代 cpu 的。
   `stopped` 之後再來的 syscall／ack 沒人處理，留在 `K/requests/`，下次 boot 的第 1 格會收。
10. **出貨**（同第 4 步）、**寫帳本**、append `kernel.log`、退 0。`kernel.log` 每格至少記：派了誰去哪顆（行程名、cpu、request 檔名）、
    收到的每則回音（行程名、cpu、`result` 或 `error` 整段）、退件時的門檻——回音 ack 掉就沒了，這是事後查「為什麼退件」唯一的地方；
    子程式自己的錯誤在工作 inst 的 `stderr` 檔。
    （09-24 補）沒有任何事件的格（`events` 空）**不寫** `kernel.log`，免得空轉一天幾十萬行。
    kernel.log 在出貨、寫帳本之後才 append，所以**不保證涵蓋崩潰中途已結帳的回音**——它不是完整的持久稽核紀錄。

一格裡 daemon 或磁碟出錯：stderr 一行、退 1、可能只做了一半；帳本＋出貨箱讓下格接得上。
