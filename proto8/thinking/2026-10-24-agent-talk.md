# 2026-10-24 agent 之間寄信（demo/talk：ann、bob、cat 分工）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[2026-10-23 腦的工具呼叫](2026-10-23-tool-calls.md)、[2026-10-24 agent 當工具](2026-10-24-agent-as-tool.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。這份是**嘗試性質**（使用者「反正只是嘗試」）。**結論全照頂層推薦定**：使用者 10-24「我現在沒空管這些小事，都按建議做」——下面的代定都是「照推薦定、可翻案」，不另留待使用者項。相關條文：[N-05、N-14、N-16](../NORMS/05-基礎設施-窗.md)（信箱，草稿）、[P-17、P-25、P-41](../CONVENTION/02-題目stack停錯腦.md)、[C-52、C-54、C-56](../CONCEPTS/01-設計理念.md)、[N-28](../NORMS/04-基礎設施-loop與daemon.md)。

## 使用者原文（整理版，10-24）

> 然後我這邊有不少想法，都麻煩你試着去思考去實作。我隨便說，你隨便做，反正只是嘗試

> …小念頭機制…還有在記憶庫裏存放各類東西　／　對，我記得proto7就有那些，去看看那些方法

> 然後是各agent之間的交流

> 我現在沒空管這些小事，都按建議做

## 考古結論（以前幾代怎麼做的、這次沿用什麼）

- **使用者自己寫過的**：wf 的 inbox 協議（08-30 收進來）——「地址＝對方工作資料夾底下的 inbox」、先寫暫存再 `mv`、信在頂層＝沒辦、`done/`＝辦完、回信＝寄一封新信到對方的 reply-to、像 email 不像聊天（沒 ack、沒重試）；名冊 ROSTER＝誰是誰、「權威永遠是對方資料夾自己」。頂層 thinking 9/16 的 CLI 草案：`say --to ~/bob "hello bob"`、`listen` 每秒 poll 回覆檔。
- **AI 以前的設計**：proto2 的 `thread` 預設＝第一封信的 id、`reply_to`、`mail_broadcast`、通訊錄 `contacts.json`；proto5 信的 id `<時間>-<pid>-<寄件人>`、正文上限 20000 字、地址白名單；proto6「帶 `in_reply_to` 的回話不觸發 LLM、不再回話，免得兩邊互回無限循環」、檔案上限 256 KiB；proto7-1 名冊 `{members:[{node,inbox,role}]}` 放進 LLM 的 prompt、`sent.jsonl`；proto7-2 `modules/mail` 回信 id 固定防重寄；proto8 10-14 N-16 Maildir（tmp／new／cur、認領靠改名）、10-15 kernel 信箱（現在 impls 的 aos-gate／aos-kernel-llm）。
- **以前沒做過的**：跳數上限（只有 proto6 那條「回話不回」）；跨機器信箱。
- **這次沿用**：地址＝對方的工作區（agent-dan 範本本來就從 `$AOS_WS/new/` 收題，信直接當題目）；名冊放進 system 訊息（proto7-1）；thread＝第一封的 id（proto2）；`reply_to`；「回覆不再自動回」（proto6，做成 `expect_reply`）；大小上限（proto5／6）；寄件備份（proto7-1 的 `sent.jsonl`，這次一封一檔 `sent/`）；先寫 `tmp/` 再改名進 `new/`（N-05、N-16、wf inbox）。

## 做了什麼（[demo/talk](../demo/README.md#talkagent-之間寄信10-24)）

```
talk/
  member/                  一隻團隊成員（照抄 agent-dan 混合寫法：idle 資料夾，think／act 內嵌單子），誰是誰看名冊
    brain.py               多兩件：題目是信就翻成「[來信] 寄件人…對話串…要你回答…主旨…---正文」；system＝system.txt＋名冊（我是誰、角色、還有誰、群組）
    act.py                 多一件：題目是要回答的信、處理時還沒寄過信給寄件人＝把答案自動寄回（expect_reply false）
    tools/send_message/    寄信（給名字、群組或名字陣列）
    tools/check_inbox/     看 new/ 裡還沒處理的（只看不拿）
    tools/math、clock/     照抄 agent-dan
  team/
    _entry                 exec aos-daemon daemon.json
    daemon.json            三個子 loop（ann、bob、cat 各跑一次 member、每 500 ms 再起一次）；daemon 自己每次跑 quiet.py
    quiet.py               大家都沒信要處理＝退 10 收工；有 member 的 loop 失敗結束＝退 1
    roster.json            名冊範例（要放進團隊工作區）
```

