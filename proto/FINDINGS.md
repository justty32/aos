# FINDINGS — 拿 spec 寫原型時撞到的事

寫的日期：2026-09-05。原型隊（一個隊長＋四支小隊）照
`WRITER-BRIEF.md` 第 4 節的檔名與欄位名做了一版能跑的 aos，
把過程中每一次「卡住／不合理／spec 沒講」都記在這裡。
**這份是原型最重要的產出**，程式本身只是拿來撞的工具。

依據：使用者 2026-09-05 拍板 8 條（M-01、F-02、G-01、E-01、I-01～I-04）；
主編的 WRITER-BRIEF 第 4 節跨檔契約。

## 每條怎麼讀

`- **情境**｜依據：哪一條｜**卡在哪**｜**怎麼繞**｜類別｜擋路程度`

類別是使用者定的三種量法，外加一種：

- **多餘的動作**：明明一件事，卻要敲好幾次、手動建好幾個東西。
- **看不見的狀態**：東西壞了或在等，但畫面上看不出來。
- **錯誤不指路**：報錯了，但沒告訴你下一步該做什麼。
- **spec 沒講**：寫程式時發現行為根本沒定義，只能自己選一邊。

擋路程度：**擋路**（不定義就寫不出來，或會靜默出錯）／**煩**／**小**。

## 前五條擋路的（要先拍板的）

1. **「沒產出新指令就停」會把等結果的 run 停死。** 父投出脫節呼叫或 LLM 請求後，
   下一格本來就沒事做，照裁決字面 run 當場停，子十秒後寫回來的結果永遠沒人收。
   原型改成「沒有串前進**且**沒有任何串停在 `await`／同步 `call` 等結果，才算閒著」。
   這是**刻意偏離** WRITER-BRIEF 的一條，spec 要正式改。（06-exec-and-run）
2. **投遞的 `prompt`／`result` 寫相對路徑時，基準是誰沒定義。** 選錯就是把檔案
   安靜地寫到別人家，不報錯。原型照 I-01 定成「投的人那塊地的根」，
   並且禁止落點指進任何 `.aos/`。（07-call-and-delivery、09-llm-world）
3. **投遞 id 去重要記在哪沒定義。** exec 把信搬走、把指令跑掉之後，
   收件匣裡那個 id 就消失了，同一個 id 可以無限重投，I-05 形同虛設。
   原型自己加了 `.aos/inbox/.seen.json`，正式實作要給它一個名字。（07）
4. **LLM 世界的圈跟 `aos run` 的走格是兩套，沒接起來。** F-02 說它是一塊地、
   有自己的鐘、由 daemon 起 `aos run`；但「取信、打端點、寫結果」不是
   `inst`／`call`／`await` 任何一種步，所以它的接力棒從頭到尾沒人用。
   daemon 到底該對它起哪一支，spec 要挑一邊。（08-daemon、09-llm-world）
5. **`.aos/stopped.json` 誰寫、誰清沒定義，於是狀態看不見。** 版面表寫「run 寫」，
   但串失敗是 exec 判的；而且沒人負責清，上一輪的「壞在哪」會一直掛在
   `aos status` 上騙人。原型讓 exec 也寫、run 開跑先清停時必寫。（06）

## 刻意偏離 WRITER-BRIEF 的地方（連同理由）

| 偏離 | 理由 |
|---|---|
| 閒著的定義加上「沒有串在等結果」 | 見上面第 1 條，照字面走會靜默卡死 |
| 結果落點禁止指進任何 `.aos/` | `.aos/` 是機器的，讓子地往裡面寫等於開後門 |
| 落點的目錄由父在開呼叫時建好，子不准 `mkdir -p` | 父地都不在了還建目錄，等於在墳墓上蓋房子 |
| 加了 `.aos/inbox/.seen.json` | 不然 I-05 的「同 id 拒絕」做不到 |
| 加了假後端 `echo:`／`fail:`／`slow:<ms>` | 不開模型就能測，且保證測試絕不偷打網路 |
| 加了 `.aos/llm-done/`、`.aos/llm-ask/` | 4.5 沒給 `kind:"llm"` 下場，直接刪＝請求人間蒸發 |
| 登記表多記 `pid_start`、`result` | 防 pid 重用誤判；子被 SIGKILL 時對帳能替它寫狀態檔 |
| `aos stop` 沒人在跑時不投控制信 | 不然那封信會變成下一趟 run 的舊帳，第一格莫名其妙就停 |
| run 開跑前掃掉陳年控制信 | 同上，兩頭堵 |
| `--register` 已登記時只更新 pid，不覆寫 `clock` | 不然 daemon 起的子行程會把登記表的鐘改掉 |
| daemon 迴圈設 `SIGCHLD=SIG_IGN` | 不然殭屍的 pid 還在，對帳永遠不會把它改成 stopped |
| `aos llm` 退出碼多分一級（請求本身寫壞回 2） | 4.7 只給 0/2/75/130，沒有「請求寫壞」那一格 |
| 原稿＝模板同格式，載入器不做拆平 | spec 沒定義原稿長什麼樣，先讓兩者一樣，記在下面 |

## 核心（版面、載入器、exec、投遞）

