# 線壬施工結果（11-13）：畫面開著的 claude 身，信改用署名訊息投進 CLI 的收件口；投不進去就照舊貼字

← [11-13 日索引](README.md)｜出處：[eca-a2a-notify](eca-a2a-notify.md)（調查、三個做法、兩題裁定）

## 出問題時一步關掉（退回貼字）

1. **單隻**：那隻定義的 `cli.json` 加 `"a2a": false`——下一輪起照舊貼字，不用重開畫面。
2. **全部**：`proto8/lib/agent/cli_a2a.py` 的 `ENABLED = True` 改成 `False`，存檔就生效（repo 那份；指令直接 import 它）。
3. **整個退掉**：`git revert` 接線那個 commit（本檔所在的 commit）。

它自己也會關：投了、CLI 閒著 30 秒沒回執，那個畫面就自動改回貼字（stderr 一行 warning），到重開畫面或 `/clear` 才再試。已經開著的舊畫面本來就沒換，照舊貼字。

## 使用者裁定（逐字）

「1.a2a這個按照建議。馬上送，eca他會自己處理。say/chat被當成不是使用者打的，我覺得可以，真的有要的話，就自己open進去說。」

## 結論

- 畫面（tmux）開著的 claude 身 eca，一批信不再「貼字＋Enter」，改成往那個 Claude Code session 自己的收件口（一條 Unix socket）寫：一封信一則訊息、各有署名。畫面上顯示「› Message from @名字: …」，CLI 自己會跟模型說這則不是它的使用者打的。
- 署名：`aos-agent say`／`chat` 對 eca 說的話＝真正的寄件人；其他（新信通知、時鐘信、goal 提醒、開場白、換台提要）＝「aos通知中心」。
- 忙時馬上送：有人接在畫面上、畫面正在跑一輪都照投；`aos-eca-turn` 在等上一批回答時又來的信，也當場認領、投進去（CLI 手上那步工具做完就讀到）。人在輸入框打到一半的字不會被動到。
- 投不進去就退回原本的貼字，`--on-busy` 照原本的規則：沒記到收件口、連不上、或投了 30 秒 CLI 閒著卻沒有回執。
- 畫面沒開的路（每輪新起 `claude -p`）、codex 身、slash 指令、工具形（`--one`、lib 的 claude／codex 工具）照舊；queue、hook、history、冷卻的流程沒改。

## 盤點 12 項各怎麼定

| # | 東西 | 畫面開著的 claude 身 | 署誰的名 |
|---|---|---|---|
| 1 | 新信通知（`mail_notify`） | 改走收件口 | aos通知中心 |
| 2 | `aos-agent say`／`chat` | 改走收件口 | 真正的寄件人：`--from` ＞ 下指令的 agent（`$AOS_STACK` 落在 daemon 表上哪一隻）＞ 登入名 |
| 3 | 父對子說話（`subagent` 的 say／ask） | 改走收件口 | 父 agent 的名字（同上第二條，自動帶，工具沒改） |
| 4 | 時鐘信 | 改走收件口 | aos通知中心 |
| 5 | goal 提醒 | 改走收件口 | aos通知中心 |
| 6 | 開場白（`--prompt FILE`） | 改走收件口（那時畫面剛好開著才會） | aos通知中心 |
| 7 | 換台／重開的前情提要 | 改走收件口，自己一則、排在那批信前面 | aos通知中心 |
| 8 | slash 指令 | 不動（照舊打字；收件口不收指令） | — |
| 9 | codex 選單自動 Enter | 不動 | — |
| 10 | 多封合一 | 走收件口時不再接成一段：一封一則、各署各的名（CLI 仍合成一輪回答）；貼字與非互動照舊用空行接 | 各封自己的 |
| 11 | `before_queue` 改信 | 不動（hook 改完的內容才包進訊息，署名照原信） | 照原信 |
| 12 | 人自己在畫面上打字 | 不動 | — |

畫面沒開、codex 身：12 項全部照舊（字樣本來就是 `[aos] 種類: 內容`，沒有要對齊的）。

## commit