**信**＝收件人工作區的 `new/<id>.json`：

```json
{"kind": "letter", "id": "20261024T035554.362553Z-ann-1a91ea", "from": "ann", "to": "bob", "group": null,
 "thread": "20261024T035554.234941Z-user-8cc9f3", "reply_to": "20261024T035554.234941Z-user-8cc9f3", "hops": 2,
 "expect_reply": true, "at": "2026-10-24T03:55:54.362+00:00", "subject": "算餐費", "body": "請算…"}
```

**名冊**＝`$AOS_ROSTER`（`roster.json`）：`{"kind": "roster", "max_hops": 8, "max_sends": 4, "max_body_bytes": 16000, "members": {"ann": {"mailbox": "ann", "role": "…"}, …, "user": {"mailbox": "user", "role": "人類使用者…", "human": true}}, "groups": {"all": ["ann", "bob", "cat"]}}`，`mailbox` 從名冊所在的資料夾算。

一封信的路：ann 的腦回 `send_message {"to": "bob", "expect_reply": true, …}` → 工具寫 `bob/tmp/<id>.json`、改名進 `bob/new/`、自己留 `ann/sent/<id>.json` → ann 這題答「已寄出，等回信」、題目搬 `done/` → bob 的子 loop 下一次起來，idle 看到 `new/` 有信 → think 認領（`new/`→`cur/`）、翻成「[來信]…」問腦 → 腦叫 math、再答 → act 看到這封要回答、bob 還沒寄過給 ann → 經 `send_message` 把答案寄回 `ann/new/`（`expect_reply` false）→ 答案也寫 `bob/out/<id>.txt`、信搬 `done/` → ann 下一次起來把回信當新題目，history 接在上次後面，所以她記得自己在做什麼。

人也是名冊上一個信箱（`user`）：人寄信＝在 `user/` 那個工作區跑同一支工具（`aos-exec --ws <ws>/user …/send_message`，stdin 一個 JSON）；人收信＝看 `user/new/`。純文字題目（`new/q1.txt`）照舊收，這題開一串 `<我>:<題名>`。

測試 [tests/test_talk.py](../tests/test_talk.py) 11 個（假 server 依 system 裡「你是 X。」分角色回）：投遞與寄件備份、群組不含自己、模型的錯退 0、送不到、環境錯退 1、對話串跟著 `cur/` 走與兩種上限、20 個同時寄同一個信箱、假腦自動回信、三隻分工、互相回信被擋、member 失敗團隊停下。

## 跑一次（10-24，`~/code/try/agent-talk/`）

- **LiteLLM 沒開**（localhost:4000 連線被拒），**用假 server 劇本跑**（`fake_brains.py`，劇本照一個合理的模型會做的寫，不是真模型的表現）。真跑指令在試驗場 `README.txt`。
- user 寄給 ann：「下週要辦讀書會：17 個人、連續 3 天、每人每天餐費 235 元。請算出總餐費，並寫一段給大家看的公告，最後把公告寄給我。」
- 六封信，同一個對話串，2 秒跑完、結束碼 0：
  1. user → ann（第 1 手，題目）
  2. ann → bob「請算讀書會總餐費：17 人 × 3 天 × 每人每天 235 元」（要回答）
  3. bob 叫 math `17*3*235` → 自動回信 bob → ann「總餐費 = 17 × 3 × 235 = 11985 元。」
  4. ann → cat「請寫一段讀書會公告（17 人、3 天），提到：總餐費…11985 元」（要回答）
  5. cat → ann（自動回信）「【讀書會公告】三天共 17 人，總餐費 11985 元，請大家準時出席。」
  6. ann → user（第 6 手）公告全文
- 然後 quiet.py 看三個信箱都空了、退 10，daemon 收掉三個子 loop、收工。現場在 `ws-fake/`，腦收到與回的每一筆在 `ws-fake-brains.jsonl`。

## 代定（照推薦定、可翻案；使用者 10-24「都按建議做」）

