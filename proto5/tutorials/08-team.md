← [教程索引](README.md)｜上一篇 [07 讓 Claude Code 和 Codex 當 cpu](07-cli-agents.md)｜規範 [spec/team/](../spec/team/README.md)

# 08 一支小團隊：丟一件事、看信、看任務狀態

**目標**：用一份名冊生三個成員（領隊、工人、審查），丟一句話給團隊，看它被誰接走、每一步誰做了什麼、單子走到哪；再看不叫模型的「門房」怎麼直接接住一句話。

**前提**：照 [教程 01](01-daemon-kernel.md) 開機（`aos-kernel ls` 第一行 `health ok`）；新終端先 `. $HOME/aos-try/env.sh`（下面的 `$W` 就是它設的 `$HOME/aos-try`；走 README「五分鐘」那段開機的沒有這個檔，照教程 01 第 1 步建一個）。從 repo 根目錄貼指令。
模型照教程 01 的 `llm.json`。整篇約 10 分鐘，模型大約被問 10～15 次。

## 0. 團隊長什麼樣

```text
你 ──aos-team ask "一句話"──▶ 門房（小程式，照句型比對）──對上了──▶ 直接做（印表、開單）
                                 │ 沒對上
                                 ▼
                         領隊 lead（模型）── handoff 派工 ──▶ 郵差（小程式）開單 t-0001、投信
                                                                   ▼
                         工人 worker-1（模型）動手做 ── team_say DONE ──▶ 郵差 ──▶ 驗收員（小程式）逐條驗
                                                                   ▼
                         要人判斷的條目 ──▶ 審查 reviewer（模型）逐條判 ──▶ 單子 done、郵差寄「完成」給你
```

- **會想的只有三個 agent**：lead、worker-1、reviewer，每個都是一個普通的 agent 家（[教程 03](03-first-agent.md)）。
- **門房、郵差、驗收員、心跳都是不叫模型的小程式**。郵差、心跳是 kernel 的反覆工作，`aos-team start` 會一起登記。
- 成員彼此不直接碰：每個人只往自己的「寄件格」放信，郵差搬進收件人的 `input/`。沒有人會自動轉寄回話，一定要叫 `team_say`。

## 1. 加 cpu

三個 agent 加郵差、心跳，`default` 池 3 顆比較順：

```sh
aos-kernel cpu add --pool default --count 1
```

印 `pool default count 2 -> 3`。

## 2. 開專案與名冊

團隊資料夾和專案資料夾要分開放（不能一個包著另一個：工人把專案整個掛成可寫，會蓋到成員的家）：

```sh
mkdir -p $W/proj
cat > $W/team.json <<'EOF'
{"_metainfo": {"_type": "aos_team", "_version": 1},
 "project": "../proj",
 "tz": "Asia/Taipei",
 "members": {
   "lead":     {"template": "lead",     "mail_to": ["worker-1", "reviewer", "human"]},
   "worker-1": {"template": "worker",   "mail_to": ["lead", "human"]},
   "reviewer": {"template": "reviewer", "mail_to": ["lead", "human"]}}}
EOF
```

- `project`：專案資料夾，**相對團隊資料夾**算。下一步名冊會被抄成 `$W/myteam/team.json`，所以 `../proj` 就是 `$W/proj`。
- `template`：成員照哪個模板生（`proto5/templates/` 的 `lead` 領隊、`worker` 工人、`reviewer` 審查）。
- `mail_to`：這個成員能寄信給誰；`human` 就是你。

## 3. 生家、裝門房規則、開工

```sh
aos-team init --config $W/team.json --target $W/myteam
aos-team route save proto5/spec/team/examples/routes.json --target $W/myteam
aos-team start --target $W/myteam
aos-team ls --target $W/myteam
```

`init` 每個成員印幾行（生了家、裝了哪些工具包），最後一行 `團隊在 …/myteam：3 個成員`。
`route save` 先跑每條規則的例句，全過才存：`5 條規則，0 條沒過`、`存好了：…/team/routes.json`。
`start` 印 `lead: started agent-lead` 等五行（三個成員＋郵差＋心跳）。`ls`：

```text
lead      lead     ok           單：-              最後寄出：-
worker-1  worker   ok           單：-              最後寄出：-
reviewer  reviewer ok           單：-              最後寄出：-
郵差  team-post-myteam-2e83ed4e  ok
心跳  team-beat-myteam-2e83ed4e  ok
```

