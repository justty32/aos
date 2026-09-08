# proto3 骨幹必須提供的接口契約（從 proto2 的 16 個工具包反推）

只讀不改的稽查結果。對照的兩邊是：

- 契約文件：`/home/guanyu/projs/aos/proto2/docs/packs-api.md`（129 行）
- 實際程式：`/home/guanyu/projs/aos/proto2/packs/*.py`（18 個檔，其中 16 個是正式工具包）
  與骨幹 `/home/guanyu/projs/aos/proto2/aos_agent.py`、`/home/guanyu/projs/aos/proto2/aos-agent`

一句話結論：**契約文件大致準確，但漏掉了三塊真正的硬依賴**——(1) 從 `aos_agent`
直接 import 的 6 個 team 相關符號；(2) 一堆骨幹管的 JSON 檔（`llm-result.json`、
`prompts.json`、`engines.json`、`usage/`、`state.json` 的欄位）被工具包直接讀寫；
(3) 骨幹反過來讀工具包寫的檔（`ledger/*.jsonl`）。詳見 (f)。

---

## (a) 從 `aos_agent`／`aos_llm` 匯出的符號

### 工具包真的 import 的（只有 6 個符號，全部來自 `aos_agent`，沒有一個包 import `aos_llm`）

| 符號 | 簽名 | 定義處 | 哪幾個包用 | 一行說明 |
|---|---|---|---|---|
| `TEAM_BUDGET_KEYS` | `tuple[str]`＝`("tokens","hours","ticks","disk_mb","mem_mb","money_usd")` | `aos_agent.py:29` | team（`packs/team.py:5`；用在 `:108`、`:115`） | 預算帳本的六個欄位名，撥款時要幫對方補零 |
| `team_lock(root, name="team", timeout=TEAM_LOCK_TIMEOUT_S)` | contextmanager，yield 鎖檔路徑 | `aos_agent.py:491` | team（`packs/team.py:5`、`:106`、`:139`）、studio（`packs/studio.py:16`） | 八個人各一個 process，共用檔要 flock 獨佔鎖；同 process 可重入 |
| `team_member_name(world)` | `-> str｜None` | `aos_agent.py:559` | team（`packs/team.py:5`、`:43`）、studio（`packs/studio.py:16`、`:128`） | 用世界路徑反查 `team.json` 裡的成員名（不是資料夾名） |
| `team_root_of(world)` | `-> str｜None`（往上最多找 4 層） | `aos_agent.py:536` | team（`packs/team.py:5`）、studio（`packs/studio.py:16`）、code（`packs/code.py:76`，try/except ImportError）、pyshop（`packs/pyshop.py:47`，同樣 try/except） | 找到有 `team/team.json` 的工作室根目錄 |
| `team_status_of(world, light=False)` | `-> dict`（見下方形狀） | `aos_agent.py:658` | team（`packs/team.py:5`、`:49`、`:148`）、studio（`packs/studio.py:16`、`:413`） | 全隊現況快照：預算、花費、剩餘、每人狀態 |
| `load_pack(home, name)` | `-> module｜None` | `aos_agent.py:120` | studio（`packs/studio.py:15` `import aos_agent`、`:424`） | studio 用它抓 team 包，再 `team.run("team_grant", …, ctx)` 跨包呼叫（`packs/studio.py:426`） |

`team_status_of` 的回值形狀（proto3 必須一模一樣，team 與 studio 都在拆它）：
`{"name","root","preset","day","budget","spent","remaining","in_flight":{"main","side"},
"members":[{"name","role","reports_to","path","clock","active","state","busy","unread",
"in_flight","blocked","today_spent","budget","remaining"}]}`（`aos_agent.py:709-733`）。

### 契約文件有寫、但工具包沒有一個直接 import 的

- `aos_agent.create_world(world, home=".", template=None, tools=None, persona=None,
  prompts=None, llm=None, parent=None)`（`aos_agent.py:821`）——契約 `packs-api.md:44-45`
  說它是「new／spawn／team 共用的唯一底層」，但工具包只透過 `ctx.spawn()` 間接用到
  （`packs/kids.py:106`）。proto3 可以自由重寫它，只要 `ctx.spawn` 語意不變。

### `aos_llm.py` 的狀況

`/home/guanyu/projs/aos/proto2/aos_llm.py` 匯出 `home_of`、`read_json`、`write_json`、
`write_json_atomic`、`stamp`、`write_request`、`read_result`（`aos_llm.py:26,31,48,58,70,76,116`）。
**沒有任何工具包 import 它**。它只被骨幹自己用：`Ctx.put_mail` 用 `aos_llm.stamp()`
（`aos_agent.py:1155`）、`Ctx.send` 用 `aos_llm.write_request()`（`aos_agent.py:1210`）、
`aos-agent:226` 用 `read_result()`。→ **proto3 對 `aos_llm` 沒有工具包層的義務，可以整個換掉。**

---

## (b) `ctx` 物件欄位表

`Ctx` 定義在 `aos_agent.py:1005-1453`。每格用 `Ctx.for_pack(name)` 複製一份給每個包
（`aos_agent.py:1017`），複製時共享同一個 `state` dict 與 `loaded` list。

### 資料屬性