1. **地址＝對方的工作區，信＝它的一道題**：不另開信箱資料夾；agent-dan 範本的 `new/`／`cur/`／`done/`（10-23 照 Maildir 改名）就是 N-16 的資料夾式信箱，加上 `tmp/`。所以信**一到就是題目**、不需要郵差、不需要 check_inbox 才收得到。對方沒在跑＝信放著等（像 email）。
2. **信是一份 JSON 檔、不是資料夾**：跟 LLM kernel（aos-gate／aos-kernel-llm）的信箱**形狀不同**——kernel 那邊一封信是 `new/<id>/letter.json`、回信 `reply.json` 寫在同一個資料夾（因為閘門要同步等回覆、要撤信）；這邊回信是寄一封新信到寄件人的信箱（wf inbox、proto2 的做法），所以一封一檔就夠，也讓人放的純文字題目跟信能混在同一個 `new/`。四格（tmp／new／cur／done）名字一樣。id 也不同：kernel 是 `<奈秒>.<pid>.<ticks>`（拿來判斷寄件人死了沒），這邊是 `<UTC 時間到微秒>Z-<寄件人>-<6 位隨機>`（人讀得懂、照時間排序；寄件人多半是一跑就退的 act，pid 沒意義）。
3. **我是誰＝名冊上信箱跟 `$AOS_WS` 同一個資料夾的那位**，不另設 `AOS_ME`；名冊位置 `AOS_ROSTER` 由叫它的那一行給（同 `AOS_BRAIN_*`，P-39）。找不到自己＝`SelfUnknown`。
4. **名冊放在團隊工作區**（`roster.json`），`mailbox` 從名冊所在的資料夾算；daemon.json 用 `{"$env": "AOS_WS", "$path": "roster.json"}` 給每隻 member。名冊的成員和 daemon.json 的 `loops` 是兩份清單，要自己對齊（名冊有、daemon 沒跑＝信會一直放著）。
5. **對話串由「正在處理的那封」決定**：寄信時 `cur/` 裡那封的 `thread` 照抄、`hops`＋1、`reply_to`＝它的 id——模型不必（也不能）自己填，處理一封信時寄出的一定接在那封後面。`cur/` 是空的（人從終端寄）＝開新串，thread＝第一封的 id。
6. **自動回信，用 `expect_reply` 擋來回**：要回答的信，答案自動寄回寄件人；**自動寄的回信一律 `expect_reply: false`，收到它的人不會再自動回**（proto6 那條的做法）。處理時已經自己寄過給寄件人＝不再自動寄。
7. **兩道上限擋迴圈**（名冊裡可改）：`max_hops` 8（一個對話串最多傳幾手）、`max_sends` 4（處理一封信最多寄幾封，群發算人頭）。到上限工具回「錯誤：…請直接用純文字給出你的結論」、退 0，讓腦收手。外面還有 member 的 loop `max` 40、daemon `max` 3600 次（每 500 ms，約 30 分鐘）。
8. **模型的錯照實回給模型**（不認得的名字附名冊、信太大、沒收件人、送不到、到上限）：stdout「錯誤：…」、退 0（同 agent-eve 子工具）；環境沒設好才退 1（`RosterMissing`、`RosterBad`、`SelfUnknown`）。
9. **信太大**：`max_body_bytes` 16000，超過叫模型寫短或把長內容放檔案、信裡寫路徑。
10. **不能寄給自己**：群組會自動扣掉自己；扣完沒人＝錯。
11. **工具三個就好**：`send_message`、`check_inbox`（只看不拿）、外加 agent-dan 的 math、clock。沒做 `who`（名冊已經在 system 訊息裡）、沒做 `reply`（`send_message` 自己接對話串）。
12. **團隊怎麼跑**：一個 aos-daemon，每隻 member 一個子 loop，子 loop 每次 `aos-exec --ws <工作區>/<名> ../member`（member 自己的 loop 處理完所有信就因 idle 退 10 結束），每 500 ms 再起一次＝輪詢。daemon 自己每次跑 `quiet.py`：三個信箱的 `tmp/`、`new/`、`cur/` 都空＝退 10 收工；有 member 的子 loop 失敗結束（小格 `state.json` 的 `code` 非 0）＝`team: MemberFailed <名>`、退 1（不然那封信卡在 `cur/`、團隊永遠不收工）。
13. **名字**：資料夾 `talk/`（`member/`、`team/`），成員照 demo 慣例取人名 ann、bob、cat（跟 agent-ann 那些無關）、人叫 `user`；欄位照 wf inbox／proto2 用 `from`、`to`、`thread`、`reply_to`、`subject`、`body`、`at`，新的 `hops`、`expect_reply`、`max_hops`、`max_sends`、`max_body_bytes`；錯誤行開頭 `talk-member:`、`send_message:`、`team:`。

