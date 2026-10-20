← [回入口 CONVENTION.md](../CONVENTION.md)｜段落：四～七｜上一份：[01-保證佈局入口](01-保證佈局入口.md)｜下一份：[03-shell版與inst版](03-shell版與inst版.md)

## 四、題目與答案

- **P-11** 題目＝`$AOS_WS/inbox/<題名>`，純文字、一題一檔；答案＝`$AOS_WS/out/<題名>`，跟題目同名；做完把題目搬到 `$AOS_WS/done/<題名>`。**結果＝工作區內容，沒有別的結果通道。**（拍板點 2；C-65 工作區只放交辦的東西與成果；C-34 求值＝空間狀態的變化。這是 agent-bob 的做法；「agent 之間傳題目走 inbox」當共同形狀，inbox 先不管〔使用者 10-19〕，不當規則）
- **P-12** 一次做一題：取 inbox 裡檔名排序最前面的那個，題名寫進 `$AOS_STACK/current`。（原型現狀；拍板點 1）
- **P-13** 需要附檔時升級成資料夾：`inbox/<題名>/` 裡題文叫 `prompt`、其餘檔是附檔；答案 `out/<題名>/` 也是資料夾、主答案叫 `answer`。一個 agent 認哪種形狀寫在它自己的說明；agent-bob 只認一題一檔。（拍板點 2「需要附檔再升級成資料夾」；檔名本稿定，照 C-54 小寫單數）
- **P-14** agent 只動 `inbox/`、`out/`、`done/` 與 `$AOS_STACK`，工作區其他東西不碰。`done/` 只進不出，清理是人的事。（C-65 工作區保持乾淨；C-56 不為清理加機制）

## 五、stack

- **P-15** 執行中的一切（狀態、草稿、紀錄、小格）只寫 `$AOS_STACK`，**定義資料夾不被寫**；所以同一個 agent 可以同時被兩個工作區跑。（C-65；§ 2；原型測試已驗）
- **P-16** agent 自己的格（idle／think／act）共用同一個 `$AOS_STACK`——它們是同一台狀態機。stack 裡放什麼、叫什麼，agent 自訂；agent-bob 的 `state`、`current`、`plan`、`trace.jsonl` 是例子不是規範。（拍板點 1「stack 內部自由」；§ 2「剩下的你自己想」；§ 3）
- **P-17** 叫**別的**資料夾程式（工具、另一個 agent）時，給它自己的 stack（**小格**）：`sub=$AOS_STACK/<名>/`、`AOS_STACK=$sub aos-exec tools/<名>`（例：cathy 的 act 用 `AOS_STACK=$sub aos-exec tools/stamp`，工具的 `runs` 落在 `$AOS_STACK/stamp/`）。小格名＝工具資料夾名（P-38 靠這點）。被叫的只看到自己的 stack、不知道上面有誰。叫完不自動收——留著給人看；要收由呼叫方自己 `rm`。巢狀時小格怎麼給、被叫者的工作區放哪，見第十二節 P-32。（§ 3「子程式的 stack 由 agent-bob 自己訂，有可能他會是 AOS_STACK/think, /act」；C-52 子 agent 只看自己的 stack；C-65 stack＝「叫工具時開的小格」；C-67 stack 放哪由呼叫方決定；拍板點 3「人來看」。這是原討論稿拍板點 4 的答案）
- **P-18** 一個工作區同時跑兩個 agent 時，呼叫方給不同的 `AOS_STACK`（例 `$AOS_WS/.aos/bob/`）；預設值只保證「一個工作區一個 agent」不撞。（C-67；C-53 入口默認正常、誤用不歸組件管）

## 六、停與錯

- **P-19** 結束碼三種：`0`＝這圈好了、下一圈；`10`＝正常停（idle 看 inbox 空了）；其他非 0＝失敗。loop 收到 10 以 0 結束；收到其他非 0 以那個碼結束；跑滿 `max` 以 0 結束、stderr 不寫（N-43 正常退出不噴 stderr；要知道有沒有跑滿看 `trace.jsonl` 行數）；loop 自己收到 SIGINT／SIGTERM／SIGHUP 時收完那拍以 128＋N 結束（P-36）。（拍板點 1；原型現狀。原與 C-63 相撞，使用者 10-19 定照用，C-63 作廢，[ideas § 9](../thinking/2026-10-19-ideas.md)；N-43）
- **P-20** 任一格失敗＝整個 agent 停下來等人：fsm 不換狀態、loop 以那個碼結束；人修好後再 `aos-exec` 一次，從 `$AOS_STACK/state` 接著做同一格、同一題。不自動重試、不數連錯。（拍板點 3；N-53 腦出錯那拍 phase 不動；N-38）
- **P-21** 誰的錯誰自己講：格的錯寫在格自己的 stderr；fsm 什麼都不轉述；loop 只說「第幾圈、誰、結束碼幾」。（C-53；N-43 每層只說自己）
- **P-22** 逾時：shell 版沒人管——某格卡住（模型沒載入、網路不通）loop 只會等，也殺不到孫程式。要逾時就把那格換成 inst 版、寫 `timeout_ms`（P-29）。（N-41「靠那張 inst 的 timeout_ms 守」；inst 討論的結論）

## 七、腦與工具

- **P-23** 腦＝OpenAI 相容的 chat completions 端點，由環境變數 `AOS_BRAIN_URL`、`AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY` 指定；`AOS_BRAIN_URL` 沒設＝假腦（demo 預設）。只取回覆的 `content`（有工具時加 `tool_calls`），模型想的內容不收、不存。這台電腦不跑本機模型。（原型現狀；使用者 10-15「維持 openai 格式」「模型想的內容丟掉」（[thinking 10-15 topics/02](../thinking/2026-10-15-topics/02-agent工具與試146.md)）；§ 6；變數名照 C-54 全大寫底線）
- **P-24** 想跟做分開：think 問腦、只把「要做什麼」寫進 `$AOS_STACK/plan`；act 照 plan 動手、不問腦。能寫死的步驟（搬檔、寫檔）放在 act 這種程式格，不交給模型。（C-22 能寫死的節點換成程式；C-25）
- **P-25** 工具＝`tools/<名>/` 子資料夾程式，**放在叫它的那一格的資料夾裡**（`act/tools/cathy/`），格裡寫 `aos-exec tools/<名>`：地址是從自己 cwd 起算的相對路徑、永遠零個 `..`、不靠 PATH；`AOS_WS` 自然傳下去（要換工作區見 P-32）；工具要不要碰工作區、怎麼碰，是工具自己的事、風險設計者自管；工具裡是不是另一個 agent，呼叫者不知道也不管。stack 照 P-17。細節與理由見 P-33。（C-61 不用 PATH、地址在自己資料夾裡；N-55；C-66；C-52）
- **P-26** 工具的參數怎麼進（args、stdin、或 stack 裡的檔）由工具自己的說明定；aos-exec 保證 args 與 stdin 原樣送到。（§ 4）入口是單子時也成立：args 接在單子 `argv` 的尾巴，單子沒寫 `stdin` 就接呼叫者的（§ 20 使用者沒異議、照預設「串流沒寫＝接呼叫者的」）；單子自己寫了 `stdin: 檔` 是它自己選的，不算 aos-exec 沒送到。

