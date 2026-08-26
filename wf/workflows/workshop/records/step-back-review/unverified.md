← [三場研討會的回頭審視](README.md)

> 本檔收兩題：**二**（哪一條假設從頭到尾沒人檢查過）、**六**（有沒有漏掉比上面全部都重要的事）。兩題指向同一處——真 LLM CLI 沒實測過、failure 與 trust 的邊界沒定義，而這兩件事比抽象設計更優先。

# 二、哪一條假設從頭到尾沒人檢查過

## `deliver --key` 的跨回合冪等其實沒有帳本

資深工程師與資深架構師**兩位獨立地檢查到同一個洞**：前一場把同 key 同內容說成 Already、
異內容說成 Conflict；但 aggregate 成功後會刪掉投遞檔。沒有一份耐久 receipt ledger，下一次
重送 `K` 時已沒有舊內容可比，根本不知道它是不是同一次。

所以最小 Deliver 現在只能承諾：驗證 payload、建立唯一同目錄 temp、write-all、rename 到 queue。
key 可以留作檔名／correlation 提示，但**不能在沒有 ledger 的情況下宣稱跨回合去重**。若日後真
遇到重送事故，要嘛另養 ledger，要嘛把去重範圍明確縮到「檔案還留在 queue 時」。

## 沒人實測 LLM CLI 是否真像一個純函式

資深研究人員與要接工具的開發者**兩位獨立地指出**，三場一直假設可以把 prompt 送進某支 CLI，
再得到完整、穩定、可解析的 tool call；但 session、streaming、schema、截斷、取消、exit code、
Ctrl-C 後狀態都沒有用真 CLI 驗證。工程師、研究人員、開發者**三位獨立地都追問同一個最基本的
問題：首支 CLI 到底是哪一支？**；架構師則先問這支 CLI 會在全信任實驗裡跑，還是會碰真實資源。

在這個假設未驗證前，events／calls、Effect 狀態與恢復 API 都可能是在替不存在的 I/O 形狀設計。
T5 的第一個產物應是觀察紀錄：CLI 在每個成功、失敗與中斷點實際留下什麼。

## failure 與 trust 的範圍一直沒定義

工程師、研究人員、開發者分別追問 Ctrl-C、hard kill、斷電是不是同一個承諾；架構師則要求先
說 T5 是全信任實驗，還是模型能碰真實檔案、網路與憑證。沒有這兩條邊界，「durable」「可恢復」
與 capability 都只是在各自想像不同故障／威脅模型。

---

# 六、有沒有漏掉比上面全部都重要的事

有兩塊，而且四位都把它們排到抽象設計之前。

## 模型輸出的執行權與威脅模型

資深工程師、資深架構師、要接工具的開發者**三位獨立地指出同一個更高優先風險**：若 translator
把模型輸出的任意 argv 直接交給 POSIX 執行，prompt injection 就取得了使用者的檔案、網路、憑證
與命令權限。前面討論的 capability 若所有程式都跑同一 UID，只是約定，擋不住這件事。

首版責任不能丟給不存在的通用 capability：三位給的最小邊界是**具名 tool allowlist → 固定 argv
映射**；未知工具停住，視威脅模型再加人工核准或 OS sandbox。使用者必須先說 T5 是全信任玩具，
還是會碰真實資料與憑證，才能知道哪一層是必要的。

## 一條真的可執行、可殺死、可觀察的 golden slice

**四位獨立地都要求先跑真 CLI 並注入 crash**：工程師要真實 LLM CLI＋受限工具來回；架構師要
最小 loop 並逐點 crash；研究人員把它叫 executable golden slice；開發者要求端到端與 crash-window
測試。這不是再寫一份規格，而是實際跑模型→工具→模型，在每一步記：

- 哪個檔一旦 rename 就是事實；
- Ctrl-C、hard kill、斷電各留下什麼；
- `.runi` 何時擋住重啟，人工要處理什麼；
- CLI 的 stdout、streaming、exit、截斷與 tool-call schema 實際長什麼；
- 哪一段 temp＋rename／掃檔／補投真的重複到值得進 core。

研究人員的一句話收住了這輪：

> **先跑出可殺死、可觀察的 loop；除 deliver 外，讓重複痛點再申請進 core。**