| 欄位 | 型別／值 | 定義處 | 哪些包用 | 契約有寫？ |
|---|---|---|---|---|
| `ctx.world` | 世界絕對路徑 | `aos_agent.py:1007` | code、fs、memory、pyshop、review、self、studio、team（共 19 處） | 有（`packs-api.md:26`） |
| `ctx.home` | 本體絕對路徑（通常＝world，可被 `--home` 改） | `aos_agent.py:1008` | 幾乎每個包，共 59 處，用最凶 | 有（`packs-api.md:26`） |
| `ctx.name` | 工作室成員名，否則資料夾名 | `aos_agent.py:1009` | bigmem、communication、self、studio、team | 有（`packs-api.md:27`） |
| `ctx.state` | 這格共用的 dict，格末寫回 `state.json` | `aos_agent.py:1010-1013` | branch、cost、memory、ref、review、studio（共 39 處） | 有（`packs-api.md:28`） |
| `ctx.loaded` | `list[(pack_name, module)]` | `aos_agent.py:1014` | **toolsmith**（`packs/toolsmith.py:120`、`:156`）、**review**（`packs/review.py:397`） | **沒寫！隱性依賴** |
| `ctx.pack` | 目前這個包的名字（`for_pack` 設的） | `aos_agent.py:1015` | 包不直接讀，但 `ctx.log` 前綴、`ctx.send` 登記 pending 都靠它（`aos_agent.py:1021`、`:1230`） | 沒寫 |

### 靜態小工具（class attribute，`aos_agent.py:1001-1004`）

| 方法 | 簽名 | 用量 | 契約 |
|---|---|---|---|
| `ctx.read_json(path, default)` | 讀不到或壞 JSON 回 default | 51 處，全部包都用 | 有（`:29`） |
| `ctx.write_json(path, obj)` | 先寫 `.tmp` 再原子換名 | 34 處 | 有（`:30`） |
| `ctx.truncate(text, n=4000)` | 截短 | 11 處（bigmem、fs、kids、memory、pyshop、think、toolsmith） | 有（`:32`） |
| `ctx.warn(msg)` | 印 stderr | **0 處** | 沒寫，也沒人用 |

### 方法

| 方法 | 簽名／回值 | 定義處 | 哪些包用 | 契約 |
|---|---|---|---|---|
| `log(text)` | 前綴 `aos-agent[名字/包名]:` 印 stderr | `:1020` | branch、studio、think | 有（`:31`） |
| `status()` | 回 `status_of()` 的九欄快照 | `:1024` | self（`packs/self.py:129`，只取 `memory.started`／`uptime_s`） | 有（`:100`） |
| `world_of(name_or_path)` | 通訊錄名／相對路徑／絕對路徑 → 世界絕對路徑；空的丟 ValueError；支援通訊錄值是 `{"dir":…}` | `:1027` | bigmem、communication | 有（`:36`） |
| `home_of(world)` | 解 `.aos/inst` 後回 home | `:1036` | **0 個包用** | 有（`:37`），沒人用 |
| `clock_of(world)` | `{"kind":"own\|shared\|none","state":…}` | `:1039` | kids（`packs/kids.py:127`）、self（`packs/self.py:126`） | 有（`:38-40`） |
| `depth()` | 沿 `parent.json` 算深度，頂層 0 | `:1078` | kids（`packs/kids.py:100`） | 有（`:41`） |
| `shared_clock(world, action)` | 改父世界 `.aos/inst` 的 `aos-exec <子>` 行；action＝pause／resume／kill；回 `(ok, msg)` | `:1089` | kids（2 處） | **沒寫！隱性依賴** |
| `find_llm()` | 找不到回 None | `:1134` | cost（`packs/cost.py:121`）、self（`packs/self.py:31`） | 有（`:92`） |
| `llm_dir()` | 找不到就人話結束該格（`die`） | `:1137` | branch（`:97`）、think（`:68`） | 有（`:92`） |
| `kids_dir()` | `<home>/kids` | `:1140` | kids | 有（`:91`） |
| `spawn(name, persona, clock="shared", template=None, packs=None, task=None, depth=None)` | 回 `(ok, msg)` | `:1143` | kids（`packs/kids.py:106`） | 有（`:46-48`） |
| `put_mail(target, source, content, **extra)` | 回檔案路徑或 None | `:1148` | communication、kids、memory、review、studio | 有（`:88-90`） |
| `contacts()` | 回 dict | `:1172` | communication、self | 有（`:90`） |
| `add_contact(name, path)` | 回 bool | `:1176` | **0 個包用** | 有（`:90`），沒人用 |
| `parent()` | 讀 `parent.json` | `:1185` | communication、self | 有（`:91`） |
| `kids()` | 讀 `kids.json` | `:1189` | communication、kids、self | 有（`:91`） |
| `send(kind, body, **opts) -> id` | opts：`engine`、`priority`、`requester`、`schedule_kind`、`deadline`、`timeout_s`（預設 600）、`target`、`mail_reply_to` | `:1193` | bigmem、branch、communication、jobs、think | 有（`:62-65`） |
| `pending()` | 只讀未完成請求 | `:1241` | jobs（`packs/jobs.py:117`） | 有（`:66`） |
| `sleep_until(kind, id)` | 寫 `state["sleeping"]` | `:1245` | bigmem、branch、communication、jobs、think | 有（`:68`） |
| `cancel(id) -> bool` | 走正常結果路徑回 `kind_of_error:"cancelled"` | `:1316` | jobs（2 處） | 有（`:66-67`） |
| `register_clock(where, interval=None, no_wait=False)` | 回 `(ok, msg)`；跑 `aos-daemon register` | `:1360` | jobs（`packs/jobs.py:103`） | 有（`:93-94`） |
| `unregister_clock(where)` | 同上 | `:1363` | jobs、kids | 有 |
| `pause_clock(where)` / `continue_clock(where)` | 同上 | `:1366`／`:1369` | kids | 有 |
| `reply(text, **extra)` | 原子寫 outbox → 叫所有 `on_reply` → 子 agent 自動轉寄父 inbox | `:1372` | jobs、studio（`packs/studio.py` 2 處） | 有（`:95-96`） |
| `sources()` | 信箱來源清單 | `:1408` | mailbox、studio | 有（`:98`） |
| `unread(source)` | 未讀檔名清單 | `:1411` | mailbox、studio（`packs/studio.py:279`） | 有 |
| `read_done(source)` | 已讀檔名清單 | `:1414` | mailbox | 有 |
| `mail_of(source, name)` | 回 `list[dict]`（一個檔可以裝 dict 或 list） | `:1417` | mailbox、studio | 有 |
| `mark_read(source, name)` | 搬進 `<source>/read/` | `:1420` | mailbox、studio | 有 |
| `preview(mail)` | 前 60 字 | `:1423` | mailbox | 有 |

