← [08 一支小團隊](../08-team.md)（分檔 3/3）｜[上一份](02-看單子到牢.md)

## 10. 讓領隊自己生工人、讓工人自己造工具

**預設就開、不用你點頭**：領隊本來就能生內建模板的新成員（`spawn_member`），工人本來就能寫工具草稿（`tool_draft`）。這篇教程的名冊什麼都沒設，就是這個預設狀態。

### 領隊生成員

跟領隊說「人手不夠，多生一個 worker-2」，它會叫 `spawn_member`；郵差檢查過（模板對、人數沒超、新成員的 `mail_to` 沒超權）就直接生：改名冊、`aos-team init` 生家、`aos-agent start` 開機、回信給領隊，另外寄一封信讓你知道。看紀錄：

```sh
aos-team spawn ls
```

### 想關掉，或想改成要你點頭

在 `team.json` 頂層加一段 `spawn`（管全隊），或在某個成員自己底下加 `"spawn": ...`（只管這個人、蓋過全隊那段）：

```json
"spawn": {"templates": [], "approve": false}
```

- `"templates": []`：這隊不准生（不寫這欄＝內建模板都能生；成員自己底下另寫 `templates` 的例外）。
- `"approve": true`：改成要你先點頭——郵差開一題「[成員] …」，你 `aos-team spawn approve q-NNNN` 才真的生。
- 只想管一個人：寫在那個成員底下，蓋過全隊那段。例：領隊生人要點頭 `"lead": {"template": "lead", "mail_to": [...], "spawn": {"approve": true}}`；不准領隊生 `"spawn": false`；讓某個工人也能生 `"spawn": true`。
- 關掉、改成要點頭：存檔後郵差下一份申請就照新的辦。**打開**一個原本不能生的成員：它手上還沒有 `spawn_member` 工具，要 `aos-team rm 名字` 再 `aos-team init` 重生它的家。

### 工人造工具

工人遇到「這件事一直機械地重複做、又沒現成工具」，可以叫 `tool_draft` 寫一支小工具（附幾條例子）。郵差自動在牢裡跑那幾條例子，過了才開一題「[工具] …」問你——**這條一定要你點頭，沒有「預設開」**：

```sh
aos-team tool ls
aos-team tool approve q-NNNN
```

批准後郵差把工具裝進寫的那個人的家；沒過會退一封信說哪條沒過，工人改了可以再交（同名）。

### 收掉生出來的成員

跟收掉手寫的成員一樣：

```sh
aos-agent stop --target $W/myteam/members/worker-2
aos-team rm worker-2
```

細節：[spawn.md](../../spec/team/spawn.md)、[toolsmith.md](../../spec/team/toolsmith.md)。

## 11. 跨團隊公共資料夾（commons）與圖書館員

每個成員預設都多看得到一格 `/work/commons`（唯讀）：同一台機器上所有團隊共用的經驗、名冊樣板、工作流、工具包。資料夾在團隊資料夾的上一層，這裡就是 `$W/commons/`（`aos-team init` 建好）。

成員自己會用兩支工具：`commons_search` 找（純程式，不花模型），`commons_submit` 投一條（例：做完一張單覺得「這個坑別隊也會踩」）。**投稿只有圖書館員隊收得進去**，所以要開一支只有一個人的圖書館員隊，跟你的團隊放同一個上層：

```sh
mkdir -p $W/lib $W/lib-proj
cat > $W/lib/team.json <<'EOF'
{"project": "../lib-proj", "members": {"librarian": {"template": "librarian", "mail_to": ["human"]}}}
EOF
aos-team init --target $W/lib && aos-team start --target $W/lib
```

它的郵差每輪自己檢查投稿（缺欄位、路徑、大小、執行位、完全重複都直接退），乾淨的直接入庫，**只有跟舊條目很像的才叫圖書館員（模型）判「收或不收」**，所以用最便宜的模型就夠。結果會寄回投稿的成員。

你自己看、加、刪：

```sh
aos-team commons ls                     # 一條一行；人看的總表是 $W/commons/INDEX.md
aos-team commons show lesson-0001
aos-team commons add lesson --title "…" --fits "適合什麼活" --tags a,b --body-file note.md
aos-team commons rm lesson-0001
aos-team commons import ~/repo/…/proto5/playbook   # 把 playbook 的經驗一次匯進來
```

不想讓某個團隊或成員看到：名冊頂層寫 `"commons": false`，或成員那列寫 `"commons": false`，再 `aos-team init`。細節：[commons.md](../../spec/team/commons.md)。
## 12. HR：這個位子用笨一點的模型行不行

公司路線是「強模型先做 → 換笨模型 → 換程式」。每換一步之前先**試用**：抄一份團隊、只換一個成員的模型、跑同一份任務集、用同一支評分指令打分，分數沒掉太多就記進薪資表。原團隊一個檔都不動。