- **一塊地的鎖沒人收屍**｜依據：WRITER-BRIEF 4.1（`.aos/lock`，O_EXCL）｜**卡在哪**：O_EXCL 建檔當鎖，程式被 kill -9 之後鎖檔留著，那塊地就永遠打不開，spec 沒講誰負責清。｜**怎麼繞**：鎖檔裡寫 `{"pid":…}`，搶不到時看那個 pid 還活不活，死了就收回來。｜類別：spec 沒講｜擋路程度：擋路
- **原稿到模板的「拆平」沒定義**｜依據：WRITER-BRIEF 4.1（載入器／編譯器）、4.2（模板格式）｜**卡在哪**：spec 只寫「編譯器吐的模板」長什麼樣，沒寫原稿長什麼樣、也沒寫要怎麼把巢狀的人寫格式攤成步陣列。｜**怎麼繞**：原型第一版讓原稿＝模板同格式，只做嚴格檢查再抄過去。｜類別：spec 沒講｜擋路程度：煩
- **投遞去重的記憶要放在哪**｜依據：WRITER-BRIEF 4.5（I-05 同 id 再投＝拒絕）｜**卡在哪**：exec 把信搬去 `.aos/mail/`、把 inst 跑掉之後，收件匣裡那個 id 就不見了，同一個 id 可以無限重投。spec 沒指定去重表住哪。｜**怎麼繞**：自己加了 `.aos/inbox/.seen.json`。這是 spec 之外的檔，正式實作要正名。｜類別：spec 沒講｜擋路程度：擋路
- **`.aos/stopped.json` 到底誰寫**｜依據：WRITER-BRIEF 4.1 版面表寫「誰寫＝run」，但 4.2 說串失敗（`on_fail` 省略）要「寫停止原因檔」，而串失敗是 exec 判的｜**卡在哪**：單跑 `aos exec` 讓一條串失敗時，照 4.1 沒人寫停止原因檔，錯誤就看不見了。｜**怎麼繞**：exec 也寫；run 停下時再覆寫成自己的原因。兩者搶同一個檔，最後看到的是誰的不好講。｜類別：看不見的狀態｜擋路程度：擋路
- **`stopped.json` 沒有欄位定義**｜依據：WRITER-BRIEF 4.1、4.5｜**卡在哪**：4.5 只給了狀態檔（`<結果落點>.status.json`）的欄位，停止原因檔沒有。｜**怎麼繞**：照狀態檔的樣子捏一份：`format_version` `reason` `message` `series` `step` `at`。｜類別：spec 沒講｜擋路程度：煩
- **`select` 讀的檔不在時怎麼算**｜依據：WRITER-BRIEF 4.2（`select`：成功後讀那個檔第一行當下一步名）｜**卡在哪**：那一步明明成功了，但 select 指的檔沒生出來，或第一行是空的——算失敗？算走下一步？spec 沒講。｜**怎麼繞**：檔不在或空行就退回 `then`／下一步，不算失敗。這很可能是錯的（安靜地走錯路比失敗更難查）。｜類別：spec 沒講｜擋路程度：擋路
- **同步呼叫的呼叫記錄不能每格重開**｜依據：WRITER-BRIEF 4.2（sync：父每格對子做一次 exec）、4.5（呼叫記錄）｜**卡在哪**：同步呼叫那一步會停在原地好幾格，每格都寫一筆新的 `.aos/calls/<call id>.json` 就會生出一堆重複記錄；但「同一步的呼叫記錄 id 記在哪」spec 沒講。｜**怎麼繞**：塞進接力棒那條串的 `ext.calls[步名]`。｜類別：spec 沒講｜擋路程度：擋路
- **`await` 的 `max_ticks` 計數放在哪**｜依據：WRITER-BRIEF 4.2（`await` 的 `max_ticks`）｜**卡在哪**：要知道「等了幾格」就得有個計數器，接力棒的串物件欄位表（4.4）裡沒有這一欄。｜**怎麼繞**：塞進 `ext.awaits[步名]`。｜類別：spec 沒講｜擋路程度：煩
- **「這格沒動」跟「閒著」是兩件事，spec 混在一起**｜依據：裁決 2026-09-04「run 通用停法＝沒產出新指令就停」、WRITER-BRIEF 4.2（`await` 三態第一態＝這格不動、不算失敗）｜**卡在哪**：一條 `await` 串在等東西時，這格什麼都沒前進（該停？），但接力棒裡它還是 `running`（沒閒著，不該停）。照「沒產出新指令就停」會把還在等的串直接停掉。｜**怎麼繞**：`exec_once` 的報告同時給 `advanced` 與 `idle` 兩個旗標，把判斷丟給 run 去拿捏。｜類別：spec 沒講｜擋路程度：擋路
- **子地閒著但沒生結果，沒有對應的錯誤代碼**｜依據：WRITER-BRIEF 4.5 的 `reason` 常用代碼清單｜**卡在哪**：同步呼叫的子地跑完閒著了，但父指定的結果落點什麼都沒有——這是最常見的失敗，清單裡卻沒有代碼。｜**怎麼繞**：自己編了 `no_result`。同理還編了 `no_expect_file`（`inst` 宣告了 `expect` 卻沒生檔）、`exit_code`（沒宣告 `expect` 只好看結束碼）、`missing_reg`、`no_such_step`、`not_a_land`。｜類別：錯誤不指路｜擋路程度：擋路
- **投遞進來的 `kind:inst` 不屬於任何一條串**｜依據：WRITER-BRIEF 4.3（exec 給每筆指令的環境變數含 `AOS_SERIES`、`AOS_FRAME`）｜**卡在哪**：從收件匣直接跑的指令沒有串，`AOS_SERIES` 跟 `AOS_FRAME` 要填什麼？｜**怎麼繞**：填死字串 `delivered`，於是地上會冒出一個 `.aos/frames/delivered/` 目錄，沒人清。｜類別：spec 沒講｜擋路程度：煩
- **`baton.tick` 是「這一格」還是「下一格」**｜依據：WRITER-BRIEF 4.4（`{"…","tick":N,…}`）｜**卡在哪**：欄位只叫 `tick`，看不出是已經跑完的格號還是接下來要跑的格號，而 `.aos/ticks/<N>/` 的 N 到底對哪一個也就跟著含糊。｜**怎麼繞**：當成「接下來要跑的格號」，跑完才 +1；`ticks/<N>/` 用跑的時候那個 N。｜類別：spec 沒講｜擋路程度：煩
- **`exclusive` 誰先誰後沒定義**｜依據：WRITER-BRIEF 4.3（`exclusive`：同組的指令不在同一格跑，後到的延到下一格）｜**卡在哪**：同一格裡兩條串搶同一組，「後到」是照接力棒陣列順序？照串 id？spec 沒講，於是排在陣列後面的串會被永遠餓死。｜**怎麼繞**：照接力棒陣列順序，先到先跑。有餓死風險。｜類別：spec 沒講｜擋路程度：煩
- **開一塊地跑一件事要敲四次**｜依據：WRITER-BRIEF 4.10（`aos init`、`compile` 不在清單裡但載入器要跑）｜**卡在哪**：`init` → 手寫 `main.aos.json` → 編出模板 → `exec`。中間那個編譯步驟對人來說是純多餘。｜**怎麼繞**：`load_program()` 找不到模板就自己去編原稿，`compile` 只留給想先驗語法的人。｜類別：多餘的動作｜擋路程度：煩
- **`aos status` 之外沒地方問「現在到底怎樣」**｜依據：WRITER-BRIEF 4.10（看的只有 `status`）｜**卡在哪**：要知道某筆指令跑成什麼樣，只能自己去翻 `.aos/ticks/<N>/results/<id>.json`；要知道某個呼叫開了沒，只能翻 `.aos/calls/`。指令面沒有「問一筆指令」「問一個呼叫」的子命令。｜**怎麼繞**：`status` 多印了停止原因與收件匣待處理數，其餘照樣翻檔。｜類別：看不見的狀態｜擋路程度：擋路
- **`env_inherit` 預設 true 但文件叫你關**｜依據：WRITER-BRIEF 4.3（`env_inherit`（布林，預設 `true`，文件寫明建議關））｜**卡在哪**：預設值跟建議值相反，等於預設就是不建議的那個。而且關掉之後 `PATH` 從哪來？`.aos/config.json` 的 `path` 白名單是空陣列時就沒有 PATH，指令一律 spawn 失敗。｜**怎麼繞**：`env_inherit:false` 且 `path` 為空時給一個保底 `PATH=/usr/bin:/bin`。｜類別：spec 沒講｜擋路程度：煩

