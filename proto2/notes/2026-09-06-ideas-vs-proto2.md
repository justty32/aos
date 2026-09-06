# 2026-09-06 構想（ideas 13 章）對 proto2：哪裡像、哪裡差、還缺啥

← [proto2/README](../README.md)｜構想入口 [ideas/README](../../wf/workflows/ideas/README.md)｜反思 [reflections](../../wf/workflows/ideas/reflections.md)｜今天原話 [world-clock-agent](2026-09-06-world-clock-agent.md)

## 一句話結論

骨幹很像——資料夾就是世界、一格一步、daemon 管鐘、LLM 是另一個資料夾、agent 是狀態機——這些都做出來了，而且比構想寫的更簡單。差最多的是「機器層」那一整塊（04、05、09 三章：json 指令批、拆平、接力棒、三次改名、失敗三態），proto2 全部不要，換成一句 shell 的 `.aos/inst`；而構想只給了一行描述的「工具」，在 proto2 反而長成最大的一塊（16 個工具包）。

## 一章一章對

### 01 aos 是什麼、拿什麼尺量 — **部分**
- 構想：agent loop 是 CPU，aos 是它上面的 OS。可預測性最優先，其次錢；第一版留成本帳插口；兩把尺（自報 vs 實際、多跑幾次的分布）今天就能量。
- proto2：錢有量（LLM `usage/` 按模型、按 requester 兩層；`cost` 包記每次工具的時間、token、錢）。可預測性沒有量：沒有固定題、沒有跑幾次看分布。
- 差：成本帳做得比 A-03「只記一行」多；A-04 拍板的兩把尺一把都沒有。「停掉隔天再來記憶還在」驗過（whole-system 第 8 步，重啟後還記得暗號）。

### 02 資料夾就是 list — **方向變了**（使用者今天改的）
- 構想：`.aos/` 是機器的地盤、人不碰；人寫原稿放頂層，父點名時載入器讀進去。子資料夾父點名才開。
- proto2：`.aos/` 只剩一句 `inst`，其他全平鋪在本體；沒有載入器。子資料夾父點名才開＝父的 inst 多一行 `aos-exec kids/x`。三種處置（讀／開／轉手）都有：讀檔、`aos-exec` 子、寄信。
- 差：使用者續四原話「`xxx/.aos/` 下可以只有一個 inst……都可以直接放在 xxx 下」，把「機器地盤」拿掉了。這是反思改的，不是順手偏掉。

### 03 一塊地：身分、生死、git — **部分**
- 構想：路徑就是身分、刪＝死、搬家＝死＋生但要有 `aos mv`；父刪子、daemon 巡邏保底；快照交給 git，`.gitignore` 是全域規範；記憶就是地。
- proto2：一個路徑一個鐘、id 是路徑的 percent-encoding（有了）。daemon 巡邏發現鐘死了是**自動重開**，不是清登記——跟構想反過來，但更合使用者續二「發現有鐘 dead 了，自動把他重啟」。`kids_kill` 預設留資料夾。`aos-user new` 會生 `.gitignore`。記憶＝`prompts.json`＋`memory`／`bigmem` 包。
- 差：沒有 `aos mv`，搬家後 contacts／parent／kids 的絕對路徑不會自己修（play/hooks）。使用者今天說「先不管 git」，所以 git 那段沒動是刻意的。

### 04 `.aos` 裡面 — **方向變了**（使用者今天改的）
- 構想：`.aos` 裡是一段命令腳本，攤開成一筆一 json 的指令，一回合一批、批內沒資料流；兩層之間只有一座橋 `aos run <子>`。
- proto2：`.aos/inst` 就是一段 shell 文字，整段丟 `os.system()`；沒有批、沒有 json 指令。橋還是那一行（`aos-exec kids/x`）。「跳轉＝寫下一格」有最小版：`aos-loop` 讀→清→跑，命令自己把下一步寫回 inst。
- 差：反思那句「若是資料夾就跑 .aos 內的 insts.json」再簡化成純文字。README「目前刻意不做」明列「批次結構」。

