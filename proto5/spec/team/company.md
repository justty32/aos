← [team](README.md)｜樣板：[examples/company/](../../examples/company/README.md)｜報告：[2026-09-25-company](../../notes/2026-09-25-company/README.md)

# 公司：幾支團隊合成一間公司，加一個機械總機

2026-09-25 第 1 版（組織設計總監）。程式：[`lib/aos_company.py`](../../lib/aos_company.py)；指令包裝 [`examples/company/company.py`](../../examples/company/company.py)。

一句話：**一間公司＝一個資料夾**：`company.json`（部門、編制、上限）＋每個部門一支普通的 aos 團隊＋這家自己的 kernel（池的大小就是這家的 cpu 上限）＋一個**總機**。
團隊的規格一個字沒改：部門之間的往來全靠「寄給 human 的信」（本來就有）與「human 寄的信／開單申請」（本來就有），總機只是在兩者之間搬。

```text
董事 company.py order "補人物 老財" ──▶ hq 的門房 ──沒命中──▶ 總裁 c1-hq-lead（模型）
總裁 team_say → human：「〔給 mfg〕補人物 老財（只寫詞條）」   （落在 hq 的 team/human/）
總機（每 5 秒一輪，不叫模型）：看到〔給 mfg〕→ 開總機單 o-0001 → 照 mfg 的門房規則，
      命中 handoff ＝往 mfg 的 outbox/human/ 放一份開單申請（寄件人 human）；沒命中＝寫信給 mfg 的窗口
mfg 郵差開單 t-0001 → 寫手做 → 驗收員 → 審查員 → 郵差寄「t-0001 完成」給 human（落在 mfg 的 team/human/）
總機：reply_to t-0001 → 查單子的 request ＝ o-0001 的申請 → 抄一封「〔總機 o-0001 回覆：mfg 部 post → DONE〕」給總裁
總裁：「〔給 qa〕驗貨 老財」→ … 同上 … → 總裁寄一封不帶〔給〕的 DONE 給 human ＝ 給董事
```

## 1. 資料夾

```text
<公司>/                    company.py 的 -C（或 AOS_COMPANY_HOME）
  company.json             部門、編制、上限（§2）；人寫
  llm.json  kernel.json    模型代號；kernel 池（up 照 company.json 的 pools 寫）
  K/                       這家的 kernel
  D/                       這家的 daemon（company.json 的 daemon，預設 D；董事 09-25：一家一個 daemon＋kernel）
  teams/<部門>/            一般的 aos 團隊資料夾（team.json＋members/＋team/）
  config/<部門>.routes.json  門房規則的來源（up 時 route save）
  persona/*.md             公司層人格：up 時接在模板人格後面（每個家只接一次，記在 state/persona/<名>）
  switchboard/             總機的帳：orders/o-NNNN.json、seen/<部門>/<信 id>.json、relay.inst.json、.lock
  proj/（可以放別處）       專案；團隊資料夾不能包著它、它也不能包著團隊資料夾（layout.md）
```

## 2. `company.json`

| 鍵 | 意思 |
|---|---|
| `prefix` | 成員名前綴（`c1-`）；`new --prefix` 會把樣板每個成員名、`mail_to`、門房的 `assignee`、`staff`、`desk` 都加上。同一台機器開幾家就不撞名 |
| `limits` | 這家的上限 `{"regular", "cpu", "llm_cpu"}`，新創預設 10／20／5 |
| `limits_max` | 擴張到頂的上限，預設 100／200／25（董事 09-25 14:20：llm cpu 20→25）；`limits` 不能超過它 |
| `pools` | kernel 兩池的顆數 `{"default", "llm"}`；`default ≤ limits.cpu`、`llm ≤ limits.llm_cpu`（**cpu 不含 llm 池**，跟 HR 部 hr.md §5 同一個算法），超了整份不收（`OverLimit`） |
| `front` | 前台部門：董事 `order` 不帶 `--to` 時交給它的門房 |
| `departments.<代號>` | 一個部門：`title`、`team`（自己一支團隊的資料夾）或 `part_of`（併在別的部門的團隊裡，新創期的兼任）、`desk`（跨部門的信沒命中門房時交給誰；沒寫＝第一個 lead，再沒有＝第一個成員）、`aliases`（〔給 …〕認的別名）、`open`（false＝尚未成立，up 不開、總機退信）、`state`／`serves`／`delivers`／`kpi`／`lib`（給人看的說明） |
| `staff.<成員名>` | `dept`、`roles`（兼任寫這裡），給人看。**正式／臨時不寫這裡**：看名冊每個成員的 `employment`（HR 部 hr.md §7：人寫的預設 `regular`、spawn 生的 `temp`） |
| `relay.interval_s` | 總機多久一輪（預設 5） |

