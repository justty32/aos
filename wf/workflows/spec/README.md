# aos spec：入口

← [WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)｜構想（只留脈絡）在 [../ideas/README.md](../ideas/README.md)

## 這是什麼

這一疊是 aos 新實作的**規定**。ideas 那 13 章講的是「為什麼」，這裡只講「要做成什麼樣」：檔案長什麼樣、指令怎麼走、壞了怎麼看得見。新實作照這疊寫程式，不用回頭翻 ideas。

三句話版本：一個資料夾就是一塊地，地裡的 `.aos/` 是機器的地盤；`aos exec` 讓一塊地走一格，`aos run` 反覆走到沒新事可做；daemon 替每塊登記的地起一支 run 看著。LLM 不是指令，是另一塊地，要用就投請求給它。

## 怎麼讀

- 第一次讀：[01 名詞表](01-terms.md) → [02 版面](02-layout.md) → [05 接力棒](05-series-format.md) → [06 走一格](06-exec-and-run.md) → [07 呼叫與投遞](07-call-and-delivery.md)。讀完就知道整台機器怎麼轉。
- 要寫編譯器：03、04、05。要寫 daemon：08。要接 LLM：09。要做 agent：10、11。要做指令面：12。要寫測試：14。
- 每檔最後兩段固定：「待使用者拍板」（那檔裡還沒被使用者批過的條款）與「現況對照」（今天的程式碼差在哪）。

## 條款怎麼編、怎麼標

- 編號 `S-NN-MM`：第 NN 份檔的第 MM 條。例：`S-05-03`＝05 接力棒那份的第 3 條。
- 三個規定用詞：**必須**（不照做就不是 aos；每條必須在 [14](14-conformance.md) 對一個可測的檢查）、**建議**（照做較好，不照做也合規）、**禁止**（做了就不是 aos）。
- 每條句尾標來源，只有三種：
  - 〔裁決 YYYY-MM-DD〕：使用者拍板。含 2026-09-05 的 8 條與 2026-09-04 那批 13 條（M-01 整批升格）。
  - 〔預設 2026-09-05，X-NN〕：照 ideas 待決定總表「我建議的預設」寫，使用者還沒批。X-NN 是待決定編號。
  - 〔主編補〕：ideas 沒講，主編為了讓 spec 閉合而補的。
- 矛盾時的優先序：rulings 8 條 ＞ ideas 各章〔裁決〕 ＞ 建議預設 ＞ 主編補。
- 舊講法「子的固定產出資料夾」不再出現；一律是「父指定的結果落點」（I-01）。

## 目錄

| 檔 | 一句話 |
|---|---|
| [01-terms.md](01-terms.md) | 名詞表：正文只用這些詞 |
| [02-layout.md](02-layout.md) | `.aos/` 裡有什麼、誰寫誰讀、進不進 git、版本欄 |
| [02b-layout-rules.md](02b-layout-rules.md) | 設定檔、子地怎麼開、記憶就是地、版本不合、地 id、tmpfs |
| [03-source-and-compile.md](03-source-and-compile.md) | 原稿 json 格式、編譯器怎麼拆平、吐出什麼、拒絕什麼 |
| [04-inst-format.md](04-inst-format.md) | 一筆指令的欄位、嚴格解析寬鬆執行、執行結果檔 |
| [05-series-format.md](05-series-format.md) | 接力棒 `series.json`：串、游標、成敗、在等、去重 |
| [05b-series-lifetimes.md](05b-series-lifetimes.md) | 暫存器替換、兩種壽命、多寫者 |
| [06-exec-and-run.md](06-exec-and-run.md) | 一格的精確順序、鎖、一格有界、子地、原稿 |
| [06b-run-rules.md](06b-run-rules.md) | run 三種走法、通用停法（含「在等」）、預算、停止原因檔、崩了怎麼接 |
| [07-call-and-delivery.md](07-call-and-delivery.md) | 開子地（同步／脫節）、呼叫記錄、三態與狀態檔、投遞協定 |
| [07b-result-path.md](07b-result-path.md) | 結果落點的規矩：原點、合法範圍、原子發布、用量檔、`message` 不可信 |
| [08-daemon.md](08-daemon.md) | 登記表格式、`aos daemon`、每地一支子行程、控制收件匣 |
| [08b-daemon-reconcile.md](08b-daemon-reconcile.md) | 對帳、巡邏與清理、一次全停、`aos mv` |
| [09-llm-world.md](09-llm-world.md) | LLM 世界：請求格式、處理單元表、帳簿、`aos llm` |
| [09b-llm-queue.md](09b-llm-queue.md) | LLM 世界的一輪、排隊、請求狀態、重啟、保留期 |
| [10-agent.md](10-agent.md) | agent 資料夾的形狀、限制參數、每圈 prompt、停法 |
| [10b-agent-loop.md](10b-agent-loop.md) | agent 的圈：一份能過 schema 的模板骨架 |
| [11-tools-and-contacts.md](11-tools-and-contacts.md) | 工具登記表、通訊錄、子命令 |
| [11b-tool-envelope.md](11b-tool-envelope.md) | 給模型看的一行、錯誤封套、一次往返幾格 |
| [12-cli.md](12-cli.md) | 子命令全表、退出碼、控制介面 |
| [12b-roster-and-canon.md](12b-roster-and-canon.md) | 三層名字、`init`／`reset`／`migrate`、核心名冊、正本與版本欄、回寫鐵律 |
| [13-doorman-l1.md](13-doorman-l1.md) | 門房第一級：只看不擋 |
| [14-conformance.md](14-conformance.md) | 每條「必須」對一個可測的檢查：怎麼跑＋02～06 |
| [14b-conformance.md](14b-conformance.md) | 同上（07～09） |
| [14c-conformance.md](14c-conformance.md) | 同上（10～13）＋測不到的「必須」清單 |
| [schemas/](schemas/) | 每種 json 一份 JSON Schema，schema 是正本 |

