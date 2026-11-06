# 2026-11-05 傍晚 小念頭做成工具 `thought`：派一個任務出去、只拿回短結論（small-thought，fable 規劃，未實作）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜前情：[10-24 小念頭（agent-gus，已刪）](../../../2026-10/24/thoughts/README.md)、[10-24 intent-context（一題只帶問題＋結論）](../../../2026-10/24/intent-context/README.md)、[feat-proto 04 agents 工具](../feat-proto/04-spawn-agent.md)、[agent-knowledge memory 工具](../agent-knowledge/README.md)｜慣例：[lib 契約](../../../../lib/docs/01-分層等.md)、[C-52](../../../../docs/CONCEPTS/05-agent.md)

狀態：**11-05 晚已實作**（[結果](#11-05-晚-結果)）；三題使用者 11-05 傍晚已裁（見下）。本檔記使用者原文（逐字）、以前「小念頭」怎麼定的、已定、裁過的題；代定在 [02-代定](02-代定.md)，實作步驟草稿在 [03-實作步驟草稿](03-實作步驟草稿.md)。時間到 16:35 收，沒想完的段標「未完」。

## 使用者原文（11-05 傍晚，逐字）

> 啊，我突然有個想法，開fable去幫我想想：是這樣的，還記得以前說過的"小念頭"嗎？也就是fork出去，做完之後回報，主線這邊對於這個任務的描述就會只剩短短幾句，至於做這個任務途中的各種細節就會被隱藏。這跟記憶一樣。這除了可以是實際做事外，也可以是去抓分散在各處的記憶項，凝聚為短短一句，主線這邊也就不用紀錄呼叫記憶工具、雜散的各類記憶子向。當然，這會比較麻煩，我也不建議把這做為agent機制，我更推薦將其作為工具。我預期它的使用場景，會是agent規劃一件事的幾個步驟：A->B->C，然後各步驟再去fork或是分派給子agent之類。

補一句：

> 或者說，其實記憶這項，他本身也算是任務，也就是"去蒐集外部訊息，加入自身記憶"這個任務

三題的裁決（11-05 傍晚，逐字選項）：題 1「預設同父 (Recommended)」、題 2「可選。默認刪掉。」、題 3「thought (Recommended)」。

## 以前「小念頭」怎麼定的（摘要＋出處）

1. **10-24 使用者原話**（[thoughts 01](../../../2026-10/24/thoughts/01-使用者原文.md)）：「讓agent先規劃一件事的steps，然後每個steps都fork出去，回來只帶結論」；json 工具那邊「拆成"找到要修改的key"->"提供值"」。
2. **agent-gus（10-24 做、11-04 隨 demo 刪）**：是 **agent 機制**——plan 格請腦拆 steps、fork 格把每步再跑一次自己（`aos-exec --ws <小格>/ws .`）、結論一步一則 `user` 訊息接回母體 history；小念頭 history 從空的開始，題目＝`context`（腦寫的摘要）＋needs 的結論＋`goal`＋「只回結論、N 字以內」；整棵樹額度 `THOUGHT_MAX_TOTAL` 10、逾時 900 秒、深度用環境變數往下帶（[thoughts 02 代定 1～10](../../../2026-10/24/thoughts/02-照推薦定的.md)）。另有能單獨叫的入口 `thought.json`（stdin `{goal, context, needs}`、stdout 只有結論；[thoughts 03](../../../2026-10/24/thoughts/03-給別的程式叫-thought-json.md)）。
3. **失敗回給腦、不停**（[tool-calls 02 § 10-24 定](../../../2026-10/23/tool-calls/02-結論.md#10-24-定叫工具與小念頭的失敗回給腦)）：小念頭退非 0／逾時／沒交答案，那一步的結論就是「小念頭 sN 失敗了（目標：…）：原因」。
4. **intent-context（10-24）**：「一題」＝一則 user 到一則沒有 tool_calls 的 assistant；舊題回到主線只帶「問題＋結論」，過程留在原始紀錄——小念頭的意思用在題的粒度上。當時「沒接」小念頭，接法寫的就是**加一個工具資料夾**轉去叫 thought.json（[intent-context 01](../../../2026-10/24/intent-context/01-使用者原文.md)）。
5. **aos-json 的 json_edit**：「小念頭式兩步改」，第二步每個位置各開一次新對話、只看那一處（[aos-json docs 02](../../../../impls/aos-json/docs/02-給腦用的兩個工具等.md)）；thinking 10-24 aos-json 定 10 說之後要換成叫 agent-gus 的小念頭。
6. lib/docs/03 記：agent-gus 的小念頭**沒收進 lib**，因為它遞迴起 agent-gus 本身、要收就得搬整隻。

## 已定（照使用者方向，不翻）

- **使用者 11-05 傍晚裁**：子的腦**預設同父**（`endpoint` 可覆寫）；子的 stack **預設做完就刪、不印 `details:`**，呼叫時 `keep: true` 才保留、保留時才印 `details: agents/<子名>/`；工具名 **`thought`**。

- **做成工具、不是 agent 機制**：腦叫一個工具、拿回短結論；agent 的 fsm／loop 不加格、不改 agent-fsm 範本。這也正好解掉第 6 點（agent-gus 進不了 lib）：工具自己不遞迴自己，而是**生一隻乾淨的子 agent**去做。
- **一種工具、一種任務**（使用者補句）：不分「做事」與「凝聚記憶」兩種機制。凝聚記憶＝一類任務描述（「去 memory 查 X，濃縮成一句」），子 agent 配 `memory` 工具就是；主線只收那一句，查詢來回全留在子的 history。
- **主線只剩短短幾句**：工具 stdout＝結論（有上限）＋最後一行指向細節存放處（子的 stack），要追查才去翻；主線 history 不出現子的工具呼叫。
- **使用場景**：腦自己規劃 A→B→C，每步叫一次工具（或用 `agents` 派給長住的子 agent）；前一步的結論由腦自己放進下一步的 `context`。串接的步驟表**不做進工具**（agent-gus 的 plan／needs／steps.json 那套不復刻），腦串最簡單、也最像「工具」。

## 三題（11-05 傍晚已裁，裁決在上面已定段；原題與選項留著對照）

1. **子的腦用誰**：推薦 **預設同父**（thought 讀父的 endpoint 代號，可用 `endpoint` 覆寫成 `stupid-fast` 省錢）；另一選是跟 `agents` 一樣**不繼承、一定明寫**（C-52 嚴格版，腦每次都得多寫一格）。
2. **子的 stack 做完留不留**：推薦 **留**（才追得回細節；`keep: false` 才刪），代價是 `agents/` 底下會積一堆 `t-*`、要人定期 `aos-agent ctl rm` 或日後加 gc；另一選是**做完就刪、結論裡不留指標**（主線更乾淨、但「之後要追查能找回」做不到）。
3. **工具名**：推薦 `thought`（呼應小念頭；操作只有一種，stdin 不帶 op）；另一選 `fork`（字面像複製父 context，但我們推薦子是乾淨的，容易誤會）。

<a id="11-05-晚-結果"></a>
## 11-05 晚 結果（實作；代定可翻案）

**做了**：[lib/agent/thought](../../../../lib/agent/thought/_entry)（`_entry`、`_tooldef.json`、`_metainfo.json`），照 02、03 做，不改 agents、memory、agent-fsm 範本、extras/agent。說明：[lib/docs/03](../../../../lib/docs/03-索引-agent等.md#索引agent)、知識庫節點 [agents/thought](../../../../knowledge/aos/agents/thought.md)（給 agent：何時用 thought、何時用 agents）。

**手跑（家機）**：T1 `echo '{}' | _entry`＝`thought: error: GoalMissing …` 退 1；假腦劇本父叫三次 thought（A 截 120 字帶 `[truncated]`、B `keep` 帶 `details:`、C 子配 math 答 `6*7 is 42.`），父 history 只有三則結論、預設的兩隻子已不在表上；深度：父→子→孫，孫再叫＝`DepthExceeded`；`fake-slow`（20 秒）＋`timeout_s: 5`＝`AnswerMissing … (details: procs/t-…/)` 退 1、子 stopped、stack 在；被 TERM＝退 143、`listen` 沒留孤兒。真腦（LM Studio gemma-4-e4b）：叫父「用 thought 從知識庫凝聚 endpoint pack 是什麼」，父自己叫 `thought {"goal": …, "tools": [{"name": "memory"}], "max_chars": 200}`，父 history 只有 user／一則 tool_call／結論一句／答案，子的 memory 來回全不在。

**實作時代定（可翻案）**：

1. **開場文放在 say 的那則訊息**，不改子的 system（用範本原樣 `ctl add`，不複製定義；子的設定全走覆蓋層）。
2. **`tools` 的 `path` 可省**：省了＝照抄父工具箱同名那支（`aos-agent tools ls --json`；沒有＝`ToolMissing`）。凝聚記憶時腦寫 `{"name": "memory"}` 就把自己那個知識庫借給子，小模型不用知道絕對路徑（真腦就是這樣叫的）。
3. **「同父」只抄 `endpoint` 一鍵**（`aos-agent llm show` 父的）；父沒宣告 llm 或沒寫 endpoint＝範本自己的預設。
4. **details 路徑是 `procs/<子名>/`**（子 stack 相對 daemon 的實際位置；02 寫的 `agents/<子名>/` 不存在）。
5. **紀錄不跟 agents 共用 children.json**：act 給每支工具各自的小格（`$AOS_STACK/tools/<名>/`），兩支工具的小格不同、共用要偷讀隔壁。thought 用自己小格的 `children/<子名>/`：mkdir＝搶號（號碼可重用，表上有的跳過），裡面 `state`＝`running PID`／`kept`／`failed`；成功刪掉就連紀錄一起刪。agents 的 `say` 追問不到 thought 的子（要長住就用 agents）。
6. **深度不用環境變數**（查過：`aos-agent ctl add` 只能帶 `--limits`，aos-daemon-ctl 也沒有帶 env 的參數）：thought 掛上子之後在子的 stack 寫 `thought.json` `{"depth": 父+1}`，自己從 `ctl who` 找到我那隻的 stack 讀（沒有＝0）；到 2＝`DepthExceeded`、不生。
7. **失敗的 gc**：每次叫先對帳（表上不在的紀錄刪掉），`failed`（含主人 PID 已死的 `running`＝thought 被殺時留的）只留最新 2 隻、加上這次最多 3 隻，多的 `ctl rm`；`kept` 不自動刪。子答不出時先 `ctl stop`（停在 stopped、stack 留）。
8. **並行**：查過 act.py——一回合多個 tool_calls 是**逐個依序**跑（`subprocess.run` 一個一個），所以「一回合發多個 thought」是排隊不是並行；要並行得改 act（這次不改）。
9. **gc 數字 3、深度 2、預設 600 字／600 秒** 寫死在 `_entry` 開頭，不開設定檔（KISS；要改再說）。

**順帶看到的（不是 thought 的）**：試驗中一隻子在 18:58 掛掉，原因 `aos-exec: error: LaunchFailed cannot start: aos-fsm (Permission denied)`——當時別隊在重建 impls，binary 正被覆寫；daemon 把它留成 stopped＋reason，行為正常。


## 11-05 晚 邊緣測試

- 同一格同時叫三個 thought：三個都搶到同一個號 `t-<父>-002`、互相 rollback、全退 1（對帳先看「不在表上＝刪紀錄」，把別人剛 mkdir、還沒 ctl add 的號刪了）→ 對帳先跳過「running 且 PID 活著」與「剛建、state 還沒寫（90 秒內）」的紀錄；重測三個各拿一號、都退 0、做完都下表。
- goal／context 含換行、非 ASCII、emoji；`max_chars: 1`（`F [truncated]`）；沒 `AOS_DAEMON`（DaemonMissing）；keep 的子被外面 `ctl rm` 後再叫（紀錄被對帳清掉、號照用）；keep 的子 pause→resume→stop→start→say→listen：都正常。
- 沒修、列給隊長：keep 的子留在表上一直 running（佔一支 loop），要追問用 `aos-agent say --target`；不要了得人 `ctl rm`。

## 11-05 夜 第二輪邊緣

- **修**（隊長推薦，可翻案）：`keep: true` 的子答完一直 running 佔一支 loop → 答完就 `ctl stop`（stack、紀錄 `kept` 都在；追問＝`aos-agent ctl start --target <子>` 再 say／listen，實測接得上）。`_entry` 說明、`_tooldef.json`、knowledge `agents/thought`、lib/docs/03、code map 同步。
- 假腦 A→B→C（B 給子 `thought`＋`memory`、子再叫 thought、孫再叫）：孫拿到 `DepthExceeded`、照樣答完；子借父的 `memory`（範本的包裝資料夾 `tools/memory`）解到 `knowledge/aos`（包裝資料夾的 `_memory.json`，跟父同一個庫）。
- 真腦（LM Studio `google/gemma-4-e4b`）：叫父「A 問 endpoint pack（給 memory）、B 問 UTC 幾點（給 clock）、C 合成一句」，父三次 thought、前一步結論自己放進 context、最後一句正確；三隻子做完都下表。
- **沒修**：父的 memory 若是**登記格 `env`**（`AOS_MEMORY`，沒有 `_memory.json`）配的，借給子會掉 env——`aos-agent tools ls --json`（aos-tools ls）不印 env、`aos-agent tools add` 也沒有 `--env`，子的 memory `MemoryMissing` → brain `MemoryFailed` → 子 stopped，thought 回 `AnswerMissing …`（看不出真因）。可攜的配法（包裝資料夾＋`_memory.json`）沒事。要修得 aos-agent 先有 `tools add --env`，再決定 env 怎麼抄給子（ls 印 env 會讓 self_tools ls 把值給腦看，值是 `$env` 解出來的金鑰就外洩）——列給隊長。
- **沒修**：thought 在 aos-sandbox 裡（bash-boxed 那種 bwrap `--unshare-all`）起不來：PID 命名空間看不到 daemon 的 pid，`aos-daemon-ctl` 判 daemon 沒在跑、thought 回 `DaemonMissing`（daemon 其實活著）。agents、self_tools 同理。屬 aos-sandbox／aos-daemon-ctl（另一位測試員範圍）。
- 每叫一次 thought，stderr 都有好幾行 aos-agent 的「this definition … is also used by …」提醒，名單隨子變長；只進 stderr、不進腦，沒改。

## 使用者裁定（11-05 夜，排在大重構之後做）

> 剩下都照推薦

- 登記格 `env` 借給 thought 子會掉：**`aos-agent tools add` 也能帶 `--env`**，值不給腦看到。
- thought／agents／self_tools 在沙箱裡**先不支援**（沙箱只包葉工具）。
  - 註（11-06 no-pid P5 已解）：綁 `AOS_DAEMON` 即可（範例 `cmd/aos-sandbox/examples/thought-boxed/`），實測見 [no-pid 13](../no-pid/13-P5實作結果.md)；「要不要正式支援」留給使用者，推薦見 13。

## 11-06 改（no-pid P4）

上面代定 5、7 與邊緣測試裡的「搶號」和紀錄 `running PID`，已由 no-pid P4 改成子名每次唯一＋紀錄寫租約（`running <到期時刻>`），對帳不再看 pid（[no-pid 11-P4實作結果](../no-pid/11-P4實作結果.md)）。
