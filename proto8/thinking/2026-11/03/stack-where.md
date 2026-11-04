# 2026-11-03 stack 不放工作區：拿掉 `.stack` 捷徑、`aos-daemon-ctl where --stack`、`aos-exec --stack`

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜同批：[eca 18](../../2026-10/30/eca/18-11-03-單隻-add-rm.md)（aos-eca 單隻、add XXX、rm）｜接著的：[11-03 procs](procs/README.md)（每項自己的 `stack`、`where` 改讀列上的 `stack`，在本批之後）｜被改的：[10-30 eca 衝突 3](../../2026-10/30/eca/08-衝突.md)（工作區 `.stack` 捷徑）、[N-54 10-30 夜補](../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-58](../../../docs/NORMS/10-基礎設施-定義與工作區.md)｜程式：[aos-daemon-ctl](../../../bin/README.md)、[aos-exec](../../../impls/aos-exec/README.md)、aos-say、aos-eca

本檔只記使用者原文、決定、頂層照原則定的細節（可翻案）（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

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
3. **aos-say／aos-listen 這次只加一行提示**：aos-say 說「目前沒有程式在跑」時，多一句「掛在 daemon 上的用 `--stack $(aos-daemon-ctl where --stack 名字)`」；其他不動，使用者之後重做。（11-04 已改：aos-say／aos-listen 併進 `aos-agent say`／`listen`，對象用 `--target 名字`，見 [11-04 aos-agent](../04/aos-agent/README.md)）
4. **`aos-exec --stack S`**：順序 `--stack` ＞ `$AOS_STACK` ＞ `$AOS_WS/.stack/`（預設照舊放工作區）；相對路徑從呼叫者的 cwd 算、絕對也行、結尾 `/` 可有可無；不在就建；`--stack -`＝沿用外面的值（跟 `--ws -` 對稱）；跟 `--ws` 一樣在讀 `.env` 之前定。

## 頂層代定（11-03，可翻案）

### where

1. **代號**：表上沒有＝`ProcMissing`。daemon 的 state 窗不在＝`StateMissing`、讀不懂＝`StateBad`，跟 `ls` 同一套。
2. **只認 `--stack`**：`where` 沒給 `--stack`、多給位置參數＝`ArgumentsBad`；別的旗標＝`FlagUnknown`。
3. **印什麼**：一行絕對路徑、結尾不帶 `/`（方便接 `$(…)`）。相對的 daemon stack 照樣印絕對路徑。
4. **表上的就算**；子項做完下表、小格資料夾還在也是 `ProcMissing`（不看資料夾在不在）。
5. **daemon 沒在跑**：照 `ls`，stderr 一句「注意 daemon 沒在跑」、照表印、退 0。
6. **路徑只在一處拼**：`cell_of(D, 名字)`。

### 捷徑拿掉

7. **工作區原本有什麼都不動、不說話**；留在工作區的舊 `.stack` 捷徑不替人清，要清自己 `rm <WS>/.stack`。
8. **aos-eca**：stop 不再補回捷徑、rm 不再拆捷徑。〔11-03 procs 實作：aos-eca stop 改走 `aos-daemon-ctl stop`，列留在表上（`stopped`），`where --stack` 找得到；小格讀列上的 `stack`（預設 `<D>/procs/<名字>/`），[procs 實作時代定](procs/10-實作時代定-11-03-實作者照原則定的.md#實作時代定11-03實作者照原則定的可翻案)〕（11-04 已改：aos-eca 併進 `aos-agent`；`AOS_DAEMON_STACK` 改名 `AOS_DAEMON`，使用者 11-04 晚「AOS_DAEMON_STACK實在太醜，還是直接簡化成AOS_DAEMON就好了」，見 [11-04 aos-agent 找 agent](../04/aos-agent/02-找-agent.md)）
9. **aos-eca add／start 等它上表才回**：掛上之後等到 daemon 表上有它（或小格的 `state.json` 在這之後動過＝起來又馬上結束）才回，最多等 30 秒（`Timeout`）。

### aos-exec --stack

10. **跟 `.env` 的關係**：跟 `--ws` 一樣每讀完一份 `.env` 就把旗標的值蓋回 `AOS_STACK`，給了 `--stack`，`.env` 的 `AOS_STACK`（加 `--dotenv-override` 也一樣）改不了這一跳；沒給旗標照舊。
11. **空值**：`--stack=`（空）跟 `-` 一樣當沒給。
12. **轉向**：字串轉向的下一跳不帶 `--stack`（同 `--ws`），但這一跳已經 export 的絕對 `AOS_STACK` 還在環境裡，下一跳就沿用它。
13. **建不了**：沿用 `MkdirFailed`「建不了 AOS_STACK：路徑」。