## run 與 daemon

寫的時候撞到的每一件事。實測環境：`AOS_HOME` 指到暫存目錄，Python 3 純標準庫。
### 一、通用停法：`advanced=False` 但 `idle=False` 到底要不要繼續（隊長點名要記的那條）
- **一條 `await` 串在等，這格沒前進但也還沒閒著，`--until idle` 該等還是該停**｜依據：裁決 2026-09-04 通用停法＋rulings M-01｜**卡在哪**：裁決講「沒產出新指令就停」，但 `--until idle` 字面是「跑到閒著」。兩句在 await 情境下相反：沒前進（該停）可是沒閒著（該等）。spec 沒說哪句大。｜**怎麼繞**：我拿捏成「看有沒有給 `--every`」——給了 `--every` 就是使用者說「我願意隔一段時間再來看一次」，那就繼續等到真的閒著；沒給 `--every` 就停，原因用新代碼 `stalled`，訊息直接指路（`aos status <地>` 看在等什麼、或加 `--every <毫秒> --until idle` 繼續等）。理由是沒 `--every` 又繼續跑就是 busy loop 燒 CPU，機器沒有別的辦法知道要隔多久回來。｜類別：spec 沒講｜擋路程度：擋路
- **`stalled` 這個原因代碼是我自己加的**｜依據：WRITER-BRIEF 4.10 只列了 `0/2/3/4/5/75`，隊長只點名 `idle／steps_done／budget／failed／control_stop`｜**卡在哪**：上面那個取捨需要一個原因代碼，五個現成的都不對（不是 idle、不是失敗、不是預算）。｜**怎麼繞**：加 `stalled`，退出碼算 `0`（沒壞掉，只是沒事做）。spec 要嘛收編它，要嘛明訂 await 卡住時 `--until idle` 該怎麼算。｜類別：spec 沒講｜擋路程度：煩
### 二、看不見的狀態
- **`.aos/stopped.json` 是陳年舊帳**｜依據：WRITER-BRIEF 4.1（`stopped.json` 由 run 寫）｜**卡在哪**：spec 沒說誰負責清。上一趟 run 停在 `failed`，下一趟 run 跑得好好的，`aos status` 還是印上一輪的「壞在哪」。｜**怎麼繞**：run 一開始就先 `unlink` 它，停的時候一定重寫一次（含被 SIGTERM 的情況）。spec 該明寫「開跑即清、停即寫」。｜類別：看不見的狀態｜擋路程度：擋路
- **控制收件匣裡的陳年停止信**｜依據：WRITER-BRIEF 4.6、L-05｜**卡在哪**：沒有 run 在跑的時候投一封 `op:stop` 進 `.aos/control/`，沒人收。下次 run 一開跑，第一格結束就被這封舊信停掉，畫面上看不出為什麼。｜**怎麼繞**：兩頭堵。(1) `aos stop` 先查有沒有人在跑，沒人在跑就**不投**，直接講「這塊地現在沒人在跑，什麼都沒做」；(2) run 開跑前把控制收件匣裡既有的信全掃進 `.aos/control/done/` 並印一行「清掉 N 封陳年停止信」。代價是有幾毫秒的競態（stop 正好在 run 開跑那一瞬間投信會被掃掉）。spec 該給控制信一個「只對某個 pid／某趟 run 有效」的欄位，或明訂保鮮期。｜類別：看不見的狀態｜擋路程度：擋路
- **處理過的控制信該挪走還是刪掉**｜依據：WRITER-BRIEF 4.6｜**卡在哪**：spec 沒講。刪掉＝事後查不到誰叫停的。｜**怎麼繞**：挪到 `.aos/control/done/<原檔名>`，看得見也不會被重複處理。｜類別：看不見的狀態｜擋路程度：小
- **`aos stop --kill` 之後沒有停止原因檔，還留一個孤兒鎖**｜依據：WRITER-BRIEF 4.6（`--kill` 直接送 SIGKILL）｜**卡在哪**：SIGKILL 攔不住，run 的 try/finally 不會跑，所以 (1) `.aos/stopped.json` 停在上一輪的內容，(2) `.aos/lock` 留著。實測確認過。｜**怎麼繞**：`aos stop --kill` 印出來的話裡直接講明這兩件事，並在殺完後幫忙把登記表那筆改成 `stopped`。孤兒鎖靠 `fsutil.Lock._steal_if_dead` 下一次自己收回來（那也是別人補的、spec 沒講的東西）。spec 該規定「殺掉之後誰補寫停止原因檔」。｜類別：看不見的狀態｜擋路程度：煩
- **run 把 exec 寫的細原因蓋掉了**｜依據：WRITER-BRIEF 4.5 reason 代碼表｜**卡在哪**：串壞掉時 `execute._fail_series` 已經寫了一份 `stopped.json`，`reason` 是細代碼（例 `exit_code`）；run 停下來又寫一次，`reason` 變成隊長點名的 `failed`，細代碼就沒了。兩個寫者搶同一個檔。｜**怎麼繞**：run 保留 `reason:"failed"`（退出碼 5 要靠它），把細代碼塞進 `message`（「串 xxxx 在 `boom` 壞了（exit_code：…）」）。spec 該說清楚 `stopped.json` 只准一個寫者，或加一個 `detail_reason` 欄。｜類別：錯誤不指路｜擋路程度：煩
### 三、多餘的動作
- **`aos daemon stop` 之後，`aos daemon start` 不會把地接回去跑**｜依據：G-01｜**卡在哪**：全停時每筆都變 `stopped`，daemon 迴圈只撿 `pending`。所以「全停再全開」不是兩個指令，是「全停 → 一塊一塊重新登記 → 再 start」。｜**怎麼繞**：原型照 spec 只撿 `pending`（不然剛跑完的地會被無限重起）。實務上需要一個 `aos daemon resume`／或 `stop` 時把 `state` 記成 `paused` 之類的第四態。spec 只有三態，不夠用。｜類別：多餘的動作｜擋路程度：擋路
- **串跑完會多空轉一格才停**｜依據：`execute.exec_once` 的 `advanced` 定義｜**卡在哪**：串推到 `end` 的那一格 `advanced=True`、`idle=True`；我停的條件是「idle 而且沒前進」，所以還要再跑一格空的才停。實測 `--until idle` 明明 5 步卻印了 6 行。｜**怎麼繞**：留著。若改成「idle 就停」，投遞進來的指令（`inbox` 有東西但沒有 running 的串）就會被漏掉一輪。spec 該講清楚「閒著」到底看接力棒還是也看收件匣。｜類別：多餘的動作｜擋路程度：小
- **一塊地要跑起來要敲兩次**｜依據：WRITER-BRIEF 4.11 第 2 條、J-03｜**卡在哪**：登記只給 `pending`、起時鐘是另一個動作，可是登記表沒有任何子命令能把一筆改成 `pending`（`aos daemon` 只有 start/stop/ls/exec/status）。我測試時只能直接呼叫 `registry.register()`。｜**怎麼繞**：原型用 python 直接叫；`aos run <地> --register` 是唯一從指令面登記的路，可是它同時就開跑了，登不出「pending 等 daemon」那種。spec 該補一個 `aos daemon add <地> --steps/--every/--until` 之類的。｜類別：多餘的動作｜擋路程度：擋路
### 四、錯誤不指路 ／ 介面沒接好
- **`aos run --register` 會把 daemon 剛登記的時鐘覆蓋掉**｜依據：隊長交代「`registry.register(land.root, clock, budget=…)`」＋`registry.register` 的實作｜**卡在哪**：`registry.register()` 對既有那筆一律覆寫 `clock` 與 `budget`。daemon 把 `{"kind":"once"}` 翻成 `--steps 1` 起子行程，子行程再 `register()` 回去，登記表那筆的鐘就從 `once` 變成 `steps/1`——資訊被子行程改掉了。｜**怎麼繞**：**故意跟交代的做法不一樣**：`--register` 先查登記表，沒那筆才 `register()`，已經有就只 `update(pid=…, state=running)`。實測 `{"kind":"until"}` 與 `{"kind":"every","every_ms":300}` 都完整保住。spec 該規定「時鐘規格是登記者說了算，被起的 run 不准改」。｜類別：spec 沒講｜擋路程度：煩
- **控制信不認得的 `op` 沒地方講**｜依據：WRITER-BRIEF 4.6 只定義 `op:"stop"`｜**卡在哪**：投一封 `op:"pause"` 進去，最省事的做法是默默無視，那封信就永遠卡在收件匣。｜**怎麼繞**：一律挪到 `done/`，並在 run 的輸出印一行「只認得 `stop`，下一步：改成 {…} 再投一次」，同時記進報告的 `notes`。｜類別：錯誤不指路｜擋路程度：小
- **沒登記的 run 用登記表查不到 pid**｜依據：WRITER-BRIEF 4.6（`--kill` 查登記表拿 pid）｜**卡在哪**：`aos run <地>` 不加 `--register` 就沒進登記表，`aos stop --kill` 依 spec 只查登記表就會說「找不到」，可是那支明明在跑。｜**怎麼繞**：加一層備援——查 `.aos/lock` 裡的 `{"pid":…}`。實測 `--kill` 一支沒登記的 run 成功。訊息會講「從鎖檔查到的」。spec 該把鎖檔的 pid 明訂成第二來源。｜類別：錯誤不指路｜擋路程度：煩
- **detach 出去的子行程會丟掉 `$AOS_HOME`**｜依據：`layout.home()` 讀環境變數｜**卡在哪**：daemon 起 `aos run` 子行程時若只 `env=None`／繼承預設，測試用的 `AOS_HOME` 沒問題，但只要有人用 `subprocess` 換過環境就會跑去改 `~/.aos/registry.json`——會動到使用者真的家。｜**怎麼繞**：所有子行程一律 `env["AOS_HOME"] = layout.home()` 明寫進去。spec 該規定「登記表位址由父行程明確傳給子行程」。｜類別：看不見的狀態｜擋路程度：煩
- **daemon 起的 `daemon start --foreground` 子行程差點自己把自己擋掉**｜依據：G-01｜**卡在哪**：父行程先 `set_daemon_pid(子 pid)` 再讓子行程跑，子行程一開頭檢查「已經有活著的 daemon 嗎」就會看到自己，然後印「已經在跑」直接退出。｜**怎麼繞**：那個檢查加一句 `and live != os.getpid()`。｜類別：spec 沒講｜擋路程度：小
- **daemon 不 wait 子行程會留一地殭屍**｜依據：G-01（daemon 只當看管者，不管子行程死活）｜**卡在哪**：`subprocess.Popen` 出去的還是直系子行程，daemon 一輩子不 wait，死一個留一個殭屍；殭屍的 pid 還在，`registry.alive()` 會說它活著，對帳永遠不會把它改成 `stopped`。｜**怎麼繞**：daemon 迴圈裡 `signal.signal(SIGCHLD, SIG_IGN)` 讓系統自動收屍。實測 kill -9 子行程後 0.3 秒內 `daemon ls` 就對帳成 `stopped`。spec 該把「怎麼確認一個登記的 pid 真的死了」寫成一條。｜類別：看不見的狀態｜擋路程度：擋路
### 五、其他取捨（沒撞到問題，但 spec 沒講、我自己選了一邊）
- **停止條件的優先序**：失敗 ＞ 控制信 ＞ 閒著 ＞ `--steps` 跑滿 ＞ `--budget` 用完 ＞ `stalled`。理由：閒著排在 budget 前面，是因為地已經跑完了卻回報「預算用完、退出碼 5」是誤報。`--steps 3 --budget 3` 同時滿足時報 `steps_done`（退出碼 0），因為使用者要的 3 格拿到了。｜類別：spec 沒講｜擋路程度：小
- **SIGTERM／SIGINT 只在格尾生效**：訊號收成旗標，不打斷跑到一半的指令。所以一筆 60 秒的指令會讓 `aos daemon stop` 等最多 60 秒。原因代碼 `signal`、退出碼 130。spec 該講「請它停」與「立刻殺」之間的最長等待。｜類別：spec 沒講｜擋路程度：煩
- **`--every` 的間隔期間也顧控制收件匣**：不然 `--every 5000` 的地要等 5 秒才理 `aos stop`。切成 50 毫秒一小段輪詢。｜類別：spec 沒講｜擋路程度：小
- **沒有「閒著也繼續等投遞」的模式**：`--every --until idle` 一旦閒著就停，所以「一直掛著等信」這種伺服器型的地寫不出來。LLM 世界（F-02）大概正需要這個。spec 該補第四種鐘，或讓 `--until` 收 `never`。｜類別：spec 沒講｜擋路程度：擋路
### 實測過的（`AOS_HOME` 指到暫存目錄）
1. `--steps 3` → `steps_done`／0；`--until idle` → `idle`／0；`--budget 1` → `budget`／5；串壞掉 → `failed`／5；鎖被佔 → 75；不是一塊地 → 4。
2. `aos stop <地>` 寫控制信 → 背景 run 在格尾停，`stopped.json` 是 `control_stop`，信挪到 `control/done/`。沒人在跑時 `aos stop` 講「什麼都沒做」並列出查過哪兩處。
3. `daemon start` → 登記一塊 `pending` → daemon 起 `aos run --register` 子行程 → `daemon ls` 看到 `running` 且時鐘沒被子行程改掉 → `daemon stop` 全收（run 收到 SIGTERM 寫 `signal`，daemon 清掉 `daemon.pid`）。
4. `kill -9` 子行程 → 0.3 秒後 `daemon ls` 對帳成 `stopped`，daemon 不會重起它。
5. `daemon start --foreground` + SIGTERM → 乾淨收尾，`daemon.pid` 清掉。
6. `daemon exec <地>` 手動催一格、`daemon status`、`daemon ls --json` 都正常。

