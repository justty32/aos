← [回入口 02-題目stack停錯腦.md](../02-題目stack停錯腦.md)｜段落：五、stack、六、停與錯｜上一份：[03-P-43續-11-04-aos-agent](03-P-43續-11-04-aos-agent.md)｜下一份：[04-六-停與錯續-P-21～P-22](04-六-停與錯續-P-21～P-22.md)

## 五、stack

<a id="p-15"></a>

P-15 全文見 [04-五-stack續-P-15](04-五-stack續-P-15.md)。

- **P-16** agent 自己的格（idle／think／wait／act）共用同一個 `$AOS_STACK`——它們是同一台狀態機。stack 裡放什麼、叫什麼，agent 自訂；`templates/agents/agent-fsm` 的 `think/pending.txt`、`think/request.json` 是例子不是規範。（拍板點 1「stack 內部自由」；§ 2「剩下的你自己想」；§ 3）
- **P-17** 叫**別的**資料夾程式（工具、另一個 agent）時，給它自己的 stack（**小格**）：`sub=$AOS_STACK/tools/<名>/`、`AOS_STACK=$sub aos-exec tools/<名>`（例：agent-fsm 的 act 經 `aos-tools call` 叫工具，工具的小格是 `$AOS_STACK/tools/<登記名>/`）。小格名＝登記名（預設是工具資料夾名；P-38 靠這點）。小格放在 `tools/` 底下，呼叫方給的名字跟格自己的固定名分開命名空間；`tools` 是 stack 頂層的保留名（格自己不能在 stack 頂層放叫 `tools` 的固定東西）（使用者 11-02「未來，搞不好會出現agent+kernel的變體，.stack底下會有一大堆東西。擋名字會擋不過來。所以我覺得最好還是tools/<name>更好」，[thinking 11-02 stack-tools](../../../thinking/2026-11/02/stack-tools/README.md)）。被叫的只看到自己的 stack、不知道上面有誰。經 `aos-tools call` 叫時另給 `AOS_STACK_IN_CALLER=tools/<登記名>`——小格在叫方 stack 裡的**相對位置**，不是叫方 stack 的路徑：只讓工具把自己小格裡的路徑印成叫方照自己的 `$AOS_STACK` 找得到的 `$AOS_STACK/tools/<登記名>/…`（`tool_io.place`），被叫的照樣只碰自己的 stack；沒給（直接 `aos-exec` 叫）＝照自己的小格印（使用者 11-13「fx-2:A」；變數名與給相對位置是代定、可翻案，[tool-stack-path](../../../thinking/2026-11/13/tool-stack-path.md)）。叫完不自動收——留著給人看；要收由呼叫方自己 `rm`。巢狀時被叫者的工作區：沒給就沿用呼叫方的 `AOS_WS`，要換就明給 `--ws`（N-58）。（§ 3「子程式的 stack 由 agent-bob 自己訂，有可能他會是 AOS_STACK/think, /act」；C-52 子 agent 只看自己的 stack；C-65 stack＝「叫工具時開的小格」；C-67 stack 放哪由呼叫方決定；拍板點 3「人來看」。這是原討論稿拍板點 4 的答案）
  - **小格不先建**（使用者 11-11「我確實想改成工具真的寫東西時才建資料夾」，[thinking tool-cells-lazy](../../../thinking/2026-11/11/tool-cells-lazy.md)）：`aos-tools call` 只把 `AOS_STACK` 設成 `<父 stack>/tools/<名>/`、交 `aos-exec --stack-lazy`，不先建資料夾；工具真的要往小格寫東西才自己 `mkdir -p`，讀的時候小格不在＝空的。所以只有寫過東西的工具才留下小格，「叫完不自動收」照舊。
- **P-18** 一個工作區同時跑兩個 agent 時，呼叫方給不同的 `AOS_STACK`（例 `$AOS_WS/.stack/bob/`）；預設值只保證「一個工作區一個 agent」不撞。掛上 daemon 的（標準範本的做法）stack 預設是 `<daemon 的 stack>/procs/<名字>/`，一隻一夾、同工作區多隻不撞；本條的預設值講的是直接 `aos-exec` 的情形。（補現況＝使用者 11-13「cv-P18:A」，[convention-vs-agent-fsm](../../../thinking/2026-11/13/convention-vs-agent-fsm.md)；C-67；C-53 入口默認正常、誤用不歸組件管）

## 六、停與錯

- **P-19** 結束碼三種：`0`＝這次好了、下一次；`10`＝正常停、沒東西了（idle 看 `$AOS_STACK/queue/` 空了，P-11）；表上明寫接住的碼（如 wait 的 11）＝分岔、不是失敗；沒列在表上的其他非 0 才是失敗。（使用者裁定 sol 審查 #29）字串 `next` 的表上只有 idle 退 10；物件 `next`（N-36）的表上，別的格也可以退 10、意思仍是 N-43 的「沒東西」、由表接住——`templates/agents/agent-fsm`（四格 idle → think → wait → act）在腦給了最後答案（沒有 `tool_calls`）時 act 退 10、think 在 history 尾巴沒有要答的時退 10，表上 `"10": "idle"` 接住、到不了 loop；範本連 idle 的 10 也接住＝停著等、不收工（P-35、P-41、[四格呼叫端](../../../thinking/2026-11/04/think-as-function/03-呼叫端.md)）。loop 收到 10 以 0 結束；收到其他非 0 以那個碼結束；跑滿 `max` 以 0 結束、stderr 不寫（N-43 正常退出不噴 stderr；要知道有沒有跑滿看 loop 的 state 窗或 log）；loop 自己收到 SIGINT／SIGTERM／SIGHUP 時收完那次以 128＋N 結束（P-36）。（拍板點 1；原型現狀。跟 C-63 相撞處使用者 10-19 定照用、C-63 作廢，[ideas § 9](../../../thinking/2026-10/19/ideas/README.md)；N-43；think 也退 10：使用者 11-04 衝突 2 選「think 也退 10，條文加註」，[thinking 11-04 loop-fsm-agent](../../../thinking/2026-11/04/loop-fsm-agent/04-衝突與方向題.md#決定11-04使用者)）
- **P-20** 任一格失敗＝整個 agent 停下來等人：fsm 不換狀態、loop 以那個碼結束；人修好後——直接跑的再 `aos-exec` 一次，掛 daemon 的（標準範本）`aos-agent ctl start`——從 `$AOS_STACK/stage.txt`（[four-elements 07 步 3](../../../thinking/2026-11/04/four-elements/07-實作步驟.md#步-3fsm-的-statetxt-換同義詞題-10)）接著做同一格、同一題。不自動重試、不數連錯；只有開了 `--auto-restart`（`aos-agent ctl add`）的，照細項「失敗後冷卻」重試。（拍板點 3；N-53 腦出錯那次 phase 不動；N-38）
  - P-20 的細項（表上沒接住時才是預設停、格的旋鈕不走環境變數；daemon 的身體例外；kernel 不在＝等它來；等回信沒有期限；失敗後冷卻）在 [01-P-20-細項](04-五-stack與六-停與錯/01-P-20-細項.md)。
- （P-21、P-22 接在 [04-六-停與錯續-P-21～P-22](04-六-停與錯續-P-21～P-22.md)。）