寫 spec 那天的材料（使用者拍板原文、83 條邊緣狀況與主編的取捨、舊資產盤點、計畫骨架）在 [notes/](notes/README.md)；能跑的 Python 原型在 repo 根目錄 `proto/`，它撞到的事在 `proto/FINDINGS.md`。

## 條款來源表

| 來源 | 待決定編號 |
|---|---|
| 使用者裁決 2026-09-05 | M-01、F-02、G-01、E-01、I-01、I-02、I-03、I-04 |
| 使用者裁決 2026-09-04（隨 M-01 升格） | F-01、H-01、H-02（agent 停法＝通用停法）、J-01 的「FUSE 要做、順序 tmpfs→inotify→FUSE」 |
| 預設 2026-09-05（使用者未批，照建議寫） | A-01～A-04、B-01～B-05、C-01～C-05、D-01～D-04、E-02～E-06、F-03～F-07、G-02～G-06、H-03～H-05、I-05～I-08、J-02～J-06、K-01～K-06、L-01～L-06、M-02、M-03 |
| 主編補 | 各檔「待使用者拍板」段列出的〔主編補〕條款；總數見下方「主編補統計」 |

註：D-01 的預設（在 `.aos/` 裡放一份入口腳本檔）被 E-02 的預設蓋掉：人寫頂層原稿、載入器編譯進 `.aos/program/`，spec 裡沒有獨立的入口腳本檔。

## 主編裁的矛盾

ideas 裡兩條裁決互相打架、rulings 又沒蓋到的，主編選一邊。每條在對應檔標〔主編補〕。

| # | 矛盾 | 選哪邊、為什麼 | 在哪檔 |
|---|---|---|---|
| 1 | 工具登記表、通訊錄住 `.aos/`（08-30）vs `.aos/` 人不碰（09-03） | 留在 `.aos/`，人只透過 `aos tool`／`aos contact` 寫；它們是靜態設定、進 git。改路徑動到的東西太多，收益小。 | 02、11 |
| 2 | 門房偵測出生就自動登記時鐘（10）vs 子地父點名才開（02 裁決） | 出生只登記成 `stopped`（`pid`、`clock` 都 null）、不起時鐘；起時鐘仍是父或使用者的動作。門房只記不做（J-03）本來就這意思。 | 13、08 |
| 3 | 同步子地「父等它做完」（09）vs 「父動一格、子動一格」（06） | 同步呼叫＝父每格對子做一次 exec，父那一步停在原地直到子閒著。兩句同時成立，一格仍有上限。 | 07、06 |
| 4 | 「一次 LLM 請求＝開一塊脫節的地」（07、08）vs F-02「LLM 是單獨一個世界」 | 照 F-02：請求是投給 LLM 世界的一筆投遞物，不再為每次請求開一塊地。C-02 的「一次性的地」只剩脫節子地那種。 | 09、10 |
| 5 | daemon 掛了時鐘照走 vs 一次全停 | 照 G-01：代價明寫；daemon 不在時 `aos daemon stop`＝先對帳再全停。 | 08 |
| 6 | 沒有 daemon 時脫節呼叫誰來起 | 脫節工作一律由 daemon 起；沒有 daemon 就立刻失敗、狀態檔 `no_daemon`。代價：daemon 不在時新的脫節工作起不來、既有的照走。（原本裁「exec 自己 detach」，邊緣狀況隊指出那樣並行上限沒人數，改掉。） | 07、08 |
| 7 | 沒宣告結果檔的指令步怎麼判成敗（I-04 說不看結束碼） | 有宣告 `expect` 就看檔；沒宣告才退而看結束碼 0／非 0。純 `mkdir` 這種指令沒別的訊號可看。 | 05、06 |
| 8 | **通用停法「沒產出新指令就停」（裁決 2026-09-04）vs 任何「在等」** | 改寫成「沒產出新指令**且沒有任何串在等**（停在 `await` 或同步 `call` 上）才停」；只剩在等的串時睡 `--every`。不改的話父投出脫節呼叫的下一格就停、結果回來沒人收。**這是改一條已升格的裁決，最需要使用者點頭。** | 06b、05、10 |
| 9 | 「一塊地只看得到自己地上的東西」vs「結果落點由父指定」（子、LLM 世界要寫到父地上） | 請求裡的落點＝父對子（或 LLM 世界）開的一個明示寫入洞，只涵蓋那條路徑與它的 `.status.json`、`.usage.json`；`prompt` 同理是讀取洞。落點必須在父地內、不得在任何 `.aos/` 內。 | 07b、09 |
| 10 | C-02「daemon 逾期連結果一起清」vs I-01「結果在父地上」 | daemon 永不刪父地上的結果檔、狀態檔、用量檔；到期只刪脫節子地本身，刪前落點沒檔就代寫狀態檔 `reaped`。 | 08b、07 |
| 11 | H-03 的 token 上限 vs F-02（token 數只有 LLM 世界知道）；G-05 處理單元表在家 vs LLM 世界只看自己地 | LLM 世界在落點旁寫 `<落點>.usage.json`，agent 累加進自己 `.aos/usage.json`；daemon 起 LLM 世界時把 `units` 抄進它的 `.aos/units.json`。 | 09、10、02 |
| 12 | LLM 世界「是一塊地、由 daemon 起 `aos run`」vs 它做的事不是三種步任一種 | LLM 世界是特殊 run：daemon 對它起的是 `aos llm serve`（登記表 `runner: "llm-serve"`），跟 exec 搶同一把鎖，不用接力棒。 | 08、09b、12 |
| 13 | agent 要知道 LLM 世界與家在哪 vs 「一塊地只看得到自己地上的東西」 | exec 給兩個內建暫存器 `${home}`、`${llm_world}`（與環境變數 `AOS_HOME`、`AOS_LLM_WORLD`），是 M-01 那條的明示例外，只開這兩條路徑。地本身仍禁止讀家的設定檔。 | 05b、04、10 |

