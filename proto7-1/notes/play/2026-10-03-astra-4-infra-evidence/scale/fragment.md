# 規模探針片段

## 方法

從 README/spec 進入，读核心 S- 與 problems-core；無 kernel/agent/LLM。`scale_probe.py` 每node 3個 each `/bin/sleep 0.01`，interval=100ms。10/50/100/200各目標15s依序單獨測量；200因採樣器自己遲到而實際18.959s。10另重跑，主表採後者（前次可能與其他組最後的短探針重疊）；另做200空tasks兩次。16 logical CPUs，Linux6.18.49、Python3.14.7，無CPU隔離，團隊測試已停但外部宿主負載不能排除。全部action rc0、daemon正常退出。

wrapper包原run_prog，以monotonic量完整tick/tock程序wall，含啟動/import/工作/排程。主間隔為tick完成→下次tick完成（S-08），另有start→start。proc/RSS/fd每約250ms採样，峰值下界；proc匹配root+後代，排除zombie。daemonCPU只自身；全組CPU以harness RUSAGE_CHILDREN累積，含daemon/tick/tock/runner/sleep與停機；除以採樣+停機+離線分析wall，僅是粗略等效核，不是精確利用率。harness設subreaper回收orphan，未改產品。

主測包含冷啟動和逐漸累積歷史，非純穩態。普通檔數於停機後盤點、扣除3個probe檔（wrapper/timings/stderr）。每raw分片<180KB。舊stop_wall_s已全更名shutdown_and_analysis_wall_s，含離線整理，**不能當daemon停機耗時**；只有最後空tasks組有獨立shutdown_wait_s=0.368。

各組起始Unix近似：50=1791010289.807、100=1791010306.020、200=1791010323.825（第一採樣點monotonic換算，含數十ms偏移）；10重跑精確1791010367.982。證據在summary-*.json、analysis.json、samples-*.json、timings-*.jsonl；`environment.json`含CPU/limits。

## 數字

|node|視窗s|完成tick/node min/中位/max|daemonCPU單核%|全組粗略等效核|RSS峰KiB|daemonFD峰|活proc採样峰|普通檔數|任務目錄|
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
|10重跑|15.085|122/123.5/124|34.03|9.68|21240|25|17|18650|3720|
|50|15.032|31/33/36|21.97|14.23|26992|107|92|26125|5073|
|100|15.832|14/18/21|18.78|14.00|32388|208|115|28491|5454|
|200|18.959|5/11/18|13.84|13.54|42552|406|205|35457|6660|

下表ms，p50/p95：

|node|tick wall|tock wall|tick end→end|tick start→start|status更新gap|rescan回條RTT|
|---:|---|---|---|---|---|---|
|10重跑|42.590/58.050|34.487/51.432|121.261/144.510|120.948/144.897|37.021/61.992|22.357/41.883|
|50|212.183/321.981|202.240/322.125|444.830/605.027|442.144/598.277|103.069/266.130|82.939/164.667|
|100|341.948/855.777|331.347/881.738|788.248/1512.145|785.054/1496.099|207.319/428.537|181.589/551.591|
|200|458.507/2301.136|455.203/2438.912|1226.618/3707.099|1192.963/3650.120|401.021/702.302|214.400/3669.784|

ctl每約2秒一筆，N=7/7/6/5，p95其實最大值，不是SLA。200首份status需4.671s、首tick完成最晚7.181s，status gap最大733ms（gap不包含首次等待）。200回合數5~18顯示起跑/排程公平性差異。RLIMIT FD524288、proc246988、cgroup pids74096，未碰硬限額。daemon RSS低不表示整系統輕，其他Python程序未含其中。先失去的是節奏和控制反應，S-08容許不準時，**不把遲到本身報bug**。

10第一次end間隔p50=101.951、tick/tock31.087/27.022，重跑121.261、42.590/34.487。首末5s資料在analysis.json：10重跑tick p50 38.803→45.634、tock30.302→37.574；50較穩、200擾動大。未固定歷史做消融，不能全歸因歷史掃描（P-12已知）。

## 空任務對照與新證據

|200空tasks|秒數|視窗內有tick node|tick/tock p50ms|end間隔p50ms|首status|ctl最大|粗略等效核|
|---|---:|---:|---|---:|---|---|---:|
|第1次|10.117|121/200|46.316/46.971|377.420|10.225s，送stop後|視窗內無回條|11.23|
|第2次|15.382|200/200|451.826/464.593|1322.091|4.354s|2671ms|6.91|

空任務也延遲且兩次差異很大。each200比第二次空任務耗更多CPU，但空任務回合速度並未改善。只能支持程序啟動/工作、掃描、排程、協調的**合計成本**已失去可預期性；不能把CPU飽和或Python啟動定成唯一瓶頸。

### 新證據：大量node發現阻塞status/ctl〔技術選型〕

重現 `python3 scale_probe.py --repo <workspace> --seconds 10 --counts 200 --tasks 0 --tag=-empty`。200個100ms空任務node，第1次10.117s只有121條有tick、無status/ctl回條，停機後才首status；重跑首status4.354s、ctl2.671s。主測有任務也首status4.671s、ctl3.670s。見timings-200-empty-*.jsonl、timings-200-empty-confirm-*.jsonl、後者daemon log分片。

Daemon.run先handle_ctl再同步scan，scan逐一start timeline並記node+，全部返回才write_status。大量冷啟動會阻塞下一次ctl與首status；沒量鎖等待，不能把原因限定某把mutex。這不是P-12舊歷史全掃：空tasks零歷史也會出現。S-01/S-05/S-06/S-18，延遲上限與排程屬核心未定技術選型。

## 需求（供主報告）

|需求|優先|證據|核心對應|proto7-1|
|---|---|---|---|---|
|控制/狀態在冷啟動與超載仍有界進度，node發現分批，不阻塞回條|必要|200空tasks10秒無status/receipt，each200ctl3.67s|S-01/05/06/18，界限未定|未做，同主迴圈串行|
|檔案公開容量、待起node、積壓、requested/actual interval、分阶段/全組資源成本|必要|所有rc0但200回合間隔p50設定12.3倍，daemonCPU低仍耗大量全組CPU|S-01/06，欄位未定|無過載/積壓/延遲摘要|
|有界並行啟動與公平排程；明定延期/拒絕/節流且可讀回條，保留程序接口|應該|200同窗5~18回合，空tasks變異大|S-04/05/06，算法未定|每node thread直接spawn，無全域限額|
|活索引與可讀歷史歸檔、儲存/程序預算|應該|15~19s即18650~35457檔，P-12新規模證據|S-01/03/06，保存政策未定|rounds已JSONL，任務全保留/全掃|
|分開tick/tock動作開始與完成時間，勿把啟動當回合內時間|應該|200tick p95=2.301s，start/end間隔不同|S-08明定tick結束才開始回合|round.json tick_at在tick一開始寫，缺完整動作時間|