## LLM 世界

寫的人：LLM 世界小隊。日期 2026-09-05。
依據：WRITER-BRIEF 4.5／4.7、rulings F-02（LLM 是單獨一塊地）、I-01（結果落點由投的人指定）、I-02（狀態檔）。
實作範圍只有 `proto/aosp/llm.py` 一支。
### 擋路
- **請求裡的 `prompt` 與 `result` 寫相對路徑時，基準是誰？**｜依據：WRITER-BRIEF 4.7＋rulings I-01｜**卡在哪**：4.7 只說這兩欄是「路徑」，沒說相對於誰。合理的候選有三個：投遞者那塊地、LLM 世界那塊地、跑 LLM 世界那支行程的 cwd。選錯就是「檔案憑空生在別人家」，而且不會報錯，只會安靜地寫錯地方。｜**怎麼繞**：照 I-01「落點由投的人指定」推，基準只能是投遞者，所以用 `layout.Land(obj["from"]).resolve(...)`；絕對路徑照用。錯誤訊息裡把基準是誰一起印出來。｜類別：spec 沒講｜擋路程度：擋路
- **帳簿的 token 數是估的，但欄位名跟真的一模一樣**｜依據：WRITER-BRIEF 4.7 帳簿欄位「一字不改」｜**卡在哪**：假後端（與任何不回 `usage` 的端點）沒有真 token 數，只能用字數估。可是帳簿只有 `tokens_in`／`tokens_out` 兩欄，沒有「這是估的」這個位子。之後拿帳簿算錢會把估的當真的加進去，而且事後完全看不出哪幾行是估的。｜**怎麼繞**：原型照抄那 9 欄不加欄位，估算規則寫在程式註解裡（非空白字元數÷4）。真正該加的是一個 `tokens_source`（`"reported"`／`"estimated"`）或把 0 保留給「不知道」。｜類別：看不見的狀態｜擋路程度：擋路
- **LLM 世界的「圈」跟 `aos run` 的走格是兩套，沒接起來**｜依據：rulings F-02(3)「LLM 世界自己有鐘、由 daemon 登記與看管」＋WRITER-BRIEF 4.6｜**卡在哪**：F-02 說 LLM 世界是一塊地、有自己的鐘、由 daemon 登記。可是 daemon 走鐘＝起一支 `aos run <地>`，而 `aos run` 走的是 `.aos/series.json` 那套接力棒與模板；LLM 世界要做的事（取信、打端點、寫結果）不是任何一種步（`inst`／`call`／`await`）。結果就是 `aos llm serve` 跟 `aos run` 兩套走格法並存，LLM 世界的 `.aos/series.json` 從頭到尾沒人用。daemon 要看管 LLM 世界時到底該起哪一支，spec 沒寫。｜**怎麼繞**：原型自己實作 `serve_once`，並且讓它跟 `exec` 搶同一把 `.aos/lock`，這樣兩支同時跑不會把同一筆請求打兩次。spec 需要挑一邊：要嘛 LLM 世界的 `main.aos.json` 用一個新的步 kind 表示「服務一輪」，要嘛明講它是特例、daemon 對它起的是 `aos llm serve`。｜類別：spec 沒講｜擋路程度：擋路
- **處理完的請求該去哪，spec 沒講**｜依據：WRITER-BRIEF 4.5 投遞物那段（只講了 `rejected/`）｜**卡在哪**：收件匣的 `kind:"inst"` 處理完是 `os.unlink`、`mail` 是搬去 `.aos/mail/`，只有 `llm` 沒有下場。直接刪＝請求人間蒸發，出事後想知道「那筆請求長什麼樣」只剩帳簿一行。｜**怎麼繞**：原型搬到 `<LLM 世界>/.aos/llm-done/<id>.json`，原檔一字不動，靠帳簿的 `request_id` 對回來。｜類別：看不見的狀態｜擋路程度：擋路
### 煩
- **`max_parallel` 到底是「同時幾條連線」還是「一格處理幾筆」**｜依據：WRITER-BRIEF 4.7 `units[].max_parallel` 與使用者層 `max_parallel`｜**卡在哪**：spec 只給數字沒給語意。在「一格一格走」的世界裡，「同時」這個詞本身就沒定義——一格之內做完的事，對外面看起來就是原子的。｜**怎麼繞**：原型解釋成「這一格最多派給這個單元幾筆」，全域與單元取小，超過的留在收件匣、下一格再處理，並在報告裡印出「單元 X 這一格已經吃滿 N 筆」。實測 `max_parallel=1` 時三筆請求會照 `priority` 一格一筆吐出來。｜類別：spec 沒講｜擋路程度：煩
- **`outcome` 有哪些值沒定義**｜依據：WRITER-BRIEF 4.7 帳簿欄位｜**卡在哪**：只說有 `outcome` 欄。要是每個實作各寫各的（`ok`／`success`／`done`），帳簿就沒辦法跨實作統計。｜**怎麼繞**：原型只用四個值，並且刻意跟 4.5 的 `reason` 代碼對齊：`ok`、`backend_error`、`queue_timeout`、`rejected`。｜類別：spec 沒講｜擋路程度：煩
- **`aos llm` 的退出碼沒有「請求本身寫壞了」那一格**｜依據：WRITER-BRIEF 4.7「`0` 成功、`2` 用法錯、`75` 後端或傳輸失敗（可重試）、`130` 被取消」｜**卡在哪**：prompt 檔不存在、少了 `result`、tier 打錯——這些重試一百次也是一樣的結果，不該回 75（可重試）；但它們也不是「敲指令的人打錯字」，回 2 也怪。而且一格裡可能同時有成功的和壞掉的請求，退出碼只有一個。｜**怎麼繞**：原型的規則是「一格裡只要有 `backend_error`／`queue_timeout` 就回 75，否則有壞掉的請求就回 2，全好回 0」。真正的答案應該是：退出碼只講「這支程式有沒有跑起來」，個別請求的成敗一律看狀態檔（跟 I-04 的兩頻道同一個道理），spec 該把這條講死。｜類別：spec 沒講｜擋路程度：煩
- **沒有假後端就沒辦法測，spec 完全沒提**｜依據：WRITER-BRIEF 4.7 `units[].endpoint`｜**卡在哪**：`endpoint` 只寫成 http 位址，那任何自動化測試、任何 CI、任何示範都得先有一台模型在跑。｜**怎麼繞**：原型自己加三個假 endpoint（**這是原型的發明，不在 spec 裡**）：`echo:` 不打網路把 prompt 原樣回、前面加一行 `echo:<單元名>`；`fail:<原因>` 一定失敗（測 `backend_error`）；`slow:<毫秒>` 睡一下再 echo（測 `queue_timeout` 與並行上限）。`aos llm init` 預設寫進去的兩筆單元都是 `echo:`，所以裝好就能跑、而且絕對不會偷打網路。spec 該把「保留 scheme」這件事寫進去，否則各家實作各發明一套。｜類別：spec 沒講｜擋路程度：煩
- **`max_wait_ms` 從哪一刻開始算**｜依據：WRITER-BRIEF 4.7｜**卡在哪**：從投遞物的 `at` 算，還是從 LLM 世界第一次看到它算？兩台機器（或兩個 container）的鐘差幾秒，前者就會把剛投進來的請求直接判逾時。｜**怎麼繞**：原型從 `at` 算（唯一落在檔裡的時間戳），並且把「排了幾 ms／上限幾 ms」寫進狀態檔的 `message`，這樣人一眼看得出是不是鐘的問題。｜類別：spec 沒講｜擋路程度：煩
- **沒有相符的 `tier` 時的退路只印在螢幕上**｜依據：WRITER-BRIEF 4.7 `units[].tier`｜**卡在哪**：spec 沒講 tier 配不到要怎麼辦。隊長要求「退回第一筆並記一行」，但那一行只在 stdout；帳簿雖然有 `unit` 也有 `tier`，可是要人自己比對「請求要 smart，卻走了 fast 單元」才看得出來被降級了。跑在 daemon 底下就沒人看得到那一行。｜**怎麼繞**：原型除了印，還把說明放進 `serve_once` 回傳的 `notes` 與 `--json` 輸出。真正該做的是狀態檔或帳簿有個地方標「這筆被降級了」。｜類別：看不見的狀態｜擋路程度：煩
- **`tools` 跟 OpenAI 的 `tools` 同名不同義**｜依據：WRITER-BRIEF 4.7「`tools`（可選，給模型看的工具行陣列）」｜**卡在哪**：OpenAI 相容端點的 `tools` 是 function schema 陣列，走的是 tool-calling 那條路；4.7 的 `tools` 是「給模型看的字串行」，走的是塞進 prompt 那條路。同名會讓人以為投進去就會有 tool call。｜**怎麼繞**：原型把 `tools` 當文字，接在 prompt 前面變成一段「可用工具：」，不碰請求 body 的 `tools` 欄。spec 要嘛改名（`tool_lines`），要嘛明講它不是 function calling。｜類別：spec 沒講｜擋路程度：煩
### 小
- **請求失敗只寫狀態檔，投遞者不會被通知**｜依據：WRITER-BRIEF 4.5 三態＋I-02｜**卡在哪**：`inbox` 對「投遞不合格」會往 `from` 回一封 `mail`（I-06），但對「收下了、處理時失敗了」沒有回信。投遞者只能靠 `await` 步輪詢 `<result>.status.json`。單看 spec 會誤以為兩種失敗都會有回信。｜**怎麼繞**：原型照三態做，不回信；`await` 步本來就會看到狀態檔。只是 spec 該把「收下之後的失敗不回信」明寫一句。｜類別：spec 沒講｜擋路程度：小
- **LLM 世界預設住在 `$AOS_HOME/.aos/llm/`，跟「`.aos/` 是機器的、人不碰」打架**｜依據：WRITER-BRIEF 4.1 末段＋4.11 第 1 條｜**卡在哪**：LLM 世界是一塊地，它有自己的 `main.aos.json`、自己的 `.aos/`，是人要編的東西；卻預設塞在家的 `.aos/` 裡面（機器的地盤）。而且路徑深到 `$AOS_HOME/.aos/llm/.aos/inbox/`，人念都念不順。｜**怎麼繞**：原型照 `layout.Home().llm_world` 走（預設 `.aos/llm`，可以用使用者層 config 的 `llm_world` 搬走），`aos llm init` 順手把實際位置寫回 `llm_world` 欄，這樣至少 `cat config.json` 看得到它在哪。｜類別：spec 沒講｜擋路程度：小
- **一本帳簿、多個 LLM 世界，帳上分不出來**｜依據：WRITER-BRIEF 4.7 帳簿路徑固定 `$AOS_HOME/.aos/ledger.jsonl`｜**卡在哪**：`llm_world` 可以改，代表同一個家底下可以有不只一個 LLM 世界（或同一個世界被搬過位置），但帳簿的 9 個欄位裡沒有「哪個 LLM 世界處理的」。`from` 是投遞者，不是處理者。｜**怎麼繞**：原型不加欄位（欄位名不准改），靠 `unit` 間接分辨。｜類別：看不見的狀態｜擋路程度：小
- **`inbox.process()` 不碰 `kind:"llm"`，所以「驗證＋隔離無效投遞」得再寫一遍**｜依據：WRITER-BRIEF 4.5 I-06＋`aosp/inbox.py`｜**卡在哪**：`inbox` 已經有一整套「驗不過就搬到 `inbox/rejected/` 並回信給投遞者」（`_reject_to`），但它是私有的，而且 `process()` 刻意跳過 `llm`。LLM 世界只好自己再寫一份隔離邏輯，於是我這份**不會**回信給投遞者，行為跟 `exec` 那邊不一致。｜**怎麼繞**：原型自己 `inbox.validate()` ＋ `os.replace` 到 `inbox/rejected/`，並在 `notes` 印出隔離到哪。要修的話是把 `_reject_to` 開成公開函式。｜類別：多餘的動作｜擋路程度：小
- **`aos llm serve` 不帶旗標時停在哪，沒定義**｜依據：WRITER-BRIEF 4.10 `aos run` 有 `--steps`／`--every`／`--until`，4.7 沒說 `llm serve` 的預設｜**卡在哪**：不帶旗標時「永遠跑下去」對自動化很危險（我被要求絕不能在自動流程裡卡住）。｜**怎麼繞**：原型當成 `--until idle`，而且**印一行說明它自己改了預設**，不默默決定。｜類別：spec 沒講｜擋路程度：小
- **`prompt` 只能是路徑，人想手打一句話沒有入口**｜依據：WRITER-BRIEF 4.7｜**卡在哪**：`prompt` 是「路徑，指向 prompt 檔」，所以人要試一句話得先自己開一個檔。｜**怎麼繞**：`aos llm ask "<一句話>"` 幫人把字串落成 `<LLM 世界>/.aos/llm-ask/<id>.prompt`，結果落在同一層的 `<id>.out`，兩個檔都留著給人看。給檔名也照收。這是指令面的糖，請求格式沒動。｜類別：多餘的動作｜擋路程度：小

