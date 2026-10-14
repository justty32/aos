# 2026-10-14 函數的統一入口改成 JSON

← [討論紀錄](README.md)｜前一份：[kernel／agent](2026-10-13-kernel-agent.md)

> 10-14 中午（公司 WSL），使用者吃飯時的想法，打字。

## 0. 背景

今天上午只做規劃：aos-llm／aos-agent 規劃與 ctl／state、inst↔LLM 工具轉接兩份研究（皆 AI 建議、未拍板；網頁 https://claude.ai/artifact/K2aQ7KCad1u3dFTfDvArda 、https://claude.ai/artifact/HvrESfVs7MAM7t6hXBFFYu ）。使用者今天說：tasks 與 tick 忽略；公司這台不用 146、今天不實打 LLM；ctl／state 最好都統一規範。

## 1. 使用者原文（照原意整理）

原話：「posix呼叫格式，還有lisp的那套list呼叫方式，我覺得最大的痛點就是和json脫節。posix呼叫，表述的是一個函數的統一入口，lisp也是，兩者也不通，我在想，要是能讓函數的統一入口，變成參數統一成json就好了，這樣可以直接對接llm工具，乃至於python等腳本語言，而且和檔案系統也能很好的合作。我知道當年因為資源不足，所以不能用map，只能用list或array，但現在有了，所以...。」

要點：
- POSIX 的呼叫格式、LISP 的 list 呼叫方式，最大的痛點是和 json 脫節。
- POSIX 呼叫表述的是一個函數的統一入口，LISP 也是；兩者彼此也不相通。
- 想法：讓函數的統一入口，參數統一成 json。
- 好處：可以直接對接 llm 工具，乃至 python 等腳本語言，而且和檔案系統也能很好地合作。
- 當年資源不足，所以不能用 map，只能用 list 或 array；現在有了，所以...（話沒說完）

## 1b. 使用者續說（同天）

原話：「我會覺得說，目前inst格式不變，因為要適應舊的時代，也作為和舊時代之間的橋樑(daemon的目標)。只是說在設計可供呼叫的程式的時候(argv[0])，我們可以在後續的標準規範說，建議，argv[1]，就是一個json檔案，作為argv[0]的參數。或是走stdin (我不太想，因為stdin在linux上有特別作用)。但是又要面臨取捨，也就是放棄了人手動用命令行的方便性。然後你說的回傳值，我也在想是否要走stdout/err，或是走argv[2]。」

要點：
- inst 格式不變：要適應舊的時代，也作為和舊時代之間的橋樑（daemon 的目標）。
- 設計可供呼叫的程式（argv[0]）時，後續標準規範「建議」argv[1] 是一個 JSON 檔，作為 argv[0] 的參數。
- 也可以走 stdin，但他不太想（stdin 在 Linux 有特別作用）。
- 取捨：放棄人手動打命令列的方便。
- 回傳值：在想走 stdout／stderr，還是走 argv[2]。

## 1c. 使用者續說（同天）

原話：「我後來想想，因為stdin/out/err，在未來的作用其實不會很大，考慮到以後一定是成千上萬個posix呼叫在跑，其中一定只有少數幾個stdin/out/err會讓人在終端機上能看到能互動，其他的要麼由agent處理，要麼由其他函數處理。  然後我又想到，假如不需要了stdin/out/err，那麼其實inst格式也未必需要，搞不好最後全面退守到C語言的system("...")」

要點：
- stdin／stdout／stderr 未來作用不大：以後是成千上萬個 POSIX 呼叫在跑，只有少數會讓人在終端機上看到、互動，其他由 agent 或其他函數處理。
- 進而想到：若不需要 stdin／out／err，inst 格式也未必需要，搞不好最後全面退守到 C 語言的 `system("...")`（想法，未定）。

## 1d. 使用者續說（同天）

脈絡（AI 列的）：退守 `system()` 會失去限時與收尾、cwd／環境、exit 紀錄、訊號轉送，且 inst 是 kernel 能讀的資料而 system 字串是黑箱。

原話：「看起來不能全面退守，這樣損失太大。但可以記下來當作以後的一個方向。 所以就是換成把stdin作為參數，stdout/err作為結果，exit作為輔助」

要點：
- 不能全面退守，損失太大；但記下來當作以後的一個方向。
- 改成：stdin 作為參數，stdout／stderr 作為結果，exit 作為輔助。

