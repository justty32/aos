# 第 1～4 段實作 findings（2026-09-22）

範圍：[stage1-task.md](stage1-task.md)（#1～#17）、[stage2-task.md](stage2-task.md)（#18～#26）、[stage3-task.md](stage3-task.md)（#27～#35）與 [stage4-task.md](stage4-task.md)（#36～#44）。以下是實作與測試遇到的具體問題、這次採用的決定與仍存在的限制；不是要求使用者現在拍板。程式與規範只改 `proto5.1/`。

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

## 27. 只看 running=false，仍有換檔到下一次 start 的窗口

`state.json` 是 daemon 最後寫出的快照。kernel 讀到 `running:false` 後，runner 可能已開始下一次，但新的 start 尚未反映到 state；只在換檔前查這個布林，仍會把正在執行的行程排到另一顆 CPU。

這段採最小的實際互斥：init 預建固定的 `cpus/<n>.json.lock`；aos-run 只對已存在的 sidecar 取 flock，從讀／解 inst 到寫完 done event 都持有。kernel 保留 `running:true` 直接跳過；false 時再非阻塞取同一把鎖，拿不到也跳過。拿到後，透過既有 remove 等 runner 真正退出、取最後結果，再換檔與 add，最後放鎖。這也避免 pipe 裡的舊 done 被算到新行程。沒有新公開旗標、op 或 daemon entry 欄位；代價是換人時重建 runner、多兩次請求。sidecar 不能隨 CPU JSON replace／刪除，否則兩邊會鎖到不同 inode。整套回歸後另補完成後的 yield 交接意圖，解短間隔飢餓，見 #35。

## 28. tool CPU 的工具在另一個 session，外層 killpg 不足以砍到底

實際呼叫鏈是 daemon → aos-run → tool CPU → run_inst 的工具 → 工具孫進程；exec 每層都可能 setsid。只 TERM tool CPU 的 group，另一個 session 的工具不會收到訊號。這次在 aos_exec 共用終止函式：Linux 上先由 `/proc` 快照直接子程式及其後代所屬 groups，全部 TERM，同一個兩秒寬限後全部 KILL，再收直接子程式；run 第一次 TERM 與原本 timeout 共用這條路。父程式先退出，也不能因此忘記已記下的後代 groups。

這不是 cgroup：終止開始前已脫離親子樹、或快照後另生並脫離原 group 的程序不在保證內；其他 POSIX 沒有 `/proc` 時只保證原 group。沒有環境標記、daemon 子孫 PID registry 或新的服務。既有 run_target 二元素／run_inst 三元素 tuple 與 timed_out 語意保持；主動停止不冒充 timeout。

## 29. done 先寫能防失單，但不是副作用與回音的交易

daemon 的回音先用同目錄 tmp 原子發布到 `requests/done/<名>.json`，成功後才刪原請求。重跑看到 done 已存在，只收掉原單，不再次 add／remove。stop 的回音等所有 runner 收屍、state 寫成 pid=0／runs={}、移除 daemon.pid 後才發布，因此 ctl stop 成功可以接著檢查停止結果；remove 同樣等被移除的 runner 收屍，result 是它最後的 entry。

若崩在 add 已產生子進程、但 done 尚未寫出，仍可能留下沒人收養的 runner；先寫 done 不能解這個窗口。這段不做 daemon 重啟收養或跨檔交易。JSON 語法壞到讀不出原物件時，無法把『原請求欄位＋ok＋result』照常合併，回音以 request:null 表示；可讀但非物件則放在 request。正常物件維持原欄位，再覆寫回音用 ok／result。

## 30. 換 runner 會歸零 runs，行程的連敗不能跟著歸零

CPU 的 `runs_at`／`seen_runs` 只描述目前 runner；換人後重新以 0 為基準。`waiting`、`wait_runs`、`bad_runs`、`bad_exit`、`aos_ticks` 則跟行程一起移到 `state.waiting[名字]` 的計數物件，重新上 CPU 時取回。保留 state 頂層 cpus／queue／waiting 三格，不另增一張 failure 表。這段的 waiting 表也能保存「不在等待、只是被量子換下」的行程計數；名稱沿用舊版，但值已由單一等待次數改成物件，格式在 kernel-home 明列。

