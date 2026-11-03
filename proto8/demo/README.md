# proto8/demo — 範例 agent 與 run.sh

← [proto8](../README.md)｜程式：[impls](../impls/README.md)（aos-exec、aos-loop、aos-fsm、aos-daemon，C++）、[bin/README](../bin/README.md)（aos-tick 等）｜慣例：[CONVENTION](../docs/CONVENTION.md)

```
sh proto8/demo/run.sh      # 在 WSL／Linux 跑
```

`run.sh` 每段各建一個暫時工作區、`cd` 進去跑（慣例用法 `aos-exec <agent資料夾>`），共六段：agent-bob、agent-ann（各放一題 `new/q1.txt`）、daemon、tick、daemon-2、daemon-3（見下；agent-nia 那段 11-03 隨 round 那套 agent 刪了）；印工作區內容（`out/`、`done/`；跑完 `new/`、`cur/` 是空的）與整棵 stack 樹（`$AOS_WS/.stack/`，每檔印內容），最後把暫時資料夾刪掉，repo 裡不留東西。

**PATH 由 `run.sh` 自己放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），agent 裡寫的 `aos-loop`、`aos-fsm`、`aos-exec`、`aos-daemon`、`aos-tick` 要呼叫端事先放進 PATH。`run.sh` 開頭放 C++ 的 `proto8/impls/<名>/bin/`（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；aos-exec、aos-loop、aos-fsm、aos-daemon、aos-json、aos-post；要先建，見 [testing](../../wf/workflows/testing.md#proto8不在-ctest-裡)；沒建好會先停、說要先建）與 Python 的 `proto8/bin/`（aos-tick、aos-tools…）。自己手動跑也一樣（例：`PATH=$PWD/proto8/impls/aos-exec/bin:$PWD/proto8/impls/aos-loop/bin:$PWD/proto8/impls/aos-fsm/bin:$PATH aos-exec --ws <工作區> proto8/demo/agent-bob`）。預設假腦；`AOS_BRAIN_URL`（OpenAI 相容 base URL，另可設 `AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY`）指到遠端才用真腦；帶 `.env` 的 agent（例 agent-gus）模型名在自己的 `.env`（`AOS_BRAIN_MODEL`），只要給 `AOS_BRAIN_URL`。**這台電腦不要跑本機模型**（使用者定「放棄跑本機模型」，[ideas § 6](../thinking/2026-10-19-ideas.md)）。

## agent-bob（混合範本，叫 cathy、cathy 叫 stamp：四層）

入口 `_entry`（預設 `$AOS_ENTRY`）＝`exec aos-loop loop.json`（設定檔是 aos-loop 唯一的位置參數）；`loop.json`＝`{"exec": "fsm.json", "max": 20}`（`exec` 是 aos-exec 的目標；使用者「exec，loop／daemon 的 run 也一起改 exec」）；`fsm.json` 帶 `"_entry": ["aos-fsm", {"$env": "AOS_CF"}]`（`AOS_CF`＝aos-exec 實際跑的那份檔），所以它本身就是 aos-exec 的入口、每次 `aos-exec -- fsm.json`；表一份看完：idle／act 是子資料夾 `idle/`、`act/`（shell），think 是內嵌單子，直接寫在 `exec`：`"exec": {"argv": ["python3", "brain.py"], "stdout": …, "timeout_ms": 120000}`（`python3 brain.py`、stdout 導到 `$AOS_STACK/plan.txt`、逾時 120 秒，aos-fsm 在自己行程內當監工；使用者 10-24「不過exec本來就應該要可以直接放內嵌單子吧」，[thinking 2026-10-24](../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)）。idle 在 `new/` 空時回 10 讓 loop 停。`brain.py` 挑 `new/` 第一題、搬到 `cur/` 認領（Maildir 的 new → cur）、題名寫 `current.txt`、答案印到 stdout。

act 把 `plan.txt` 當題目交給 `act/tools/cathy/`（另一隻完整 agent，同一套範本；P-32、P-33）：在她的小格 `$AOS_STACK/tools/cathy/` 裡備 `ws/new/<題名>`、`AOS_STACK=$sub aos-exec --ws "$sub/ws" tools/cathy`、從 `$sub/ws/out/<題名>` 拿答案寫進 `$AOS_WS/out/`、題目從 `cur/` 搬 `done/`；cathy 失敗（非 0）bob 的 act 說「cathy 失敗」並退 1。cathy 的 act 再經 `act/tools/cathy/act/tools/stamp`（工具，自己的 stack 在 `$AOS_STACK/tools/stamp/`，前面加一行 UTC 時間戳、`runs.txt` 計次）寫她的 out。一次跑完是四層：bob 的 loop／fsm → act → cathy 的 loop／fsm → 她的 act → stamp；`aos-exec --ws <工作區> proto8/demo/agent-bob/act/tools/cathy` 也能單獨跑 cathy。

stack 樹＝呼叫樹：`.stack/{state.txt,current.txt,plan.txt}`、`.stack/tools/cathy/{…,ws/{out,done}/q1.txt,tools/stamp/runs.txt}`（P-38）。

## agent-ann（全內嵌對照）

跟 bob 做同一件事（一題一答），零子資料夾：入口 `_entry`＝`exec aos-exec loop.json`，`loop.json` 是 `{"_entry": ["aos-loop", {"$env": "AOS_CF"}], "exec": {"argv": ["aos-fsm", "fsm.json"]}, "max": 20}`——loop.json 自己帶 `_entry`，`aos-exec loop.json` 就把 loop 跑起來（跟 bob 的 `exec aos-loop loop.json`、`"exec": "fsm.json"` 對照，兩種都行），`fsm.json` 三格全是直接寫在 `exec` 的單子，各指一支小腳本——`idle.py`（`new/` 空退 10）、`brain.py`（同 bob 的那份，複製）、`act.py`（`plan.txt` 寫 out、題目從 cur 搬 done）。資料夾裡只有 `_entry`、`loop.json`、`fsm.json`、三支 `.py`，和一份 `.env` 範例（全是註解、不設任何東西：示範 API key 與 `PATH=${AOS_CD}/bin:${PATH}` 怎麼寫。`.env` 預設不蓋環境裡已有的名字，PATH 那行要從外面叫 `aos-exec --dotenv-override agent-ann` 才生效；旗標只管那一次，入口的 `aos-exec loop.json` 照樣讀這份檔但不蓋；loop、fsm 在自己行程內跑單子、不經 aos-exec、不讀這份檔，所以格裡的 PATH 只多一份 `${AOS_CD}/bin`）。適合「格全是一行、不叫工具」的小 agent；要叫工具、要用 sh 搬檔，就回到 bob 的混合寫法。

<a id="agent-danagent-dan-q11-02-晚刪了"></a>
<a id="agent-eveagent-當工具10-24"></a>
## agent-eve（agent 當工具；真腦＋工具的問答範本）

agent-eve 也是下面各隻「照抄 agent-eve」的範本：讀舊協議 `new/*.txt`、寫 `out/`，腦的工具呼叫照 P-41；走 queue、say／listen 說得到的是 [eca-claude／eca-codex](#eca-templates)。

把一隻 agent 包成另一隻 agent 的腦可以叫的工具（嘗試性質；使用者 10-24「把agent當做工具拿去給agent呼叫，比如一個專精於修改python程式的agent」）。設計、代定、邊緣狀況在 [thinking 2026-10-24-agent-as-tool](../thinking/2026-10-24-agent-as-tool.md)。

```
agent-eve/                主 agent：真腦＋工具的問答範本，act 逾時放寬到 30 分鐘
  system.txt              改 Python 的事交給 pyfix、task 寫清楚、回答前看 diff
  tools/pyfix -> ../../../lib/agent/pyfix   （函式庫的 agent 層）
    _tooldef.json         給 eve 的腦看：task（必填）、dir（相對於工作區，預設 .）
    _entry                轉接（python3，通用那段在 lib/agent/agent_tool.py）：stdin 的 task → 子 agent 的 new/task.txt；跑完把 out/task.txt＋實際 diff 印到 stdout
    agent/                子 agent（pyfix-agent）：也是一整隻同範本的 agent，自己的 system.txt、.env、loop.json（max 60）、fsm.json（think 180 秒、act 300 秒）
      act.py              同 agent-eve，差一條：工具的工作區一律是 $AOS_STACK/pyfix_dir.txt 寫的資料夾
      tools/              ls、read、write、edit、bash → lib/base 的捷徑（bash 逾時預設 30 秒、上限 300）
```

每次呼叫 pyfix 開一個新小格 `$AOS_STACK/tools/pyfix/runs/<三位數>/`：`ws/`（子 agent 收題、交答案）、`stack/`（它的 history）、`before/`（改之前的備份）；子 agent 要改的程式碼是 `$AOS_WS/<dir>`，絕對路徑寫在 `stack/pyfix_dir.txt`（一行，pyfix 開子 agent 前寫）。子 agent 用 `aos-exec --dotenv-override` 叫，所以模型用它自己 `.env` 的。子 agent 失敗＝`pyfix: AgentFailed …`、退 1，eve 的 act 把那行接成 tool 訊息回給腦、不停；其他代號 `AnswerMissing`、`DirBad`、`ArgumentsBad`、`StackMissing`；子 agent 的 stack 沒有 `pyfix_dir.txt`（或寫的不是資料夾）＝它的 act 停在 `pyfix-agent: DirMissing`（路徑跑出去、edit 對不上這類模型的錯，庫的工具退 1、子 agent 的 act 把那行回給模型、不算失敗）。子 agent 自己的逾時：think 180 秒、act 300 秒（`agent/fsm.json`）、最多 60 次（`agent/loop.json`）；eve 的 act 等它 30 分鐘。

真腦：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/agent-eve`；試驗場 `~/code/try/agent-as-tool/`（`setup_ws.py` 建一個有 bug 的 `proj/`，LiteLLM 沒開時用 `fake_brains.py` 劇本）。沒設 `AOS_BRAIN_URL`＝假腦，eve 沒有 clock 工具、會直接答 `FAKE ANSWER`，不會叫 pyfix。測試 `test_eve.py`。

## pi-tools 與 agent-pip（仿 pi coding agent 的基本工具）

下面兩組工具（pi 那組與 file-tools）都在 [proto8/lib/base](../lib/README.md)，路徑是 `lib/base/<名>`；工具的共通契約（參數、結果、錯、沙盒、逾時）見 [lib/README](../lib/README.md)。

pi 那組是一套可重用的寫程式工具，仿 [pi](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent) 預設的四個：`read`（讀檔，最多 2000 行或 50KB、提示 offset 接著讀）、`write`（建檔或整份蓋掉）、`edit`（`edits: [{old_text, new_text}]`，每段對原檔比、要唯一、不重疊，全有或全無）、`bash`（在 `$AOS_WS` 裡跑一行指令，留最後 2000 行或 50KB，逾時 `timeout_s` 預設 30 秒、上限 300 秒、整群停）。read／write／edit 的路徑從 `$AOS_WS` 算、不能跑出去（`PathBad`，符號連結也算）；bash 的指令本身擋不住。

`agent-pip/` 是掛上這套（與下面的 file-tools）的 coding agent：照抄 agent-eve，`tools/` 裡是十二個指到 `../../../lib/base/<名>` 的符號連結，`system.txt` 照 pi 的精神寫短版。**工具出的問題回給腦、不停**（工具退非 0、叫了沒有的工具、arguments 不是 JSON，都接成一則 tool 訊息）。真跑：`AOS_BRAIN_URL=http://localhost:4000/v1 AOS_STACK=<工作區外的資料夾>/ aos-exec --ws <工作區> proto8/demo/agent-pip`（stack 放工作區外，免得腦用工具改到自己的對話）。試驗場 `~/code/try/pi-tools/`。設計與 pi 的調查在 [thinking 2026-10-24-pi-tools](../thinking/2026-10-24-pi-tools.md)；測試 `tests/test_pi_tools.py`。

file-tools 是資料夾與檔案的漸進工具（使用者「資料夾修改和檔案這兩個工具我需要特別設計」），**輸出一律 JSON**：`ls`、`stat`、`view`、`json_edit`、`mkdir`、`move`、`copy`、`trash`（各自做什麼見 [lib/README 索引：base](../lib/README.md#索引base)）。json_edit 要 PATH 上有 `aos-json`（`proto8/impls/aos-json/bin`）。測試 `tests/test_file_tools.py`。

<a id="agent-meg記憶庫10-24"></a>
## agent-meg（記憶庫）

照抄 agent-eve 的問答 agent，多一個跨對話保留的**記憶庫**（heap）：對話（stack）清空了，記得的事還在。設計在 [thinking 2026-10-24-memory](../thinking/2026-10-24-memory.md)（使用者「還有在記憶庫裏存放各類東西」「我記得proto7就有那些，去看看那些方法」「都按建議做」）。

```
agent-meg/
  brain.py            同 agent-eve，只多一件事：每次問腦前把記憶庫的偏好（全部）＋跟題目有關的 5 筆接在 system 後面（不進 history）
  act.py、fsm.json、loop.json、idle/   同 agent-eve
  system.txt          教腦什麼該存、只存確認過的、衝突以現在說的為準
  tools/memory -> ../../../lib/aos/memory   唯一的工具：op＝save（同類同標題＝覆蓋）／search（關鍵字）／read／forget（搬去 archive）
    heap.py           記憶庫的讀寫（brain.py 也用它）

$AOS_HEAP/            記憶庫（沒設＝$AOS_WS/.heap/）：index.json（頂層，wf-table/1）→ <類>/index.json → <類>/001.md
                      六類 prefs、facts、outcomes、gotchas、snippets、skills；forget 的搬 archive/<類>/；寫入持 .flock
```

位置由叫的人給（像 stack，C-67）：兩隻 agent 的 `AOS_HEAP` 指同一個＝共用記憶，各指各的＝私有。人也能直接叫工具：`echo '{"op": "search", "query": "縮排"}' | AOS_HEAP=<庫> proto8/lib/aos/memory/_entry`。錯：模型的錯照實回給它（工具照 lib 契約退 1、印一行 `memory: 代號 原因`，agent-meg 的 act 把那行回給腦、不停）；庫的索引壞了＝`HeapBad`（工具退 1、或 think 退 1）。

真腦：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/agent-meg`；試驗場 `~/code/try/memory/`（`run.py`：第一題記兩件事、換全新 stack 問第二題；LiteLLM 沒開自動用 `fake_brain.py`）。沒設 `AOS_BRAIN_URL`＝假腦，直接答 `FAKE ANSWER`（附上記憶的字數）。測試 `test_meg.py`。

<a id="talkagent-之間寄信10-24"></a>
## talk（agent 之間寄信）

幾隻 agent 互相寄信分工（嘗試性質；使用者 10-24「然後是各agent之間的交流」）。設計、代定、限制在 [thinking 2026-10-24-agent-talk](../thinking/2026-10-24-agent-talk.md)。

```
talk/
  member/                 一隻成員（照抄 agent-eve）：brain.py 把信翻成「[來信]…」、system 加上名冊；act.py 答完要回答的信就自動寄回寄件人
    tools/send_message -> ../../../../lib/aos/send_message（check_inbox 同）   寄信：{to（名字、群組或陣列）, body, subject?, expect_reply?}；寫對方的 tmp/ 再改名進 new/、自己留 sent/
    tools/check_inbox/    看 new/ 裡還沒處理的（只看不拿）；另有 math、clock（捷徑掛 lib/base）
  team/                   _entry＝exec aos-daemon daemon.json：ann、bob、cat 各一個子 loop（每 500 ms 跑一次 member）；quiet.py 大家都沒信了退 10 收工
    roster.json           名冊範例（放進團隊工作區）：members（mailbox、role、human）、groups、max_hops 8、max_sends 4、max_body_bytes 16000
```

**地址＝對方的工作區**：信是 `<工作區>/new/<id>.json`（`{"kind": "letter", "id", "from", "to", "group", "thread", "reply_to", "counter_hops", "expect_reply", "sent_at", "subject", "body"}`（`sent_at`＝寄出的時間）），一到就是那隻 agent 的一道題（`new/`→`cur/`→`done/`）；答案寫 `out/<id>.txt`。名冊＝`$AOS_ROSTER`，我是誰＝信箱跟 `$AOS_WS` 同一個資料夾的那位。對話串由正在處理的那封（`cur/`）決定：`thread` 照抄、`counter_hops`＋1、`reply_to`＝它的 id。要回答的信（`expect_reply`）答完自動寄回、自動寄的回信不再自動回；手數超過 `max_hops`、處理一封寄超過 `max_sends` 封，工具回一行錯（`send_message: HopsBad …`／`SendsBad …`、退 1，member 的 act 把它回給腦）讓腦收手。人也是名冊上一個信箱（`user`，`human`），人寄信＝`AOS_ROSTER=<ws>/roster.json aos-exec --ws <ws>/user proto8/demo/talk/member/tools/send_message`、stdin 一個 JSON。

跑：建團隊工作區（`roster.json`＋`ann/`、`bob/`、`cat/`、`user/` 四個資料夾、user 先寄一封），`cd` 進去 `AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec proto8/demo/talk/team`（PATH 照上面放好 aos-daemon 等四支；沒設 URL＝假腦，直接答 `FAKE ANSWER`）。試驗場 `~/code/try/agent-talk/`（`setup_ws.py`、LiteLLM 沒開時用 `fake_brains.py` 劇本）。測試 `test_talk.py`。錯：`talk-member: 代號 原因`（同 agent-eve 五種）、`send_message: RosterMissing／RosterBad／SelfUnknown`、`team: MemberFailed <名>`（有 member 的 loop 失敗結束，團隊退 1）。

<a id="agent-gus小念頭10-24"></a>
## agent-gus（小念頭）

先規劃、再把每一步 fork 成「小念頭」、回來只帶結論的 agent（照抄 agent-eve，多兩格；嘗試性質）。設計、照推薦定的、邊緣狀況在 [thinking 2026-10-24-thoughts](../thinking/2026-10-24-thoughts.md)（使用者「讓agent先規劃一件事的steps，然後每個steps都fork出去，回來只帶結論」「fork出去的東西，又可以繼續steps」「都按建議做」）。

```
agent-gus/
  fsm.json            idle → plan → fork → think → act → idle（plan 120 秒、fork 1 小時、think 120 秒、act 180 秒）
  plan.py             認領題目、接進 history、請腦回 {"context", "steps": [{id, goal, needs}]} → $AOS_STACK/steps.json；
                      腦回 steps: []＝不拆；到深度上限或額度不夠＝不問腦、不拆
  fork.py             每步起一個小念頭＝再跑一次自己（aos-exec --ws <小格>/ws .），needs 齊了才起、同時最多 3 個；
                      小念頭 out/ 裡那段答案＝結論，全到齊後一步一則接進 history：「小念頭 sN 的結論（目標：…）：…」；
                      小念頭失敗（退非 0、逾時、沒交答案）＝「小念頭 sN 失敗了（目標：…）：原因」照樣接、不停，needs 它的步不起
  brain.py、act.py    think／act 同 agent-eve（act 交答案時 steps.json 收進 plans/）
  thought.json        給別的程式叫一個小念頭：stdin {"goal", "context"?, "needs"?: [{id?, goal, conclusion}]} → stdout 只有結論
  thought.py          thought.json 的身體：開 $AOS_STACK/runs/NNN/、把這一步當題目起一個小念頭（shared.launch）、逾時（900 秒）整群收、印結論；
                      自己的深度與額度照給的 $AOS_STACK 裡的 thought_depth.txt、thought_budget.txt（沒有＝當母體）
  shared.py           各格共用，上限也寫死在這：一次最多 4 步、最多 2 層、整棵樹 10 個、同時 3 個、900 秒、結論 1500 字；tools/run_python -> ../../../lib/base/run_python 工具：stdin {"code"} → 結束碼與輸出（錯一律退 1，act 把工具退非 0 回給腦、不停）
  .env                模型名（AOS_BRAIN_MODEL）

$AOS_STACK/thoughts/<id>/   小格：ws/（小念頭的工作區，題目 new/<id>.txt、答案 out/<id>.txt）、stack/（它自己的，可能又有 thoughts/）、log.txt；
                            stack/thought_depth.txt（第幾層）、thought_budget.txt（整棵樹的額度資料夾）由 launch 寫、小念頭的 plan 讀（母體沒有＝第 0 層）
$AOS_STACK/budgets/<plan_id>/  整棵念頭樹的額度（一個檔＝一個小念頭）；usage.jsonl 每次問腦一行（usage、送出字數）
```

**別的程式叫一個小念頭**（JSON 工具集「找到要修改的 key → 提供值」那種）：`echo '{"goal": "找到要修改的 key", "context": "…"}' | AOS_STACK=<小格>/ aos-exec proto8/demo/agent-gus/thought.json`，stdout 只有結論、過程在 `<小格>/runs/NNN/`；下一步把這次的結論放進 `needs` 再叫一次。錯：`agent-gus: StepBad`（stdin 不對）、`ThoughtFailed`，退 1。

真腦：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/agent-gus`；沒設＝假腦（第 0 層拆兩步、s2 帶 s1 的結論，答 `FAKE ANSWER … （彙整了 2 個小念頭的結論）`）。試驗場 `~/code/try/thoughts/`（`run.sh` 用 `fake_brains.py` 跑排序比較題、`measure.py` 印念頭樹與 context 省多少）。錯：同 agent-eve，另有 `PlanBad`（規劃寫錯：超過步數、needs 指錯或繞圈；腦回的不是規劃、是散文＝當不拆自己做）、`ThoughtFailed`（小念頭退非 0、逾時、沒交答案；同批其他的照跑完，重跑只補失敗的、在原小格接著做）。測試 `test_gus.py`。

## agent-kai（按意圖組 context）

照抄 agent-eve，只改「送給腦的是什麼」：`$AOS_STACK/history.jsonl` 照舊完整、只附加，但問腦時不送整份，而是按這題的意圖現組一份工作 context（使用者 10-24「現在history.jsonl就是一直累積，但問題在於那太多冗餘資訊了，我希望AI能夠按照意圖去做」）。設計、對比數據、邊緣狀況在 [thinking 2026-10-24-intent-context](../thinking/2026-10-24-intent-context.md)。

```
agent-kai/
  brain.py            組 context：system.txt ＋ 先前對話的目錄（一題一行）＋〔有記憶庫就附幾筆〕＋ 挑出來的舊題（只有問題與結論）＋ 這題的完整訊息
                      挑：上一題、指代詞（剛剛、那個…）再加一題、「第 N 題」、字面重疊最多兩題；整份粗估 ≤ 1500 token（寫死）就全送
  act.py              同 agent-eve（工具的 stack＝$AOS_STACK/tools/<名>/，P-17）
  system.txt          告訴腦它看到的不是全部、不夠就 recall 或重查、回答把關鍵寫完整
  tools/recall/       op＝search（關鍵字找舊題）／read（展開一題；detail=true 連當時的工具原始輸出）；讀 $AOS_STACK/../../history.jsonl（靠 P-17：上兩層是 agent 的 stack）
    turns.py          把 history 切成題、照意圖挑（brain.py 也用它）
  tools/read、math、clock → ../../../lib/base/<名>（符號連結）
  （選配）tools/memory → ../../../lib/aos/memory：放了就每題自動 search 記憶庫 3 筆附進 system

$AOS_STACK/context.jsonl   每次組了什麼：mode（full／intent）、picked（[題號, 原因]）、粗估 token、整份全送的話多少
```

真腦：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/agent-kai`；沒設＝假腦（同 agent-eve）。對比腳本 `python3 proto8/tests/bench_intent_context.py [--upstream http://localhost:4000/v1]`：15 題跳來跳去的對話，各跑 dan（整份）、kai、kai0（kai 拿掉 recall），結果放 `~/code/try/intent-context/runs/<時間>/`；LiteLLM 沒開時用「照證據回答」的假腦。錯：同 agent-eve；recall 自己的 `recall: HistoryMissing`（沒設 `AOS_STACK`、或 `$AOS_STACK/../history.jsonl` 不在）、`HistoryBad`。測試 `test_kai.py`。

## agent-liv（掛函式庫的工具）

照抄 agent-eve 的問答 agent，工具改成**引用 [proto8/lib](../lib/README.md)**（使用者 10-24「我們在做工具集，這其實挺像是在做函式庫。因爲agent是函數，我們給他的工具就是他在內部自己跑的時候會呼叫的外部函數……把函數庫做好」）。怎麼引用見 [lib/README](../lib/README.md#範例demoagent-liv)。

```
agent-liv/
  _entry、loop.json、fsm.json、.env、idle/   同 agent-eve
  brain.py、act.py                           同 agent-eve，只改錯誤訊息開頭與假腦（假腦叫一次 ls、拿 total 答）
  system.txt                                 教腦哪件事用哪個工具
  _metainfo                                  這隻 agent 的特性（照 _metainfo 規劃的範例 2）
  tools/read -> ../../../lib/base/read       一條相對捷徑一個工具：read、write、edit、bash、ls、json_read、json_edit 七條
  tools/clock/                               自己的工具（真資料夾）：庫裡也有 clock，同名自己的贏（示範覆寫）
```

跑：`aos-exec --ws <工作區> proto8/demo/agent-liv`（沒設 `AOS_BRAIN_URL`＝假腦：`idle think act idle think act idle(10)`，答 `FAKE ANSWER to: …（ls said: N items）`，小格 `.stack/tools/ls/`）。錯同 agent-eve（`agent-liv: 代號 原因`）；庫的工具出錯、叫了沒有的工具、arguments 不是 JSON 照 agent-pip **回給腦、不停**。測試 `test_lib.py`。

## agent-hal（土法 compact）

history 太大時自己壓短的 agent（嘗試性質；使用者 10-24「做一套土法compact吧」）。設計、數據、代定、邊緣狀況、跟 agent-kai 怎麼搭配在 [thinking 2026-10-24-compact](../thinking/2026-10-24-compact.md)。

```
agent-hal/                 照抄 agent-eve（brain.py、act.py 只改錯誤訊息開頭）；system.txt 多一句「開頭【compact】那則是摘要」；tools/math、clock 捷徑掛 lib/base
  fsm.json                 idle → compact → think → act → idle
  compact/                 資料夾程式，也能手動跑：aos-exec --ws <工作區> proto8/demo/agent-hal/compact --force
    _entry、compact.py     history 沒超過 32 KB 直接退 0；超過就三步（門檻、段大小、保留上限、三步的模型都寫死在 compact.py）：
                           ① 每則叫工具的 assistant＋結果 → 便宜模型各一句「在幹嘛、結果如何」（tool_note）
                           ② 每 8 KB 一段 → 摘要＋挑幾行原樣保留（keep，標 user_words／decision／number／open／other）
                           ③ 各段摘要＋候選保留行 → 強一點的模型修成一份、選最後留哪幾行
    ask.py                 問腦（AOS_BRAIN_URL；沒設＝假腦照字面拼；一次最多等 120 秒）
    prompts/*.txt          三步的 system 訊息
```

新 history＝一則 user（`【compact】run=…` 摘要＋保留行原文）＋一則 assistant（讀過了）＋最近 2 題與沒答完那題原樣——形狀同一般 history，brain 直接用。原檔整份收進 `$AOS_STACK/compact/<run>/orig.jsonl`（不刪不改），同資料夾有每步產物與 `report.json`（前後大小、三步各叫幾次、token、保留了哪些、丟了哪些）；`compact/log.jsonl` 一次一行。做到一半失敗重跑從斷的那步接著做。錯：stderr 一行 `compact: 代號 原因`、退 1、history 不動——`BrainFailed`、`ReplyBad`、`HistoryBad`、`SummaryEmpty`（摘要是空的就不換）、`HistoryChanged`（壓的期間被寫了）、`ArgumentsBad`、`StackMissing`；壓完沒變小不換（收成 `nosave-*`）。agent 的錯同 agent-eve（`agent-hal: 代號 原因`）。

試驗場 `~/code/try/compact/`（`run.sh`：合成 51 則 53 KB 的 history，LiteLLM 沒開用 `fake_brain.py`）。測試 `test_compact.py`。

## daemon（一個 daemon 同時管 bob、ann）

`daemon/_entry`＝`exec aos-daemon daemon.json`；`daemon.json` 是 `{"max": 10, "interval_ms": 200, "ctl", "state", "procs": {"bob": …, "ann": …}}`，每個子項是一份 loop 設定：`{"exec": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agent-bob"]}, "max": 1}`（ann 同樣；單子直接寫在子項的 `exec`，相對路徑從 daemon 的 cwd＝`demo/daemon/` 算，daemon 寫小格時補 `cwd`，見 [aos-daemon](../impls/aos-daemon/README.md)）——子 loop 跑一次那隻 agent，工作區是 `$AOS_WS/bob`、`$AOS_WS/ann`。`run.sh` 這段建暫時工作區、在 `bob/new/`、`ann/new/` 各放一題、`aos-exec` daemon：它跑 10 次（約 2 秒）就結束、結束前收掉子項。

stack 樹：`.stack/state.json`（daemon 自己的 state）、`.stack/procs_state.json`（子項表 `procs`）、`.stack/procs/bob/`、`.stack/procs/ann/`（各子項的小格：daemon 寫的 `loop.json`、子 loop 的 `state.json`、`stderr.txt`，以及那隻 agent 自己的 `state.txt`、`current.txt`、`plan.txt`…——agent 的 stack 就是小格，因為 `AOS_STACK` 已經有值、aos-exec 沿用）。子 loop 結束後不重起、也不留在表上（使用者「改成子項結束後不留名單」）：兩項跑完就從 procs_state 拿掉，結束碼要加 `--enable-logs` 看 daemon 的 stdout（一個子項起來一行、結束一行）。state.json 長這樣：`{"phase": "done", "counter_runs": 10, "max": 10, …, "code": 0, "pid", "started_at_ticks", "boot_id", "updated_at": "2026-10-23T02:46:30.317+00:00"}`，procs_state.json：`{"ctl_seq": null, "ctl_warning": null, "procs": {}, "pid", "started_at_ticks", "boot_id", "updated_at"}`（計數欄一律 `counter_*`，使用者「計數這塊，幫我改成counter_*」）。各欄意思見 [aos-daemon](../impls/aos-daemon/README.md)、[NORMS N-28](../docs/NORMS/04-基礎設施-loop與daemon.md)。

## daemon-2（信箱模式的 daemon）

一頁說明在 [daemon-2/README.md](daemon-2/README.md)（怎麼起、人怎麼寄、怎麼看、怎麼停）；程式見 [aos-daemon § 信箱](../impls/aos-daemon/README.md)、[aos-post](../impls/aos-post/README.md)。兩個寄信人：agent 格 `agent-sam/`（daemon 照 `procs` 起它、跑一次：`aos-post send` 一封加子項 `tick` 的信，不接腦）與人（命令列手寫 `aos-post send`）。`run.sh` 這段：先 `aos-post init` 一個收回信的 `inbox/`、`aos-exec daemon-2 --max 25` 放背景（約 5 秒），信箱建好就寄一封加 `tock`（`--reply-to inbox`），等 daemon 收工；印回信（`body: {"applied": true}`、`in_reply_to`＝那封的信件名稱）與 stack 樹：`.stack/procs_state.json` 的 `procs` 收工後是空的、多一欄 `mailbox_warning: null`（開了信箱才有）；`.stack/procs/tick/tick.txt`、`.stack/procs/tock/tock.txt` 是各自走到的數；`.stack/procs_ctl_mailbox/` 的三格是空的（信收完就刪）。自動測：`impls/aos-daemon/tests/test_demo.py`（`run_daemon2`）。

## daemon-3（一次性的東西掛 daemon 的兩種寫法）

一頁說明在 [daemon-3/README.md](daemon-3/README.md)（兩種寫法對照、怎麼跑、跑一次的結果、半路加一個）。同一支 [tick](tick/) 在一份 `daemon.json` 的名單 `procs` 裡掛兩次：`tick_loop`＝`{"exec": "../tick", "max": 1}`（① 包成跑一次的子 loop，使用者 10-30「包成max:1也是可以」）、`tick_exec`＝`"../tick"`（② exec 型：daemon 直接 `aos-exec` 它一次、不包 aos-loop，使用者 10-30「讓daemon可以掛aos-exec，也是不錯的」）。`run.sh` 這段：`aos-exec daemon-3` 跑一次、印 stack 樹：`procs` 收工後是空的；兩格的 `tick.txt` 都是 5；`tick_loop/` 多 `loop.json`、`state.json`（外層 aos-loop 的），`tick_exec/` 只有 `stderr.txt` 與 `tick.txt`。自動測：`impls/aos-daemon/tests/test_demo.py`（`run_daemon3`）。

## tick（時鐘）

`tick/_entry`＝`exec aos-loop loop.json`；`loop.json`＝`{"exec": {"argv": ["aos-tick", {"$env": "AOS_STACK", "$path": "tick.txt"}]}, "max": 5}`——loop 跑 5 次，每次在自己行程內跑那張單子 `aos-tick $AOS_STACK/tick.txt`，所以跑完工作區的 `.stack/tick.txt` 是 `5`（C-44、N-01）。節奏、停交給 loop：要隔多久走一格就在 loop.json 加 `interval_ms`，要能暫停就加 `ctl`、寫 `{"cmd": "pause"}`。程式見 [bin/README 的 aos-tick](../bin/README.md)。

<a id="eca-templates"></a>
## 外部 coding agent 範本（eca-claude、eca-codex）

claude code／codex **整隻當成一隻平級的 agent**（不是腦、不是工具）：包成跟 aos agent 同形的定義資料夾，`loop.json` 直接叫 [`aos-eca-turn`](../bin/README.md)，aos 只碰它 stack 裡的 queue／history／ctl（P-42）。設計：[thinking 2026-10-30 eca](../thinking/2026-10-30-eca.md)；條文草稿 P-43。兩份只差 `cli.json`。

```
eca-claude/
  _entry      ["aos-loop", "loop.json"]（JSON 入口）
  loop.json   {"exec": {"argv": ["aos-eca-turn", "--on-empty", "idle", "--on-busy", "yield", {"$env": "AOS_CD"}], "timeout_ms": 900000},
               "interval_ms": 300, "ctl": "ctl.json", "state": "state.json"}（停著等版：沒有 max；queue 空就退 0、loop 隔 300 毫秒再來；兩扇窗落在 $AOS_STACK）
  cli.json    怎麼叫 CLI（kind、flags、print_flags、timeout_ms），抄 lib/agent/claude 的保守旗標；eca-codex 抄 lib/agent/codex 的
  prompt.txt  （選填，範本沒有）開場白：history 與 queue 都空時當第一則 user 投進 queue
  tools.json  aos-tools 的登記檔，只登記 clock（"../../lib/base/clock"，相對路徑從這份檔的資料夾算）；cli.json 沒寫 tools＝用它，
              cli_session 起 CLI 前接上 aos-mcp（工具名 mcp__aos__clock）；不要工具就刪掉它
```

**實例＝定義 × 工作區**：工作區＝CLI 的 cwd（你的程式專案）；stack 預設 `<工作區>/.stack/`，裡面長 `queue/`、`history.jsonl`、`ctl.json`、`state.json`、`eca.json`（kind、ws、template）與 cli_session 的小格 `claude/`（`session.txt`、`transcripts/`…）。

```sh
aos-exec --ws ~/code/myproj proto8/demo/eca-claude &     # PATH 要有 impls 的 aos-exec／aos-loop／aos-post、proto8/bin 的 aos-eca-turn 與 aos-tools、extras/ai_tools/bin 的 aos-mcp、claude
aos-say --ws ~/code/myproj 看一下 README 在講什麼 && aos-listen --ws ~/code/myproj
echo '{"cmd": "pause"}' > ~/code/myproj/.stack/ctl.json      # 暫停：不餵下一則（新信留 queue/new/），粒度＝一則訊息
echo '{"cmd": "stop"}' > ~/code/myproj/.stack/ctl.json       # 收工
```

`aos-eca-turn` 一次答一批（怎麼答、`--on-empty`／`--on-busy`、錯見 [bin/README](../bin/README.md)）。人在畫面上自己打的話不進 history，完整對話看小格的 `transcripts/`。**射後不理**：複製一份，`loop.json` 的 `--on-empty idle` 改 `stop`（或拿掉，沒給＝stop；要開場白就在定義放 `prompt.txt`）——queue 空 aos-eca-turn 退 10、loop 以 0 收工。CLI 那層出錯＝aos-eca-turn 退 1、loop 停下等人（信留 `cur/`）。測試 `test_eca.py`（範本）、`test_eca_turn.py`（aos-eca-turn）。

## 測試

`python3 -m unittest discover -s proto8/tests`（跑 impls 的 C++ 程式＋bin 的 aos-tick，先建 impls）：`test_loop.py`（直接叫 aos-loop：訊號、PATH、`interval_ms`／`ctl`／`state` 窗、命令列（設定檔是唯一的位置參數、`exec` 陣列、`檔#/指標`））、`test_daemon.py`（aos-daemon）、`test_exec.py`（aos-exec、aos-loop、兩隻 agent 與 cathy／stamp 巢狀）、`test_exec_rules.py`（aos-exec 的規則：命令列旗標、找入口、`#/`、四種入口、`AOS_CF`／`AOS_CD`）、`test_inst.py`（inst 單子，經 aos-exec 跑）、`test_fsm.py`（aos-fsm）、`test_tick.py`（aos-tick 與 demo/tick）、`test_llm_kernel.py`（LLM kernel：aos-llm-send＋aos-llm-kernel 經 aos-loop 端到端、包閘門那格逾時撤信、kernel 不在時信堆著、high 先與 slots、kernel 整群死掉後 `RunFailed`、只死本體時照常交回；token 回報與額度：agent-eve 的 `brain.py` 經閘門、kernel 跑時把假 server 的 usage 寫進回報、沒經 kernel 不寫、額度到頂閘門印 `BudgetMissing`）；各 demo agent 的測試寫在上面各段。
