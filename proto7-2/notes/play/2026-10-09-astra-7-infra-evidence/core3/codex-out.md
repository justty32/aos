core3 完成，受測 HEAD `ad1dfa25`。主要回收驗收通過；R8-29 使用明示的模擬替代真實同號重用。新增 1 項低嚴重度 B，僅記錄未修。

- **通過｜R8-01**：Popen 前暫停／放行各 3 次；先回 `ok:false / unknown` 並留請求，放行後成功收掉同 PID＋starttime 任務。[r801.py](r801.py)；原始結果 `r801-{1..3}.json`。
- **通過｜R8-03 前半**：register、unregister 的 nodes.json 寫入 EIO 均有命中記錄；失敗不改登記，重送及重起後 status 與磁碟一致。[r803.py](r803.py)、[r803.json](r803.json)。
- **通過｜C8-01**：3／3 中斷＋3／3 正常對照；中斷均在忽略 TERM 後 0.001～0.010 秒內，成功回條後的 `reaping` 留存，重起收掉舊任務才清除。[c801.py](c801.py)；`c801-{crash,control}-{1..3}.json`。
- **通過｜C8-02 指定案例**：3／3 中斷＋3／3 對照，每案連續 98～100 次快照、跨度 1.958～2.000 秒，零雙活；新任務起始檢查也確認舊 PID 已不再活著。EIO 案另觀測 199 次／3.996 秒，故障期間 missing、無新回合、舊任務仍活，撤故障才回收並開線。[c802.py](c802.py)；`c802-{crash,control}-{1..3}.json`、[c802-eio.json](c802-eio.json)。
- **通過｜K-04**：10／10；真 tick／runner／aos-exec／tock，FIFO 卡在 Popen 前，runner 死亡後，在後代快照完成、實際 TERM 前放行。晚生子程序確實位於快照外的新群組，仍被補掃收掉，下一代僅剩 run 2。[k04.py](k04.py)；`k04-{01..10}.json`。TERM 前使用純排程閘門，沒有偽造程序或回收結果；停用補掃的記憶體負對照確實測出 run 1＋2 雙活：[k04-negative-control.json](k04-negative-control.json)。
- **部分｜R8-29**：8 次真 setsid 配號未取得原 pgid；改用「記憶體中的舊 pgid 指向真外人群組」模擬重用，外人未被送訊號、同 node 對照確實被收；另完成 items 指定的 `_table/environ_of` mock 驗證。未完成真實同號 pgid 重用。[r829.py](r829.py)、[r829.json](r829.json)。
- **通過｜作者測試對照**：各單跑一次，`test_ctl.py` 25／25、`test_daemon.py` 51／51；不列入獨立驗收。[author.py](author.py)、[author-ctl.json](author-ctl.json)、[author-daemon.json](author-daemon.json)。
- **通過｜指定自由邊角**：nodes.json 截斷及 reaping 錯型別拒絕啟動且不覆寫（X）；重複 unregister／re-register 撞 reaping、daemon 連殺兩次、stop --kill 帶未登記的 reaping（含 EIO）均安全恢復。[edges.py](edges.py)；`edge-*.json`。
- **不通過｜新增延伸案例 NEW-core3-1（B／低）**：回收 EIO 持續時重起 daemon，待回收 node 顯示 idle，未保留 missing。初次發現後另確認 3／3，各 40／40 樣本均為 idle。契約：`proto7-2/spec.md:95、97`、契約卡 §2.1。最小重現：任務 ready → 注入該 PID 的 stat EIO → 替換 node → 確認 missing／reaping → SIGKILL／重起。影響限於狀態誤報；實測仍阻擋新回合，撤故障後正常回收，沒有雙活。建議：由已登記且仍有 reaping 義務的狀態恢復 missing，清乾淨才解除。這不是「daemon 停機期間才替換 node」的已知限制。[new_core3_1.py](new_core3_1.py)（重跑預期 exit 1）、[findings.json](findings.json)；`new-core3-1-confirm-{1..3}.json`。

所有入口探針均只用 Python 標準庫，docstring 附重跑指令，直接執行會自動套指定 systemd scope。共 42 份案例結果（含作者對照、負對照及同一新發現的重驗），索引見 [results-index.json](results-index.json)；每案同名 tar.gz 保存快照，單檔均小於 300 KB。

收尾：42 個自建暫存根已清除，未見本線殘留程序，tracked diff 為空；未 commit／push／呼叫 LLM。[cleanup.json](cleanup.json)、[ps-before.txt](ps-before.txt)、[ps-final.txt](ps-final.txt)。除真實 pgid 同號重用改採模擬外，指定項目無未做。