daemon 仍只保留最後退出碼，不加 invocation journal。kernel 兩次觀察之間若完成多次，只能把 runs 差值依最新碼累計，無法還原中間不同結果；100 也可能在 kernel 看到並停 runner 前被再執行。這段沒有宣稱精確每次對帳或行程 exactly-once。aos 失敗改按新完成的次數計，不把同一份不變快照在兩次 tick 反覆算失敗；一般 child 125 也屬非零失敗，靠 kind 分開判。

## 31. inst 搬進 procs／cpus，必須保留原本的解析中心

直接複製原始 inst 會把相對 cwd、串流路徑、外部 `$ref` 的中心換成 kernel 資料夾。這次 add 先在來源 inst 的家用 `aos_inst.load()` 完整解析，再重建等價的 posix v1 JSON：絕對 cwd／串流路徑、已解 argv／envs、以及原有 mkdir／append／inherit／merge／clear 選項。tick 對手工放到 procs 的檔也先完整 load，再固化後排程；不再要求 raw argv／cwd 是字面，也不因 argv[0] 的檔暫時不存在就拒收。

代價是 add 成功後 `$env`／`$ref` 已在當時固定，下次執行不再重新追原引用；未 clear 的環境仍依 exec 語意繼承 daemon／runner 執行環境，並非整份環境快照。這是在『把一個行程 add 進 kernel』時保存可搬移 inst 的選擇，沒有新增第二種 inst 格式或指向舊 repo 的 import。

## 32. run 的事件必須用 125，壞編碼也不能讓 done 消失

`aos_exec.run_target()` 既有 library API 對 kind=aos 回 1，CLI 才換成 125。aos-run 若直接把 library code 寫事件，`--stop-exit 1` 就會把 inst 讀驗錯誤跟子程式 exit 1 混在一起。這次只在 run 的事件／stop-exit 判斷正規化為 125，保留函式庫原回傳；kind 照樣保留，普通 child 125 不冒充 aos。

真進程測試另撞到兩條 traceback 路：非 UTF-8 inst 在 load 讀字串時逸出 UnicodeDecodeError；argv 含 NUL 在 Popen 逸出 ValueError。exec 執行入口分別轉為 JsonSyntax／FieldTypeMismatch 的 aos 結果，讓 runner 可照常產生 done、重試或停；沒有改指示詞或 inst 的讀驗 API，也沒有刪舊測試。

## 33. daemon 的 stop 預算與家路徑必須跨層一致

ctl 最多只等十秒，daemon 若逐支 runner 各等五秒，三顆 CPU 就會超過它。因此停止時先同時 TERM 所有 runner，各自以同一輪起算的五秒 deadline 做 KILL；remove 留 pending，主迴圈繼續收其他事件與請求。收到 SIGTERM 剛好落在 Popen 與 jobs 登記之間時，新登記的 runner 也必須補 stop；I/O 失敗退場時，寫 state／done 再失敗不能跳過其他 runner 的清理。這些都有故障注入或真進程驗證。

`--home X` 可以覆蓋 daemon 的環境／預設家，但 child kernel tick 若只繼承原環境，會去讀另一個家。daemon 因此在啟動 runner 時把實際 `AOS_DAEMON_HOME` 放進環境；不是由底層 exec 注入，exec 既有環境規則不變。`.daemon.lock` 判斷本家是否有人執行，pidfile 只供觀察，不靠舊 PID 推斷身分或殺程序。

## 34. 工作 timeout 不應順便砍 kernel 自己的控制流程

`info.timeout_ms` 用於各 CPU runner 的一次工作；boot 只把 interval 傳給 kernel 自己的 runner，不給工作 timeout。tick 換人時可能正等 daemon 的 remove 回音，若也套一個很短的工作期限，控制流程會在搬檔／存 state 中途被截斷。這段沒有另外加 kernel_timeout 欄位。