---

## (c) 骨幹管的檔案格式表（工具包直接讀寫的那些）

「誰寫」欄的「骨幹」＝ `aos-agent`／`aos_agent.py`。

| 檔案（相對 `<home>` 或 `<world>`） | 誰寫 | 誰讀 | 關鍵欄位 | 契約 |
|---|---|---|---|---|
| `state.json` | 骨幹 `aos-agent:581-585`、格末統一寫回 | 骨幹＋幾乎每個包（透過 `ctx.state`） | 骨幹欄位：`state`、`step`、`busy`、`request`、`last_usage`、`started`、`announced`、`wait_ticks`、`empty_replies`、`sleeping`、`pending`、`question_steps`、`budget_block`、`llm_error_step`、`llm_errors`、`unread_told_step`、`recent_question_steps`。**包直接讀的骨幹欄位**：`step`（branch/cost/memory/review/studio）、`sleeping`＋`pending`（`packs/studio.py:810`）、`last_usage`（`packs/cost.py:237`、`:287`） | 只寫「這格共用狀態」，**欄位全沒列** |
| `prompts.json` | 骨幹 `append_history()`（`aos_agent.py:1510`） | **包直接改寫**：bigmem（`packs/bigmem.py:110-117` 把某段換成歸檔標記）、branch（`packs/branch.py:349` 整個換掉＝adopt、`:361-365` 砍掉最後一則 tool）、memory（`packs/memory.py:122`、`:241` 摘要／截半）、ref（`packs/ref.py:141`）、review（`packs/review.py:326` 只讀） | `list[{"role","content",…}]`，OpenAI 格式；最後一則若是 `role:"tool"` 有特殊語意 | **完全沒寫**，是最大的隱性依賴 |
| `llm-result.json` | 骨幹 `aos-agent:249`、`:287` | **cost**（`packs/cost.py:117`、`:134` 取 mtime_ns、`:234`） | `choices[0].message`、`aos.usage`、`aos.engine` | **沒寫** |
| `tools.json` | 使用者／`create_world`／**toolsmith**（`packs/toolsmith.py:47`、`:143`、`:154`） | 骨幹 `tools_conf`（`aos_agent.py:81`）、`tools_only`（`:92`）、`inline_sources`（`:99`） | `packs[]`、`tools[]`、`only[]`、`inline_mail[]` | 只寫了 `packs`（`packs-api.md:17`）與同名規則（`:20`） |
| `llm.json` | 使用者／`create_world` | 骨幹 `find_llm`（`:358`）、`agent_limits`（`:448`）、`Ctx.send`（`:1206`）；**包**：bigmem `mem_dir`（`packs/bigmem.py:36`）、branch `engine`（`:92`）、cost、review `review.{daily_cost,tool_cost}`（`packs/review.py:461-462`）、self `engine`（`packs/self.py:36`）、think（`:77`、`:86`） | `dir`、`engine`、`priority`、`max_steps_per_question`、`max_tokens_per_day`、`mem_dir`、`review{}` | 沒寫 |
| `contacts.json` | `create_world`／`ctx.add_contact` | `ctx.contacts()`、communication | `{名字: 路徑}` 或 `{名字: {"dir":…,"relation":…}}` **兩種形狀都要吃** | 有（`:90`），但沒說有兩種形狀 |
| `parent.json` | `spawn`／`create_world` | `ctx.parent()`、`ctx.depth()`、`ctx.clock_of` | `dir`、`name`、`clock` | 有 |
| `kids.json` | `spawn`／`team install`（`aos_agent.py:970`）／**kids 包**（`packs/kids.py:56`） | `ctx.kids()`、kids、self | `{名字: {name,dir,clock,created,depth,parent,alive,task,reports_to}}` | 有（`:91`） |
| `system-prompt.json` | 使用者／`create_world` | 骨幹 `system_text`（`aos_agent.py:191`） | `{"role":"system","content":…}` | 沒寫（但包不碰） |
| `inbox/<來源>/*.json` | `ctx.put_mail`（`:1148`）、外部 | 骨幹 `scan_inbox`（`:298`）、mailbox、**studio 直接列 `inbox/user/read/`**（`packs/studio.py:284-291`） | 信固定有 `from`／`to`／`time`／`content`；`**extra` 可加（studio 加 `order_id`，communication 加 `thread`／`reply_to`） | 有（`:88-89`），但 `read/` 子夾與「一檔可裝 list」沒寫 |
| `outbox/%04d.json` | `ctx.reply`（`:1372`） | **review 直接 glob**（`packs/review.py:127`、`:327`） | `role:"assistant"`、`content`、可選 `error:true` | 有（`:95`），但沒說包可以掃 |
| `side/<kind>/<id>.json` | 骨幹 `_finish_side`（`:1262`） | **包直接讀**：bigmem `side/mem-meta/`、communication `side/mail-meta/`（也**寫**，`packs/communication.py:152`）、jobs `side/jobs/`（`packs/jobs.py:125`） | 旁線結果原文 | 半有（`:73`） |
| `prompt-overrides/<包>.md` | **review 寫**（`packs/review.py:402`） | 骨幹 `system_text`（`aos_agent.py:192-199`） | 純文字，空檔＝不放 PROMPT | 有（`:114`） |
| `packs/<包>.py` | **toolsmith 寫**（`packs/toolsmith.py:86`） | 骨幹 `find_pack_file`（`aos_agent.py:143`：先 `<home>/packs`，再 `proto2/packs`） | Python 模組 | 有（`:17`） |
| `ledger/<日期>.jsonl` | **cost 包寫**（`packs/cost.py:295`） | **骨幹 `_team_ledger_money` 讀**（`aos_agent.py:623-641`，被 `status_of:438` 與 `team_status_of:695` 用）＋review 讀（`packs/review.py:104`） | 每行 `{time,step,tool,args_chars,result_chars,took_ms,round_steps,ok,error_kind,llm_round:{…,cost}}` | **完全沒寫**，而且是骨幹倒過來依賴工具包 |
| `<llm世界>/engines.json` | LLM 世界 | branch（`:97`）、cost（`:122`）、self（`:34`）、think（`:68`）、`team install`（`aos_agent.py:886`） | `[{name, base_url, model, price:{…}}]` | 沒寫 |
| `<llm世界>/defaults.json` | LLM 世界 | self（`:37`）、think（`:78`、`:87`） | `engine` 等預設 | 沒寫 |
| `<llm世界>/usage/<日期>.json` | aos-llm | self（`packs/self.py:95`）、骨幹 `today_usage_for`（`:462`）、`today_usage_all`（`:369`） | `by-model`（key＝`"<base_url>\|<model>"`）／`by-requester`（key＝requester 名）／舊式扁平 | 沒寫 |
| `<world>/.aos/inst` | `aos-exec`／`aos-loop` 讀（`aos-exec:32`、`aos-loop:44`）；`team install` 寫（`aos_agent.py:967`）；`ctx.shared_clock` 改（`:1089`）；**jobs 包直接寫**（`packs/jobs.py:101`） | 同上 | 純文字 shell script，整段丟 `os.system()` | 沒寫 |
| `<root>/team/team.json` | `team install`（`aos_agent.py:948`） | team、studio、code、pyshop（都經 `team_root_of`） | 見 (e) | 沒寫 |
| `<root>/team/budget.json` | `team install`（`:953`）、**team 包**（`packs/team.py:129`）、`team_auto_grant`（`aos_agent.py:735`） | `team_status_of` | `{schema,total,allocations:{名字:{六鍵}},grants:[],updated}` | 沒寫 |
| `<root>/team/progress.md` | **team 包 append**（`packs/team.py:137-139`） | 人 | Markdown 條列 | 沒寫 |
| `<root>/team/{orders,tasks,projects,files,notes,assets}/` | **studio 包**（`packs/studio.py:158-162`）、`team install` 建骨架（`aos_agent.py:927-943`） | studio、pyshop（`packs/pyshop.py:53`、`:57`） | studio 自己的單／任務 JSON | 沒寫（studio 專屬） |