### 05 寫→編譯→執行 — **沒有**（刻意）
- 構想：寫（不確定）→編譯拆平（確定）→照接力棒走（確定）；全塔 json；接力棒 `series.json` 記進度；停止＝這次沒產新指令。
- proto2：沒有編譯、沒有接力棒、沒有兩種壽命。停止只剩 `aos-loop --stop-when-empty`（形狀一樣）。agent 沒有「跑完」，靠 idle 空轉。
- 差：這章是整套裡差最多的。反思「太早考慮邊緣狀況」直接把它砍了。

### 06 時間與時鐘 — **有了**
- 構想：一格＝一次 exec、一個鐘＝一個 run；同步子借父鐘、脫節子自己有鐘；LLM 永遠脫節；時間要有界，主線是限 PATH、timeout 不是首選；一格有預算。
- proto2：`aos-exec`／`aos-loop` 就是；shared／own 小孩就是同步／脫節；LLM 資料夾一格「絕對不等網路」，worker 在背景。
- 差：有界靠 `sh` 60 秒硬砍，沒有限 PATH（反而自動把工具目錄加進 PATH）；一格預算沒有；「有變動才動」（F-03 門鈴）沒有，全是固定 interval 輪詢。使用者今天「tick 內卡住怎麼辦」自己說「再想想吧」，所以還懸著。

### 07 daemon — **做得比構想好**
- 構想：時鐘總管（登記／走／一次全停）、每塊地一支子行程、REPL 桌子、LLM 管家；daemon 掛了鐘照走、重啟對帳。
- proto2：`aos-daemon-kernel start|stop|ls`＋`aos-daemon register|unregister|pause|continue`；一鐘一個 `aos-loop` 進程、自己一個 process group；`requests/` 就是桌子；stop→start 認領舊 pid；dead 自動重開。LLM 併發由 LLM 自己數（G-06 拍板照做）。
- 差：多了構想沒有的 `pause`（SIGSTOP）；kernel 被 SIGKILL 時鐘會變孤兒（SESSION-LOG 已記）。systemd 使用者說以後。

### 08 agent — **有了**
- 構想：agent 就是一塊地，不進核心；三步循環、小狀態機；停不是死；限制參數（格數／呼叫數／token，H-03 拍板）；使用者住 `~` 也是 agent。
- proto2：五態狀態機（idle→llm→wait→act→collect）、信箱按來源分資料夾、outbox、kids、等 LLM 滿 60 格提示。使用者是 `aos-user` 殼，README 明說「暫時的」。
- 差：限制參數沒做（只有 60 格等待、studio 的軟預算）；agent 從不「睡」，每格都掃一次信箱。借父鐘 vs 自己登記兩種都有、預設 shared（照 H-05 原建議，沒跟 spec 的反轉）。

### 09 呼叫、交接、失敗 — **部分**
- 構想：指令＝POSIX 呼叫、嚴格解析寬鬆執行、三次改名交接、三態（還沒好／好了／壞了）、結束碼兩頻道、env 預設不繼承（I-07 拍板）。
- proto2：LLM 請求那條有三態（`requests/`→`running/`→`done/`＋結果檔帶 `error`；worker 死了補 `worker died`）。寫 JSON 走 `.tmp` 換名（原子）。鎖、fsync、重試「刻意不做」。
- 差：三態只在 LLM 這條，工具／小孩／job 那條沒有（小孩鐘死了父不知道，job 死了整個重跑）。env：daemon `legacy_env` 預設 true，跟 I-07 相反，文件自己說「下一步改 false」。play 撞到結果所有權競速（agent 拿走結果、LLM 又補 worker died）。

### 10 門房 — **沒有**
- 構想：tmpfs→inotify→FUSE，門房只記不做。
- proto2：完全沒有，今天也沒提。`chattr +i` 鎖設定檔只停在發想（T-27）。
- 差：合理，使用者裁「何時做未定」。