其他 KISS 邊界：init 不覆蓋已存在的 K；具名 add 連 done／bad 同名也拒絕，要重用先 rm；done_exit=0 保留關閉完成判定，bad_after=0 保留關閉一般連敗。rm CPU 上的行程等本次執行結束才移除，十秒未完成就退錯但 syscall 留著，因此 rm 不是緊急中止；緊急停整套走 daemon stop。kernel 沒收到成功 remove 回音，就不把 NotRunning／其他失敗猜成『舊 runner 已死』並搬檔。設定改動只在 runner 下次重建時套用，不加熱更新控制命令。

## 35. 全套測試抓到短間隔飢餓：安全的鎖還不夠，必須留下交接窗口

第一輪整套跑 **754 條、90.241 秒，1 條失敗**：三個行程輪用兩顆 CPU，工作每次 220 ms、間隔 15 ms、quantum=1；十二秒後 a／b 各完成 44 次，c 仍在 queue，沒有換到它。單跑時曾通過，整套才重現。原因是 daemon 的 20 ms 輪詢與 kernel 抽樣可能一直錯過短暫的 running=false；即使快照曾 false，取得槽鎖前也可能已開始下一次。這不是把測試等待時間拉長就能解的公平性問題，interval=0 更沒有自然交接窗口。

採用既有 sidecar 的一個內部 yield 意圖，不加檔案、公開旗標或 state 欄位：kernel 有換人／退休／rm 需求時，先要求 runner 在本次完成後等；running=true 的當輪仍不換人。run 完成本次後放鎖，下次取得槽鎖時看見意圖就再放鎖、可被 TERM 中止地等候，不再開始新工作。下一格 kernel 便有穩定的 running=false，可按 #27 的槽鎖／remove 回音換檔，成功後在鎖內清意圖。這讓 0 ms 也有真正可交接的間隔，沒有用 TERM 中止正常工作。

曾評估把 daemon sleep 改成 status pipe select 立即喚醒；它只縮短延遲，不能保證 kernel 一定看到空檔，所以撤回該變更，保留原輪詢與一套確定交接。代價是 kernel 若崩在留下意圖後，runner 會停在兩次工作之間；重新 tick 可完成交接，daemon stop 仍能中止它。不做自動清意圖的時限，以免舊行程又在未交接完成時開跑。

最終驗證：修正後 Python **760/760、84.607 秒、無 skip**；原 15 ms 與新增 0 ms 的三行程／兩 CPU 長任務案例各重跑三輪，**6/6** 全過。原失敗測試保留、期限未放寬，另加意圖取消、remove 失敗保留與 run 等待／中止的測試。完整真跑與停止記錄見 [stage3-report](stage3-report.md)。

## 36. 模型連線設定移到 CPU，請求只留代號

第 4 段照使用者拍板：agent 的 engine 只有 cpu／model／params，cpu 必填；LLM CPU 的 info 必須有 models 物件，可以是空表。表裡的 endpoint、真名、api_key、timeout_ms 在 CPU 讀 info 時解指示詞，timeout_ms 預設 120000。送件檔只有 model 代號／body／result，body 不含 model；CPU 用表裡真名填入，不信請求自己塞的 body.model。連線設定與 api_key 不再因 engine 整包抄入 requests／done。

整合審查抓到 agent 送件前若呼叫完整 LLM CPU load，就會拿 agent 的環境先解 models；API key 只放在 CPU 環境時，合法請求反而交不出去。修正為 agent 只驗 CPU 身分，models 留到 CPU 執行時解。回歸測試讓 agent 環境沒有 KEY，CPU tick 才提供 KEY，實際 HTTP 驗 Bearer 與真模型名。

不認識的代號是一次有結果的請求：不打 HTTP，回 `{"ok":false,"error":"不認識的模型代號"}`，照常進 done。models 壞掉則是 CPU 設定讀驗錯，不能假裝是某一次模型失敗。沒有新增請求身分、重試或路由備援；#11～#13／#23 的跨檔中斷限制仍在。

## 37. 同步路徑拿掉後，aos-llm-ask CLI 只組 body

