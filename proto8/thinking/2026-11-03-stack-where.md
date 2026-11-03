# 2026-11-03 stack 不放工作區：拿掉 `.stack` 捷徑、`aos-daemon-ctl where --stack`、`aos-exec --stack`

← [thinking README](README.md)｜月份表 [2026-11](months/2026-11.md)｜同批：[eca 18](2026-10-30-eca/18-11-03-單隻-add-rm.md)（aos-eca 單隻、add XXX、rm）｜接著的：[11-03 procs](2026-11-03-procs.md)（每項自己的 `stack`、`where` 改讀列上的 `stack`，在本批之後）｜被改的：[10-30 eca 衝突 3](2026-10-30-eca/08-衝突.md)（工作區 `.stack` 捷徑）、[N-54 10-30 夜補](../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-58](../docs/NORMS/10-基礎設施-定義與工作區.md)｜程式：[aos-daemon-ctl](../bin/README.md)、[aos-exec](../impls/aos-exec/README.md)、[aos-say](../extras/human/README.md)、[aos-eca](../extras/eca/README.md)

本檔只記使用者原文、決定、頂層照原則定的細節（可翻案）（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-03）

使用者的想法（整理）：daemon 是硬體，proc 的 stack 像 CPU 的暫存器，歸 daemon 管；`AOS_WS` 只是一個位址。接著（逐字）：

> 那其實.stack根本不需要放到ws那邊

頂層照這個想法攤了四題（工作區不再建捷徑、怎麼找到一個子項的 stack、say／listen 怎麼辦、aos-exec 要不要能直接指 stack）的建議，使用者（逐字）：

> 那四題照建議，只是say/listen這塊之後還要再改。

`where` 找不找得到已經拿下名單的（逐字，同日 procs 那段）：

> 一個proc在daemon中的狀態，包括運行中、暫停中，除此之外就是不存在於daemon了

> 拿下名單後，對於daemon來說他就不存在了，自然找不到

`aos-exec --stack` 的預設（逐字）：

> 預設還是要放工作區。要自動建。要沿用外面的。

## 決定（11-03，使用者）

1. **工作區不放子項的 stack**：`aos-daemon-ctl add --ws` 不再在 `<WS>/.stack` 建指到小格的 symlink，`rm` 也不再拆；aos-eca 的 stop／rm 跟著不碰捷徑。
2. **`aos-daemon-ctl where --stack 名字`**：印那個子項的 stack 路徑；只認目前在 daemon 表上的，表上沒有＝錯。今天的表是 `loops`／`execs`，小格在 `<D>/loops/<名字>/`（procs 改名在下一批）。〔11-03 procs 實作：表是一張 `procs`、印列上的 `stack`（含 `stopped` 的列）〕
3. **aos-say／aos-listen 這次只加一行提示**：aos-say 說「目前沒有程式在跑」時，多一句「掛在 daemon 上的用 `--stack $(aos-daemon-ctl where --stack 名字)`」；其他不動，使用者之後重做。
4. **`aos-exec --stack S`**：順序 `--stack` ＞ `$AOS_STACK` ＞ `$AOS_WS/.stack/`（預設照舊放工作區）；相對路徑從呼叫者的 cwd 算、絕對也行、結尾 `/` 可有可無；不在就建；`--stack -`＝沿用外面的值（跟 `--ws -` 對稱）；跟 `--ws` 一樣在讀 `.env` 之前定。

## 頂層代定（11-03，可翻案）

### where

1. **代號**：表上沒有＝`ProcMissing`（「proc」是使用者在 procs 那段用的詞；跟 `DaemonMissing` 同一個造法，C-54）。`loops_state.json` 不在＝`StateMissing`、讀不懂＝`StateBad`，跟 `ls` 同一套。
2. **只認 `--stack`**：`where` 沒給 `--stack`、多給位置參數＝`ArgumentsBad`；別的旗標（例 `--ws`）＝`FlagUnknown`。旗標的值就是名字（`--stack 名字`＝「我要它的 stack」）。
3. **印什麼**：一行絕對路徑、結尾不帶 `/`（方便接 `$(…)`；`aos-say --stack` 收兩種）。相對的 `--daemon-stack` 照樣印絕對路徑。
4. **表上的就算**：`loops`、`execs` 兩張表都認，`running`、`stopping` 都算；子項做完下表、小格資料夾還在也是 `ProcMissing`（不看資料夾在不在）。
5. **daemon 沒在跑**：照 `ls`，stderr 一句「注意 daemon 沒在跑」、照表印、退 0（表是它最後寫的）。
6. **路徑只在一處拼**：`cell_of(D, 名字)`；procs 那批改成讀列上的 `stack` 時只改這裡。

### 捷徑拿掉

7. **工作區原本有什麼都不動、不說話**：以前「工作區已有 .stack…請先搬開」那句注意一起拿掉（已經不建，就沒有撞到的事）；10-30～11-02 留在工作區的舊捷徑不替人清，要清自己 `rm <WS>/.stack`。
8. **aos-eca**：stop 不再補回捷徑、rm 不再拆捷徑。stop 之後那隻不在 daemon 表上，`where` 找不到——要在停著時寄信，直接 `--stack $AOS_DAEMON_STACK/loops/<名字>`（小格路徑）；procs 那批的 stop 會留在表上，到時就能用 `where`。〔11-03 procs 實作：aos-eca stop 改走 `aos-daemon-ctl stop`，列留在表上（`stopped`），`where --stack` 找得到、`aos-say` 投得進；小格改讀列上的 `stack`（預設 `<D>/procs/<名字>/`），[procs 實作時代定](2026-11-03-procs.md#實作時代定11-03實作者照原則定的可翻案)〕
9. **aos-eca add／start 等它上表才回**：信是 daemon 下一圈才套，以前 add 完馬上 cd 進工作區說話靠的是捷徑；現在要 `where`，而 `where` 只認表上的，所以 aos-eca 掛上之後等到 daemon 表上有它（或小格的 `state.json` 在這之後動過＝起來又馬上結束）才回，最多等 30 秒（`Timeout`）。start 印的「queue 裡幾封」改在掛上之前數。
10. **測試與說明**：原本「cd 進工作區就說得到」的測試改成先 `where` 拿 stack、再 `aos-say --stack`／`aos-listen --stack`；README 的例子同。

### aos-exec --stack

11. **跟 `.env` 的關係**：跟 `--ws` 一樣每讀完一份 `.env` 就把旗標的值蓋回 `AOS_STACK`，所以給了 `--stack`，`.env` 的 `AOS_STACK`（加 `--dotenv-override` 也一樣）改不了這一跳；沒給旗標照舊。
12. **空值**：`--stack=`（空）跟 `-` 一樣當沒給（照 `--ws` 現有的寫法，對稱）。
13. **轉向**：字串轉向的下一跳不帶 `--stack`（同 `--ws`），但這一跳已經 export 的絕對 `AOS_STACK` 還在環境裡，下一跳就沿用它，不從下一跳的 cwd 重算。
14. **建不了**：沿用原本的 `MkdirFailed`「建不了 AOS_STACK：路徑」，不另分是旗標給的。
15. **N-58 正文**「旗標有兩個」不改寫，只在條末加 11-03 補註說多了 `--stack`。