### 11 工具與通訊錄 — **做得比構想好**
- 構想：一工具一檔登記表、給模型一行純文字、封套、`slow` 欄、通訊錄三欄。
- proto2：一包一檔 `packs/*.py`（自帶 TOOLS／PROMPT／run／掛勾）、直接走後端原生 tool_calls、`prompt-overrides/`、`toolsmith` 讓 agent 自己造工具；`contacts.json` 名字→路徑；慢工具不靠 `slow` 欄，靠模型自己選 `run_long`。
- 差：跳過了構想「先自己嚴格檢查再升級成原生工具呼叫」那一步。「登記表是行為契約、代價寫進描述」沒了；叫錯工具只回一句「沒有這個工具」字串。

### 12 指令面、分圈、正本 — **有了**（指令面）／**沒有**（分圈與正本）
- 構想：exec／run／daemon 三名字；agent 那組 init／say／listen／talk／state；核心四圈；一份正本規範；版面歸屬表。
- proto2：`aos-exec`／`aos-loop`／`aos-daemon-kernel`；`aos-user new|say|listen|talk|status|spawn|team`（幾乎照構想）。沒有分圈（`aos_agent.py` 1066 行混殼、狀態機、建隊）；沒有正本、沒有版本欄；README 就是唯一文件。
- 差：使用者續一「後續會把使用界面和底層分開，目前粗糙原型先這樣」——刻意。但欄位已出現兩套說法（requester、token 名、截斷長度，見 play/README）。

### 13 洞與先玩 — **有了**
- 構想：先玩兩級劇本，不打分數、只記阻礙；順手記四條橋撞到的實例；玩完選 OS 第一塊。
- proto2：17 份 play note＋whole-system，格式就是「做的坑／玩的坑／缺接點／自評／邊緣狀況」；兩級劇本都玩到（`coder` 模板、`studio` 七人）。
- 差：tmpfs、三支串各跑五次、二十幾支重現腳本——都沒做。「最常撞到的坑」那張表就是構想要的阻礙清單，但沒有任何一條回頭對到 13 章的洞。

## 還缺什麼

### 使用者明說要、還沒有
- tick 內卡住怎麼辦（原話「再想想吧」）——現在只有 `sh` 60 秒硬砍。→ 續、docs/fs
- 介面與底層分開（「後續會把使用界面和底層運行機制分開」）——`aos-user` 與 `aos_agent.py` 還混著。→ 續一
- 使用者本人變成一個 agent（「使用者自己也是一個 agent……特殊地位」）——還是殼＋`inbox/user` 短路。→ 續五
- 新鐘／新 agent 設身份與權限（「設置其身份與權限的」）——`user` 欄要 root 才有效，identity 停在建議稿。→ 續五、notes/tools/identity-and-env
- 管 PATH 和環境、不讓 agent 弄壞自己的 `.aos`——`legacy_env` 預設 true，`.aos/inst` 不鎖。→ 續五、docs/identity-and-env
- daemon 重啟接續——有了；kernel 被 SIGKILL 的孤兒鐘沒處理。→ 續一、SESSION-LOG
- 真的拿 proto2 開發一支 python 程式（「嘗試開發一個python程式」）——只玩到 coder 模板小事跑 66 格。→ 續五、play/newagent
- systemd、幾千個鐘的管理介面——使用者自己說以後。→ 續一

### 構想有、今天沒提、可能還想要
- 可預測性的兩把尺（A-04 拍板）。→ ideas/01
- agent 硬上限：格數、呼叫數、token（H-03 拍板）。→ ideas/08
- `aos mv`／搬家後路徑自修（C-04 拍板）。→ ideas/03、play/hooks
- 工具與小孩那條的失敗三態（I-02 拍板只在 LLM 落地）。→ ideas/09、play/kids K11
- env 預設不繼承（I-07 拍板）。→ ideas/09、docs/identity-and-env
- 「有變動才動」的門鈴（F-03）；agent 沒事時真的睡。→ ideas/06、08
- 工具描述帶「代價」（慢、貴、不確定）。→ ideas/11
- 門房第一級（偵測出生／死亡、記帳）。→ ideas/10
- 一份說了算的格式表＋版本欄。→ ideas/12
- 通訊錄天然有一格 `~`。→ ideas/11