刪除 `ask`／`request_from_info` 與 agent 直接打 HTTP 的分支。`build_request(dir_or_info)` 可用家路徑或已讀驗 info 組 body，`call(engine, body)` 留給 CPU。原本不帶 --dry-run 就同步詢問的 CLI，現在跟 --dry-run 一樣只印 body，退出碼只剩 0／1／2；沒有另做一套 CLI 交件等待流程。這是任務未細定 CLI 去向時採取的最小保留方式，使用者要跑一次思考走 agent 與 CPU tick。

規範也分開：人格、記憶、工具、engine 的資料格式集中到 agent.md；aos-llm-ask.md 只講組 body 的程式，HTTP 行為寫在 aos-llm-cpu.md。原本的 HTTP 測試改搭 CPU 家、交件後呼叫 tick，沒有留同步相容分支。

## 38. continue 的 consume 是門開時吃，不是暫停時先清

第三次引擎失敗把 errors 歸零，加入 `{"$opt":"consume","$val":"continue.json"}`。達門檻時不再封存既有 continue.json；如果使用者已放檔，下一格會開門並把檔 rename 成 .done。第一次恢復後檔已被吃掉，所以第二次連敗仍會停住，必須再放一次檔。任務書示意的 `{file, consume}` 不是 agent.md 既有 waits 格式，因此按同一句「照 agent.md 的 waits 格式寫」使用 `$opt`／`$val`，沒有新增第二套等待語法。這取代 #3 的「每次暫停先清舊檔」，沒有另外的暫停狀態或欄位。

## 39. 結果不明只用在工具執行結果無法確認時

tool CPU 的 running 超過執行預算加 30 秒、由另一顆 CPU 收屍而沒有已發布結果時，error 固定為「結果不明：工具可能已經跑了，也可能沒有」。agent 收到這個錯誤，tool content 就是 `{"ok":false,"error":"結果不明：工具可能已經跑了，也可能沒有"}` 的 JSON 字串，不重送。共用佇列讓工具薄層指定收屍文字，不加新的結果型別欄位。

真的拿到 run_inst 回傳的逾時、非零退出、執行前已知錯誤，各自維持原訊息；不因工具出錯就一律宣稱結果不明。已有結果時收屍仍保留結果，遲到回覆仍按 inode 檢查丟棄。CPU 失聯要等既有收屍期限才會變成結果；沒有另加心跳、掃 requests 猜執行狀態或自動重試。

## 40. run.json 的 target 必須是固定檔案，連 idle 都一樣

硬連結沒有「原始檔路徑」可讓 realpath 還原，若 run.json 只寫 cpus/N.json，就無法跨 CPU 辨認 X。因此 procs/<NAME>.json 保留實體檔，CPU 槽改成原子替換的符號連結。runner 在 busy:true／target:null 之後解析連結，公布固定的 procs 路徑，再從同一路徑讀 inst；換槽不會改掉已選定的目標。aos_exec 多一個 on_target callback，只有 runner 使用時才固定 realpath，普通 exec 的既有路徑語意保留。

審查還抓到 idle 的同一個漏洞：如果空槽仍是普通 inst，runner 先公布 target=槽路徑，kernel 隨後把槽換成 X 連結，load 就會實跑 X 卻仍宣告空槽。修正為固定 K/idle.json，所有 CPU 槽連 idle 都只換連結。測試卡在 on_target 後把 idle 換成 X，確認當次仍執行原本的 idle。

防重疊的順序是：kernel 先撤掉舊槽，再逐顆新讀 run.json；busy 且 target 是 X 或 null，這格就不排 X。撤槽前已選 X 的 runner 必先寫 busy，會被擋住；撤槽後才選目標的 runner 只能看到別的固定檔。新增 idle.json 與常駐 procs 是讓這個推論成立的必要檔案佈局補充，不加鎖、讓位意圖或新狀態欄位。rm 同樣立即撤槽／移除行程，不等已讀入的工作完成；它不是中止命令。

## 41. run.json 不是完成歷史，不能把不明的差值算成失敗