## 範例與說明書

- **情境**：寫 `call-sync`／`call-async`，父地要開一塊子地｜依據：WRITER-BRIEF 4.1／02 層｜**卡在哪**：`aos init` 一次只認一塊地；父子兩塊地要跑兩次 `mkdir`＋兩次 `aos init`，沒有「連子地一起建」的旗標或子命令，寫一個最小的父子範例要敲 4 行指令外加手動 `mkdir child`｜**怎麼繞**：run.sh 裡把兩個 init 都列出來，順手 `mkdir -p child` 保底｜類別：多餘的動作｜擋路程度：煩
- **情境**：`hello` 範例三步一串，要看到「印出來」的結果｜依據：WRITER-BRIEF 4.2（inst 的 expect／結束碼判定）｜**卡在哪**：一步跑完就推進一格，三步要敲三次 `aos exec`；而且串跑完的同一格堆疊框 `${frame}` 就被刪掉了（`execute.py` 的 `_drop_frame` 在 cursor 變成 `end` 那一步同時執行），所以想「從外面 cat 堆疊框裡的檔案」看最終結果會撲空——沒地方寫清楚「串做完，中間值就消失，要看結果得去 `stdout` 或自己安排一個串外的落點」｜**怎麼繞**：run.sh 改成從 `.aos/ticks/*/results/*.stdout` 撈非空檔案，而不是去讀已經被刪掉的 `${frame}/copy.txt`｜類別：看不見的狀態｜擋路程度：煩
- **情境**：故意讓原稿的一步少寫 `kind`｜依據：WRITER-BRIEF 4.2｜**卡在哪**：無——`aos exec` 直接印
  `錯誤：原稿 main.aos.json 第 1 步 少了 \`kind\``
  `下一步：改原稿或模板`
  退出碼 3。講清楚是哪個檔、第幾步、少哪個欄，這條夠指路｜類別：（對照組，不算擋路）｜擋路程度：小