### 兩邊都沒想到、玩的時候撞到
- 小模型不照工具說明走，乘法繞 84 格、看資料夾 66 格。→ play/kids K7、newagent
- 旁線結果不是當格回來，模型「自己等自己」。→ play/README
- reasoning 吃光額度、正文空白。→ play/think、whole-system
- 結果所有權競速：agent 拿走結果，LLM 又補 worker died、灌水用量。→ play/whole-system
- world／home／相對路徑／通訊錄別名不是同一件事，算錯就投到沒鐘的地方。→ play/README
- 少開任何一顆鐘，表面只像「一直沒回」。→ play/mcp、whole-system
- shared 小孩跟父共用一份 clock log，行上沒名字。→ play/whole-system
- 各包直接摸 `state.json`、`clocks/`、父的 inst 繞接點。→ play/README、docs/packs-api 第 7 節
- `today_usage` 只算目前 endpoint，名字卻像全日總數。→ play/whole-system

## 哪裡比構想好

- `aos-exec`（41 行）＋`aos-loop`（69 行）：反思那句「檔案就執行、資料夾就跑 .aos」直接落地，比 04／05 兩章加起來小一百倍，而且真的能跑整套。
- shared 小孩＝父 inst 加一行：借父鐘不經 daemon，暫停就是把那行註解掉（T-20），最土也最看得懂。
- daemon 用 Linux 輪子（process group、SIGSTOP／SIGCONT、pid 認領）：G-01 拍板每地一支子行程，順手白拿到 `pause`，構想沒這個。
- LLM 資料夾 `requests/`→`running/`→`done/`＋`aos-llm ls`：F-07「另查請求狀態」在這裡是真的能看，拔掉鐘一眼看出排隊沒人做。
- `packs/*.py` 帶 PROMPT／掛勾／`prompt-overrides/`：構想只有一行描述，這裡每包能改工具結果、接旁線結果、加動態 system prompt。
- `jobs` 包 `run_long`：慢工具開脫節小地做完寄信回來（T-22），比「父每格看檔在不在」省，實測 `sleep 15` 沒卡住。
- `usage/` 按模型、按 requester 兩層＋`cost` 包：A-03 只要一行帳，這裡已經能算錢、能分帳給 studio 成員。
- play note 固定格式（做的坑／玩的坑／缺接點／自評／邊緣狀況）：正是 01 章要的「不打分數、記阻礙、附對照」。
- `aos-mcp`：讓 Claude 扮演使用者去下指令測試，構想沒想到，今天使用者臨時想到的。
- `aos-user new` 問答＋三個模板：構想 12 章 `init` 互動問答的樣子，比構想多了模板。

## 哪裡比構想差或走偏

- 工具／小孩／job 沒有失敗三態：小孩鐘死了父只能靠信箱猜，job 死了整個重跑。**要拉回**：至少 `kids_list` 顯示 alive、daemon 開一個只讀狀態接點。
- env 整包繼承（`legacy_env` 預設 true）：跟 I-07 拍板相反，金鑰 agent 看得到。**要拉回**：預設改 false，文件自己也這麼說。
- 沒有 agent 硬上限：H-03 拍過，小模型繞 84 格沒人擋。**要拉回**，很便宜。
- 各包自己摸 `clocks/`、父的 inst、`state.json`：違反 12 章「每圈只知道自己以內」。**要拉回**：補 `Ctx` 只讀接點（play/README「如果只修三件」第 2 條）。
- 只量錢、不量可預測性：01 章拍板可預測性第一。**要拉回一半**：三支固定題各跑五次記格數分布，不用改程式。
- 欄位兩套說法（requester、token 名、截斷長度）：沒有正本的後果開始出現。**拉回一半**：不寫 spec，但 packs-api.md 當契約、欄位名統一。
- 一格有界靠 timeout 硬砍不靠限 PATH：跟 06 章主線相反。**先不拉**：使用者自己說「再想想」。
- agent 永遠空轉不「睡」：跟 08 章「停不是死、有信再醒」形狀不同。**先不拉**：一秒一格便宜，LLM 沒被叫就不燒錢。
- `aos-user` 殼混了建隊邏輯：使用者說之後分。**先不拉**。
- 子 agent 自動繼承 `spawn`、孫子還能生：使用者說「之後再說」（WAIT_USER A-6）。**先不拉**。