runner 忙碌時 target 是本次工作，last_exit／last_kind 仍可能屬於上次工作。kernel 因此只在 busy:false、target 符合目前行程且 runs 有新進展時收結果。換人不用重建 runner，runs 不歸零，quantum 仍用完成次數差；跨換人的 waiting／bad 計數跟行程保存。

審查抓到另一個具體窗口：kernel 讀基線 runs=0 → idle 在指派前完成一次 → X 第一回失敗時 runs=2。若把差值 2 全當 X 的失敗，bad_after=2 就會首敗退件。修正為每個可確認的新快照最多增加一次 wait／bad／aos 計數，未知差值不灌入連敗。測試保留這個時序，確認 X 第一回失敗不會退 bad。

代價是抽樣可能少算：interval=0 時，kernel 可能一直只看到 busy，漏掉 done／wait／失敗碼；即使觀察到新完成，也不能還原中間每次結果。quantum 仍可前進並換人。這與 #30 原本「差值按最新碼全部累計」不同，是拿掉狀態事件、又不新增 last_target 或逐次歷史後採取的保守計數。沒有把有限快照宣稱為逐次對帳。

## 42. 兩段停止要給 ctl 足夠時間，kill_tree 只存 daemon 內部

預設 stop 是同時 TERM 所有 runner，各等 5 秒、再 TERM、再等 5 秒才 KILL runner group；kill_tree 模式是 TERM 後 5 秒 KILL。若沿用 request／ctl 的 10 秒期限，前者可能剛要回音時 ctl 已超時，因此等回音的預設改為 15 秒。remove 使用同一套停止流程；stop 仍等 runner 全收屍、state 清空、pidfile 移除後才回成功。

runner 預設首次 TERM／INT 只請它做完本次，第二次才 TERM 直接子程式那組；kill_tree 首次才走既有 terminate 的後代快照與兩秒升級，重複訊號不重入 terminate。daemon 不複製 busy／runs／last_*，entry 只留 pid／target／args／state／home；kill_tree 供停止流程用，放內部 job，沒有再加一個公開 state 欄位。

## 43. runner 家每次 add 取新名字，避免吃到舊 ctl

每次 daemon add 建立新的 runners/<唯一名>/，home 寫進 entry；remove 後留下 run.json 供查看，不重用那個家的 ctl.json。這避免同一 target 再 add 時被上次留下的 hold／stop 控制；daemon 與 runner 都不代替寫 ctl 的人刪檔。代價是 runner 家與請求 done 一樣會累積，本段不加清理政策。

## 44. 全套抓到遷移測試把合法輪轉當成失敗

第一輪完整測試 780 條、109.640 秒，只有 `test_swap_busy_two_second_job_blocks_other_cpu_at_zero_interval` 失敗：最後預期 CPU1 是 X，實際是 Y。X 原本的兩秒工作已完成，替代者 Y 卻是立即結束的 pass；interval=0 下，下一次測試觀察前 Y 已用完量子，kernel 合法把 X 排回 CPU0、Y 排到 CPU1。測試只等「CPU1 非空」就認定「X 已移往 CPU1」，這個前提不成立，失敗本身不是重疊證據。

修正只把測試的替代者 Y 也設成兩秒工作，讓 X 舊工作完成後 CPU0 仍由 Y 佔用，才有確定條件驗 X 遷往 CPU1。X 維持兩秒、interval 維持 0，等待期限與 busy／target／無重疊斷言都保留，排程程式不為測試改規則。首輪失敗 log 與修後完整測試數字見 stage4-report.md。

## 45. daemon 死掉後先等本次工作完成，舊 runner 活著就拒絕重啟

第 5 段照 R1：有 `--home` 的 runner 記住啟動時的父 PID，每圈與間歇檢查；父 PID 改變就不再開下一次，正在跑的工作仍完成。不加心跳、收養或子程序登記表。daemon 在持家鎖後掃 `runners/*/run.json`，任何 pid 仍可被 `kill(pid, 0)` 看見便回 AlreadyRunning；權限不足也保守視為存活。舊 run.json 壞 JSON、不可讀或 pid 非正整數時，用既有讀驗錯誤拒起，不略過未知狀態。