部門代號 `[a-z][a-z0-9]{0,11}`。其他鍵＝`FormatInvalid`。

## 3. 總機（relay）

kernel 反覆叫 `aos_company.py relay --company <公司>`（`up` 登記成 `company-relay-<路徑 crc>`），每輪拿 `switchboard/.lock`，看每個開著的部門的 `team/human/*.json`（寄給 human 的信），**每封只判一次**：

| 信 | 判成 | 做什麼 |
|---|---|---|
| 成員寄的、text 第一行開頭 `〔給 X〕`（也認 `[給 X]`、`【給 X】`；X＝部門代號、title 或 alias） | `order` | 開總機單 `o-NNNN`；X 的團隊有門房規則且**第一行**命中 `handoff`＝往 X 的 `outbox/human/` 放開單申請（goal 前加「〔總機 o-NNNN，… 交辦〕」，第二行以後併進 `facts`）；命中 `tool`（`run` 那種）＝在總機這裡跑、輸出當回覆立刻寄回；沒命中＝寫一封 REQUEST 給 X 的窗口，信頭說「做完 team_say 回 human，reply_to 寫 o-NNNN」 |
| 同上但 X 不存在／尚未成立／就是自己的團隊／後面沒字 | `bounce` | 退一封 FAILED 給寄件人（`〔總機退信〕…`） |
| `reply_to` 對得上一張總機單：單號本身、總機寫的那份申請或信的 id、或一張任務單（`t-0001`／`t-0001.r1`，看單子的 `request` 是不是總機寫的那份） | `reply` | 抄一封給下單的人（寄件人 human、status 照原信、`reply_to`＝下單那封信的 id），開頭 `〔總機 o-NNNN 回覆：<部門> 部 <寄件人> → <狀態>（<單號>）〕` |
| 窗口寄的、**沒寫** `reply_to`，而它手上正好只有一張開著的總機單 | `reply` | 同上（模型常忘了寫 reply_to）。有寫但對不上＝不猜，留給董事 |
| 開單類的總機單，負責人自己寄的 DONE | `note` | 只記下、不轉：還沒驗收，等郵差驗完寄的那封 |
| 其他（郵差、心跳寄的、沒標〔給〕的） | `board` | 不動，留給董事：`company.py mail` 列 |

- **結案**：開單類（`via: handoff`）看郵差寄的 DONE／FAILED；窗口類（`desk`）只看**窗口本人**寄的 DONE／FAILED（同部門別人寄的照抄給下單的人，但不結案）；`tool` 當場結。單子 `status`：`open`／`running`（工具跑到一半）／`done`／`failed`，結案時記 `closed_at`（市場層照它算「這一輪結的單」）。
- **董事直接下單**（`order --to 部門`）：一樣開總機單，`from.dept` 是 `board`；回覆不抄給誰，留在那個部門的收件匣給董事看（`mail` 會列）。
- **寄件人一律 human**：從對方部門看，總機交辦的事就是「公司」交辦的，郵差照 human 的權限收（human 能寄給任何成員、能開單）。總機寫的每一份都先過 `validate_letter`／`validate_request`，郵差還會再驗一次。
- **冪等**：每封信先記 `seen/<部門>/<信 id>.json`（判成什麼、要用的 id），再動作，做完標 `done`；總機單先記單號與要用的申請 id 再派。崩在中間重跑用同一個 id、`write_new` 不覆蓋，不會重派、不會重寄。
  - 崩在「單寫好、單號還沒記回 seen」：重跑照來信（`from.letter`）找回同一張，不另開。
  - 每輪最後**接續沒派完的單**：`via` 還是空的（董事單崩在派送前也算）＝再派一次。
  - 門房的 `tool` 規則：先把單標 `running` 存好再跑；重跑看到 `running`＝上次跑到一半，**不自動重跑**（工具可能有副作用），標 `failed` 回報下單的人（回信已經寄出＝照回信補記）。
- 總機**不叫模型、不改任何團隊的檔**：只寫 `switchboard/` 與各部門的 `outbox/human/`（那一格本來就是 human 的寄件格）。

## 4. 數人頭、數 cpu（`status`）

