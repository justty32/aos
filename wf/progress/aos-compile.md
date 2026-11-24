# 編譯與 Python 庫：aos-compile、aos-pylib、aos-compile-base、aos-gdb-1120 四條併成一條，install.py 已跑，只剩使用者親手試與幾個未答的題

← [progress.json](../progress.json)｜[progress 整理-1122](../../proto8/thinking/2026-11/22/progress整理-1122/README.md)

## 11-22 合併後剩的

- 四條的下一步原本都是「使用者點頭跑 install.py 後親手試」；install.py 11-21 起已跑多次（11-22 又跑），前提已滿足，只剩使用者照各紀錄試：編譯（複製骨架、改 agent.py、`python3 agent.py --compile`、ctl add）、Python 庫入口 aos.py 與 a.bp／a.look、gdb 的 wait=／Pending／斷點物件（已經掛著舊名 gdb_1 的 agent 先 `aos-agent hook rm` 再重下）。
- 「工具包靜態／動態連結做成編譯選項」已做（`--compile --static|--dynamic`）。
- 還沒答的：std 留不留在入口頂層、建斷點參數名 `id=`／`tool=`（brain_failed 是 code）、`skip`／`wait_stopped` 名字（aos-pylib）；kernel 入口替使用者做的九個選擇；loop.json 其餘可開放的鍵（max、on_timeout_ms）；C-87 加註那句等點頭（整理報告歸組 4 條文大修）（aos-compile-base）。
- 小尾巴：py/README.md、templates/README.md、py/docs/04 等共用文件要補的字，列在 aos-compile-base 各刀紀錄。
- 同組沒併的：aos-inherit、aos-ns（整理報告第 4 類大方向發想，不動）。

## 併進來的四條（逐字）

### aos-compile：用 Python 寫、編譯成 aos 夾

（等使用者，since 2026-11-18）

**what**：使用者 11-18 晚裁定：庚（一支 agent.py 宣告 SYSTEM／TOOLS／LLM／FSM 編譯成定義夾的 json）先做、己（一頁總覽）後做；除錯以 loop 那層為主。11-19 設計稿與六題裁定（定調「C 與 .o」：重新編譯直接蓋、不記指紋、產出後的 json 照常能改）。11-19 第一刀施工完（線 compile-geng-s1-1119）：py/aos/agent_spec.py、templates/agents/agent-python（agent.py＋編譯產物＋英文 README）、py/tests/test_agent_spec.py，七條驗收在乾淨複本全過；沒動 agent_def、知識庫、現有範本。11-19 寫定義的名字 ag 改叫 defs（線 aos-defs-rename-1119，使用者「就 aos.py.agent.defs 吧」）：agent.py 開頭 from aos.py.agent import defs、其後 defs.main／defs.tool／defs.load…。11-19 換成編譯用語（線 aos-defs-rename2-1119，使用者「要，可以參考那些程式語言的類似的功能的名字」「然後以後也用編譯、重新編譯來說，不要再用生、重生這樣」）：指令 --compile／--dry-run、Python defs.compile／defs.write；編譯產物一字不變。11-19 下午兩個名字照使用者改（線 aos-defs-rename3-1119，選項框「改 defs.drop」「留 defs.load」「改 defs.extern」）：defs.no→defs.drop、defs.by_hand→defs.extern；工具骨架 tool.py 旗標對齊（「開一刀對齊 (Recommended)」）：--compile [位置]／--dry-run、Python tool_spec.write，--tooldef／--metainfo 留著（aos-tools 協定）；編譯產物一字不變。

**next**：使用者：點頭後在 ~/repo/aos/proto8 跑 install.py（會換掉使用中的 bin/lib），照紀錄「使用者怎麼試」複製骨架、改 agent.py、python3 agent.py --compile、ctl add 試用。之後：工具包靜態／動態連結做成編譯選項（線 aos-defs-rename2-1119 第二筆）；第二刀（agent_def check 順手重新編譯）使用者 11-19 劃掉、不做；知識庫最後

### aos-pylib：整套 Python 庫版面（aos.py 入口＋通用代理＋把手）

（等使用者，since 2026-11-19）

**what**：三刀已交（3c4cc4c52 install.py 抄完刪孤兒、ee96fd190 入口 aos.py＋通用代理＋把手、1b1e108cc a.bp／a.look 接上與 a.bp.add.<種類>(...)）。寫定義的叫 defs、在 aos.py.agent.defs（使用者 11-19「就 aos.py.agent.defs 吧」），入口不轉出 ag；std 暫放入口頂層（頂層暫定）。

