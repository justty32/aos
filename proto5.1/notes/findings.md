# 第 1～2 段實作 findings（2026-09-22）

範圍：[stage1-task.md](stage1-task.md)（#1～#17）與 [stage2-task.md](stage2-task.md)（#18 起）。以下是實作與測試遇到的具體問題、這次採用的決定與仍存在的限制；不是要求使用者現在拍板。程式與規範只改 `proto5.1/`。

## 1. POSIX rename 不會替我們拒絕同名

`aos_llm_cpu.py` 的認領需要 `requests/x.json → running/x.json`。Linux 的 `os.rename()` 若目的檔存在會覆蓋，先 `exists()` 再 rename 也會有兩顆 cpu 同時通過檢查的窗口。因此不能照總結的「rename 撞到就跳過、不用鎖」字面實作。

這次採用 Python 標準庫 `fcntl.flock` 的短鎖 `.queue.lock`，只保護交件、認領、收屍與結果發布；HTTP 呼叫不持鎖，兩顆 cpu 仍可同時問不同請求。所有內建交件者共用同一把鎖，鎖內確認三處同名再 rename。這是對原建議的實作補充，不引入背景 worker 或 pid 登記。

## 2. 既有 571 條測試與新契約有直接衝突

改動前從 repo 根執行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5.1/lib python3 -m unittest discover -s proto5.1/lib/test`：571 條全過。

`test_agent_info.py` 原本對整個 engine dict 做相等比較，新要求「沒寫 cpu 回 None」必然多一格；`test_agent.py` 原本要求引擎失敗後所有檔案 bytes 不變，新要求又必須把 `state.errors` 加一。這次保留原測試案例與其餘斷言，只更新這些被新需求明確改變的期待值；沒有刪測試、用 skip 避開或維持一條不寫 errors 的假相容路。

## 3. continue.json 留著會讓第二次暫停失效

任務要求加字面 `"continue.json"` 等人 touch；但不開 consume 的 exists 門開過一次後檔案仍在，第二輪連敗三次就會立刻通過。`aos_agent.py` 在每次達到三敗門檻時，先把當時已存在的 `continue.json` rename 成 `.done`，再加入等待。保留字面等待格式，也確保每輪都要新的 touch；新 `input.json` 不能解鎖。

## 4. timed_out 必須獨立於退出碼

`aos_exec.run_inst()` 的既有 API 是三元素 tuple，既有呼叫者會解包或直接比較。工具自行 `exit 143`、被外人 TERM，以及真正超時都可能回 143；反過來，父行程回 0、孫行程卡住 stdout 也會觸發 `communicate()` 超時。

這次保留三元素 tuple 相容性，回傳 tuple 子類另帶 `timed_out` 布林屬性，由實際捕獲 `TimeoutExpired` 的位置設定。agent 以旗標判斷逾時，訊息保留已收到的 stdout；`run_target()` 的既有回傳與 CLI 退出碼不變。

## 5. 壞結果要先驗，否則門已被劃掉

既有 `step()` 會先 consume／寫回 waits 再走 think；若此時才發現 `ask-result.json` 是壞 JSON，就違反規範「讀驗錯誤什麼都不寫」。非同步收回因此在門可以打開、且不走 tool_calls 自癒時，先讀驗結果，再提交門的變更。壞結果退 1、留下結果檔與原 waits，修好後可重跑；不把資料格式錯誤冒充引擎失敗，也不加 errors。

## 6. errors 的整數範圍

任務只寫「整數、字面、沒寫 0」。計數器沒有負值的合理意義，`state.json` 的 `errors` 這次限定非負字面整數，拒絕 bool、負數、浮點、字串與指示詞，錯誤代號 `FieldTypeMismatch`。收到引擎成功才歸零；送出非同步請求本身不代表成功。

## 7. root 的 default build cache 是另一個路徑留下的

照 repo 指令從根跑 `cmake --build --preset default && ctest --preset default`，build 退 2，ctest 尚未開始。`build/CMakeCache.txt` 指向 `/mnt/c/code/mine/simple_tools/aos`，目前 repo 則在 `/home/guanyu/projs/aos`；再生成時還找不到 Catch2。

為遵守只改 `proto5.1/`，不刪改舊 cache、不改根 preset。改從 repo 根用同一個 `default` configure preset，僅以 `-B proto5.1/.build` 指定新的產物位置，再在那裡建置與跑整套 ctest。最終結果另記驗證紀錄。

實跑還發現 `ctest --preset default --test-dir proto5.1/.build` 仍被 preset 導回根 build，7 個執行檔找不到；因此改用 `ctest --test-dir proto5.1/.build --output-on-failure`。新的 build 成功，這 8 個相同測試目標全部通過（5.21 秒）。

## 8. rename 不會更新 mtime，排隊時間不能當執行時間

`aos_llm_cpu.tick()` 認領前在短鎖內刷新請求 mtime，再 rename 到 running。否則一份排隊超過 150 秒的預設請求剛被認領，第二顆 cpu 就會把它當死掉的工作。收屍使用嚴格大於 `timeout_ms / 1000 + 30`，不是大於等於；只有 running 算，requests 這階段沒有排隊期限。

## 9. socket timeout 不能保證收屍時原 cpu 已死

`aos_llm_ask.call()` 用 urllib 的 socket timeout，慢慢滴回資料仍可能超過總時間。因此第二顆 cpu 收屍後，第一顆可能稍後才回來。`aos_llm_cpu.py` 在發布前重新拿短鎖，核對 running 的 device/inode 與 done；已被收屍就丟棄遲到回覆，避免把 timeout 又改成成功。收屍不會真的殺死原進程，整次 HTTP 硬上限留到外層。

## 10. 一次 tick 的「一件」與只收屍的退出碼

任務同時要求先掃 running 與只處理一份 requests，未指定一次能收幾具屍體、只收屍退什麼。這次掃完當次看見的所有過期 running，再最多認領一份 requests；有收屍或有問模型就退 0，兩者都沒有才 101。碰到跨資料夾同名檔保留並跳過；碰到壞請求則退 1 留原位，不猜 result 路徑。

## 11. 結果發布與 done 搬移仍不是一筆交易

CPU 順序是結果 `.tmp → result`，再 `running → done`。若崩在兩步中間，收屍看到 result 已在就保留它，避免把成功蓋成 timeout。這是對任務「收屍寫 ok:false」的窄例外。

**仍未解掉的具體情境**：CPU 發布成功 → agent 把結果 rename `.done`、甚至送下一單 → CPU 在搬 done 前崩潰 → 舊 running 到期。此時 result 不在，收屍會回填舊請求的失敗，卻可能被 agent 當下一單的結果。反過來，當時 result 已是下一單的結果，CPU 也無法區分。固定 `ask-result.json` 加上沒有 request id／完成標記，無法可靠對帳；本階段保留三欄請求與兩欄結果協議，明列這個限制，沒有宣稱 exactly-once。

## 12. agent 送出與加 waits 之間的中斷會多送

`aos_agent._submit()` 先發布請求，之後才寫 state.waits；測試注入 `state.json` replace 失敗，確認請求已在 requests 而原 state 還留 think。下次 `time_ns()` 換了名字，同名拒收不能阻止第二份同內容請求。這個窗口照建議保留：先加 waits 反而會造成永遠等不到尚未送出的單。未加 pending／request id，因此不保證去重。

## 13. agent 收回後自癒要封存已接過的 tool_calls 結果

注入 `ask-result.json → .done` 失敗時，記憶已接進 assistant tool_calls，state 還是 think。舊自癒直接轉 act，卻把 result 留著，工具跑完回 think 就再次吃到同一份 tool_calls，工具被重跑。

這次補一個可確定的窄修復：尾巴帶 tool_calls，且正規化後成功 result.message 完全等於尾巴，就在自癒時封存結果並清 errors，再轉 act。測試跑到 act 執行完、再次送新請求，確認不重吃舊結果。壞結果或不同結果不阻擋原有 tool_calls 自癒，保留到後續 think 再驗。

一般文字回話沒有工具尾巴可辨識，**不能只憑訊息相等就去重**（新一輪也可能合法回答相同文字）。history 寫了但 result 未封存仍可能重複接；result 已封存但 state 未寫則可能再送；失敗結果已封存但 errors 未寫則可能漏計一次。這些仍需要請求關聯／交易才能處理。

## 14. 結果讀驗與 CPU 設定的時機

門仍有未到條目就 101，不提前讀壞 result，與 idle 輸入的時機一致；門全開後，壞 JSON、非 UTF-8、`ok:1`、非字串 error、非 assistant message 等會在寫回門之前退 1。非 UTF-8 特別補捕 `UnicodeDecodeError`，不讓 CLI 噴 traceback。成功 content:null 且沒有 calls 沿既有規則補空字串。

收回既有結果不再驗 CPU 家的 info：CPU 資料夾暫時不可讀，不應阻擋 agent 收手上的結果。只有真正送新單前驗 CPU info，且讀驗先於門變更。

## 15. engine.cpu 與工具私有欄位的邊界

`aos_agent_info._engine()` 的 cpu 路徑以 agent 家為中心，即使整包 engine 經 `$ref` 從子資料夾取得也一樣。缺省回 None、明寫 null 拒絕；空字串依既有路徑規則代表 agent 自己，送出時會因那裡不是 llm_cpu 而被拒。

`_timeout_ms` 位於工具檔，內容檔本來不解指示詞，因此只能寫字面正整數（包括 bool、指示詞物件都拒絕），`_meta` 原樣保留。`aos_llm_ask.RESERVED` 額外擋 `engine.params.cpu`，防止有人把本機路徑塞進 params 後又外送模型。

## 16. CPU 的最小讀驗與檔案 I/O 決定

沿用 `AgentError`：錯誤的 CPU 身分也用 `NotAnAgent` 代號，但白話指出 llm cpu；不新造一套代號。請求 engine 可帶 load 回傳的 `api_key:null`，不再經 info 的指示詞解析。CPU 只驗 engine 執行必需欄位、body 是物件、result 是無 NUL 的絕對路徑，不重驗 OpenAI 訊息內容。

缺少 requests／running／done 會建立；result 的父目錄必須已存在，寫不進去退 1、running 留給後續修復／收屍。結果用同目錄唯一 `.tmp` 避免暫存檔撞名，再 replace；不 fsync，因此保證不讀半份 JSON，但不承諾斷電持久化。請求含明文 api_key，done 原樣保留，照建議不遮罩、不清理。

## 17. 範圍限制與 code map

repo 通用工作流要求同步 `wf/` code map 與活狀態，但此次使用者明確要求只動 `proto5.1/`。所以本次逐檔職責與 API 更新集中在 `proto5.1/lib/README.md`，未改 `wf/`、未改母本 `proto5/`，沒有執行 commit／push／stash／checkout。全套測試、真模型記錄與尚未做的事見 [stage1-report.md](stage1-report.md)。

## 18. 第 2 段按 KISS 收斂：D 只評估，E 的舊字句不擴張實作

本段依 [stage2-task.md](stage2-task.md) 現行 D 節「只評估、不實作」：不加結果 `name`、state `ask`／`calls`，不建 pending journal。E 節仍寫「對帳丟舊結果」，與 D 不相容；這次只測能由完整記憶尾端確定已處理的工具批次清理，不把它宣稱為任意舊結果對帳。正式 B 方案評估在 #26。

任務 A 所稱「既有 64 條 llm cpu 測試」實際是第 1 段總共新增 64 條，分散於各模組；`test_llm_cpu.py` 本身 29 條。這 29 條原文未改，全套原有 635 條也保留，沒有刪案例或新增 skip 來避開回歸。

## 19. 共用佇列只抽機制，執行差異留在兩個薄層

新增單一 `aos_cpu.py`，用 `load(dir, cpu_type)`、`submit(dir, name, request)`、`tick(dir, execute)` 與短鎖函式承接原實作；沒有類別階層、CPU registry、worker 或背景程序。`tick` 只有兩個可選 callback：認領前 `validate(request, path)`、取得收屍預算 `timeout_ms(request)`。LLM 要在認領前驗 engine／body，工具 CPU 則在 execute 內把壞 payload 轉成失敗結果，不能硬塞成同一條驗法。

三處同名仍拒收、排隊不計時、認領刷新 mtime、執行不持鎖、結果原子替換、發布前核對 running inode，都沿用第 1 段。`aos_llm_cpu.queue_lock` 留相容別名，agent 交件改走共用 submit；結果仍無身分，沒有順手更改 #11 的限制。

## 20. 壞工具請求：能確定結果路徑才有地方回報

任務 B 的 `ok:false`「請求檔壞掉那類」需要分清楚兩種：JSON 根本讀不出來、頂層非物件、`result` 不是絕對路徑／含 NUL，無法安全決定回哪裡，CPU 退 1 並留原檔；`result` 正常但 inst／stdin／timeout_ms 壞了，認領後寫 `ok:false`，搬 done、CPU 退 0。工具 CPU 只驗已解 inst 的執行欄位，不再解指示詞；缺 cwd／stream flags、未解的 argv 指示詞等會被拒絕。

工具預算是正整數；running 壞 payload 若已無合法預算可讀，收屍採工具預設 60000 ms＋30 秒，避免自身讀驗錯誤讓它永遠留 running。LLM 維持既有規則：engine／body 壞了就在認領前退 1，不趁抽取變更原本的故障語意。

## 21. 混合批次的送收邊界與「整批先驗」

`tool-results/<i>.json` 的 i 是原始 tool_calls 索引，sync 的位置不壓掉；送出時 sync 完全不跑，CPU inst 在 agent 解好、請求各自交件，最後寫一條 all waits。收回先驗全部結果，再劃門、執行 sync，照原呼叫順序把整批 tool 訊息接記憶。壞 JSON／UTF-8／ok／code／kind／timed_out／stdout／error 不能先消耗 waits 或產生 sync 副作用；測試核對檔案 bytes 與 sync 未被呼叫。

`_meta` 解不開時 CPU 無法收到「已解好的 inst」，這次由 agent 直接在該索引寫 `ok:false`，其餘 CPU 照送，下一格統一收回。這是工具執行失敗，跟壞 info／壞結果的讀驗退 1 不同。收回現有結果不再驗 CPU 家，CPU 設定暫時不可讀也能完成手上的批次。工具表有任何 `_run:cpu` 而缺 `tool_cpu`，即使還沒走 act 就報 `FieldTypeMismatch`。

## 22. act 自癒只認「記憶已寫完的完整工具批次」

順序為：整批訊息寫記憶 → 每份結果 rename `.done` → state 換 think。重跑 act 若尾巴已不是待跑 assistant，往前取連續 tool 訊息，核對前一則 assistant 的 call 數量及 call id 順序；確實整批已接好，就封存該批尚在的 CPU 索引結果，再轉 think，不重跑 sync、不重接記憶。只是一則任意 tool 訊息不足以讓程式亂清結果。

測試注入第二份結果 rename 失敗（第一份已封存）、最後 state replace 失敗（全部已封存），重跑均保持記憶不重複、sync 只執行一次、殘留結果收乾淨。舊 `.json.done` 不當成本批待收結果，下一輪仍會正常送件。這解的是已知批次的收尾，不是一般請求身分對帳；call id 是模型訊息的關聯，不是 CPU request id。

## 23. 沒有提交紀錄時，部分批次中斷仍可能重送或永遠等

具體流程一：兩個 CPU call，第一份已交、第二份還沒交，agent 崩在寫 waits 前。重跑時若結果都沒到，會把整批用新名字再交一次，第一個工具可能重做。具體流程二：第一份已交且結果已到、第二份未交，重跑看見部分結果就補整批 all 門；第二份其實不存在於佇列，於是永遠等不到。`_meta` 錯誤已寫本地結果後崩潰，也可能形成同一種部分結果情境。沒有結果時看不出「還沒送」或「已送未回」，有部分結果時看不出其他 call 有沒有送。

這次依 KISS 不掃 CPU 三個目錄猜內容、不添批次 manifest、不自動重送有結果的半批。測試注入第二份 submit 失敗，再產生第一份結果，確認重跑補門且不跑 sync，下一格退 101；測到的是這個已知等待限制，不宣稱恢復未提交的工作。還有：sync 已產生副作用但整批記憶尚未寫會再跑；CPU 子程式可能執行過，但 CPU 崩在寫結果前，收屍只會回失敗。工具 timeout 會砍 process group，queue 收屍本身不會殺掉原 CPU 或其子程式；這些都不保證 exactly-once。

## 24. 解好的 inst 不等於整份環境快照

`$env` 由 agent 解；cwd 與各檔案路徑也在 agent 端確定。但 `envs_clear:false` 時，run_inst 繼承的是 **tool CPU 進程**的環境，並以 inst.envs 疊加；裸 argv[0] 同樣在那個 PATH 查找。這是既有 exec 的語意，不為搬到 CPU 偷加整份環境快照。

真進程驗證：agent 的解析環境 `P51_INHERITED=agent-value`，透過 `$env` 寫入 inst.envs.P51_RESOLVED；CPU 以 `P51_INHERITED=cpu-value` 啟動，工具印兩個變數得到 `cpu-value|agent-value`，CPU 退 0、結果 ok:true／child／code 0，stderr 空。要固定值就明寫 inst.envs（或 clear＋完整表），不能以為換 CPU 環境沒有差異。

## 25. CPU 執行狀態與模型看見的文字分開

CPU 的 `ok:true` 表示拿到了 run_inst 的回傳，並不等於子程式 exit 0：非零退出、真的 timeout、kind=aos 的前置失敗都能帶 code／kind／timed_out／stdout。agent 照任務 C：timed_out 優先顯示「工具 xxx 逾時」，普通非零顯示 exit n＋stdout，ok:false 顯示「跑不起來」＋error；kind=aos 的非零也依這條顯示 exit n，不加新的 stderr 欄位。故 CPU 結果仍保留 timeout 時收到的 stdout，但本段給模型的 CPU 逾時訊息不帶它。sync 維持第 1 段含毫秒與 stdout 的文字，沒有為求一致改掉既有行為。普通 exit 143 不會被誤判逾時。

## 26. D 給使用者拍板：B 方案的收益與代價（只評估，未實作）

最小資料差異是 **3 個協議欄位**：結果 `name`、state `ask`、state `calls`（原 call 索引到請求檔名的表）。但不只是加三格：需要驗字面身分、先記下且重用待送名字、處理同名交件與缺單、收回比對、舊結果封存後補等待、成功或失敗清除身分，並測這些步驟各自的中斷窗口。狀態仍三格，卻每格都要區分「已記名未交／已交未回／已回未收／已收未清」。若只在原本送件後順手寫 ask／calls，#12 的重送窗口根本還在；若先寫身分卻沒有缺單恢復，就換成永久等待。未實作，沒有捏造增加幾行或測試通過的數字。

對 #11，name 比對可拒絕把舊 running 收屍結果當下一單；但舊結果若已蓋掉新結果，識別錯配並不能把新結果變回來，CPU 發布／封存也必須配合身分。對 #13，可確定結果屬於哪個請求，工具尾巴的相等猜測可收斂；**單靠 name＋ask/calls 仍不能證明文字回覆是否已接過記憶**，記憶已寫但 state 未清時仍會重接。相同文字在新一輪本來也合法，不能靠內容相等去重。#12 和 #23 的部分交件只有加上「先記名、重用名字、缺單恢復」才改善。失敗 errors 漏計／重計、sync 工具副作用、CPU 執行與發布的窗口，仍需消費標記或交易紀錄，不能由三個欄位承諾 exactly-once。

**拍板結論：目前這個可重建、人工觀察的原型可維持 KISS，接受並保留 #11～#13／#23 的中斷限制；若下一步要在崩潰後自動續跑、又不能接受工具重做或結果串單，就值得採 B，但應把「請求身分＋送件恢復」一起列入範圍。B 能辨識串單，不能單獨保證只執行或只收回一次；若第 6 題要的是後者，還必須另決定消費紀錄／交易機制。本段沒有實作對帳，也沒有把工具尾巴自癒當成對帳完成。**
