# proto8 討論紀錄：2026-10-15

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-15 主題分法](topics/README.md) | 待定清帳：`檔#/位置`＝N-35、aos-fsm＝N-36～N-41 進規範，資料夾別亂弄結案、argv[0] 擱置、kernel 公告／時鐘／`_metainfo` 晚點；概念／規範／實作之外再按主題分（設計理念含時空、總則、基礎設施含組合子 tasks＋fsm 為 stdlib 地位、kernel、agent）；fsm 補細則（心跳不寫時間、第一拍、error 格、`step`、結束碼、窗）；agent：工具＝inst（說明在 `_tool`）、模型走 OpenAI 內建 tool calling、思考統一介面（換腦＝換 TARGET）、agent 當函數 |
| [2026-10-15 kernel 截流](kernel-intercept.md) | agent 只管叫、不管成本（C-20）；貴的呼叫套一層閘門 inst，請求當信丟給 kernel 的 daemon 排隊，呼叫端照拿 N-30 結果；卡死不防護（N-20 精神）；kernel 看呼叫樹的特性由子葉彙總、寫在 `_metainfo`；六題照建議定（先只包腦、信箱排隊、`resource` 一個欄位、作者自報彙總、排隊算在呼叫者的 `timeout_ms`、重起回錯） |
| [2026-10-15 LLM kernel](llm-kernel.md) | 基本規則確定性（先來先上、token 額度見底就擋）；請求由發送者填 `priority`——簡單值或物件（分級、分類、時限），由閘門抄進信；`_metainfo`＝被叫者自報、`priority`＝呼叫者這次多急，`_metainfo` 不蓋過 level；額度放 kernel state 窗、見底回 `BudgetExhausted`；六題照建議定；`class` 排序、每發送者配額留待之後 |
| [2026-10-15 報時員實跑](clerk-live.md) | agent 當工具用 LM Studio 小模型實跑端到端通；小模型有時不叫 clock 直接編答案，使用者「隨意」→ 先不處理、接受此限制 |
| [2026-10-15 JSON 格式族](json-families.md) | 使用者定：新 JSON 除非必要不開新格式，沿用 inst 族、ctl／state 窗族，靠加 key 與任意 value 擴充；私有 key 共享格式（不重疊）、值的雙形（純值或物件，像 Lisp 的 `3` 與 `(+ 1 2)`）；指示詞（`$ref`／`$env`）只是拆檔與讀環境變數的便利，設計不依賴它（C-48） |
| [2026-10-15 通用 kernel](general-kernel.md) | N-42 第二種：判斷交給 agent；閘門不改、信箱換一個；身體一拍照 LLM kernel 骨架，排序那步問判官（表上一格 inst），只回 run／reject；判官沒給合法答案就這拍退回確定規則；判官的腦不走自己的信箱；局面沒變、格全滿不問，空格由規則補位；原六題照建議定；公告欄晚點再說 |
| [2026-10-15 agent 判官實跑](judge-live.md) | 小模型判官在 kernel 底下太慢、常空回覆；使用者定：不靠模型思考（判官 `/no_think`）、判官輸入瘦身成 state 窗子集；全 defer 會卡住 → 補位（判官沒挑的空格由確定規則補滿） |
| [2026-10-15 agent 判官實跑之二](judge-live2.md) | 補位之後信全服務完、順序對（human 先、high 先於 low），小模型判官幾乎不自己挑；定：格全滿時不問判官 |
| [2026-10-15 LiteLLM 實跑](litellm-live.md) | 本機 LiteLLM（GPT 類）實跑新架構都通；五題拍板：換腦只換那一層、判官腳本收定義資料夾當引數、多個 tool_calls 一拍照順序跑完、halted 時 loop 照舊退 0（看 `ret.json` 的 `error`）、proxy 多塞 token 不處理 |
| [2026-10-15 同像性](homoiconic.md) | 使用者定：inst 寫路徑或整張內嵌＝C-48 值的雙形的大號版，`(daemon (fsm b c))` 程式＝資料；JSON schema 當型別用（`_tool.parameters` 已是、簽名、interface＝一份 schema、雙形＝oneOf、驗證選用）；原七題照建議定（內嵌 id、相對路徑、循環、深度、只看位置、`_schema`、不做繼承）；aos_tree 只是看狀況的工具、不進規範 |
| [2026-10-15 意見 5～7](opinions-5-7.md) | 資料夾⇄JSON 可互通（資料夾＝object、key 留副檔名、非 JSON 檔用存根）但別濫用；JSON schema 先用在 LLM 回話與 fsm 表，能規範資料夾「形狀」、管不到互指與非 JSON 內容；照建議拍板，隱藏檔例外的資料夾名由 `AOS_DIRNAME` 定（「都AOS_DIRNAME」） |
| [2026-10-15 意見 1～4](opinions-1-4.md) | fsm 只管「狀態→inst」、只留表（`start`／`states`／state 窗只剩 `phase`／選填 `end`）；agent＝定義資料夾（表＋每格一張 inst）；呼叫＝新建 frame 資料夾當 cwd、找名字往上找（Lisp 環境式）；`end` 可多個、frame 放哪由呼叫方定，其餘 15 題照推薦；args.json／ret.json 10-16 撤掉（見 agent 繼承） |
| [2026-10-15 兩條總原則](principles/README.md) | 使用者定：巢狀只管自己這一層、同一原則貫穿每層（C-52）；錯誤只處理自己的、錯誤路徑濃縮（C-53）；KISS 是最高原則（C-56）；盤點各條與「正常退出」S1～S5 照推薦（loop／daemon 只退 0／1、警告記 state 窗、判官錯一條路、think 自己寫錯）；第 2、4、5、6 條：daemon add 不驗子項裡面、fsm 不讀格 stderr、`next: null`＝留原狀態、agent 只看到工具清單；kernel 的錯誤路徑評估列待定 |
| [2026-10-15 命名](naming/README.md) | 使用者的命名習慣（好懂、結構先行、一次記住全體系通用、已知縮寫、主題放前、全小寫加底線、程式照 PEP8、靠資料夾布局少用底線）→ C-54；指令名＝底線換連字號、aos 認可縮寫表（[abbr.json](../../../docs/CONCEPTS/abbr.json)，新縮寫先進表）、複數資料夾裝同類（只加 s）；盤點 P1～P7、M1～M9 照推薦；未決：md 檔名與日期、「點」的用法 |
| [2026-10-15 inst 只吃 stdin／aos-exec](inst-exec.md) | 第二版（續稿見第三、四版）：呼叫機制不能靠指示詞（C-48）；已定：`$ref` 從所在檔算、基準 dirname(abspath) 不解 symlink（「捷徑＝懶得 copy」）、inst 的 cwd／串流從 aos-inst 的 cwd 算、aos-inst 只吃 stdin、aos-exec TARGET 當語法糖、刪 aos-tree、`$abs_path` 不做 |
| [2026-10-15 inst／aos-exec 第三版](inst-exec-v3.md) | 兩條前提（KISS 最高原則、層徹底切割）；aos-exec＝最小語法糖（檔／資料夾＋旗標＋argv → 一張 inst；不 cd、不寫檔、不認得 agent）；B、E、I、J、K、L 照推薦定（同行程 run、frame.json／parent 鏈退場、旗標只在 aos-exec、`aos_inst.run(dict)`、閘門旁檔不動、私有 key 路徑只是資料），其餘見第四版 |
| [2026-10-15 inst／aos-exec 第四版](inst-exec-v4/README.md) | 「後續都默認沒有指示詞能用，但不用擔心json太大」→ N-45；一個 agent 的定義＝一張 inst，跑在哪 cwd 就是 frame；aos-exec TARGET 必填；`stdin_inline: true` 時 `stdin` 才是內嵌 JSON；工具一律走 frame、agent 當工具＝argv 直接 `aos loop`、零 sh；矛盾選 (a)，未決 C～P 照推薦定（「C-50 選 a，其他都按照推薦」） |
| [2026-10-15 布局成長](layout-growth.md) | 使用者定：資料夾／檔案與 JSON 物件同像，長大規則同一套——檔太大或職責太多→資料夾、原檔變入口（照 wf/STRUCTURE.md）；純值不夠用→物件（`priority: {"val": 1, …}`）→ C-55；拍板（「都按照推薦」）：原值一律 `val` |
| [2026-10-15 畫家 demo 真腦實跑](paint-live.md) | 畫家→畫筆→調色盤三層巢狀、同 frame 續聊、腦連錯都跟 README 一致；demo 不用修、lib 無新問題 |
| [2026-10-15 KISS 審視](kiss/README.md) | 使用者「拿KISS原則重新去思考各種東西」「去思考現有的規範和實作。概念倒是不用」：彙整總表與批次；批次 1 已做（1.2 三個 inherit 10-16 還原）；10-16 使用者撤回「都照推薦」，批次 2～6 暫停，逐項見 [10-16 重審](../16/kiss-recheck.md) |
