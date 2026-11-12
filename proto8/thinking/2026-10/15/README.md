# proto8 討論紀錄：2026-10-15

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-15 主題分法](topics/README.md) | 待定清帳（N-35、N-36～N-41 進規範）、條文按主題分（設計理念、總則、基礎設施、kernel、agent）；agent 的工具＝inst、走 OpenAI tool calling、換腦＝換 TARGET |
| [2026-10-15 kernel 截流](kernel-intercept.md) | agent 只管叫、不管成本（C-20）；貴的呼叫套閘門 inst、請求當信排進 kernel 的 daemon；六題照建議定 |
| [2026-10-15 LLM kernel](llm-kernel.md) | 確定性規則（先來先上、額度見底回 `BudgetExhausted`）、發送者填 `priority`；六題照建議定；未決：`class` 排序、每發送者配額 |
| [2026-10-15 報時員實跑](clerk-live.md) | 報時員小模型實跑端到端通；小模型不叫工具直接編答案，先接受此限制 |
| [2026-10-15 JSON 格式族](json-families.md) | 新 JSON 沿用 inst 族與窗族、靠加 key 擴充；值的雙形；指示詞只是便利、設計不依賴它（C-48） |
| [2026-10-15 通用 kernel](general-kernel.md) | N-42 第二種：排序那步問判官 inst（只回 run／reject），沒給合法答案就退回確定規則；六題照建議定；公告欄晚點再說 |
| [2026-10-15 agent 判官實跑](judge-live.md) | 判官不靠模型思考（`/no_think`）、輸入瘦身成 state 窗子集；判官沒挑的空格由確定規則補位 |
| [2026-10-15 agent 判官實跑之二](judge-live2.md) | 補位之後信全服務完、順序對；格全滿時不問判官 |
| [2026-10-15 LiteLLM 實跑](litellm-live.md) | 本機 LiteLLM 實跑都通；五題拍板（換腦只換那一層、多個 tool_calls 照順序跑完、halted 時 loop 照舊退 0 等） |
| [2026-10-15 同像性](homoiconic.md) | inst 寫路徑或整張內嵌＝值的雙形（程式＝資料）；JSON schema 當型別用、驗證選用；七題照建議定 |
| [2026-10-15 意見 5～7](opinions-5-7.md) | 資料夾⇄JSON 可互通但別濫用；JSON schema 先用在 LLM 回話與 fsm 表；隱藏檔例外的資料夾名由 `AOS_DIRNAME` 定 |
| [2026-10-15 意見 1～4](opinions-1-4.md) | fsm 只管「狀態→inst」、只留表；agent＝定義資料夾；呼叫＝新建 frame、名字往上找；其餘照推薦（args.json／ret.json 10-16 撤掉） |
| [2026-10-15 兩條總原則](principles/README.md) | 巢狀只管自己這一層（C-52）、錯誤只處理自己的（C-53）、KISS 是最高原則（C-56）；其餘照推薦；kernel 的錯誤路徑評估待定 |
| [2026-10-15 命名](naming/README.md) | 使用者的命名習慣成 C-54；指令名底線換連字號、認可縮寫表（abbr.json）；未決：md 檔名與日期、「點」的用法 |
| [2026-10-15 inst 只吃 stdin／aos-exec](inst-exec.md) | 第二版：呼叫機制不靠指示詞（C-48）、`$ref` 從所在檔算、aos-exec TARGET 當語法糖；呼叫機制以第四版為準 |
| [2026-10-15 inst／aos-exec 第三版](inst-exec-v3.md) | 兩條前提（KISS 最高原則、層徹底切割）、aos-exec＝最小語法糖；B、E、I～L 照推薦定，其餘見第四版 |
| [2026-10-15 inst／aos-exec 第四版](inst-exec-v4/README.md) | 當時默認沒有指示詞可用（已推翻，現行 [N-45](../../../docs/NORMS/06-基礎設施-命令列與指示詞.md)：`$env`、`$ref`，`$ref` 可帶 `$at`）、agent 的定義＝一張 inst、工具一律走 frame、零 sh；C-50 選 a、其餘照推薦定 |
| [2026-10-15 布局成長](layout-growth.md) | 資料夾／檔案與 JSON 物件長大規則同一套（C-55）；原值一律 `val` |
| [2026-10-15 畫家 demo 真腦實跑](paint-live.md) | 畫家三層巢狀真腦實跑跟 README 一致，demo 不用修 |
| [2026-10-15 KISS 審視](kiss/README.md) | KISS 審視總表：批次 1 已做；10-16 使用者撤回「都照推薦」，批次 2～6 暫停（見 10-16 重審） |