- **情境**：故意把 `then` 打錯字指到不存在的步名｜依據：WRITER-BRIEF 4.2｜**卡在哪**：無——`aos exec` 印
  `錯誤：步 \`a\` 的 \`then\` 指向不存在的步名 \`bbb\``
  這條在**編譯期**就攔下來（`loader.check_program`），不用等跑到那一步才炸，比我原本以為的好｜類別：（對照組）｜擋路程度：小
- **情境**：故意投遞一個 `kind:"inst"` 但沒帶 `inst.argv` 的投遞物｜依據：WRITER-BRIEF 4.5｜**卡在哪**：無——`aos deliver` 印
  `錯誤：投遞物不合格（bad_inst）：\`kind:inst\` 要帶 \`inst\` 物件，且 \`argv\` 是非空陣列`
  `下一步：看 WRITER-BRIEF 4.5 投遞物欄位`
  講出了 reason 代碼＋原因，但「下一步」只叫你去讀 spec 文件，沒指出具體要改哪個欄位值——跟前兩條比起來指路力道弱一截｜類別：錯誤不指路｜擋路程度：煩
- **情境**：對一個沒 `aos init` 過的目錄下 `exec`／`status`｜依據：WRITER-BRIEF 12（指令面）｜**卡在哪**：無——兩個子命令都印
  `錯誤：<路徑> 不是一塊地；先跑：python3 proto/aos.py init <路徑>`（exec，退出碼 4）
  `錯誤：<路徑> 不是一塊地`／`下一步：python3 proto/aos.py init <路徑>`（status）
  連指令都幫你打好了，這條算是這次測試裡「錯誤最指路」的一條｜類別：（對照組）｜擋路程度：小