| commit | 做了什麼 |
|---|---|
| `24a3f797d` | 批 1：三個新檔（`lib/agent/cli_a2a.py`、`cmd/aos-eca/aos_eca/midturn.py`、`cmd/aos-agent/aos_agent/sender.py`），現有程式還沒 import，行為不變 |
| 本檔所在的那個 commit（批 2） | 批 2＝**接線**：`cli_ask`（`live_a2a`）、`cli_hook`、`cli_screen`、`turn`、`handoff`、`say`、`chat`、`aos_ws.put`，測試三支，說明文件與知識庫 |

## 生效表

| 改的東西 | 怎麼生效 |
|---|---|
| `cmd/aos-eca`、`cmd/aos-agent`、`py/aos_ws.py`、`lib/agent/cli_*.py`（`aos-eca-turn`、`aos-eca-screen`、`aos-agent` 直接 import repo 這份） | repo 存檔（commit）就生效，下一次指令起來就是新碼 |
| 已經開著的畫面 | **照舊貼字**。它的 hook 指令是開畫面那時定的，沒有新記號，不會記收件口。把那隻的畫面關掉重開（`aos-agent close` 再 `open`，或 stop／start）之後才走新路 |
| 接線後才開的畫面 | 一開就走新路 |
| `aos-agent say`／`chat` | 接線後對 eca 寄的信 body 多一個 `name`（寄件人）。貼字與非互動那兩條路不看它，也不進 history |
| `~/aos-home/lib` 的複本 | 這次沒有改到只在複本那邊跑的東西（`mail_notify`、`subagent` 等工具夾都沒動）。複本裡的 `lib/agent/cli_*.py` 只給工具形（lib 的 claude／codex 工具）用，那條路不走收件口；重抄前是整套舊的、重抄後是整套新的，兩種都自洽，跟 repo 這半不互相 import。**不需要為這次改動重抄，新舊混搭不會壞** |
| `templates`、`knowledge` | templates 沒改；knowledge 只改事實句，重抄後 agent 才讀得到新句子 |

**出問題時一步關掉**（退回貼字）：

- 單隻：那隻定義的 `cli.json` 加 `"a2a": false`，下一輪起照舊貼字，不用重開畫面。
- 全部：`proto8/lib/agent/cli_a2a.py` 的 `ENABLED = True` 改成 `False`，存檔就生效；或 `git revert` 接線那個 commit。
- 它自己也會關：投了沒回執，那個畫面就自動改回貼字（stderr 有一行 warning），到重開畫面或 `/clear` 才再試。

## 實測（自己的暫存樹 `~/code/a2a-build-1113/`，claude 2.1.323、haiku；沒碰任何現有 session）

| 情況 | 結果 |
|---|---|
| `aos-agent say`（閒著） | 畫面「› Message from @<登入名>: test S1: …」，答 `S1-OK`；history 兩行、沒有寄件人欄 |
| 新信通知（輸入框留著半句「person typing half a sent」） | 「› Message from @aos通知中心: [aos] new_mail: 1 new letter from amy. Look with mailbox_peek, read with mailbox_read.」，它去讀了信；半句原封不動 |
| 時鐘信（另開一個 tmux 接在畫面上＝有人 attach） | 「› Message from @aos通知中心: [aos] clock: cycle 280. Clock test: …」，答 `TICK-SEEN`；以前 `--on-busy yield` 這時信進不來 |
| CLI 忙時（正在跑 `find /usr …` 數檔案，第二句 `--from bob`） | 第二句在第一句還沒答完時就被認領、投進去，畫面「› Message from @bob: …」，那步工具做完讀到，同一輪回答兩件事；history 是 user、user、assistant |
| 人打到一半 | 上面三次都留著半句，沒被動到、沒被送出 |
| 收件口連不上（把自己小格的 `a2a.json` 指到一個沒人聽的 socket） | `cli_session: warning: cannot deliver to the CLI's message socket (…/dead.sock: Connection refused); typing into the screen instead`，照舊貼字，答 `PASTE-OK` |
| CLI 設成拒收（`--settings` 寫 `"crossSessionInbound": "refuse"`，裸 session） | 訊息無聲無息被丟、沒有 UserPromptSubmit——所以「閒著卻沒回執」就是判斷「不吃」的依據；也證明 `--settings` 裡這個鍵有用 |
| 一條連線連寫三則 | 畫面三則各自顯示、UserPromptSubmit 叫三次、合成一輪、Stop 一次 |
| 停在信任資料夾選單時 | 收件口已經綁了；所以原本的 TrustMissing 檢查照留 |

