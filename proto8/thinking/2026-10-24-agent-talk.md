# 2026-10-24 agent 之間寄信（demo/talk：ann、bob、cat 分工）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[2026-10-23 腦的工具呼叫](2026-10-23-tool-calls.md)、[2026-10-24 agent 當工具](2026-10-24-agent-as-tool.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。這份是**嘗試性質**（使用者「反正只是嘗試」）。**結論全照頂層推薦定**：使用者 10-24「我現在沒空管這些小事，都按建議做」——下面的代定都是「照推薦定、可翻案」，不另留待使用者項。程式與佈局在 [demo/talk](../demo/README.md#talkagent-之間寄信10-24)。相關條文：[N-05、N-14、N-16](../docs/NORMS/05-基礎設施-窗.md)（信箱，草稿）、[P-17、P-25、P-41](../docs/CONVENTION/02-題目stack停錯腦.md)、[C-52、C-54、C-56](../docs/CONCEPTS/01-設計理念.md)、[N-28](../docs/NORMS/04-基礎設施-loop與daemon.md)。

## 使用者原文（整理版，10-24）

> 然後我這邊有不少想法，都麻煩你試着去思考去實作。我隨便說，你隨便做，反正只是嘗試

> …小念頭機制…還有在記憶庫裏存放各類東西　／　對，我記得proto7就有那些，去看看那些方法

> 然後是各agent之間的交流

> 我現在沒空管這些小事，都按建議做

10-25（C-54 命名方法 R6）：「計數這塊，幫我改成counter_*」；欄位改名那兩題回頂層「都好」（頂層代定、可翻案）。

## 代定（照推薦定、可翻案；使用者 10-24「都按建議做」）

**信**＝收件人工作區的 `new/<id>.json`：

```json
{"kind": "letter", "id": "20261024T035554.362553Z-ann-1a91ea", "from": "ann", "to": "bob", "group": null,
 "thread": "20261024T035554.234941Z-user-8cc9f3", "reply_to": "20261024T035554.234941Z-user-8cc9f3", "counter_hops": 2,
 "expect_reply": true, "sent_at": "2026-10-24T03:55:54.362+00:00", "subject": "算餐費", "body": "請算…"}
```

**名冊**＝`$AOS_ROSTER`（`roster.json`）：`{"kind": "roster", "max_hops": 8, "max_sends": 4, "max_body_bytes": 16000, "members": {"ann": {"mailbox": "ann", "role": "…"}, …, "user": {"mailbox": "user", "role": "人類使用者…", "human": true}}, "groups": {"all": ["ann", "bob", "cat"]}}`，`mailbox` 從名冊所在的資料夾算。

**沿用使用者寫過的 wf inbox 協議**：「地址＝對方工作資料夾底下的 inbox」、先寫暫存再 `mv`、信在頂層＝沒辦、`done/`＝辦完、回信＝寄一封新信到對方的 reply-to、像 email 不像聊天（沒 ack、沒重試）；名冊 ROSTER＝誰是誰、「權威永遠是對方資料夾自己」。