- **情境**：`call` 步的 `child` 打錯字（子地路徑不存在／不是地）｜依據：WRITER-BRIEF 4.2（call 的三態）｜**卡在哪**：`execute._do_call` 印
  `失敗停在 \`ask\`（not_a_land：子地 <路徑> 不是一塊地（沒有 .aos/layout.json））`
  講出了絕對路徑跟原因，但沒講「下一步」是要去 `mkdir` 還是去 `aos init` 那個子地——跟頂層 `_die()` 那套「錯誤＋下一步」兩行格式不一致，這裡失敗訊息全塞在 `fail_reason` 裡，沒有單獨的「下一步」提示｜類別：錯誤不指路｜擋路程度：煩
- **情境**：`call` 步 `mode:"async"` 沒有 daemon 在跑時要怎麼動｜依據：WRITER-BRIEF 4.11 第 6 條（主編補，沒把握）｜**卡在哪**：exec 會自己 `Popen` 一支 detach 的 `aos run <子> --register`，但父地的 `aos exec` 完全不等它、也不回報這支背景行程有沒有真的啟動成功（`subprocess.Popen` 沒檢查 spawn 有沒有成功、log 寫到子地的 `.aos/detached.log`，要自己去翻才知道發生了什麼）。第一次寫這個範例時，因為 `run.py`／`daemon.py` 那兩支還是空檔，detach 起來的行程直接 `AttributeError` 崩潰，但父地完全沒感覺、`await` 只會一直 HOLD 到 `max_ticks` 逾時——從父地這邊看不出「子地的背景行程根本沒起來」跟「子地還在正常跑只是比較慢」的差別，得去翻 `child/.aos/detached.log` 才知道｜**怎麼繞**：等別隊把 `run.py` 補完就自動好了（這次確認已經補完，範例現在會過）；但這個「detach 失敗時父地看不見」的洞還在，記下來｜類別：看不見的狀態｜擋路程度：擋路
- **情境**：`llm-echo` 範例，`aos llm ls` 印出處理單元清單時欄位對齊用固定寬度格式化｜依據：WRITER-BRIEF 4.7｜**卡在哪**：非擋路項，只是備註——`_op_ls` 的人類可讀輸出把 `unit`/`tier`/`endpoint` 用 `%-12s` 之類固定寬度撐版面，這對 README 抄指令範例沒差，純粹路過看到記一筆｜類別：spec 沒講｜擋路程度：小
- **情境**：`llm` 請求要跨兩塊地協調（父地 `await` ＋ LLM 世界 `tick`）｜依據：WRITER-BRIEF 4.7｜**卡在哪**：沒有一支指令能「父地 exec 順便把 LLM 世界的請求也處理掉」；寫 `run.sh` 得手動交替呼叫 `aos exec <父地>` 跟 `aos llm tick --land <LLM世界>`，兩邊各自的迴圈要對齊格數，稍微算錯順序（比如先 tick 再 exec）結果會差一格。四個範例裡這個的「一鍵重跑」腳本最長最囉唆｜類別：多餘的動作｜擋路程度：煩

