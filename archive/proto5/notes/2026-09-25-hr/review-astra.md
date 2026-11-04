**必修**

以下路徑皆相對 `proto5/`。

- `lib/aos_team_hr.py:403`：試用只換 `project`，原名冊的額外可寫 mounts 原樣保留；若絕對路徑指原專案，試用仍能改到原檔。`:488` 也允許 `--out` 放進原團隊／原專案。修：解析實際路徑，拒絕輸出重疊，並重映射或拒絕指向原資料的可寫掛載。
- `lib/aos_team_hr.py:368`：`hr set` 未拿 info 共用鎖便整份覆寫，會與 `tools add` 等修改互蓋；而且先改模型才 stop，stop 後立即 start 仍可能遇到舊 tick 尚未結束。修：停登記、等舊 tick 結束，再持 `.info.lock` 重讀修改、最後啟動。一般 tick 主要寫 `state.json`，不能直接說它必然覆寫 info。
- `lib/aos_team_hr.py:431`：評分退非零只補 `error`，仍保留分數與 `mech_ok=true`，因此可能調薪；`:434` 也接受超出 0～100、NaN、Infinity，NaN 比較甚至可能落入「通過」。修：非零退出或非有限／越界分數一律 `score=null、mech_ok=false`。
- `lib/aos_team.py:134`：`AOS_HR_TRIAL` 直接讓 HR 家變成 None，連 start 與 `aos_team_spawn.py:150` 的 cpu 擋點都跳過，違反「試用仍管 cpu」。修：只跳人頭與登記，保留 cpu 檢查；開跑前檢查一次不能涵蓋後續 spawn。
- `lib/aos_team_hr.py:355`：人頭檢查與寫名冊沒有共用公司鎖，兩隊同時轉正可各自通過、合計超額。修：跨隊以同一把 HR 鎖包住數人頭及提交，並統一鎖順序。
- `lib/aos_team.py:35`：`employment` 沒傳入建家流程，`aos_agent_init.py:78` 仍只照模板裝 notes／mem；spawn 的 temp worker 仍有記憶工具，與規格「不裝 notes、不 recall」矛盾。修：讓建家／工具安裝依 employment 處理，或明確把此限制列為未實作。
- `lib/aos_team_hr.py:508`：啟動後沒有 `finally` 收尾；ask／輪詢子程序逾時等例外會直接離開，試用團隊可能繼續跑。修：啟動後用 `try/finally` 保證嘗試 stop，另留下失敗紀錄。

**建議**

- `verdict()` 的「同任務集」只比 `name`；同名改題目、評分指令後會混用舊基準。建議記任務集及評分版本／摘要。
- 補測非零評分、NaN、failed／timeout 不調薪、較貴不覆蓋、最近有效基準、試用 spawn cpu 擋點與並行轉正；目前測試未覆蓋這些。
- 規格說清楚 `cpu_max` 不含 llm cpu、start 也會檢查正式人頭；「同級可替換」不代表實際價格更便宜。

**不用改但值得記下**

- `check_regular()` 以新名冊人數覆蓋自己這隊，正常登記路徑不會重算。
- 正常 trial 寫紀錄時以 `mech_ok AND status==done` 收斂，未完成單不會成為有效基準或通過候選；`verdict()` 本身則信任此條件。
- 基準取同位子、同任務集、強、機械過且有數字分數的最後一筆紀錄；`min_pass` 僅空缺、較便宜或同級時更新，不會換成較貴等級。
- `register_team` 寫 HR 家的 `teams.json`，通常不算改原團隊；但 HR 家若設在原團隊內，字面保證便不成立。
- 無兩個 HR／kernel 環境變數時不擋；只設 kernel 就會啟用預設額度，未建 HR 目錄不代表停用。
- 非 JSON、逾時皆記 null／false 與 error；bool 分數已排除。
- 全程未改檔、未叫模型。指定測試 33 條中 4 條通過，29 條因唯讀環境無可寫暫存目錄而未能執行，不能宣稱全綠。