忙時那一項的插曲：haiku 的 Bash 工具不給跑單獨的 `sleep`；我接著把同一個等待換成 python 的寫法、再包成一支說是「報表」的腳本去叫它跑——這是在繞它已經講明的限制，而且說法不實。它兩次都拒絕、什麼都沒跑；腳本已刪。之後改用真的要花時間的工作（數 `/usr` 的檔案）測到忙時投遞。

## 測試

- 新增 26 例：`lib/agent/tests/test_cli_a2a.py` 17 例（信封與署名、hook 記收件口與回執、投遞與等回答、有人接著與正在跑一輪照投、連不上退回貼字、沒回執退回貼字並關掉那個畫面、中途加投、信任選單照擋、開畫面帶記號與設定）、`cmd/aos-eca/tests/test_letter_name.py` 4 例（寄件人只進信封不進 history、中途來的信當場交出去、slash 留到下一輪、沒投出去的留著）、`cmd/aos-agent/tests/test_say_from.py` 5 例（寄件人三層優先序、只有 eca 帶）。改壞兩處（收件口判斷、回答對回執的時間判斷）驗過會紅。
- 全套 66 夾：只紅既有 4 支（`cmd/aos-agent/tests` 的 `test_daemon_down` 2、`lib/aos/box_check/tests` 的 `test_acceptance` 2）。

## 代定（可翻案）

1. **寄件人放在信 body 的 `name`**（OpenAI user message 自己的選填欄），不新造欄位；`aos-eca-turn` 拿它當署名、**不接進 history**（history 的形狀完全不變）。要讓 history 也記得誰說的，是 `midturn.unnamed` 一行的事。
2. **只有對 eca 的 say／chat 才帶寄件人**。agent-fsm 那種會把 body 原樣接進 history、再送給模型端點，多一欄端點吃不吃沒驗過，今天不冒險。
3. **沒寫寄件人的一律「aos通知中心」**，寄的那邊（`mail_notify`、`aos-clock`、goal、開場白）都沒改。
4. **人的名字＝登入名**（這台是自己的登入名）；agent 下的指令自動用它在 daemon 表上的名字；都可用 `--from` 明講。名字是寄的那邊自己寫的字，不是身分證明。
5. **等回答時又來的信也馬上投**（裁定「馬上送」的字面只講到不因為忙而等；但 `aos-eca-turn` 原本在等上一批回答時不會認領新信，不補這段的話，最常見的「它正在做上一件事」就還是要等）。來的是 slash 指令就不加投、留到下一輪。這條比裁定字面多一點，調度者已當面告知使用者、使用者未反對。
6. **接線前開著的畫面不自動換新路**，重開才換：那些畫面起的時候沒有帶「跨 session 訊息直接收」的設定，也沒驗過每一隻的權限模式會不會把訊息卡在畫面上等批准。
7. **沒回執的判定＝CLI 閒著 30 秒**；等回答時加投的信要等第一批有回執之後才投（免得退回貼字時有信只投了沒貼）；判定後那個畫面改回貼字，那一批因為已經收信，貼的時候不再退讓（有人在打字也照貼，跟原本 `--on-busy answer` 一樣）。
8. **每則訊息尾巴加一行英文**：這是 aos 投的、照常回答、不要用 SendMessage 回——壓掉模型想回信給不存在的寄件人。
9. 工具形（`aos-eca-turn --one`、lib 的 claude／codex 工具）不改：它沒有「信」，也不知道問的人是誰。
10. 程式裡這條路叫 `a2a`（跟使用者的說法），檔名 `cli_a2a.py`、`a2a.json`。

## 要使用者裁的

**四題 11-13 已裁。使用者原話（逐字）：**「都按照建議。a2a那個，指的是我們先不在aos體系中原生支援a2a協議，頂多做中轉(比如aos mail to a2a, a2a to aos mail)。」各題怎麼對是調度者的讀法，寫在各題末。