## 測試

- **情境**：驗「aos stop <地> 該寫控制收件匣的檔」｜依據：WRITER-BRIEF 4.6｜**卡在哪**：任務簡報寫「aos stop <地> 寫出控制收件匣的檔」，但實際 `daemon.py` 的 `cli_stop` 刻意在 `who_runs()` 查不到任何人在跑這塊地時（登記表沒有 running 且 pid 活著、鎖檔也沒有活 pid）直接印「沒人在跑，什麼都沒做」就回 0，**不寫**任何控制信（程式裡有註解說明這是故意的：先投進去只會變成下一趟 run 的舊帳）。一開始沒注意到這個前提，測試對著一塊「沒人在跑」的地呼叫 `aos stop`，斷言控制收件匣有檔，結果假紅——後來才發現是我沒搭好情境，不是 aosp 的 bug｜**怎麼繞**：測試改成先手動把自己的 pid（保證活著）寫進 `.aos/lock`，讓 `who_runs()` 查得到，`aos stop` 才會真的投信｜類別：spec 沒講（簡報漏了這個前提）｜擋路程度：煩
- **情境**：驗「同一格兩條串搶同一組 exclusive，只有一條跑」｜依據：WRITER-BRIEF 4.3｜**卡在哪**：沒有任何 CLI／API 可以「幫我在同一格塞兩條同時 running 的串」——`aos exec`/`aos run` 一次只會照 series.json 現狀跑，series.json 本身也沒有子命令可以新增第二條串。只能繞過所有指令，直接 import `aosp.series`，用 `new_series()` 手動組兩條串塞進 `series.json` 再存檔，才測得到 exclusive 搶佔的行為｜**怎麼繞**：`series.load_or_start`/`new_series`/`save` 直接組 baton，繞過 CLI｜類別：看不見的狀態｜擋路程度：煩
- **情境**：驗「call 的三態（子還沒閒、子閒了但沒結果、子閒了且失敗）」跟「await 的三態」｜依據：WRITER-BRIEF 4.2/4.5｜**卡在哪**：要讓子地「失敗」或讓某個結果落點「壞了」，唯一辦法是直接 import `aosp.status` 呼叫 `status.write_failed()` 自己寫一份 `<result>.status.json`，或讓子指令自己用一行 inline python 產生狀態檔——沒有任何 `aos` 子命令可以「回報這格失敗」。同樣，要驗「三態裡『還沒好』」也只能直接看檔案存不存在，沒有子命令可以問「這個結果落點現在是哪一態」（`status.triple()` 是純內部函式，不是 CLI）｜**怎麼繞**：測試直接 import `aosp.status`／`aosp.inbox` 組資料、或讓子行程的 inline python 腳本自己動手｜類別：看不見的狀態｜擋路程度：煩
- **情境**：驗「無效投遞（少 kind／kind 不認得／kind:inst 沒 argv）被 process() 隔離」｜依據：WRITER-BRIEF 4.5、I-06｜**卡在哪**：`inbox.deliver()` 本身完全不驗證內容（只要求有 `id`），驗證是 `aos deliver`（CLI 層）跟 `inbox.process()`（消費時）各自做一次，兩層驗證規則理論上要一致但沒有共用測試或型別保證。這代表要測「process() 怎麼隔離無效投遞」，沒辦法透過正常的 `aos deliver` 走到（CLI 會先擋掉），只能繞過 CLI，直接呼叫 `inbox.deliver()` 塞一個手造的壞物件進收件匣，再呼叫 `inbox.process()`｜**怎麼繞**：繞過 CLI 直接呼叫 `inbox.deliver()`｜類別：spec 沒講（沒講兩層驗證是否保證同步）／看不見的狀態｜擋路程度：小
- **情境**：驗 llm.py 假後端（echo:/fail:）的行為與帳簿欄位｜依據：WRITER-BRIEF 4.7｜**卡在哪**：`proto-interface.md` 只釘死 `cli_llm(args)` 這個入口，`init_llm_world()`／`serve_once()` 這兩個任務簡報點名要測的函式沒有另外一份簽名文件（不像 `run`/`daemon` 有 `args.xxx` 欄位表可以照抄）。寫測試時只能猜測呼叫方式（先試零參數、再試傳 `home`），用 `hasattr`/`try except TypeError` 防呆，兜不起來就整支測試 skip，而不是整批炸掉｜**怎麼繞**：`_try_init_world`/`_try_serve_once` 兩層防呆＋按需 SkipTest｜類別：spec 沒講（llm.py 內部 API 沒有跨隊釘死的合約）｜擋路程度：煩
- **情境**：驗 daemon start/stop 的真實 detach 行為｜依據：任務簡報第 8 條｜**卡在哪**：起一支真的背景 daemon、等它把登記表的地改成 running、再 stop 等它改回 stopped，這條路徑本質上跟時間賽跑，用輪詢＋10 秒逾時已經算穩了，但仍然是這套測試裡最脆弱的一支，跟 CI 環境的行程排程有關｜**怎麼繞**：照任務簡報建議，用 `AOS_TEST_DAEMON=1` 環境變數開關這條，預設 skip，跑起來時輪詢不用固定 sleep｜類別：多餘的動作（測試基礎設施層面的無奈，非 aosp 本身的問題）｜擋路程度：煩