## 1e. 使用者續說（同天）

原文：「也就是回歸posix的最原始本意。stdin/out/err都不一定要是json，但是在我們的規範中，必須是json。exit檔案是否出現確實是一個好的判斷標準」

要點：
- 回歸 POSIX 最原始本意：stdin＝參數，stdout／stderr＝結果。
- POSIX 本身 stdin／stdout／stderr 不一定要是 JSON，但在 aos 規範中必須是 JSON。
- exit 檔是否出現，是判斷結果寫完的好標準（AI 提議，使用者認可）。

## 1f. 使用者續說（同天）

脈絡：AI 建議 stderr 用「一行一個 JSON」。

使用者：「stderr一邊跑一邊吐...還是換成jsonl格式？」

使用者：「stdout/in也都換成jsonl?」

AI 說明：只有一行的 JSONL 就是一份普通 JSON；嚴格 JSONL 會讓人手寫排版的參數檔不合規，可放寬成「一串 JSON 值接著一串」（每份可單行或跨行，像 jq 讀法）。

使用者（意識到這就是串流）：「喔買尬，串流，我滴神」

AI 補充連帶意義（使用者沒反對）：stdio 全改 JSON 串流後，每支程式是一個 JSON 串流處理站，管線 `a | b | c` 就是函數套函數。

使用者：「放寬。」

## 1g. 使用者續說（同天）

原文：「jsonl，本質上就是在最外層包一個[]」「所以檔#/位置就很自然」。

## 1h. 使用者續說（同天）

原文：「好，所以現在inst json格式不動，但是對於inst 中所呼叫的argv[0]程式，我們訂下了規範，要符合規範，就是stdin/out/err都是jsonl，具體怎麼處理就自己弄，並且寬鬆。然後以這個方式去重作aos-inst/loop/daemon，這是後續，應該是沒啥問題的」

要點：
- inst.json 格式不動。
- 規範管的是 inst 所呼叫的 argv[0] 程式：stdin／stdout／stderr 都是 JSONL，具體怎麼處理自己弄、寬鬆。
- 後續要以這個方式重做 aos-inst／loop／daemon；使用者認為應該沒啥問題。

後來使用者對 AI 挖的四條邊緣回：「都按照建議。」（照建議＝決定，見 §2）

## 1i. 使用者續說（同天）

原文：「state.json/ctl.json這塊，我會覺得，它本質上是程式內部狀態的外顯，有點plan 9 fuse的感覺，會在參數(stdin)中指定其狀態外顯，要放在哪裡。」

要點：
- state.json／ctl.json 本質上是程式內部狀態的外顯，像 Plan 9／FUSE。
- 外顯放在哪裡，由參數（stdin）指定。

## 1j. 使用者續說（同天）

脈絡：回應 AI 在 §3 列的 (a)–(f) 待想項。

原文：「外顯之後，程式本身會固定一段時間抓外顯的狀態進行同步。參數不指定位置時，就是stdout吐出一句警告。窗的名字要統一，state或status都可以。daemon的控制資料夾先不管。fuse是可選，用了會更舒服，以後再說。然後stdin/out/err他是程式本身的標準對外窗口，代表輸入輸出錯誤，而state/ctl則是程式內部的東西，程式願意分享給大家，兩者完全沒關係」

## 1k. 使用者續說（同天）

脈絡：回應 AI 在 §3 列的三條待確認（警告走 stdout 還是 stderr、統一名 `state` 還是 `status`、loop／daemon 的 stdout 每回合吐狀態 JSON 是否保留）。

原文：「三件事都按照建議。」（照建議＝警告走 stderr；統一名用 `state`；拿掉「loop／daemon 的 stdout 每回合吐一份狀態 JSON」，stdout 吐什麼另議。）

原文：「然後我說的這些，其意義是這樣的：我用一串json丟給loop，跟他說，請你用這個參數啟動，也就是函數的args，然後函數的返回值ret就是exit+stdout，途中出錯拋出來的東西，就是stderr」

## 1l. 使用者續說（同天）

使用者：「返回值這塊，你知道async, yield嗎？」

AI 說明（一句帶過）：stdout 的 JSON 串流像 yield、exit 像最後的 return、async＝不等 exit、await＝等 exit 檔出現。