**工具包自己的目錄（proto3 不用管，但別擋）**：`<home>/branches/`（branch）、
`<home>/thoughts/`（think）、`<home>/jobs/`（jobs）、`<home>/refs/`（ref）、
`<home>/memory/{notes,forgotten,lessons.md,lessons-archive,self-note.md}`（memory、review）、
`<home>/ledger/`（cost）。

---

## (d) hook／入口表

### 入口（骨幹去模組上抓的名字）

| 名字 | 形狀 | 骨幹取用處 | 說明 |
|---|---|---|---|
| `PROMPT` | `str`（模組層變數） | `aos_agent.py:207`、`:209` | 靜態 system prompt；有 `prompt-overrides/<包>.md` 就被取代 |
| `TOOLS` | `list[{"name","description","parameters"}]` | `aos_agent.py:164`（送模型）、`:228`（`pack_owners` 建歸屬表） | 同名工具「tools.json 的包排前面的贏」（`aos_agent.py:169`） |
| `run(name, args, ctx)` | 回 dict（會 `json.dumps`）或 str | `aos-agent:317`（`run_tool`） | 丟例外不會弄死該格，被包成 `{"error": "<工具> 出錯：…"}`（`aos-agent:319-321`）；`ctx` 是 `for_pack` 過的 |

### 掛勾（全部 `getattr(module, 名字, None)`，沒定義就跳過，丟例外只記 log）

