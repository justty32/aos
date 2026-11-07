C 隊審 json-argv J7「條文照實作修字面」（commit `7a2adf2dc`，D 隊 sol＋opus）落進 P-44、P-41、C-52、N-43 續、lib 規則、knowledge 的部分。

← [入口](../03-條文-no-pid-tick-json-argv-special-cases.md)｜上一份 [02-tick-time-續](02-tick-time-續.md)｜下一份 [04-special-cases](04-special-cases.md)

## json-argv J7

**先回隊長問的那題：「條文照實作修字面」本身對不對？** 這批大多數改動是在條文裡加「11-06 註（已實作）」把現況記進去、原句都留著——這種寫法是可以的，使用者定的原句沒被翻掉。有三處越線：一處把沒做的東西寫成已實作（第 1 條）；一處把 codex 自己定的實作細節用「不得」「例外」這種規範句寫進條文、沒標是代定（第 2 條）；一處 C-52 的例外 ④ 是先寫進條文再標「要使用者看」，使用者後來選了「保留」，這條反而是對的做法（已核對）。使用者原話（旗標只是補充、巢狀可以、旗標＞stdin＞環境變數、只吃想吃的不報錯、`--target` 待補、子資料夾要先看）都在 P-45 與 lib 規則 1 裡逐字留著，J7 沒寫歪。

### 1. P-44 把「aos-agent tools add 也收 `--env-file`／`--envs`」寫成已實作，程式其實會報 `FlagUnknown`
- **類別**：條文｜**嚴重度**：錯誤行為（照條文做會出錯）
- **檔:行**：`proto8/docs/CONVENTION/02-題目stack停錯腦/07-P-44.md:13`（「**11-06 註（已實作）**：…首例 aos-tools add、aos-agent tools add…11-06 J3 已實作」）；程式 `proto8/cmd/aos-agent/aos_agent/tools.py:104`（只認 `--target`）、`proto8/cmd/aos-tools/bin/aos-tools:512-514`（只有 aos-tools 認這兩個旗標）
- **commit／哪隊**：`7a2adf2dc`（D 隊，J7 條文是 codex sol 寫、opus 隊長審）
- **問題**：這一條原本是「規劃中」，J7 整條改成「已實作」，但 J3 只做了 `aos-tools add`；`aos-agent tools add --envs K=V` 現在是 `FlagUnknown`。HANDOFF「明天要接 ④」也還排著「`--env-file`＋`--envs`」。同一個錯寫進英文知識書時，F 隊 11-07 已經照實更正（`proto8/knowledge/aos/cli/tool_env.md:11`，commit `54d8407a1`），但條文這邊沒跟著改。
- **使用者原話**：「或者改成--env-file xxx搭配--envs K=V...也不錯，兩者並存吧。」（`proto8/thinking/2026-11/05/no-pid/03-找daemon與脫鉤.md`，P-44 自己引的）——原話只定「兩者並存」，沒說哪支先做。
- **建議**：直接修：那條開頭改成「11-06 註（aos-tools add 已實作 `a6d8cd9a`；aos-agent tools add 還沒，排程見 HANDOFF）」。

### 2. J3 codex 自己定的三條實作細節，用規範句寫進 P-44、沒標代定
- **類別**：代定｜**嚴重度**：品質（細節題，但寫法像已裁）
- **檔:行**：`proto8/docs/CONVENTION/02-題目stack停錯腦/07-P-44.md:13` 後半：「add 當下讀檔、存內容；`--envs` ＞ `--env-file` 合成登記格 `env`，call 時登記格 `env` ＞ 繼承環境；`AOS_STACK` 例外…登記格**不得**覆蓋」
- **commit／哪隊**：`7a2adf2dc`（D 隊 sol）；來源 `proto8/thinking/2026-11/05/json-argv/10-J3到J7實作結果.md` J3 節「代定（codex 定、隊長審過；可翻案）」1～3
- **問題**：10 自己寫明這三條是 codex 代定、可翻案，但條文那一句接在「使用者…已定（11-05）」後面、用「不得」收尾，讀起來像整句都是使用者定的。其中「存內容不存路徑」有實際後果：之後改 `.env` 檔要 `add --override` 重登記，使用者沒看過這個取捨。
- **使用者原話**：優先級那句是「關於優先級，就是旗標>stdin>環境變數，至於程式自己讀的設定檔，我們不管。」（`proto8/thinking/2026-11/05/json-argv/07-使用者回覆-11-05晚.md`）——講的是工具參數的來源，不是登記格 `env` 跟檔的先後；「存內容」「不得覆蓋 `AOS_STACK`」沒有原話。
- **建議**：條文那段加「（J3 代定，可翻案）」三個字就好；「存內容還是存路徑」要不要問使用者：A 存內容（現況；改檔要重登記，推薦，因為登記檔自足、搬家不斷）；B 存路徑（改檔即生效，但搬家就斷）。

### 3. C-52 的「現行清單」三份寫法互相不同
- **類別**：條文｜**嚴重度**：品質
- **檔:行**：`proto8/docs/CONCEPTS/01-設計理念/03-最高原則與兩條總原則.md:13`（「現行清單為 ①、③、④」）；`proto8/docs/CONCEPTS/01-設計理念/03-續-C-52-例外.md:7`（「現行清單為 ①、③、④、⑤」）；同檔 `:17-25`（表列 ①③④⑤⑥⑦⑧）；`wf/workflows/common/conventions.md:26`（「明文例外四類」）
- **commit／哪隊**：主檔那句 `7a2adf2dc`（D 隊 sol）；續檔 ⑤ `b7e86dcc6`（claude）；表 `c56e53751`（K 隊 sol）；conventions 那行先後被 `7a2adf2dc`、`c56e53751` 改
- **問題**：同一件事（現在准讀下層 stderr 的有哪些）在四處寫了三個不同答案：三處、四處、七列。special-cases 已把它改成「判準＋現行表」，但主檔與 conventions 的舊數字沒改讀、只在後面疊註。F 隊另外發現表上 ⑧ 做完沒擦（[06 第 2 條](../06-special-cases抽核/01-發現.md)）。
- **使用者原話**：「改成判準＋現行表 (Recommended)」（`proto8/thinking/2026-11/06/special-cases/README.md` 裁定 2）
- **建議**：直接修：主檔 :13 與 conventions :26 的數字句都改成「現行清單見 C-52 續的表」，不再各自數。

### 4. P-41「子資料夾＝子動作」一句裡同時寫「已定」和「使用者要先看實作再定稿」
- **類別**：條文｜**嚴重度**：跟原話不符（輕）
- **檔:行**：`proto8/docs/CONVENTION/02-題目stack停錯腦/06-P-41.md:12`
- **commit／哪隊**：`76297cae1`（lift-to-norms，CONVENTION 那半是 codex sol 寫）；J7 沒動它但也沒修
- **問題**：使用者的話是「我覺得這個最好，但這個之後實作的時候我要看一眼，怕有些問題」——方向傾向有了、定稿要等他看。條文先寫「已定（11-05）」再寫「要先看實作再定稿、目前未實作」，前後兩句打架；照鐵律 5 這題還在他手上。
- **使用者原話**：「2.子資料夾就是子動作，我覺得這個最好，但這個之後實作的時候我要看一眼，怕有些問題。」（`proto8/thinking/2026-11/05/json-argv/07-使用者回覆-11-05晚.md`）
- **建議**：直接修：「已定」改成「方向已選（11-05）；定稿等使用者看過實作」。

（已核對沒問題的在 [06-已核對](06-已核對-json-argv與special-cases.md)。）
