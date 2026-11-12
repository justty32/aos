# kernel-as-bridge 送 Argon 的提示原文（11-12 晚；回覆原文已在 04，不重抄）

← [kernel-as-bridge](README.md)

照 [aos-teams/05](../../../../../wf/workflows/dispatch/aos-teams/05-同機session與Argon.md) 用 `agy`（Gemini 4 Argon High、plan 模式）送出；下面兩段原樣照抄、沒改寫（是 Argon 的意見，不是使用者的）。回覆原文在 [04 § 原文](04-Argon審查.md#原文)，逐字相同、這裡不重抄。

## 送去的提示

```text
你是 Gemini Argon，aos 專案的共同設計者（不只審稿，也提案）。不要用任何工具、不要讀檔、不要跑指令，直接依下面文字作答。用繁體中文、白話、完整句子。產出分兩段：(A) 審查——我的初步整理哪裡錯、哪裡漏、哪裡說得太滿；(B) 提案——你自己看到的整理法、邊緣狀況、給使用者的方向題。限 1500 字內，條列，每條先結論。不要替使用者選大方向（大方向是他的），只擺選項與後果。

# 背景（aos 現況，極簡）
- aos＝「資料夾＝程式」的 AI agent 體系，跑在一台 linux 上。daemon（C++ aos-daemon）是一個迴圈：照表起 proc（fork/exec）、看活著（waitpid）、照表重起、收 ctl 信（信箱是資料夾，信是檔；別人想掛 proc 就寄信到它的 procs_requests 信箱）、把狀態寫成公開檔（state.json／procs_state.json「窗」）。daemon 來者不拒照掛。
- 監管樹（11-05 已定已做）：每台 daemon 都是某台 daemon 底下的 proc；根 daemon 由使用者顧。子 daemon 與根是同一支程式，子 daemon 底下的 proc 是子 daemon 自己直接向 linux fork 的；父對子「只看他有沒有活着，子daemon的其他東西父daemon別碰。盡量解耦合」（使用者 11-06）。卡住＝父標 stuck、可選自動重起。只有上一層動 pid（no-pid：別人不碰 pid，一律寄信）。子 daemon 被殺時它的 proc 變孤兒（setsid 過）、重起後 adopt 接回；根 crash 再起也一樣 adopt 整棵樹。
- 時鐘：只有根的表上有一列 `_clock`（一個 proc，寫鐘檔），子 daemon 與 agent 靠環境變數 `AOS_CLOCK` 讀同一份鐘檔；牆鐘各自直接讀 linux。
- 叫「kernel」的東西現在有：(1) daemon＝「最基礎的 kernel」；(2) 判官 lib/aos/judge（Python，規則型：白名單、max_running、排隊，判完把掛 proc 信轉寄給 daemon）；(3) 問腦總機 aos-llm-kernel（C++：收問腦請求信、照急不急排、看併發格與每寄件人額度、記帳，放行就請 daemon 掛一個問腦 proc 去打 LLM API）；(4) 隊 kernel llm-team（把問腦請求轉交給總機）；(5) 通用 kernel 框架圖紙（11-12 畫好未施工：一份 Python 骨架＋零件——收信、規則、三個 hook 時機、下一站 `next`、數量另指 `count_daemon`、回信二選一、排隊、「自己跑」runner；判官＝掛 proc 那一包、問腦總機用 Python 重寫成問腦那一包〔代定 K-F47〕；代定 K-F50：問腦總機的掛信去處只看設定裡的 `next`，不再看環境變數 AOS_KERNEL，這跟條文 N-63「認 AOS_KERNEL 的是 aos-llm-kernel 與 aos-agent」衝突）。你審過這份圖紙。
- 現行條文 C-47（使用者 11-11 定）：kernel＝「資源管理＋排程」，且是從外面看的身分——請求寄到哪，那裡對寄件人就是 kernel；收件 proc 不必自覺；轉交也算；鏈 agent→kernel_1→kernel_2→…→daemon 自然形成；一般 proc 一律寄 AOS_KERNEL（沒設退回 AOS_DAEMON），「如同linux一樣，user space的proc他只能看到kernel，除非有特殊需求，否則他看不到硬體」；問腦走另一個變數 AOS_LLM_KERNEL（「我們有多種syscall，有些syscall是走另一個kernel」）。安全保底是 linux 本身（帳號、權限），aos 不驗寄件人，繞過的風險使用者自擔。沙箱（bwrap、一個 agent 一個 linux 帳號）是遠期。cgroup、保留格都只在規劃。
- 使用者更早的話：11-05「daemon就像是硬體，各stack就是各程序所佔據的記憶體空間」「所有牽涉到linux原生行程的機制，都以daemon爲界面，而daemon所擔任的，就是橋梁」「其實daemon也算是一種kernel，只是他就是來者不拒」；11-06「假如root daemon就是底下的那個硬體板子，在嵌入式中的那個內部晶振，應該也是板子附帶的」。
- 單機開發，沒有跨機實作。

# 使用者 11-12 晚的新想法（逐字）
「然後是kernel這塊我也有新的想法，就是說，我一直說kernel負責排程和資源分配，後來發現linux kernel這個最通用的kernel，他的核心功能其實是作業系統與硬體的橋梁，套用到我們這邊，首先是root daemon本身就是一個kernel，他的所謂硬體對象就是linux，那，如果root daemon底下掛了另一個daemon，那對這個子daemon來說，root daemon就是他的硬體，去幫我想想。」

# 我（fable 隊長）的初步整理
1. 這句話把他三句舊話併成一句相對的話：「daemon 是硬體」（從上面看）、「daemon 是橋梁」（它自己做的事）、「daemon 是最基礎的 kernel」。新的是「硬體是相對的：你的硬體＝你的上一層」。
2. 對到現況有兩種「下面」：
   形一（監管樹的子 daemon）：根只給子三樣——電源（起、看活著、重起、收工一層層睡醒）、時鐘（AOS_CLOCK）、環境變數；行程、檔案、牆鐘、網路子 daemon 都直接碰 linux。像虛擬機／容器的「直通」：上層畫框，下層在框裡直接用真硬體。
   形二（請求鏈的站）：agent→站→站→daemon，中間站完全不碰 linux，只把信往下轉（圖紙的 `next`）；這才是嚴格的「上一層是我的硬體」。
   所以「子 daemon 的硬體是 root daemon」在形二完全成立、在形一只成立三樣。要嚴格可以是一種擺法（子層做成站、next 指向根，proc 全掛在根的表上），不必是全體規矩。
3. 「橋樑」跟「排程＋資源分配」的關係：我看是一個 kernel 的兩半——動手的那半（橋：把信變成底下的動作，daemon 做的）與做主的那半（准不准、先後、給多少：判官、總機做的）。多人共用一座橋才需要排程。C-47「請求寄到哪那裡就是 kernel」本來就是橋的說法，只缺「它底下是什麼」那一半。
4. 三種整理法（不替他選）：甲「一個 kernel 兩半」：kernel 以層為單位＝一台 daemon＋它門口的站，橋與做主都叫 kernel；條文加一段、圖紙不重畫。乙「kernel 只留給橋」：只有 daemon 叫 kernel，判官／總機／框架改叫別的（站、總機、排程站）；改名量大（AOS_KERNEL、框架夾名、C-47 重寫）。丙「kernel 定義不動，另立『層與硬體』一條」：C-47 維持從外面看的身分，新增一條講每層對上是硬體、對下是軟體；改動最少。
5. 問腦總機：LLM 是另一種「硬體」（條文 C-29 的外部處理單元），總機是通到它的橋頭管制、真正碰 API 的是問腦 proc 裡的 endpoint 函數。所以「地」不只一種：linux、LLM 供應商、人。
6. K-F50 在新看法下有更自然的理由：AOS_KERNEL 是給「上面的東西」找 kernel 用的；身為 kernel 的東西往下只認自己的硬體（設定裡的 next），所以總機不該看 AOS_KERNEL。K-F47（Python 重寫）是工法，不受影響。
7. 邊緣狀況：
   a. 硬體壞了軟體照跑：根被 kill -9，子 daemon 與 proc 都還活著（真電源是 linux），這裡比喻不貼；根不在期間寄給根的信堆在信箱。
   b. 「父只看活著」反而貼硬體（硬體不看作業系統裡面）；stuck 自動重起＝看門狗。
   c. 資源往下切：形二天然成立（上層會拒，下層頂多超賣）；形一不成立（根的 max_running 把子 daemon 算一格，裡面掛幾個根不知道），要成立得靠 cgroup（上層開機時定規格、linux 代為執行）。
   d. 權限：真硬體的保護也是硬體（MMU）執行、kernel 只設定；對應「保底是 linux，每層只負責起 proc 時套帳號／bwrap」。沒設 linux 權限時「上一層是硬體」只是約定（像沒有記憶體保護的 DOS）。
   e. 時間：根的 _clock＝板載晶振已是既有說法；子層自己帶 _clock 就是虛擬時間（可慢、可停）；牆鐘大家直讀 linux＝繞過。
   f. 跨機：父子要 waitpid，跨不了機；遠端 daemon 對本機比較像外部設備（外部 PU），不是下一層。判準提案：「你的硬體＝起你、能關你的那個」。
   g. 最上面：agent 掛 subagent 時，動手掛的是 daemon，不是 agent；agent 對 subagent 是請求者（上面），不是硬體（下面）——agent 樹是呼叫樹、daemon 樹是供應樹，遞迴不往 agent 走。例外：eca 的 claude 身用內建 Agent 工具開的子 agent 活在 CLI 行程裡，那個 CLI 才是它們的硬體，aos 看不到。
8. 給使用者的方向題：(1)「硬體」嚴不嚴格（只是讀法／上層畫框下層直通／全部經上一層）；(2) kernel 一詞留給誰（甲乙丙）；(3) 要不要為此重畫框架圖紙（我的看法：不用，框架是做主那半的零件，新看法補的是橋那半）。

請審與提案。特別想聽：形一／形二這個切法對不對；「兩半」的說法有沒有更好的；我漏了哪些邊緣狀況；K-F50 的理由站不站得住；有沒有第四種整理法。
```