之後一直打 `--target $W/myteam` 很煩，設環境變數就能省（新終端要再設一次）：

```sh
export AOS_TEAM_HOME=$W/myteam
```

## 4. 丟一件事

```sh
aos-team ask "在專案建一個 hello.md，第一行寫「# 你好」，第二行寫一句自我介紹"
```

印 `沒有規則命中，已交給領隊 lead：…-human`。門房沒有這種句型的規則，所以**落穿給領隊**。等一兩分鐘，看信：

```sh
aos-team mail
```

```text
09-24 20:40  人 → lead  REQUEST  ✓收  在專案建一個 hello.md，第一行寫「# 你好」，第二行寫一句自我介紹
09-24 20:41  post → worker-1  REQUEST  t-0001 rev1  ✓收  任務 t-0001（rev1，第 1/2 次）：在專案根目錄建立 hello.md：…
09-24 20:41  worker-1 → lead  DONE  t-0001 rev1  ✓收  已在專案根目錄建立 hello.md：第一行「# 你好」，第二行「我是 worker-1…
09-24 20:41  post → reviewer  REQUEST  t-0001.r1 rev1  ✓收  審查單 t-0001.r1：替 t-0001（rev1，第 1 次）判下面幾條；…
09-24 20:41  post → lead  DONE  t-0001 rev1  ✓收  t-0001 完成（審查通過）：…
09-24 20:41  post → 人  DONE  t-0001 rev1  t-0001 完成（審查通過）：…
```

一行一封信：時間、**誰 → 誰**、狀態、哪張單、收件人收走了沒（`✓收`／`未收`）、內文開頭。怎麼讀這六行：

1. 你的話變成一封信寄給領隊（`人 → lead`）。
2. 領隊（模型）看了之後用 `handoff` 派工；**開單、寄派工信的是郵差**（`post → worker-1`），領隊自己不寄。
3. 工人（模型）做完，自己用 `team_say` 回 DONE（`worker-1 → lead`）。
4. 郵差把單子交給驗收員（小程式，不寄信）跑機械的檢查；過了，還有一條要人判斷的，就開審查單寄給審查員（`post → reviewer`）。
5. 審查員（模型）用 `review_result` 回結果（這是申請、不是信，所以 mail 不列）；全過，郵差寄「完成」給領隊和你（最後兩行）。

`aos-team mail --full` 看全文；`--task t-0001` 只看這張單的；`--follow` 一直等新的。你的收件匣是 `$W/myteam/team/human/`。

## 5. 看單子

```sh
aos-team task ls --all
aos-team task show t-0001
cat $W/proj/hello.md
```

`task ls --all` 一張單一行（`t-0001.r1` 是它的審查子單）。`task show`：

```text
t-0001  done
負責人：worker-1（開單：lead）  rev1  第 1/2 次
目標：在專案根目錄建立 hello.md：第一行是「# 你好」，第二行是一句自我介紹（…）。
工作流：無
…
驗收：
  0. 檔案在：hello.md
  1. 檢查器 contains {'path': 'hello.md', 'text': '# 你好'}
  2. （審查員判）hello.md 第一行是「# 你好」，第二行是一句通順的自我介紹（…）。
驗收結果 rev1 第1次：過
…
審查結果 rev1 第1次：過
  2 PASS hello.md 第一行為「# 你好」，第二行為通順的自我介紹…
經過：
  2026-09-24T20:40:55+08:00  opened  -→queued  by lead
  2026-09-24T20:41:01+08:00  delivered  queued→sent
  2026-09-24T20:41:07+08:00  picked_up  sent→working
  2026-09-24T20:41:32+08:00  report  working→verifying  by worker-1
  2026-09-24T20:41:38+08:00  verified  verifying→reviewing
  2026-09-24T20:41:57+08:00  reviewed  reviewing→done  by reviewer
```

「驗收」那幾條是領隊開單時寫的「怎樣算做完」：`檔案在`、`檢查器` 由驗收員（小程式）驗，`（審查員判）` 才交給審查員。
「開單：lead」「by lead」是**誰下的令**（領隊叫了 `handoff`）；真正寫單子檔、投信的是郵差。
「經過」是單子的每一步：`queued` 排隊 → `sent` 信投進工人的 input → `working` 工人收走 → `verifying` 工人說做完、驗收中 → `reviewing` 審查中 → `done`。
沒過會怎樣：驗收員或審查員說不過，郵差寄「REQUEST 修正（第 2/2 次）＋逐條結果」回工人，單子回 `working`；次數用完才 `failed`。`hello.md` 內容每次模型寫得不一樣。