| hook | 簽名 | 骨幹呼叫處 | 回值語意 | 哪些包實作 |
|---|---|---|---|---|
| `on_idle(ctx)` | 1 參數 | `aos-agent:28-36`（`call_idle_hooks`） | 回值忽略；必須短 | memory `packs/memory.py:232`、cost `packs/cost.py:305`、studio `packs/studio.py:806`、review `packs/review.py:492` |
| `on_act(ctx, tool, args, result, took_ms)` | 5 參數 | `aos-agent:358-368` | 回 None 不改；回別的就**取代**工具結果，後面的包與模型都看新值 | cost `packs/cost.py:282`、ref `packs/ref.py:64`、review `packs/review.py:425` |
| `on_reply(ctx, msg)` | 2 參數，`msg` 是剛寫進 outbox 的 dict | `aos_agent.py:1382-1389`（在 `Ctx.reply` 裡） | 回值忽略 | communication `packs/communication.py:171`、cost `packs/cost.py:309` |
| `on_result(ctx, kind, request_id, result)` | 4 參數 | `aos_agent.py:1263-1269`（`_finish_side`） | **只叫登記該旁線的那一包**；回文字＝新的 user 訊息喚醒主線，包成 `[<kind> <id>] <文字>`（`aos_agent.py:1310`）；沒實作就把結果原文投進自己 inbox（`aos_agent.py:1271`） | bigmem `:120`、branch `:289`、communication `:159`、cost `:313`、jobs `:166`、think `:296` |
| `on_main_result(ctx, request_id, result)` | 3 參數 | `aos-agent:40-48` | 回值忽略；每包都看得到 | 只有 cost `packs/cost.py:319` |
| `on_system_prompt(ctx)` | 1 參數 → `str` | `aos_agent.py:212-219`（`system_text`） | 非空就接在 PROMPT 後面；**每次主線請求前都叫**，所以有副作用的包塞在這（cost 在這裡結帳、branch 在這裡清 prompts.json 尾巴） | memory `:222`、cost `:325`、studio `:861`、branch `:357`、review `:517`、team `:157` |

**沒有 `on_tick`、沒有 `before_llm`。** 契約 `packs-api.md:126` 自己也承認「仍缺：送主線
LLM 前的通用攔截掛勾」。你問題裡提到的 `before_llm` 在 proto2 不存在。

順序保證：`on_act`、`on_reply`、`on_idle`、`on_main_result`、`on_system_prompt` 都照
`ctx.loaded` 的順序＝`tools.json` 的 `packs[]` 順序（`aos_agent.py:140-153`）。`on_result`
不照順序，只叫 `pending` 項目裡記的那一包（`aos_agent.py:1230` 存 `"pack": self.pack`）。

---

## (e) preset 設定鍵表

檔案：`/home/guanyu/projs/aos/proto2/presets/studio/team.json`，
搭配每人一份 `<成員>/system-prompt.json` 與 `<成員>/prompts.json`
（例：`presets/studio/pm/system-prompt.json`、`presets/studio/pm/prompts.json`，
後者現在都是空陣列 `[]`）。

安裝這份 preset 的程式是 `aos_agent.py:869-976`（team install）。

### 頂層鍵

| 鍵 | preset 值 | 誰讀 | 說明 |
|---|---|---|---|
| `name` | `"studio"` | `aos_agent.py:730` | 隊名，顯示用 |
| `preset` | `"studio"` | `aos_agent.py:730` | 只是回顯 |
| `leader` | `"owner"` | `aos_agent.py:908`、`:934`、`:961`、`:972`、`:790`、`:647` | 誰是頂層世界（`path: "."`）、誰不用 parent、誰不進 `kids.json`、誰不上父鐘 |
| `llm_dir` | `"../llm"` | `aos_agent.py:881`（`AOS_LLM_DIR` 環境變數優先） | 全隊共用的 LLM 世界 |
| `max_depth` | `2` | **沒人讀** | 死鍵；kids 包用的是自己的 `MAX_DEPTH = 2`（`packs/kids.py:6`） |
| `project_root` | `"team/projects"` | **沒人讀** | 死鍵；studio 自己寫死 `team/projects`（`packs/studio.py:161`） |
| `budget` | 六鍵＋`reserve_pct` | `aos_agent.py:880` → `normalize_team_budget`（`:596-612`） | 全隊總預算；`reserve_pct` 預設 10，須 0–100（`:603-606`） |
| `members[]` | 8 人 | `aos_agent.py:876` | 見下 |
| `auto_grant` | `{from:["pm","owner"], tokens:50000, max_per_member:100000}` | `aos_agent.py:735-762`（`team_auto_grant`），由 `aos-agent:413`、`:434` 在額度閘門裡叫 | 成員 tokens 用完又有活等著，直接從 from 清單第一個「剩得夠」的人撥一筆，不寄信、不叫模型 |

### 成員鍵