## 挖出的邊緣狀況

- **對方沒在跑**：信放在它的 `new/`，等它起來（名冊有、daemon 沒跑它＝永遠放著；quiet.py 會一直覺得「還有事」，daemon 跑到 `max` 才停）。寄件人不會知道。
- **地址錯**：名字不在名冊＝工具回錯給模型並附名冊；名字在、資料夾不在＝「送不到」（不自動建，免得寄到打錯的地方）。名冊本身寫錯路徑一樣是送不到。
- **信遺失**：投遞是改名，改名之前死掉＝`tmp/` 裡留一份半成品（沒人清，quiet.py 也會因此覺得「還有事」）；改名之後才寫寄件備份，中間死掉＝信寄到了但 `sent/` 沒有，上限少算一封、自動回信可能重寄一次。收件人處理到一半死掉＝信留在 `cur/`，下次起來接著做（agent-dan 本來就這樣）。
- **迴圈**：自動回信不會互回（代定 6）；模型自己一直 `send_message` 互寄＝最多 `max_hops` 手（測試釘住：上限 5 時第 6 手被擋）。群發的分岔最多 `max_sends` 封一層，最壞 4^8 封（理論上，實際被 loop `max` 先擋）。**開新串可以繞過手數**——現在做不到，因為處理信時寄的一定接在那封後面；人放的純文字題目才開新串。
- **同時寫入**：很多人同時寄同一個信箱：id 帶微秒＋隨機、改名是原子的，測試 20 封同時寄全到、`tmp/` 沒殘留。一個信箱只有它自己那隻在認領（同一隻 member 不會同時跑兩份，子 loop 是一次一次跑）。兩個 daemon 跑同一個團隊工作區＝兩份 ann 搶同一個 `new/`，沒有鎖（N-15 現無實作）。
- **信很大**：上限 16000 位元組（代定 9）；但來信整封會進收件人的 history，對話越積越長（history.jsonl 只附加，10-23 待看的「對話太長」同一題）。
- **回信對不上**：ann 同時等 bob、cat 兩封時，回信照到達順序一封封變題目，靠 history 記得在等什麼；history 很長或模型忘了，就可能漏掉「兩封都到了才整理」。
- **自動回信被上限擋**：要回答的信剛好是第 `max_hops` 手，答案寄不回去（寫在 `out/` 後面「〔自動回信〕錯誤：…」），問的人永遠等不到。
- **member 失敗**：腦連不上等，那隻的 loop 退 1、子 loop 不重起（N-28），信留在 `cur/`；quiet.py 讓整個團隊退 1。修好再跑團隊，從 `cur/` 接著做。
- **人寄的信沒人回答**：`user` 是 `human`，quiet.py 不看它的信箱；要回答的信寄給 user 也只是放著。
- **輪詢**：member 沒信時每 500 ms 起一次 aos-exec＋aos-loop＋aos-fsm＋idle（很便宜，但不是零）；信到了最慢 500 ms 才有人看。inotify 加速（N-14）沒做。

## 留給使用者的選項（都不擋，現在照推薦）

1. 回覆要**自動寄回**（現在，靠 `expect_reply`）還是**一律要模型自己 `send_message`**。
2. 對話串上限要不要換成**整串總封數**（要一份大家共用的計數檔＋鎖），而不是現在的手數＋每層封數。
3. 信箱形狀要不要跟 LLM kernel 的**統一成一封一資料夾**（`new/<id>/letter.json`），以後信裡可以夾附件檔。
4. 名冊要不要**直接生出 daemon.json 的 `loops`**（現在兩份清單手動對齊）。
5. 真模型還沒跑過——LiteLLM 開著時照試驗場 `README.txt` 跑一次。

**10-25 註**（C-54 命名方法 R6）：信的 `hops` 現叫 `counter_hops`（使用者「計數這塊，幫我改成counter_*」）、`at` 現叫 `sent_at`（時間點＝`<發生了什麼>_at`；使用者回頂層兩題「都好」，頂層代定、可翻案）。上面的決定照留。