**next**：等使用者：std 留不留在入口頂層、建斷點參數名 id=／tool=（brain_failed 是 code）、skip／wait_stopped 名字；在要用的那份 proto8 跑 install.py（換活樹）要使用者說。py/README.md 補一段 aos.py 等 aos-defs-rename-1119 交完再做；骨架與測試的 ag.→defs. 歸那條改名線。

### aos-compile-base：編譯的通用底座與 Python 函數直接當工具／hook

（等使用者，since 2026-11-20）

**what**：調查與發想已寫好（只查只寫，沒改程式）：底座五個形狀、函數當工具／hook 四個形狀與一個 repo 外原型；八題待裁。使用者 11-20 選項框答四題：底座做到哪一步「整套是一個程式庫」；函數變成工具或 hook 後產物要不要跟 agent.py 脫鉤「抽出來」；說明與參數從哪來「兩種都收，明寫的贏」；先做哪個「一起，同一套寫法」。11-20 規劃稿已交（線 aos-pylib-plan-1120，只出稿）：程式庫長相（defs.Agent 物件、.dry_run()／.compile(夾)、fn 模組的 @fn.tool／@fn.hook、defs.extern 連結版）、跟已定的逐條對照、施工六刀、Argon 審一次。11-20 使用者選項框答規劃稿待裁四題：第 4 題「新名字 fn」、第 1 題「先不定」、第 6 題「接受，寫進「別濫用」」、第 5 題「先不定」（先照全部報錯）；第 2、3 題只告知、未明確裁；問開工答「兩邊都開工」。第 0 刀已交（線 aos-pylib-k0-1120）：新檔 py/aos/spec_base.py（例外、推名字、旗標殼、寫檔後端含程式檔與連結），agent_spec、tool_spec、tools_def 改用它，兩個骨架的產物與輸出逐 byte 不變。第 1 刀已交（線 aos-pylib-k1-1120）：新模組 fn（py/aos/py/fn.py 只轉出，本體 fn_mark、fn_run）：@fn.tool、@fn.hook、fn.param、fn.fail、fn.block、fn.main；說明取 docstring、型別取註記、參數說明取 Args:，也收明寫的、明寫的贏；工具骨架換成 @fn.tool def add(a: float, b: float)＋fn.main(add)，tools_def 跟著，舊寫法不留、tool_spec 留作內部零件；骨架產物與四個旗標、直接執行的輸出逐 byte 不變；@fn.hook 的回話（None／dict／fn.block 退 10）已能用。11-20 使用者選項框再答：第 2 題「.compile(夾) 寫檔、.dry_run() 只算」、第 3 題「小寫」、開哪幾刀「第 1、2 刀都開」。第 2 刀已交（線 aos-pylib-k2-1120）：defs.Agent(說明, system=, tools=, llm=, fsm=, hooks=…) 物件與 .dry_run()／.compile(夾)、defs.main(物件)、defs.fsm 回的能單獨編譯 fsm.json、defs.load 回物件（欄位小寫、base.pack(...)）；defs.compile／defs.write 拿掉；agent 骨架、教學 04～08、骨架 README 改新寫法；骨架與八隻例子重新編譯的產物與各旗標輸出逐 byte 不變（--help 除外）。11-20 使用者說「開工吧」，第 3 刀已交（線 aos-pylib-k3-1120）：agent.py 裡 @fn.tool／@fn.hook 的函數放進 tools=[…]／hooks=[…]，編譯時抽成定義夾的 fn/<名>.py、寫進 tools.json／hooks.json（新 aos/fn_spec.py、hook 那塊拆成 aos/agent_spec_hooks.py）；函數只能用內建、自己的變數、fn、最上層 import 的模組，其餘 SpecBad（第 5 題「先不定」照設計）；相對路徑從 fn/ 算（第 7 題）；沒用函數的骨架與八隻例子產物逐 byte 不變；假腦實掛：腦叫 add 拿到 5、含 secret 的 ws_write 被攔。第 4 刀第一筆已交（線 aos-pylib-k4-1120）：defs.extern(目標) 換意思＝那一欄編成連結（照字面存、只重做連結、不碰目標）；fsm 只能連同一夾（實測：連到夾外格程式讀錯夾）；defs.load 的底連到夾外照樣交出、夾內接不上；agent_def check 報斷鏈；說明寫明別濫用與會被指令寫穿（第 6 題「接受」）；沒用 extern 的產物逐 byte 不變。第 4 刀第二筆已交：defs.Agent(..., loop=defs.loop(every_ms=N)) 定 loop.json 的 interval_ms（第 8 題「加一個宣告」；只開 every_ms），不給＝300、產物逐 byte 不變；實掛量到間隔約 1000 毫秒。第 5 刀已交（線 aos-pylib-k5-1120）：教學 01～08 照新寫法在乾淨複本＋暫存教學夾、真 daemon、假腦從頭打兩遍，程式沒錯；改了教學五處字（06-1 兩處舊詞 SYSTEM／TOOLS、aos-llm ls 挪到問過腦之後、06-2「衍生還能做的」兩個例子補前提）；C-87 加註字擬好在紀錄裡、沒交進條文檔。11-21 kernel 入口已交（線 top-1121-kdefs，使用者「編譯的kernel入口那塊可以派」、待裁第 9 題「from aos.py.kernel import defs」）：defs.Kernel(說明, knobs=, hooks=, program="kernel"／"kernel_llm", body=defs.loop()／defs.daemon())、defs.main(物件)；編出跟 templates/kernels 手寫夾同樣的 _entry、loop.json／daemon.json、kernel.json、loop_hooks.json、llm 的 interfaces.json；@fn.hook 抽成 fn/<名>.py；骨架 templates/kernels/kernel-python；真站跑一輪、真 daemon 掛一列都驗過