1. **地址＝對方的工作區，信＝它的一道題**：不另開信箱資料夾；agent-dan 範本的 `new/`／`cur/`／`done/` 就是 N-16 的資料夾式信箱，加上 `tmp/`。信**一到就是題目**、不需要郵差。對方沒在跑＝信放著等（像 email）。投遞＝先寫對方 `tmp/` 再改名進 `new/`，寄件人留一份 `sent/<id>.json`。
2. **信是一份 JSON 檔、不是資料夾**：回信是寄一封新信到寄件人的信箱（wf inbox 的做法），一封一檔就夠，人放的純文字題目跟信能混在同一個 `new/`。跟 LLM kernel（aos-gate／aos-kernel-llm）的信箱形狀不同（那邊一封信是 `new/<id>/letter.json`、回信寫在同一個資料夾），四格（tmp／new／cur／done）名字一樣。id＝`<UTC 時間到微秒>Z-<寄件人>-<6 位隨機>`。
3. **我是誰＝名冊上信箱跟 `$AOS_WS` 同一個資料夾的那位**，不另設 `AOS_ME`；名冊位置 `AOS_ROSTER` 由叫它的那一行給（同 `AOS_BRAIN_*`，P-39）。找不到自己＝`SelfUnknown`。
4. **名冊放在團隊工作區**（`roster.json`）；daemon.json 用 `{"$env": "AOS_WS", "$path": "roster.json"}` 給每隻 member。名冊的成員和 daemon.json 的 `loops` 是兩份清單，要自己對齊（名冊有、daemon 沒跑＝信會一直放著）。
5. **對話串由「正在處理的那封」決定**：寄信時 `cur/` 裡那封的 `thread` 照抄、`counter_hops`＋1、`reply_to`＝它的 id——模型不必（也不能）自己填。`cur/` 是空的（人從終端寄）＝開新串，thread＝第一封的 id。
6. **自動回信，用 `expect_reply` 擋來回**：要回答的信，答案自動寄回寄件人；**自動寄的回信一律 `expect_reply: false`，收到它的人不會再自動回**。處理時已經自己寄過給寄件人＝不再自動寄。
7. **兩道上限擋迴圈**（名冊裡可改）：`max_hops` 8（一個對話串最多傳幾手）、`max_sends` 4（處理一封信最多寄幾封，群發算人頭）。到上限工具回錯，讓腦改用純文字給結論。外面還有 member 的 loop `max` 40、daemon `max` 3600 次（每 500 ms，約 30 分鐘）。
8. **模型的錯照實回給模型**（不認得的名字附名冊、信太大、沒收件人、送不到、到上限）；環境沒設好才是工具失敗（`RosterMissing`、`RosterBad`、`SelfUnknown`）。
9. **信太大**：`max_body_bytes` 16000，超過叫模型寫短或把長內容放檔案、信裡寫路徑。
10. **不能寄給自己**：群組會自動扣掉自己；扣完沒人＝錯。
11. **工具**：`send_message`、`check_inbox`（只看不拿），外加 math、clock。不做 `who`（名冊已經在 system 訊息裡）、不做 `reply`（`send_message` 自己接對話串）。
12. **團隊怎麼跑**：一個 aos-daemon，每隻 member 一個子 loop，子 loop 每次 `aos-exec --ws <工作區>/<名> ../member`（處理完所有信就因 idle 退 10），每 500 ms 再起一次＝輪詢。daemon 每次跑 `quiet.py`：三個信箱的 `tmp/`、`new/`、`cur/` 都空＝退 10 收工；有 member 的子 loop 失敗結束＝`team: MemberFailed <名>`、退 1。
13. **人也是名冊上一個信箱**（`user`，`human`）：人寄信＝在 `user/` 那個工作區跑同一支 `send_message`；人收信＝看 `user/new/`。quiet.py 不看 `user` 的信箱。
14. **名字**：資料夾 `talk/`（`member/`、`team/`），成員 ann、bob、cat（跟 agent-ann 那些無關）、人叫 `user`；欄位 `from`、`to`、`thread`、`reply_to`、`subject`、`body`、`sent_at`（時間點＝`<發生了什麼>_at`）、`counter_hops`、`expect_reply`、`max_hops`、`max_sends`、`max_body_bytes`；錯誤行開頭 `talk-member:`、`send_message:`、`team:`。

## 已知限制

- **對方沒在跑**：信放著等，寄件人不會知道；名冊有、daemon 沒跑它＝quiet.py 一直覺得「還有事」，daemon 跑到 `max` 才停。
- **地址錯**：名字不在名冊＝回錯給模型並附名冊；名字在、資料夾不在＝送不到（不自動建）。
- **信遺失**：改名之前死掉＝`tmp/` 留半成品（沒人清，quiet.py 也會因此不收工）；改名之後、寫寄件備份之前死掉＝`sent/` 少一封，上限少算、自動回信可能重寄一次。收件人處理到一半死掉＝信留在 `cur/`，下次接著做。
- **迴圈**：模型自己互寄最多 `max_hops` 手；處理信時寄的一定接在那封後面，只有人放的純文字題目開新串。
- **同時寫入**：id 帶微秒＋隨機、改名是原子的，同時寄同一個信箱不撞。兩個 daemon 跑同一個團隊工作區＝兩份 ann 搶同一個 `new/`，沒有鎖。
- 來信整封會進收件人的 history，對話越積越長。
- **回信對不上**：同時等兩封回信時，回信照到達順序一封封變題目，靠 history 記得在等什麼。
- **自動回信被上限擋**：要回答的信剛好是第 `max_hops` 手，答案寄不回去，問的人永遠等不到。
- **member 失敗**：那隻的 loop 退 1、子 loop 不重起（N-28），信留在 `cur/`、整個團隊退 1；修好再跑，從 `cur/` 接著做。
- **輪詢**：信到了最慢 500 ms 才有人看；inotify 加速（N-14）沒做。

## 未決（現在照推薦，要翻案時看這裡）

1. 回覆要**自動寄回**（現在）還是**一律要模型自己 `send_message`**。
2. 對話串上限要不要換成**整串總封數**（要共用計數檔＋鎖），而不是現在的手數＋每層封數。
3. 信箱形狀要不要跟 LLM kernel 的**統一成一封一資料夾**（以後信裡可以夾附件檔）。
4. 名冊要不要**直接生出 daemon.json 的 `loops`**（現在兩份清單手動對齊）。