| 鍵 | 誰讀 | 說明 |
|---|---|---|
| `name` | `aos_agent.py:877`、`:892` | 必須唯一且合 `NAME_OK` |
| `role` | `aos_agent.py:710`、team 包 `packs/team.py:93` | 顯示＋`team_grant` 可以用 role 找人 |
| `path` | `aos_agent.py:568`、`:616`、`:711`、`:893`；`aos-agent:452`；`aos-user:274,304,556,657` | 相對 root 的世界路徑；leader 是 `"."` |
| `reports_to` | `aos_agent.py:710`、`:967`、`:1396-1404`；`aos-agent:441`；studio `packs/studio.py:855` | **關掉「子 agent 每句話自動轉寄父」**（`aos_agent.py:1392`）；studio 卡住時往上報 |
| `persona` / `prompts` | `aos_agent.py:895-896` | preset 目錄下的相對檔名；預設 `<名字>/system-prompt.json`、`<名字>/prompts.json` |
| `packs` | `aos_agent.py:911` | 直接抄進該成員的 `tools.json.packs` |
| `clock` | `aos_agent.py:910`、`:965`、`:972`；`aos-user:302,655` | **只比對 `== "own"`**。`"shared:owner"` 的 `:owner` 後綴**從來沒被解析過**——任何不是 `"own"` 的值都當 shared，然後在 root 的 `.aos/inst` 追加一行 `aos-exec <相對路徑>`（`aos_agent.py:973`）。`team_status_of:711` 只是把原字串回顯 |
| `engine` | `aos_agent.py:901-906` | `cheap`／`thinking` 是**檔次不是引擎名**：只有 `<llm世界>/engines.json` 真的有同名 engine 才寫進 `llm.json.engine`，否則走 LLM 預設（`aos_agent.py:886-888`、`:902`） |
| `budget_pct` | `aos_agent.py:952`（`_budget_part`） | 初始 `budget.json.allocations` 的百分比；studio preset 給 owner 10／sales 5／pm 85，其餘 0（靠 `team_grant`／`auto_grant` 撥） |
| `only` | `aos_agent.py:912-913` → 寫進 `tools.json.only` → `tools_only()`（`:92`）→ `tool_specs(…, only)`（`:186`），由 `aos-agent:61` 套用 | 白名單：**包照樣載入、掛勾照樣跑**，只是不把工具送給模型 |
| `inline_mail` | `aos_agent.py:914-915` → `tools.json.inline_mail` → `inline_sources()`（`:99`）→ `scan_inbox()`（`:303`、`:308`） | 列到的來源（或 `"*"`）的信整封直接進 prompt 並當場搬進 `read/`，不再只通知「你有新信」 |
| `active` | `aos_agent.py:907` 安裝時強制 True；`:712-713` 讀；`aos-user:505,666` 讀寫 | 停掉的人在 `team_status_of` 顯示 `stopped` |

### 安裝時的副產物（proto3 也得照做，不然 studio 流程整個不會動）

`aos_agent.py:919-975`：每人一份 `contacts.json`（互相認識；`sales` 額外加 `user`＝
`AOS_USER_DIR`）→ 建 `team/{projects,notes,files/final}` → 把 `presets/studio/assets`
整包 `copytree` 進 `team/assets`（`:932-934`）→ **非 leader 的成員世界建一個
`team` symlink 指向共用區**（`:938`，這就是 `packs/code.py:71-83` 要特別把共用區也算
「專案內」的原因）→ 寫 `team/team.json`（runtime 版，多了 `root`／`llm_dir`／`created`）
→ `team/budget.json` → `team/progress.md` → root 的 `kids.json` → root 的 `.aos/inst`。

---

## (f) 契約 vs 實際：隱性依賴與沒人用的

### 契約沒寫、但實際硬依賴（proto3 一定要提供，不然工具包直接 ImportError／KeyError）

1. **`from aos_agent import TEAM_BUDGET_KEYS, team_lock, team_member_name, team_root_of,
   team_status_of`**（`packs/team.py:5-6`、`packs/studio.py:16`）。契約通篇沒提「工具包可以
   直接 import 骨幹符號」，但這是 studio preset 的地基。`code`／`pyshop` 還加了
   try/except ImportError 的防禦寫法（`packs/code.py:75-79`、`packs/pyshop.py:46-50`），
   說明作者自己也知道這條線很脆。
2. **`import aos_agent` + `aos_agent.load_pack(ctx.home, "team")` 跨包呼叫**
   （`packs/studio.py:15`、`:424-427`）。studio 直接把自己的 `ctx` 傳給 team 的 `run()`
   ——注意那個 ctx 的 `ctx.pack` 是 `"studio"`，不是 `"team"`。proto3 若改成沙箱化的
   pack 載入，這條會斷。
3. **`ctx.loaded`**（`packs/toolsmith.py:120`、`:156`、`packs/review.py:397`）——契約沒列的
   `list[(名字, module)]`。
4. **`ctx.shared_clock(world, action)`**（`packs/kids.py` 2 處）——契約只寫了 register／
   unregister／pause／continue 四個，漏了這個。它是**直接編輯父世界 `.aos/inst` 文字**
   的，等於工具包知道 inst 的檔案格式。
5. **`state.json` 的骨幹欄位**：`step`（6 個包）、`sleeping`＋`pending`
   （`packs/studio.py:810`）、`last_usage`（`packs/cost.py:237`、`:287`）。契約只說
   「ctx.state 是這格共用狀態」，沒說裡面有骨幹的東西。
6. **`prompts.json` 是可寫的**：branch 用 `write_json` 整個換掉來實作 adopt
   （`packs/branch.py:349`），bigmem 換掉一個 slice（`:110-117`），memory 砍半
   （`packs/memory.py:241`）。契約完全沒提對話歷史檔的存在與格式。