```sh
aos-team hr ls                       # 每個成員：位子、正式／臨時、模型、等級、薪資表的「最低通過」
aos-team stop                        # 試用副本的成員名跟你的一樣，同一個 kernel 上會撞名：先停（或用另一個 kernel）
aos-team hr trial --member worker-1 --model chatgpt-gpt-6-astra --taskset proto5/examples/hr/ex1/taskset-worker.json
aos-team hr trial --member worker-1 --model deepseek-chat       --taskset proto5/examples/hr/ex1/taskset-worker.json
aos-team hr salary
```

- `--model` 是 `llm.json` 的**代號**，要先在 `llm.json` 加好（例如代號 `chatgpt-gpt-6-astra` 指到 LiteLLM 同名模型）。
- 每次試用印一行：分數、機械檢查過沒、token、秒、六軸、判定。強模型那次是「基準」；便宜的那次分數 ≥ 基準 − 5 而且機械全過＝「通過」，薪資表 `worker` 的「最低通過」就填它（附兩次的編號當證據）。
- **薪資表不會自動改你的名冊**。看過紀錄（`aos-team hr trials`）覺得可以，再 `aos-team hr set worker-1 --model deepseek-chat`：改名冊、改那個成員家裡的模型、登記著就重啟它。
- HR 的檔在 `$AOS_KERNEL_HOME/hr/`：`salary.json`、`policy.json`（人頭與 cpu 上限、容差）、`trials.jsonl`，都能用文字編輯器看、改。`aos-team hr cap` 看全公司正式員工幾人、cpu 開了幾顆。
- 名冊每個成員可以寫 `"employment": "regular"`（正式員工，預設）或 `"temp"`（臨時工，領隊 `spawn_member` 生的就是這種）。

細節：[hr.md](../../spec/team/hr.md)。

## 底下在幹嘛

- `init` 照模板替每個成員生一個 agent 家（`$W/myteam/members/<名>/`），人格裡的 `{name}`、`{mail_to}` 換成實際值，工具包照模板裝；每個家都有 `access.json`，工具關在牢裡跑：專案掛成 `/work/ws`（工人可寫，領隊、審查唯讀）、自己的寄件格 `/work/outbox`、任務表 `/work/board`（唯讀）。
- 模型能做的只有「往自己的寄件格放一個檔」：`team_say` 寄信、`handoff` 派工、`review_result` 回審查、`ask_human` 問你。開單、改單子狀態、投信、交驗收，全是郵差照規則做。郵差預設 5 秒巡一次（`team.json` 的 `post.interval_s`）。
- agent 沒事時會停車（不佔 cpu），信投進它的 `input/` 就被叫醒。
- 資料夾怎麼長、誰寫哪個檔：[layout.md](../../spec/team/layout.md)。

`route test` 只跑規則檔裡自帶的例句（`--file F` 換一個規則檔）。想知道一句話會不會命中：`aos-team route try "看一下單子"`，印它會命中哪條、會跑什麼或開什麼單、落穿給誰，**什麼都不做**（不跑、不開單、不寄信、不寫 route.log）。

想給工人一支自己寫的 Python 函式當工具（第二波 A 隊）：`aos-agent tools wrap-py mytools.py --out $W`（有型別註解的函式才收，印一張收／拒收表）→ `aos-agent tools test $W/mytools`（自動試正例、型別錯、缺參數，關在牢裡跑）→ `aos-agent tools add $W/mytools --target $W/myteam/members/worker-1`。工具關在牢裡、只碰得到專案，派工信直接叫它用那支工具就好。細節見 [tools-dev.md](../../spec/aos-agent/tools-dev.md)。

## 常見錯誤

- **`BadProject`**：團隊資料夾跟專案一個包著另一個。分開放。
- **`專案資料夾 … 不存在`**：先 `mkdir -p` 專案；`project` 是相對團隊資料夾（`$W/myteam`）算的。
- **`aos-team: Usage: 要設 AOS_KERNEL_HOME`**：新終端沒 `. $HOME/aos-try/env.sh`。
- **`AlreadyExists … 同名行程`**：同一個 kernel 上兩支團隊不能有同名成員（kernel 用 `agent-<名>` 登記）。第二支團隊的成員換名字。
- **信一直 `未收`、單子不動**：`aos-team ls` 看最後兩行；郵差寫「壞了」就照那行說的看 `post.err`、修好後重登記。成員的 health 不是 `ok` 就照 [教程 03](../03-first-agent.md) 看 `aos-agent status --target $W/myteam/members/<名>`。
- **工人卡住問你問題**：`aos-team wait ls` 看題目，`aos-team answer q-0001 "…"` 回答；答案會變成一封信回到發問的人。

## 收工

`aos-team stop` 之後，要整個丟掉就刪 `$W/myteam` 和 `$W/proj`。daemon、kernel 照 [教程 01](../01-daemon-kernel.md) 關。