這個雙保險的代價是舊 PID 已被重用、或退出後尚未收屍的 zombie，仍可能擋住重啟；沒有擴充程序身分協議。runner 本身被 KILL、另一個 session 的工具仍活著（R4）這輪不處理。

## 46. 壞單隔離與結果寫入失敗，不能再堵住整顆 CPU

R2 分兩條：JSON／共同 result 欄位讀驗失敗，在短鎖內搬 `bad/<原名>.json`、stderr 一行，繼續掃後面的單，這格最後退 1；可讀 result 的 payload 錯誤則先認領，再由 LLM／tool execute 回 BadPayload，照常進 done，這格退 0。running 的壞檔同樣隔離，不中斷其他收屍或新單。

結果發布遇到 OSError 也搬 done、退 1。這表示 CPU 可以繼續，但結果沒寫出來的 agent 仍可能一直等；沒有假裝結果已交付，也不增加重試／等待期限。submit 先驗 result 父目錄存在只能擋住交件當下的錯誤，擋不了交件後家被移除。同名拒收統一用 AgentError ReadFailed（R14），壞檔名的 bad 副本不列入原本三處同名檢查；之後同名壞單會替換 bad 裡的舊副本。

## 47. last_target 讓忙碌快照也能對上最新完成的工作

R5 取代 #41「必須 busy=false 才能算」：run.json 的 target 描述本次，last_target 與 last_exit／last_kind／last_ms 描述最後完成那次，完成時一起發布。kernel 用 last_target 對 NAME，即使 runner 已 busy，新的 runs 仍可算一次。

仍然只有最後一份快照，沒有新增逐次歷史；一份新快照最多加一次等待／連敗，不能把 runs 差值全當成同一結果。這保留 #41 防止 idle 差值灌到新人身上的修正，但不再因忙碌而整段拒讀結果。同格多次完成與已換下行程的遲到結果仍可能漏記。

## 48. 失敗回音統一，但模型看見的工具文字保持原樣

R8 的 CPU 結果、daemon done、kernel syscall done 都使用 `{ok:false,code,msg}`。daemon 失敗不再附原請求或巢狀 result；成功仍保留原請求與 ok／result。CPU 代號包括 Reaped、UnknownModel、Timeout、EngineFailed、BadPayload；tool 真正拿到 run_inst 回傳的非零／逾時仍是 ok:true，因為已取得執行結果。

agent 用 code=Reaped 判斷結果不明，不比較 msg；交給模型的 tool 訊息仍是原本 `{"ok":false,"error":"結果不明：工具可能已經跑了，也可能沒有"}` 字串，不重送。這個模型文字不是第四種 CPU 回音格式。tool 請求的 inst.stdin／stdout 不再交件，CPU 不讀驗也不用它們，實際輸入仍是請求頂層 stdin，輸出仍由管線收回。

## 49. kernel 的 daemon 家只在 boot 選一次

R9：daemon 啟動時缺 info.json 才建 daemon/version1 身分；ctl／kernel 先驗身分。kernel init 暫不綁 daemon，boot 以當時環境／預設選家並把絕對路徑寫進 K/info.json；tick／ls／rm 從此讀這格。未 boot 時 tick／rm 回 NotRunning，ls 仍能看本地排程、顯示 daemon=None，不偷偷借當下 shell 的家。既有家沒有新身分檔時，先啟 daemon 才會補上；沒有另做遷移命令。

整份 info 可以是 `$ref`；若 boot 只新增 daemon 而 load 仍先解整份引用，這格會被忽略。因此 boot 寫的最外層 daemon 是字面綁定、讀取優先於引用內容；沒有最外層值才讀解開後的 daemon，其餘設定照舊解指示詞，沒有為記路徑把整份設定固化。

state 的行程名稱與 rm syscall 都改 name，Linux pid 保持 pid。remove 等回音逾時與 daemon ctl 同用 ReadFailed，請求仍留著；kernel 判 daemon 是否在跑依然只看最後 state 快照的 pid，不新增存活探測（R16）。

## 50. 減少重寫只改有把握的地方，格式與程式分開

