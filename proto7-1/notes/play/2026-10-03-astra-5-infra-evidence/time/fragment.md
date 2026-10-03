# time 回歸（astra-5）

執行 `python proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/time/probe.py`。從 astra-4 原檔複製，只改 `/tmp` prefix 及 `run_prog` wrapper 接受／轉交新版 `*args, **kwargs`。七案全跑完；未動產品。`extra.py` 是直接啟 daemon 的補驗，不使用 wrapper。所有時間是短窗、非隔離主機基準。

| astra-4 | 判定 | 本輪證據 |
|---|---|---|
| I-06 | **部分修好**：不再永久停線，錯型別有 last_error、修檔後會恢復；但「所有壞 interval 用預設」不成立 | `invalid.json`：null/text/NaN/Infinity 開 r1、effective=1000；10**309 仍 r0/error、interval_ms=null、OverflowError。`extra.json` overflow 觀察1.25秒仍 r0，log 每0.5秒 error；修100ms+rescan後477ms到r3。不是永久死，卻不是預設值繼續跑 |
| I-08 | **已修最小範圍**：effective interval 看得到；要催用 wake | `change.json` 1000→100ms 後第一個 tick 起點差999.94ms，之後100ms；`longchange.json` 一天→10ms+rescan觀察300ms仍r1，status清楚報86400000。`extra.json` wake：一天→100ms+單次wake，151.70ms到r3；不再要求 rescan 有 wake 語意 |
| I-10 牆鐘 | **既知限制仍在**，排程對照通過 | `clock.json` +1h→−1h→0，11 ticks 起點間隔中位100.058ms、範圍99.961–100.124ms；牆鐘標記倒退，仍無供讀者排序的單調事件序號。N-07 調度已做、觀测耗時未做 |

## 新問題：超大合法 JSON 整數仍不走 interval 預設〔bug〕

重現 `extra.py`：`timeline.json={"interval_ms":10**309}`。1.25秒內保持r0/error、interval_ms=null，每0.5秒重試；改成100後自行恢復。`aos7_daemon_timeline.py:91` 先 `math.isfinite(ms)`，會先做整數轉浮點而 OverflowError，走不到後面的上限比較及 DEFAULT_INTERVAL_MS。S-01、S-05、S-06；N-21「已做」改「部分」，或修數值驗證後再標已做。最小對策先比上下限、再做有限值檢查／捕捉 OverflowError。无需改核心語意或重問使用者。

## 限制與清理

原 invalid 案修復後只等300ms，小於1000ms預設回合，不能把仍r1誤判成不恢復；這正是另外做補驗的原因。原 stall wrapper 在注入的第一個 tick 直接 Popen，未套新版 generation/timeout 參數，因此該案只能驗 SIGSTOP 引起的調度遲到，不能拿來證明 N-18/N-54。牆鐘案 monkeypatch Python datetime，沒有改宿主時鐘。`cleanup.json` 驗證本組和 nested 的 `/tmp/astra5-time-*`／`astra5-nested-*` 空間、活程序皆0，單檔均<200000 bytes。