## 使用者今天的反思 vs 舊構想

推翻的：
- 「執行 aos exec xxx，若是資料夾就跑 .aos 內的 insts.json」→ 推翻 04（json 指令批）、05（拆平、接力棒）、D-01／D-04／E-01／E-02。全塔 json 變一句 shell。
- 「太早考慮這些邊緣狀況了」→ 推翻 09 章整章（三次改名、fsync、鎖、背壓、足跡）和 13 章「最大的洞」的優先序。README「目前刻意不做」就是這句。
- 「其實不需要 linux，任何語言都行；agent 就只是一個迴圈」→ 推翻 01 章「邊緣狀況只准從 LLM 來、機器來的就是抽象漏了」那種嚴格；也拿掉 12 章「核心四圈」的必要。
- 「`.aos/` 下可以只有一個 inst」→ 推翻 02 章「`.aos/` 是機器的地盤、人不碰」與 12 章版面歸屬表。
- 「父子的聯繫與時鐘脫節與否無關，這是管理權／從屬的問題」→ 修正 06／08 章把「同步／脫節」跟「父子」綁一起的講法。proto2 的 `parent.json`（從屬）和 shared／own（時間）是兩個軸，正是照這句做的。
- 「daemon……還可以設定這個 tick 進程的 user 身份權限」→ 跟 10 章「權限很後面才做」相反，身份提早進了 daemon 設定（雖然還沒真的用）。

同一件事換說法：
- 「LLM 就是一個一直跑的 aos exec，請求丟到底下某個資料夾」＝06 章 F-02、07 章「LLM 是另一個世界」。
- 「agent 是遊戲物件，每次 aos exec 都是 process()」＝06 章「像遊戲引擎一格」、08 章逐格走法。原話就是同一句。
- 「檔案系統是最好的膠水」＝01 章「狀態必然落在檔案系統」。但理由不同：舊的是推導出來的必然（於是推出 json 塔），新的是「LLM 會用 shell、能承載任意程式碼」（於是推出 `packs/*.py` 隨便寫）。理由換了，形狀就換了。
- 「daemon 每隔一小段時間看資料夾有沒有請求」＝07 章「桌子」。
- 「信箱有子信箱，按來源分類」＝08 章「信要帶寄件人」、11 章通訊錄，具體化成「來源＝資料夾」。
- 「怪癖歸 aos-llm、讓其他使用者面對統一介面」＝11 章「aos llm 是 unix 過濾器」，多了「吃掉 `</think>`」。
- 「使用者自己也是一個 agent」＝01／08 章原話，沒變。
- 「fork 一個 process 但那樣會逃離 daemon 管束……再想想吧」＝06 章 F-05（半途超預算怎麼記），構想沒答，今天還是沒答。

## 建議下一步

1. 補 agent 硬上限（每題最多幾格、每日 token）——H-03 拍過，小模型繞 84 格那種要有東西擋。
2. 補 `Ctx` 只讀接點（daemon 鐘狀態、world／home／別名解析），讓各包不再自己摸 `clocks/` 和父的 inst。
3. 修非同步結果的所有權（結果只有一個主人、等待會睡、缺鐘直接回到聊天端）——play/README 三件裡的第一件，whole-system 實撞。
4. `legacy_env` 預設改 false，跟 I-07 拍板對齊；順便決定 `.aos/inst` 鎖不鎖（T-28）。
5. 真的拿 proto2 寫一支 python 程式（使用者自己說的），把撞到的阻礙記成一張表；同一題跑五次記格數分布，可預測性的尺就有了。