R3 的 hold 固定睡 50 ms，held 只有變化才寫；R6 daemon state 只在啟動、add、停止狀態改變、收屍與收尾時寫。原本靠閒置重寫觸發的磁碟故障測試，改由 stop 觸發真正的狀態變動。R7 add 固化 inst 一次，tick 讀驗排隊檔，與固化後內容相同就不寫；手放進 procs 的未固化 inst 仍按原解析中心固化一次。

依「格式一份、程式一份」，runner 家抽成 run-home.md，aos-run.md 留命令列與行為；CPU 共用函式與步驟抽成 aos-cpu.md，cpu-queue.md 留交件／回音協議。沒有新增執行模組或修訂記錄。R4、R10～R13 依任務留在 backlog，未延伸實作。

## 51. 完整測試撞到 idle 的 busy/null 窗口

第 5 段首輪完整測試 **800 條、112.199 秒，1 個 error**。零間隔換槽測試預期 CPU0 當格已指派 Y，實際是 null。CPU1 雖在空轉，每次開始仍先發布 busy=true／target=null；kernel 此時無法排除它已選定候選，因此暫不派 Y，這是既有防重疊規則的合法結果，不是 X 被 last_target 誤判退休。

可控快照重現：CPU0 busy X／runs=1／last_exit=0，CPU1 busy／target=null，queue=[Y]；排程後兩槽 null、queue=[Y,X]、bad_runs=0。測試改用既有 ctl hold 把 CPU1 固定在 idle 間歇，X 指派到 CPU1 後再解除 hold 驗實跑。只固定測試前提，不改排程、兩秒 X、interval=0、期限與防重疊斷言。首輪 log 保留在 `.build/stage5-first-tests.log`。

## 52. JSON 合法的 result 字串也可能不是可用檔名

整合審查找到 result 含孤立 Unicode surrogate（例如 JSON 的 `"/tmp/\ud800.json"`）會通過字串／絕對路徑檢查，發布時卻拋 UnicodeEncodeError，不屬 OSError；原單留 running，之後收屍同樣失敗，重新造成 R2 的堵單。共同讀驗加 `os.fsencode` 檢查，不能編碼就回 FieldTypeMismatch，走既有 bad 隔離路徑。新增壞 result 與後續好單同格的回歸，確認好單完成、下一格 101；沒有新增路徑抽象或捕捉所有例外。

## 53. 失敗的 boot 不應留下換錯的 daemon 家

原本 boot 先改 K/info.json 再 add；若 K 正在 D1 跑，換環境指向身份完整但已停止的 D2，再 boot 會回 NotRunning，卻把 K 永久留在 D2，連 D1 的後續 tick 都找錯家。

先驗目標 daemon 持鎖存活，確認後才寫 binding；值相同不重寫。若後續 add 丟 DaemonError／OSError，恢復原 info。回歸涵蓋同家重複 boot 的 AlreadyRunning 不改 inode、停止的 D2 不改原綁定，以及存活檢查後交件失敗的還原。這是失敗路徑的本地復原，仍不是跨檔交易：程序中途崩潰或等回音逾時但 add 實際已發生，仍不能保證自動對帳。

## 54. pgrep 命中啟動本次 Codex 的上層 shell

真跑前、stop 後的 `pgrep -f aos-` 都只列 PID 158716。查 `/proc/158716/cmdline` 與父鏈，這是啟動本次 Codex 的 zsh 包裝程序，其命令列包含整份任務書與 `aos-` 字樣；不是 daemon／runner，也不是本輪新增進程。不能為了讓字面輸出空白而殺掉本次工作所依附的上層 shell。

因此原始 pgrep 證據如實保留，另加 `pgrep -A -f aos-`（排除祖先程序）驗證。第一次真跑 12.950 秒完成，daemon 退 0、state 清空、pidfile 消失、new_aos_pids_after_stop 與 remaining_demo_processes 都是空陣列；補上祖先排除輸出後再完整真跑一次，最後證據見 stage5-report／stage5-trace。這是任務要求「pgrep 字面空」與本次啟動環境之間的差異，沒有留下實際 aos 程序。