使用者：「stdout可以承擔這份職責」「但沒有那麼死」。

## 2. 決定（10-14）

- 不全面退守 `system("...")`，損失太大；記為以後的一個方向。
- 可供呼叫的程式：stdin 作為參數，stdout／stderr 作為結果，exit 作為輔助。（細節如參數是否必為 JSON、stdout 格式，待確認；後來以函數看法細分，見本節末。）
- 回歸 POSIX 原始本意。
- aos 規範中 stdin／stdout／stderr 都是 **JSON 串流**（POSIX 本身不要求），採放寬寫法：一串 JSON 值接著一串，每份可單行（即 JSONL）或排版跨行；只有一份就是普通 JSON（使用者 10-14「放寬」）。取代先前「stdio 必須是 JSON」的寫法。
- 結果寫完的判定＝exit 檔出現（AI 提議、使用者認可）；串流沒有「整份寫完」的時刻，所以仍以 exit 檔為準。
- JSON 串流本質上＝最外層省略的 `[]` 陣列，所以 `檔#/位置` 自然適用：`檔#/0` 是第一份、`檔#/3/key` 是第四份的 key、`檔#`（整份）＝整個陣列（使用者 10-14）。
- stdin 多份＝整串一次呼叫，程式自己解讀（使用者 10-14 選項題）；規範只管格式不管意思。
- 已寫進 NORMS N-12 草稿（使用者 10-14 選項題）。
- 後續以 N-12 重做 aos-inst／loop／daemon（還沒動工）。
- 三支程式改從 stdin 收設定後，要指 `檔#/位置` 時 stdin 內容寫 `{"$ref": "x.json#/clock"}`，用現成指示詞，不發明新東西（使用者 10-14「都按照建議」）。
- 寬鬆：人手動打 `aos-inst x.json`（argv[1] 給路徑）保留，stdin 與 argv[1] 兩種都收（同上）。
- 先前「loop／daemon 長時間跑時，stdout 串流每回合吐一份狀態 JSON」這條拿掉（使用者 10-14「三件事都按照建議」）；stdio 與 state／ctl 無關，loop／daemon 的 stdout 吐什麼另議（見 §3）。
- aos-inst 自己的 stdio 與它所呼叫程式的 stdio（inst.json 的 stdin／stdout／stderr key 指定的檔）分開，不是同一回事（同上）。
- state.json／ctl.json＝程式內部狀態的外顯（像 Plan 9／FUSE）；位置由 stdin 參數指定（使用者 10-14）
- 外顯之後，程式自己每隔一段固定時間跟外顯的狀態同步（讀 ctl、寫 state）（使用者 10-14）。
- 參數沒指定外顯位置時：不外顯，stderr 吐一句警告（使用者 10-14 先說 stdout，後「按照建議」改 stderr：stdout 是結果、警告屬途中拋出）。
- 窗的名字統一為 `state`、`ctl`（使用者 10-14「按照建議」；現有程式已用 state.json）；ctl 是別人寫、程式讀的可寫面，state 是唯讀面（同上）。
- daemon 的控制資料夾先不管（同上）。
- FUSE 可選，用了更舒服，以後再說（同上）。
- stdin／stdout／stderr＝程式本身的標準對外窗口（輸入、輸出、錯誤）；state／ctl＝程式內部的東西、程式願意分享給大家；兩者完全沒關係（同上）。
- 以函數來看：stdin（一串 JSON）＝args；返回值 ret＝exit＋stdout；途中拋出來的東西（錯誤、警告）＝stderr（使用者 10-14）。
- stdout 可以承擔 yield 的職責（一份一份吐出），但不強制（使用者 10-14：「沒有那麼死」）。

## 3. 未決

- 手動打命令列的方便怎麼補。
- 被殺時最後半份壞掉，讀的人怎麼處理。
- 落成檔案時，上游太快會讓檔案無限長。
- 串流還沒跑完時，指到的位置可能還不存在（AI 補）。
- 最後半份壞掉時，要不要算進陣列（AI 補）。
- 巢狀串流先不碰。
- loop／daemon 的 stdout（ret）要吐什麼（AI 提）。
- stdin 是否也像產生器的 `send()` 那樣持續流入、一來一回（AI 提）。
- 輸出落成檔案時沒有管子的煞車（AI 提）。