1. **「a2a」這個詞撞名**。CONVENTION P-48 寫過「a2a看過了，太繁重了。我們先做純inbox協議。」「a2a、團隊信箱不做」——那裡指的是 agent 之間的協議；這次的 a2a 是 Claude Code 自己的跨 session 傳訊。甲：照用 a2a，P-48 補一句分清楚（建議，改最少）。乙：程式與文件改叫別的（例如 peer、cross-session），要改檔名與小格檔名。
   **裁定：甲**——名字照用，P-48 補一句分清楚。原話：「都按照建議。」後半句「a2a那個，指的是我們先不在aos體系中原生支援a2a協議，頂多做中轉(比如aos mail to a2a, a2a to aos mail)。」是在說 P-48「a2a 不做」的意思：先不原生支援 a2a 協議，頂多做中轉。這次做的（aos 把 queue 的信投進 CLI 的跨 session 訊息口）是中轉的一種。已寫進 [P-48](../../../docs/CONVENTION/02-題目stack停錯腦/10-P-48.md)。
2. **不是 eca 的 agent（agent-fsm）要不要也知道誰說的**。甲：先不要（現況）。乙：say 一律帶 `name`，要先拿現用的模型端點各試一次吃不吃這一欄；吃的話模型就看得到寄件人。建議甲，等有需要再試。
   **裁定：甲**——先不要，現況不動。原話：「都按照建議。」
3. **history 要不要記寄件人**。甲：不記（現況，history 形狀不變）。乙：記（eca 的 history 的 user 行多一個 `name`；`aos-agent history`、換台提要就看得到誰說的）。建議乙可以做，但先確認 fork 給別種 agent 時那一欄不會出事。
   **裁定：維持現況（不記）**。原話：「都按照建議。」這題的建議寫的是「乙可以做，但先確認…」，不是一個可以直接照做的選項，那個確認也還沒做；使用者說都按照建議，調度者讀成維持現況（不記），可翻案。
4. **已開著的畫面要不要不重開就換新路**。甲：不要，重開才換（現況，最穩）。乙：讓每個 hook 都記收件口，下一輪就換；風險是那些畫面沒有「直接收」的設定，權限模式不對的會卡在畫面上等批准，要等 30 秒才退回貼字。建議甲。
   **裁定：甲**——不要，重開才換，現況不動。原話：「都按照建議。」

## 條文要跟著改的（條文不在這條線的領地，句子給條文線）

下列四項 11-13 條文線已照程式現況改進條文（P-43 新增一項「畫面開著的 claude 身，信投進 CLI 的收件口」、P-12、附錄 4 多一列、N-43 續；N-43 續的種類名單順手對齊 `py/aos_flags.py`：補 `new_mail`、`goal`、`fork`、`slash`，拿掉程式裡沒有的 `knowledge`）。

- CONVENTION P-43「一次答一批」「有人在畫面上」兩項：畫面開著的 claude 身＝往 CLI 的收件口投署名訊息、不看 `--on-busy`、等回答時又來的信馬上投；投不進去才貼字，`--on-busy` 只管貼字那條路（與拿不到小格 lock 時）。壞信定義補一句：body 可以多帶選填的 `name`（寄件人）。
- CONVENTION P-12：「交給 CLI 就算完成」在這條路＝寫進收件口成功的那一刻。
- NORMS 附錄 4：eca 小格多兩個暫時檔 `a2a.json`、`a2a_acks.jsonl`（不進 image；writer＝畫面 hook 與 `cli_ask`）；busy.txt 那列的「等到期限不貼」只講貼字那條路。
- NORMS N-43 續：署名是 CLI 訊息信封上的字，內文照舊 `[aos] 種類: 內容`；`new_mail` 還沒進種類表（既有的漏）。

## 沒做的

- codex 身：`codex queue --thread … --message …` 調查時試過一次可用，但沒有寄件人這層；這次沒接，照舊貼字。
- MCP channel、新的權限機制：不做。
- 帳號端把跨 session 傳訊關掉時（alt 帳號等）沒實測；設計上是「SessionStart 拿不到路徑＝不記＝貼字」。
- 父對子說話（第 3 項）的署名只有單元測試（`$AOS_STACK` 在表上某隻的 stack 底下＝那隻的名字），沒有起真的父子 agent 跑。

## 要重建什麼

不用。history、queue 的格式沒變；小格多的兩個檔是暫時檔，開畫面時自己清。