7. **`llm-result.json`**（`packs/cost.py:117`、`:134`、`:234`）——cost 靠它的 `aos.usage`、
   `aos.engine` 與**檔案 mtime_ns** 判斷「這是不是新的一輪」。這是最髒的一條依賴。
8. **`<llm世界>/engines.json`／`defaults.json`／`usage/<日期>.json`** 的形狀（branch、
   cost、self、think）。特別是 usage 有三種歷史形狀：`by-model`／`by-requester`／扁平
   （`aos_agent.py:369-377`、`:462-476`、`packs/self.py:97`）。
9. **`inbox/<來源>/read/` 子目錄**與「一個信檔可以是 dict 也可以是 list」
   （`aos_agent.py:278-285`、`packs/studio.py:284-291`）。
10. **`outbox/*.json` 可被工具包 glob**（`packs/review.py:127`、`:327`）。
11. **`.aos/inst` 的格式**：jobs 直接生一份三行的 inst（`packs/jobs.py:96-102`），最後一行是
    `aos-daemon unregister . --no-wait`——所以工具包**間接依賴 `aos-daemon` 在 PATH 上**
    （`aos-exec:20-22` 與 `aos-loop:16-18` 會把自己的目錄塞進 PATH）。這是唯一一處
    工具包直接叫骨幹執行檔的地方（沒有任何包用 subprocess 直接叫 `aos-exec`／`aos-loop`／
    `aos-llm`／`aos-user`）。
12. **反向依賴：骨幹讀工具包寫的檔。** `_team_ledger_money`（`aos_agent.py:623-641`）讀
    `<home>/ledger/<日期>.jsonl`，那是 **cost 包**寫的（`packs/cost.py:295`）。它被
    `status_of:438`（→`ctx.status()`→self 包）與 `team_status_of:695`（→ 額度閘門
    `aos-agent:378`）用。**沒開 cost 包的 agent，`money_usd` 永遠是 0。**
13. **環境變數**：`AOS_USER_DIR`（`packs/communication.py:41`、`:172`）、`AOS_DAEMON_DIR`
    （`packs/jobs.py:70`）、`AOS_MEM_DIR`（`packs/bigmem.py:36`）。契約只在 `:94` 提了
    `AOS_DAEMON_DIR` 一次。
14. **`contacts.json` 的值有兩種形狀**（純字串路徑 vs `{"dir":…}`）：`Ctx.world_of` 兩種都吃
    （`aos_agent.py:1028-1031`），communication 自己也做同樣的事（`packs/communication.py:46-50`）。
15. **`ctx.name` 的解析順序**：先 `team_member_name(world)`，才退回資料夾名
    （`aos_agent.py:1009`）——所以 `ctx.name` 在工作室裡是 `pm`，不是 `kids/pm`。
    寄信、旁線 requester、ledger 都靠這個。

### 契約寫了、但沒有任何工具包用

| 東西 | 契約行 | 狀況 |
|---|---|---|
| `ctx.home_of(world)` | `packs-api.md:37` | 0 個包用（只有骨幹自己的 `put_mail` 用） |
| `ctx.add_contact(name, path)` | `packs-api.md:90` | 0 個包用 |
| `ctx.warn` | 沒寫但存在（`aos_agent.py:1003`） | 0 個包用 |
| `aos_agent.create_world(...)` 當公開 API | `packs-api.md:44-45` | 包只透過 `ctx.spawn` 間接用 |
| `ctx.send` 的 `requester` opt | `packs-api.md:63` | 0 個包傳；骨幹自己算（`aos_agent.py:1213`） |
| `ctx.send` 的 `schedule_kind`／`deadline`／`priority` | `packs-api.md:57-58,63-64` | 0 個包傳（只有 branch 傳 `engine`、多數包只傳 `timeout_s`／`target`） |
| 舊名 `shell` 自動改載 `fs` | `packs-api.md:18` | `aos_agent.py:143-146` 還在做；`presets/studio/team.json` 已經全部寫 `fs`。可以在 proto3 直接砍掉 |
| `on_result` 的 `no_clock` 錯誤種類 | `packs-api.md:82` | 骨幹會產（`aos_agent.py:1305`），但沒有包針對它分支處理（都只看 `result.get("error")`） |

### preset 裡的死鍵

- `team.json.project_root`（`presets/studio/team.json:6`）——全 repo 沒有第二處提到。
- `team.json.max_depth`（`presets/studio/team.json:7`）——同上。
- `members[].clock` 的 `":owner"` 後綴（8 人裡 6 人寫 `"shared:owner"`）——只被
  `!= "own"` 比對，後綴是裝飾。

---

## (g) 判斷：哪些難搬、哪些包一層薄的相容層就好

### 一層薄相容層就能包起來（低風險，proto3 可以自由重寫底層）

- **`ctx` 的純函式面**：`read_json`／`write_json`／`truncate`／`log`／`world`／`home`／`name`。
  這幾個沒有狀態，proto3 內部隨便怎麼實作，外面照抄簽名即可（`aos_agent.py:1001-1021`）。
- **信箱七件套**：`sources`／`unread`／`read_done`／`mail_of`／`mark_read`／`preview`／
  `put_mail`。都是純檔案系統操作，只要保住「`inbox/<來源>/*.json`＋`read/` 子夾＋
  一檔可裝 dict 或 list」這個磁碟格式（`aos_agent.py:255-296`），內部怎麼寫都行。
