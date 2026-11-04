# nested 回歸與 subroot 攻擊（astra-5）

`reproduce.py` 從 astra-4 原檔複製，只把 `/tmp/astra4-` 改為 `/tmp/astra5-`，五案全跑完。原三層測試事先建子 `.aosd/`，因此不代表 subroot 新功能已通過；另用 `subroot.py` 做三次沒有預建標記的原生冷啟動。

| astra-4 | 判定 | 本輪證據 |
|---|---|---|
| I-09 | **未修／已知文件缺口** | `results.json` cycle-native：父→子可掛，子→父symlink／../仍被拒，只有子停住；cycle-reexport：預配父.aosd實體到子可達處，兩邊都pause，外部resume後都前進。這仍是S-07、S-21、S-23的合法空間邊界，不建議撤檢查；N-45「部分」準確 |
| I-10 三層TERM | **正常對照通過；頑固任務限制未修** | `results.json` term：A退出163.52ms，1.4秒後0活程序；term-stubborn：A退出1114.53ms，1.4秒後仍6活程序，與前輪相同規模。N-27仍沒做；S-01、S-03、S-06、S-21 |
| I-10 三層SIGKILL | **既知限制未修** | `results.json` kill：A退出1.07ms，1.4秒後仍6活程序；僅觀察窗，不宣稱永久存活 |
| I-11 | 本組不判 | 需scale重跑，交主線 |

## 新問題：宣告 subroot 仍擋不住第一輪誤接管〔bug〕

**重現：** 執行 `subroot.py`。父 root 的 `n` 任務宣告 `subroot:"n/child"`、mount 該路徑，tick 起子 daemon；子樹先備好 `n/child/n/.aos/timeline.json`／tasks.json，故意不預建 `.aosd`（正是欄位承諾替呼叫者處理的步驟）。三次都等1.1秒採樣。

**看到：** 三次父 daemon log 都先 `node+ n`、`node+ n/child/n`，父 tick 在子node的r1起 `leaf-r1`，birth.node都為父視角`n/child/n`；父下一掃才 `node- n/child/n`，子 daemon接著自r2管理該線。最後child-r1的birth確實有subroot欄位，不能歸因忘記宣告。`subroot.json`保存三次父子log／status／birth／程序。

**原因：** daemon `scan()` 先一次收完整 `now_ids` 再開各 Timeline；task `start_task()` 才建子root標記，來不及改已取好的掃描清單。action.lock只序列化兩邊动作，不判「這條線應歸哪個daemon」，兩root世代也碰巧同為1。證據僅主張父先誤管／寫出生資料，不主張本案有回合倒退。

**牽涉：** S-06、S-15、S-21、N-47。N-47「已做」應改「部分／冷啟動不成立」。最小對策在開任何新時間線前先登記宣告的subroot；或文件要求先建`.aosd`並撤掉欄位能避免冷啟動搶管的承諾。這是已選機制沒落實，不需使用者再次決定路一語意。N-47維持必要級。

## 清理與限制

`reproduce.py` 的 cleanup 會额外殺實驗程序，不能當成產品停機通過；測試控制器subreaper只為reap。本輪第一次subroot補驗曾遇清理單次scan後子daemon剛好又起新leaf，留下runner及leaf；已限定自己的root/env補SIGKILL並刪空間，未碰其他測試。最終版本先SIGSTOP本次所有程序，再kill/reap，三次cleanup全部0活程序、root_removed=true；全組最後檢查見`../time/cleanup.json`。巢狀測試數字是產品操作後1.4秒的觀察，沒有將harness清理計入。

## 補測：node 檢查之後消失，tick／tock 仍重建舊路徑〔bug〕

`gone_mid_action.py` 直接跑產品 CLI，`sitecustomize` 在 tick 第一次 `write_json(round.json)`、tock `append_jsonl(rounds.jsonl)` 前 SIGSTOP；此時動作已通過 timeline 存在檢查且持有 action.lock。控制器刪 node 或 rename 到 `moved/` 後放行。沒有任務、没有daemon、沒有LLM；共 tick/delete、tick/rename、tock/delete、tock/rename 四案。

四案全部 rc=0，舊路徑在放行前不存在、之後重生：tick 建回 `.aos/round.json`；tock 建回 `.aos/round.json` 和 `.aos/rounds.jsonl`。rename 案新位置仍保有原來 r1/open，舊位置卻有新回合／摘要，結果分岔。見 `gone_mid_action.json` 的舊／新位置完整檔案快照。

原因是單次入口檢查存在 TOCTOU，action.lock 並不阻止外界刪／搬目錄；共用 `write_json`／`append_jsonl` 會自動 `makedirs`。**N-24「已做」必須改「部分」**，S-06、S-13、S-14。工程修復須讓 action 對已開啟node身份寫入、明確處理目錄已移走／unlink，而非只在入口看路徑存在；僅多加一次 exists 仍有窗口。不改使用者已答的 Q4 kill 政策，這是落實「不把node建回來」。所有四個CLI已wait、實驗root已刪，cleanup在每案列出。
