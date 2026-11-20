# proto8 討論紀錄：2026-11-20

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [T7 第 9 步回公司（14-真機驗證）](../10/two-machines/14-真機驗證.md#第-9-步回公司那一步-11-20-實跑) | two-machines T7 第 9 步回公司那一步公司機代跑、全過：pull 到 rv day 2、兩台起來不用換台指令、ann 答 back at office、error: 0 行、git status 只有 stack 狀態檔；T7 全部跑完（第 5 步 codex 先前已跳過），~/code/rv 沒 commit、沒 push |
| [初始 kernel＝llm＋權限沙箱（aos-init-kernel-1120）](aos-init-kernel-1120/README.md) | 調查＋發想：今天灌 kernel 實際只灌 llm kernel；權限那側沒有隨灌 kernel 裝上的東西（站與 kernel_gate 預設不裝，limits／sub:N 在 daemon 本體，guard／sandbox 在 agent 與工具）；四種切法與八題待裁，等使用者 |
| [編譯的通用底座與函數當工具／hook（aos-compile-base-1120）](aos-compile-base-1120/README.md) | 只查只寫：能編譯的只有 agent 與工具、兩支共用 0 行；底座攤五個形狀（甲～戊）；函數當工具／hook 分「抽出來」與「回頭跑」兩大類，小原型兩種都走通；八題待裁，等使用者 |
| [aos-gdb 問答（aos-gdb-問答-1120）](aos-gdb-問答-1120.md) | 使用者問 a.stop() 是不是阻塞、斷點 id 為什麼是 xxxx_1；只讀快查：把手沒有 a.stop，暫停是 a.bp.pause()、停掉是 a.ctl.stop()，正在跑的一格不被打斷、扣在斷點上停不了，id 是施工線順手定的「種類_N」且刪了會重用；選項框四題已答（pause 加 wait=、不等回可查的物件 is_done()、id 純數字搭配屬性待確認、add 回物件），還沒施工 |
| [hook 點的介面與耦合（aos-hook-iface-1120）](aos-hook-iface-1120/README.md) | 只查只寫：hook 是程式走到時機明叫、不是每圈觸發；引擎一份、事件表 agent 與 kernel 各一份同形狀，表裡沒有欄位與誰觸發，沒有提供點的條文；fsm 加一個點約 16 處、手抄清單約 19 處（5 處漏改不報錯）；五個形狀、十題待裁，等使用者 |
| [kernel 的資源基底與排程介面（aos-kres-1120）](aos-kres-1120/README.md) | 發想：資源基底＝請求帶的自由 json＋kernel 放話 schema＋粗化／細化＋記帳，今天用 llm kernel 的 hook 能做單人版，缺宣稱的約定位置、帳不收宣稱、schema 放哪與跨體系；排程介面「骨架本來就有」對一半：骨架有叫「誰先」的口，規則每包自寫、hook 碰不到；repo 外小原型；九題等使用者。使用者答了四題（08：「給位置和格式。當然，這都是可選的，kernel自己可以選擇不給。」、誰判與經驗存哪先不定、選「把原型接成 hook 試一次」）；試跑（09，線 aos-kres-try-1120）：跑起來了，換規則不用重起，hook 改的優先序這一輪不算數（實測），卡點是宣稱沒約定位置、帳不收宣稱、兩支 hook 的格對不起來、hook 壞了整站停；五題還沒問 |
| [aos-gdb 施工：wait=、純數字 id、斷點物件（aos-gdb-wait-1120）](aos-gdb-wait-1120.md) | 照使用者 11-20 裁定改 a.bp：resume／step／pause 加 wait=（False＝回 Pending，is_done() 問好了沒、wait() 拿同樣結果）；id 改純數字、刪了不重用（計數器在 agent 的 stack，觀察者從看的每一隻一起拿）；add 回斷點物件，屬性每次重查、刪了讀報錯；自己取名 id="mine" 照留（替使用者選的）；乾淨複本假腦全過，沒在 repo 跑 install.py，等使用者點頭後試 |
| [「提供 hook 點」的介面：設計與施工計劃（aos-hook-plan-1120）](aos-hook-plan-1120/README.md) | 只出稿：使用者選「宣告式＋小函式都做」「任何子程式，含非 Python」「在 loop 層加通用的點」；設計＝每個提供者一份 hook_points.json、小庫 aos.hook_point、指令 aos-hook fire（取代 hook_fire）、aos-loop 的 before_run／after_run（沒人掛每圈約 2 微秒、有人掛每點約 18 毫秒起跳）；加一個點從約 16 處變 2 處；六條衝突、十四題待裁、施工七刀（1、2、4 刀可先做），等使用者；使用者 11-20 已答七題、四個點都跟著停改掉設計預設、還有十題沒問（見 13） |
| [「編譯變成整套一個 Python 程式庫」設計稿與施工計劃（aos-pylib-plan-1120）](aos-pylib-plan-1120/README.md) | 只出稿：寫定義變成物件（defs.Agent、.dry_run() 只算、.compile(夾) 寫，defs.main 旗標不變）；Python 函數用新模組 fn（@fn.tool、@fn.hook、fn.block）標成工具與 hook，編譯時抽成定義夾的 fn/名.py；defs.extern(目標) 編成連結並附「別濫用」說明；跟已定的逐條對照、衝突六條、待裁十題、施工六刀（只有第 0 刀不依賴任何題）；Argon 審一次、採納表 |
| [編譯程式庫第 0 刀：共用的底 spec_base（aos-pylib-k0-1120）](aos-pylib-k0-1120.md) | 新檔 py/aos/spec_base.py（SpecBad／DefBad、推名字、--compile／--dry-run 小旗標殼、寫檔後端：文字、JSON、程式檔 755、連結，可帶一層子夾）；agent_spec、tool_spec、tools_def 改用它；兩個骨架重新編譯的產物與各旗標輸出逐 byte 不變，既有測試沒改全過；跟設計稿對不上的八處與處理 |
| [「提供 hook 點」的介面：施工第 1 刀（aos-hook-k1-1120）](aos-hook-k1-1120.md) | 只加不改：五份 hook_points.json（loop、agent-fsm、eca、mcp、kernel；before_run／after_run 先宣告標 not_fired_yet）、小庫 aos.hook_point、兩支測試；宣告跟現在的 EVENTS 逐項相同；文件、self_hook 說明、知識庫 17 項既有漂移列成已知、沒改；全套測試跟基準逐夾相同；使用者「兩邊都開工」 |
| [編譯程式庫第 1 刀：fn 與工具骨架（aos-pylib-k1-1120）](aos-pylib-k1-1120.md) | 新模組 fn（@fn.tool、@fn.hook、fn.param、fn.fail、fn.block、fn.main，本體 fn_mark／fn_run）；工具骨架換成一個函數加 @fn.tool＋fn.main(add)，說明與參數自動抽與明寫都收、明寫的贏；tools_def 跟著，舊寫法不留；骨架產物與四個旗標、直接執行的輸出逐 byte 不變，全套測試跟基準相同；手寫 @fn.hook 經 agent 的 hook 引擎攔得下；三份共用文件被別線佔著沒改；沒在 repo 跑 install.py |
| [編譯程式庫第 2 刀：defs.Agent 物件與 agent 骨架改寫（aos-pylib-k2-1120）](aos-pylib-k2-1120.md) | defs.Agent 物件（.dry_run() 只算、.compile(夾) 寫）、defs.main(物件)、fsm 單獨編譯、defs.load 回物件且欄位小寫（base.pack）；defs.compile／defs.write 拿掉；骨架、教學、測試改寫後產物與輸出逐 byte 不變；新檔 agent_spec_agent.py、spec_unit.py，測試拆成五支；對不上處十條 |
| [aos-hook-k4-1120](aos-hook-k4-1120.md) | hook 介面施工第 4 刀：新指令 aos-hook（fire／points／check），C++、shell 也能發 hook 事件；只加不改、--agent 等第 2 刀 |
| [寄信問 kernel 的基礎協議（aos-kask-1120）](aos-kask-1120/README.md) | 調查＋發想：今天唯一的問句信 procs_state_path 由 daemon 本體回、框架站只轉寄；問腦總機把問句當 LetterBad 拒（aos-llm send 也不讓它出門），掛 proc 的站轉給 daemon 回 applied true；自動回信能放七處、三個 hook 都不能回信；「另外一個 json」的擺法與跟 interfaces.json、hook_points.json 的分工；原型一支 before_verdict hook 兩種 kernel 都回了 json，但一問兩答、灌 30 封拖慢普通請求；八題等使用者 |
| [aos-gdb 三小題施工：cancel()、set 回物件、名字補零（aos-gdb-small-1120）](aos-gdb-small-1120.md) | 照使用者 11-20 選的三小題：Pending 加 cancel()（只是不等、送出的不收回，之後 outcome cancelled）；a.bp.set 回斷點物件；hook 名、小格夾、觀察者 proc 名的號碼補零到 4 位（gdb_0012，12 個以上照號碼排；.id 照舊是 int）；乾淨複本 gdb 測試 66 支全過、暫存樹假腦實跑 12 個斷點與 cancel；沒在 repo 跑 install.py |
| [agent_def new 改成純粹 cp（aos-defnew-cp-1120）](aos-defnew-cp-1120.md) | 拿掉 tools 檔相對路徑的換算（rebase_tools），整夾照抄、路徑一律不改寫不警告，只寫 lineage；新測試逐 byte 比、repo 每份範本也比；暫存樹假腦實跑：抄出的定義用自己那份工具；repo 裡沒有登記檔寫相對路徑，沒東西壞；使用者第 10 題「純粹的cp過去」 |
| [編譯程式庫第 3 刀：函數工具與 hook 抽成 fn/<名>.py（aos-pylib-k3-1120）](aos-pylib-k3-1120.md) | agent.py 的 @fn.tool／@fn.hook 函數放進 tools／hooks，編譯時抽成定義夾的 fn/<名>.py；新 fn_spec.py、agent_spec_hooks.py；函數用到 agent.py 自己的東西、defs／std、旁邊模組都 SpecBad；沒用函數的產物逐 byte 不變；假腦實掛工具被叫、hook 攔得下；對不上處十一條 |
| [aos-hook-drift-1120](aos-hook-drift-1120.md) | hook 待裁第 8 題：17 項文件漂移補齊、一致性測試守住；eca 中途來的 /compact 信過兩次 before_queue 實跑屬實，沒修 |
| [aos-kinit-tpl-1120](aos-kinit-tpl-1120.md) | 照初始 kernel 八題的答案改文件與 start-api：最小核心＋llm 件＋權限件，另有一串可選件待定；llm kernel 改掛同板（llm/）、加選裝不開的權限站 perm/；重建步驟單跟著改；假腦實跑 |