- **鐘的四件套** `register/unregister/pause/continue_clock`：現在只是 subprocess 叫
  `aos-daemon`（`aos_agent.py:1335-1359`），回 `(ok, 一句話)`。proto3 換成 in-process
  呼叫也完全不影響工具包。
- **`ctx.status()`**：只有 self 包用，而且只取 `memory.started`／`memory.uptime_s`
  （`packs/self.py:129-135`）。九欄可以先給一個最小可用的 stub。
- **`ctx.spawn`／`create_world`**：只有 kids 包用一次（`packs/kids.py:106`），回
  `(ok, msg)`。內部大改沒差。
- **`TEAM_BUDGET_KEYS`／`team_lock`／`team_member_name`／`team_root_of`**：語意很乾淨，
  給一個 `aos_agent.py` 相容 shim 模組（`from aos3.team import ...` 再 re-export）就結案。

### 難搬（proto3 要正面設計，包不動就得原樣復刻）

1. **`ctx.state` 是「一格內共享、格末寫回」的可變 dict，而且骨幹欄位和工具包欄位混在同一
   個 namespace**（`aos_agent.py:1010-1013`、`aos-agent:581-585`）。如果 proto3 想把 agent
   狀態換成 SQLite 或分檔，就得做一個「假 dict」代理，而且 `pop`／`setdefault`／
   巢狀 dict 就地修改（`packs/review.py:140-143` 拿到 `ctx.state["review"]` 之後直接改
   裡面的欄位）都得撐住。**這是最難的一條。**
2. **`prompts.json` 被工具包當可寫的一級公民**（branch adopt 整檔換、bigmem 換 slice、
   memory 砍半、branch 的 `on_system_prompt` 還會砍掉最後一則 `role:"tool"`）。proto3
   若把對話歷史改成結構化儲存，至少要保留一個「讀出 list、寫回 list」的
   `<home>/prompts.json` 視圖，而且**寫回要立刻生效於下一次 LLM 請求**。
3. **`llm-result.json` ＋ `state.last_usage` ＋ 檔案 mtime 的三角**（`packs/cost.py:225-280`）。
   cost 用 mtime_ns 判斷「主線結果換新了沒」。proto3 如果不再落地這個檔，cost 包整包失效，
   連帶 `ledger/*.jsonl` 沒了，`_team_ledger_money` 回 0，`money_usd` 閘門形同虛設。
   建議：proto3 直接把「本輪 usage／engine」做成 `on_main_result` 的正式參數，然後在
   相容層裡假造一個 `llm-result.json`——**或者乾脆承認這是要改 cost 包的一處**。
4. **骨幹反過來讀 cost 包的 `ledger/*.jsonl`**（`aos_agent.py:623-641`）。這是層次顛倒。
   proto3 應該把「花了多少錢」變成骨幹自己的帳，讓 cost 包降級成「讀帳＋分攤到工具」的
   分析器。這需要動 `packs/cost.py`，但只動它一個。
5. **`ctx.shared_clock` 與 jobs 寫 `.aos/inst`**：兩者都把「排程」暴露成一個純文字
   shell script 檔案格式（`aos_agent.py:1089-1132`、`packs/jobs.py:96-102`、`aos-exec:32-36`）。
   proto3 若改用真正的 scheduler，這兩處只能用「維護一個假的 inst 檔」硬撐，或改包。
   `kids` 與 `jobs` 是唯二受影響的包。
6. **`aos_agent.load_pack` 的跨包呼叫**（`packs/studio.py:424-427`）。proto3 若做 pack 隔離
   （不同 process／不同 module namespace），這條必須換成正式的「跨包呼叫 API」，例如
   `ctx.call_pack("team", "team_grant", args)`。這是 studio preset 的必經路徑，不能不管。
7. **`on_system_prompt` 事實上是「每輪前的通用攔截 hook」**：cost 在裡面結帳
   （`packs/cost.py:325-327`）、branch 在裡面改 `prompts.json`（`packs/branch.py:357-365`）。
   契約自己也說缺一個真正的 `before_llm`（`packs-api.md:126`）。proto3 應該加
   `before_llm(ctx)`，但**同時保留 `on_system_prompt` 在同一時機被叫**，否則這兩包壞掉。
8. **`only` 白名單的語意細節**：「包照樣載入、掛勾照樣跑，只是工具不送給模型」
   （`aos_agent.py:92-96`、`aos-agent:61`）。studio preset 八個人全部依賴這個
   ——例如 chief 的 `only` 沒有 `task_assign`，但 studio 包的 `on_idle` 和
   `on_system_prompt` 對他照樣運作。若 proto3 把 `only` 實作成「不載入該包」，
   整套流程會靜默壞掉。

### 建議的相容層形狀

proto3 保留一個 `aos_agent.py` 薄殼（只做 re-export），內容是：

- 6 個 team 符號 + `load_pack` + `create_world`
- `Ctx` 類別（含 `loaded`、`pack`、`shared_clock` 這三個契約沒寫的）
- 檔案格式維持不變的：`state.json`、`prompts.json`、`inbox/`、`outbox/`、`side/`、
  `contacts.json`、`parent.json`、`kids.json`、`tools.json`、`llm.json`、
  `prompt-overrides/`、`team/*`

需要接受「要改包」的只有兩處：**cost 的 `llm-result.json` 依賴**，
以及 **studio 的跨包呼叫**。其餘 14 個包理論上可以一行不改地搬過去。
