# astra-6：subd 驗收

HEAD `04c5d28866cdeacbb71e8bde43000f0e14a0c149`。A6-01 修補通過；正式 G3 壓力 10／10，全數與全套測試重疊。新增邊界沒有 B／G 候選。牆鐘倒退確實會讓控制檔 stop 不符 `allowed_stop`，重開後收掉原任務；此為 loop6 已自報的時間假設界線，以下保留具體現象，沒有當成已受保護。

| 驗收 | 結果 | 證據 |
|---|---|---|
| A6-01：astra-5 原流程，正常 stop | 3／3；刪 stopped.json 後同 PID／starttime 接回、run=1 | [confirm-stop.json](confirm-stop.json) |
| A6-01：astra-5 原流程，兩個原窗口 | stopped-tmp、life-tmp 各 3／3；真 SIGKILL 命中，任務不收；life-tmp 先刪標記者會補標記、多擋一次 | [confirm-stop.log](confirm-stop.log) |
| A6-01：新 stop-seen 窗口＋藍圖流程 | 原流程 stop-seen 3／3；藍圖正常與三窗口各 3／3；總計 24／24，18 次注入全部命中正確 hook＋rc=-9 | [audit.json](audit.json) |
| G3 正式壓力 | 10／10；每案前代都留下任務，替代 daemon 首次可見時舊任務已全不在；2.242～2.279 秒，總案耗時 27.342 秒；起訖皆有全套程序 | [stress-parallel.json](stress-parallel.json)、[stress.log](stress.log) |
| 直接 TERM 子 daemon | allow-stop=false／true 各 1 案；核心收任務、status stopped=true；無 stop 回條、無 stopped.json；life 保持 running，重開成功 | [new-edges.json](new-edges.json) `term-allow-*` |
| 上代 stop 回條＋本代直接 TERM | 1／1；舊回條 at<本代 since，不會誤擋重開 | 同上 `term-with-old-receipt` |
| life 缺 since | 合成模型 1／1；判不出本代 stop，重開回收。**M，非實際舊版遷移失敗** | 同上 `synthetic-life-no-since`、[life-history.json](life-history.json) |
| 牆鐘倒退 3600 秒 | 1／1 重現已知界線：stop 回條 at<since、不寫 stopped.json、重開收原任務 | 同上 `clock-rollback` |
| status／ctl-done 回條 EIO | 各 1／1；rc=1、不收不起、life=running；解除 EIO 後 rc=1 補成 stopped，原 PID／starttime 保留 | 同上 `eio-status`／`eio-receipt` |
| 清場 | 正式＋預跑全部 root 已移除、存活程序清單皆空；只按自己 PID 收程序 | [audit.json](audit.json)、[ps-final.txt](ps-final.txt)；各案 cleanup 含 PID／ps |

A6-01 依據 [subd 契約卡與「重開前回收」第 2 步](../../../../modules/subd/README.md)：合法 stop 的提交中斷，起點與收尾共用 status＋本代回條判定，補完停止記錄而不回收。探針由 astra-5 的 [probe_subd.py](../../2026-10-04-astra-5-infra-evidence/subd/probe_subd.py) 共用程序框架，沿用 loop6 的兩種重開流程；本次重新跑 HEAD，沒有直接引用舊結果。逐案比較 `/proc/PID/stat` starttime 及槽 birth.run，排除 PID 重用、舊 ready.json 假陽性。

G3 保留第一次預跑 [preliminary/stress-parallel.json](preliminary/stress-parallel.json)：10／10，其中 8 案與全套重疊、前 2 案早於全套起跑；不混入正式統計。正式再跑 10 案全部重疊，且本報告採比舊探針「最多兩回合內收完」更強的實際觀察：首次看見新 daemon 即全部收完。

直接 TERM 的語意符合 [核心 daemon 契約](../../../../notes/component-contracts.md)及 subd README：SIGTERM 是核心 stop＋kill，不看守門檔；subd 要有本代控制檔 stop 成功回條才算被允許外部 stop。因此即使 `--allow-stop`，直接 TERM 也不留下永久擋重開標記。這是 loop6 自報的刻意語意變化。

`since` 查歷史：初版 `8c6f08b8` 尚無 subd-life；A5 `8c2145c4` 首度寫 running life 時已含 since。現有 Git 歷史未找到「包自己寫出 running、但無 since」的版本。本輪以測試根中刪除此欄的合成模型觀察防守分支，違反「subd-life.json 只有 subd 寫」，依原則 9／10 記 M，不列 bug，也不宣稱驗證了真實舊版遷移。

倒鐘試驗只對測試程序的 `datetime.now()` 加 offset，未改主機時鐘或內部生命週期檔。實際控制檔 stop 成功、status stopped=true、原任務仍活；但回條時間比 running.since 早一小時，wrapper 留 running、不留 stopped.json，重開按「非 allowed_stop」回收原任務。subd README「規則」明定 `result.at >= since`，沒有承諾倒鐘容錯；[loop6 自報](../../2026-10-04-loop6-subd-evidence/summary.md)明說「時間比較用 now() 牆鐘字串（原則 9，不另防）」。所以分類 **X：環境時鐘假設失效／已知界線**，本輪不新增 B／G。README 契約卡目前沒有明寫「正常牆鐘」前置；建議把上述倒鐘後果寫進界線，讓使用者看得出合法控制檔 stop 也可能不符這個時間判定。這是揭露既有界線，不以「理論上能更穩」要求新增保護。

可重跑：從 repo 根設定 `PYTHONDONTWRITEBYTECODE=1` 執行 [confirm_stop.py](confirm_stop.py)、[probe_edges.py](probe_edges.py)；[run_stress_parallel.py](run_stress_parallel.py) 須與全套重疊以重現壓力條件。共用 [probe_subd.py](probe_subd.py) 保留原探針輔助函式，正式 A6-01 入口是 confirm_stop.py。新增邊界原始空間依案壓成 `*-snapshot.tar.gz`，清理前保存；原始觀察在 JSON／log。

最該修的三條：沒有新的 B／G；僅建議 subd README 明列倒鐘的既有界線。