**next**：A2、A3、B4、C1 未問；往程式庫走要先規劃，還沒派線；規劃稿已交、等使用者看衝突六條與待裁十題（只有第 0 刀不依賴任何題；施工另要他點頭）；第 0 刀已交，下一步是第 1 刀（fn，第 4 題已答）與第 2 刀（Agent 物件），都等使用者點頭；第 2 刀前宜再明確問第 2、3 題；活樹要在 repo 跑 install.py 才吃到（要使用者點頭）；第 1 刀已交：第 3 刀（函數進 agent、抽成 fn/<名>.py）等第 2 刀交了才開；py/README.md、templates/README.md、py/docs/04 三份共用文件本線交件時被別線佔著，要加的字在第 1 刀紀錄末節；第 2 刀已交：下一步第 4 刀（extern 連結版）、第 3 刀（函數進 agent，等第 1 刀）；教學 06-1 兩行與 py/docs/04 一列因別線 claim 未改（見第 2 刀紀錄）；活樹要在 repo 跑 install.py 才吃到新寫法（要使用者點頭）；第 3 刀已交：下一步第 4 刀（extern 連結版）；py/docs/01、py/README.md、py/docs/04 要補的字列在第 3 刀紀錄；第 4 刀已交：第二筆 loop= 宣告（第 8 題）同線接著交；之後第 5 刀（教學實跑、條文加註）等使用者；第二筆已交：loop.json 其餘可開放的鍵（max、on_timeout_ms）列在第 4 刀紀錄等使用者看；第 5 刀已交：C-87 加註那句等使用者點頭；hook 兩條線（k2b、k5）交件後教學 06-3、06-1 末節、04 的 loop.json 那幾處要再對一次（列在第 5 刀紀錄）；kernel 入口已交：替使用者做的九個選擇（一個類別用 program= 分兩種、body 預設照 start-api、knobs 不驗等）等使用者看；defs.load／extern／files= 與 endpoint 程式沒做；活樹要 install.py 才吃到

### aos-gdb-1120：aos-gdb：pause 加 wait=、斷點 id 與 add 的回傳（11-20 問答）

（等使用者，since 2026-11-20）

**what**：使用者 11-20 問 a.stop() 是不是阻塞、斷點 id 為什麼是 xxxx_1；只讀快查後選項框答四題：加 wait= 的是「暫停 a.bp.pause()」；不等時「回一個可以查的物件。用is_done()」；id 格式他在 Other 反問「不能純數字，然後搭配id、屬性(hook點種類)嗎？」（頂層的解讀：要純數字 id、種類放屬性，刪了重不重用待確認）；a.bp.add「回物件、帶屬性」。之後又答：resume／step「三個都加」、號碼「不重用」、屬性「每次讀都重新查」、扣在斷點上下 ctl stop「這次不動」。線 aos-gdb-wait-1120 已施工：三個動作 wait=False 回 Pending（is_done()、wait()）；id 純數字不重用；add 回斷點物件；替使用者選了：id="mine" 照留、號碼不能自己挑、觀察者與觸發器同一條數列、Pending 只多 wait()。乾淨複本假腦測試全過。三小題使用者選「Pending 加 cancel(),a.bp.set 也回物件,斷點號碼檔名補零」，線 aos-gdb-small-1120 已施工：cancel() 只是不等、不收回；set 回斷點物件；名字號碼補零到 4 位（gdb_0012）；gdb 測試 66 支全過

**next**：使用者點頭後在要用的 proto8 跑 install.py，照兩份紀錄試；已經掛著舊名 gdb_1 的 agent 先 aos-agent hook rm 再重下
