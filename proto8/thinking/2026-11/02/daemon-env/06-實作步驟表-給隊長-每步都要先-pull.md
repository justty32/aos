← [入口](README.md)｜涵蓋：實作步驟表（給隊長；每步都要先 pull）；工人提的三點（11-02，使用者）；aos-daemon-ctl 的定位（11-02，使用者）｜上一份 [05-方案-A-B-C-怎麼選-fable-的](05-方案-A-B-C-怎麼選-fable-的.md)

## 實作步驟表（給隊長；每步都要先 pull）

做完了：aos-daemon-ctl、aos-eca-hub 改讀新變數與旗標，各 README、N-63／N-28 與總表、code map 同步；daemon 起子項時把變數設給子項（方向題 2）。方案 C 的示範與權限腳本沒做（不切）。改名 `AOS_DAEMON` 時要同步的範圍見 [11-04 aos-agent](../../04/aos-agent/README.md)。

## 工人提的三點（11-02，使用者）

小格改 `loops/<名>/` 時（[11-02 stack-tools § 實作結論](../stack-tools/05-要使用者看的衝突與方向題.md#實作結論11-02隊長代定可翻案)）工人提的三點；使用者原文在[決定](01-使用者原文-11-02-逐字.md#決定11-02使用者)（「3.a.那就是後續使用者要自己小心。b.自己小心。c.不用測試。」）。

- **(a) `loops` 成了 daemon stack 的保留名**（子項小格在 `.stack/loops/<名>/`，窗或信箱路徑取名 `loops` 會撞、程式不檢查）：使用者自己小心，不加檢查。
- **(b) 路徑 `./x/../s.json` 在 x 不存在時 `WriteFailed`**（沒先化簡路徑）：使用者自己小心，不改。
- **(c) 子項與信箱同名缺正向測試**：不補測試。

## aos-daemon-ctl 的定位（11-02，使用者）

使用者原文（逐字）：

> 對的，aos-daemon-ctl目前主要是對daemon底下的procs進行操作，對daemon本身操作這塊目前還是繼承於loop那樣，用ctl/state.json，往後可以給aos-daemon-ctl添加一些相關指令，但那是以後的事情

- aos-daemon-ctl 現在管 daemon **底下的子項**（add／rm／ls）。
- 對 daemon **本身**的操作（停、暫停、節奏）照 loop 的做法，寫它的 ctl 窗、讀它的 state 窗。
- 給 aos-daemon-ctl 加管 daemon 本身的指令：以後再說。