## 條款統計與審稿卡點

02～13（含 b 檔）共 756 條：〔裁決〕185、〔預設 2026-09-05〕120、〔主編補〕451。主編補這麼多，是因為三件事：邊緣狀況隊 83 條（採 53、部分 4）、原型隊 FINDINGS（採 20 組）、審稿 10 條都要補成條款；每一條都列在各檔「待使用者拍板」段，可以整批翻。

審稿（Opus，讀完整疊之後）列了 10 條卡點，補得了的 6 條已補進條款（run 閒著就停不重載、exec 十五步補齊呼叫與落點檢查、`aos llm` 加 `--usage-out`／`--request-id`、用量累加改成下一步一筆指令、agent schema 描述對齊、登記表 `last_started_at`）；要使用者裁的列在下一段。審稿的整體評價：核心那半（02～07 加 schema）能直接開工；最弱的是 10（agent），最強的是 07b、04、05b。

## 待使用者拍板

各檔的〔預設〕與〔主編補〕在各檔末段，一行一條。下面是整疊層級、主編補了但最需要你點頭的：

1. **通用停法改寫**（矛盾表 #8）：「沒產出新指令且沒有串在等才停」，動到 09-04 升格的裁決。
2. **借父鐘的 agent**：預設借父鐘（H-05）意味它沒有自己的 run；限制參數超標投的 `stop` 現在由父的 exec 在格頭讀（S-06-62）。要不要改成 agent 預設自己登記時鐘，是方向題。
3. **`${home}`、`${llm_world}` 兩個內建暫存器**（矛盾表 #13）：M-01「只看自己地」的明示例外。另一條路是寫進 `agent.json`。
4. **沒有 daemon 時脫節呼叫直接失敗**（矛盾表 #6）：代價是沒開 daemon 就開不了脫節子地。
5. **「同步子地整棵樹不得有 LLM」沒有執行者**：S-04-27、S-06-32、S-07-05、S-09-05、S-09-06 五條禁止，但原稿裡直接寫 `curl` 打 LLM 沒人擋，只能靠 `path` 白名單。要不要第一版就做靜態檢查。
6. **測試要切一個假家**：`AOS_HOME` 禁止被指令的 `env` 蓋掉（S-04-38），所以測試只能靠跑 exec 的那支行程自己的 `$AOS_HOME`；spec 沒明寫。
7. **schema 比條款鬆的幾處**（14 的「測不到的必須」有列）：投遞 id 的 32 hex、`fail_reason` 只在 failed／stopped、登記表 `path` 不重複、`ext.retryable`——都靠指令檢查不靠 schema。
8. 三個數字是主編編的、沒依據：`fail_streak` 上限 3、`reap_after_ms` 用牆鐘、一次全停等 10 秒才 SIGKILL。

## 現況對照

今天的程式碼（`core/exec`、`core/loop`、`core/agent`…）沒有接力棒、沒有呼叫記錄、沒有 daemon 登記表、LLM 是同步等 HTTP；agent 住在 `.aos/agents/` 裡。這疊 spec 是新實作的起點，不是對現有程式的描述。