- **正式員工**：開著的部門名冊裡 `employment: regular` 的成員（跟 HR 的 `count_regular` 同一個數法）。
- **cpu**：`aos-kernel ls --json` 裡 llm 池以外的 `want` 加總；**llm cpu**：`pools.llm.want`（跟 HR 的 `count_cpus` 同一個算法：cpu 不含 llm）。kernel 沒開＝照 `company.json` 的 `pools` 算，並標 kernel down。
- 印一行 `正式 N/10、cpu N/20、llm cpu N/5`，超過的標出來，`status` 退 1。
- `up` 前先擋：正式員工超過 `limits.regular`、部門之間有同名成員 ＝ 不開。cpu 靠 `pools` 已經在 `company.json` 驗過（kernel 就只開那麼多顆，這是**硬擋**：多的工作排隊，不會多開）。
- **上限只有一個來源**：`company.json` 的 `limits`。`up` 把它寫進這家的 HR 政策 `K/hr/policy.json`（`regular_max`／`cpu_max`／`llm_cpu_max`，其他欄原樣留），所以 HR 的擋點（`aos-team init`／`start`／生成員）與 `status` 用同一組數；財務 `budget.json` 的 `cpus` 只拿來印 cost 表，不擋。
- 給 `aos-team` 的環境帶這家的 `AOS_KERNEL_HOME`、`AOS_HR_HOME=<公司>/K/hr`。`AOS_DAEMON_HOME`：daemon 是這家自己的（在公司資料夾裡，預設 `<公司>/D`）＝照帶，HR 數 cpu 只數得到自己；company.json 寫成幾家共用（例 `"daemon": "../D"`）＝不帶，因為 HR 數 cpu 會把同一個 daemon 上的每個 kernel 都算進來、互相擋。`aos up／down`、`aos-kernel init／ls` 一律帶。

## 5. 指令

| 指令 | 做什麼 |
|---|---|
| `new 資料夾 [--prefix c1-] [--project P] [--llm-cpu N] [--cpu N] [--from 樣板]` | 照樣板生一家（不蓋已有的 `company.json`）；`--llm-cpu` 同時把 llm 池縮到它以下 |
| `up -C 公司` | 寫 `kernel.json` → `aos-kernel init`（第一次）；**K 已經在＝把 `K/info.json` 兩池的顆數對到 `company.json` 的 `pools`**（`aos-kernel cpu add／rm`，對不上不開；市場層 `slots` 改的上限這時生效）→ `aos up` → 每個開著的部門 `aos-team init`、`route save`、接公司人格、`start` → 登記總機。設了 `AOS_COST_HOME` 會傳進兩個池（帳記得到這家；K 建好後再改 envs 要手編 `K/info.json`） |
| `down -C 公司` | 撤總機（印「總機撤了」）→ 每個部門 `aos-team stop` → `aos down`（印 kernel、daemon 停了沒；自家 daemon 一起關）。任何一步沒停好＝退 1（市場層靠它決定能不能封存） |
| `status -C 公司 [--json] [--no-kernel]` | 上限一行＋每部門成員數、單子（進行／全部）、等人答的題數＋最近的總機單＋董事收件匣封數 |
| `order -C 公司 "一句話" [--to 部門]` | 董事下單：預設 `aos-team ask` 給前台部門；`--to` 直接開總機單給那個部門 |
| `mail -C 公司` | 董事收件匣：各部門寄給 human、判成 `board` 的信，和董事自己下的總機單的回覆 |
| `answer -C 公司 部門 q-NNNN "…"` | 回某部門的題（就是 `aos-team answer --target 那個部門`） |
| `relay -C 公司 [--quiet]` | 總機走一輪（kernel 反覆叫；人手動也行） |

## 6. 沒做的、保證外

- **總機只認〔給 …〕與 reply_to**：模型把〔給 mfg〕寫在第二行、或回信寫錯 reply_to（又不只一張開著的單）＝那封留給董事。`mail` 看得到，董事可以用 `order --to` 補派。
- 跨部門的**開單申請**只走對方的門房：想跨部門直接指定負責人、`done_when`，沒有這條路（要就在對方門房加規則，人批）。
- 一家公司一個 kernel：上限是真的（池只有那麼多顆）；幾家共用一個 kernel 的話池是共用的，`status` 的 cpu 會算到別家——所以樣板一律一家一個 kernel、一個 daemon（`K/`、`D/` 都在公司資料夾裡，`down` 一起關；董事 09-25 授權「有需要的話，可以每公司一個 daemon 和 kernel」），名字照樣加前綴（萬一共用也不撞名）。
- 部門的 `open` 只管 up 與總機；已經在跑的團隊改成 `false` 不會自己停（先 `aos-team stop`）。
- 市場層（幾家公司競爭、按表現撥額度、倒閉、合併）見 [market.md](market.md)。