## 6. 門房直接接住（不叫模型）

```sh
aos-team ask "看一下單子"
```

印 `沒有進行中的任務單（--all 連結束的一起看）`：這句對上 `routes.json` 的 `tasks` 規則，門房直接跑 `aos-team task ls`，**沒有任何 agent 被叫醒**。
規則是整句比對，不是找關鍵字：「列任務給 bob 看」對不上；句子裡有否定詞（「不要看單子」）也一律落穿給領隊：領隊可能用 `team_say` 回你一封信（`aos-team mail` 看得到），也可能反問你——反問不是信，要 `aos-team wait ls` 看題目、`aos-team answer q-0001 "…"` 回答。每次判了什麼記在 `$W/myteam/team/route.log`。
`routes.json` 裡還有「看一下例行」（列心跳的例行）、「每 2m 數一次 md 檔」（登記一條例行，心跳每 2 分鐘派給工人）、「把 workflows 導入 …，照 …」（直接開單給工人，領隊不經手），規則怎麼寫見 [route.md](../spec/team/route.md)。

## 7. 這件事花了多少

```sh
aos-team score --task t-0001
```

印一句總結和一張六軸表：問了模型幾次（按成員分）、用了多少 token、從你丟話到單子結束幾秒、時間花在哪。人易懂、邊界兩軸留給人填。量法見 [score.md](../spec/team/score.md)。

## 8. 收工

```sh
aos-team stop
```

印三個成員 `stopped agent-…` 和郵差、心跳各一行。家、信、單子都還在資料夾裡；再 `aos-team start` 就接著用。

## 底下在幹嘛

- `init` 照模板替每個成員生一個 agent 家（`$W/myteam/members/<名>/`），人格裡的 `{name}`、`{mail_to}` 換成實際值，工具包照模板裝；每個家都有 `access.json`，工具關在牢裡跑：專案掛成 `/work/ws`（工人可寫，領隊、審查唯讀）、自己的寄件格 `/work/outbox`、任務表 `/work/board`（唯讀）。
- 模型能做的只有「往自己的寄件格放一個檔」：`team_say` 寄信、`handoff` 派工、`review_result` 回審查、`ask_human` 問你。開單、改單子狀態、投信、交驗收，全是郵差照規則做。郵差預設 5 秒巡一次（`team.json` 的 `post.interval_s`）。
- agent 沒事時會停車（不佔 cpu），信投進它的 `input/` 就被叫醒。
- 資料夾怎麼長、誰寫哪個檔：[layout.md](../spec/team/layout.md)。

`route test` 只跑規則檔裡自帶的例句（`--file F` 換一個規則檔），不能拿一句話來試；想知道一句話會不會命中，看 `routes.json` 的 `pattern` 或直接 `ask`。

## 常見錯誤

- **`BadProject`**：團隊資料夾跟專案一個包著另一個。分開放。
- **`專案資料夾 … 不存在`**：先 `mkdir -p` 專案；`project` 是相對團隊資料夾（`$W/myteam`）算的。
- **`aos-team: Usage: 要設 AOS_KERNEL_HOME`**：新終端沒 `. $HOME/aos-try/env.sh`。
- **`AlreadyExists … 同名行程`**：同一個 kernel 上兩支團隊不能有同名成員（kernel 用 `agent-<名>` 登記）。第二支團隊的成員換名字。
- **信一直 `未收`、單子不動**：`aos-team ls` 看最後兩行；郵差寫「壞了」就照那行說的看 `post.err`、修好後重登記。成員的 health 不是 `ok` 就照 [教程 03](03-first-agent.md) 看 `aos-agent status --target $W/myteam/members/<名>`。
- **工人卡住問你問題**：`aos-team wait ls` 看題目，`aos-team answer q-0001 "…"` 回答；答案會變成一封信回到發問的人。

## 收工

`aos-team stop` 之後，要整個丟掉就刪 `$W/myteam` 和 `$W/proj`。daemon、kernel 照 [教程 01](01-daemon-kernel.md) 關。
