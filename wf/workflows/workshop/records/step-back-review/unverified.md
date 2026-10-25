← [三場研討會的回頭審視](README.md)

本檔收第**二**、**六**題：真 LLM CLI 沒實測過、failure 與 trust 的邊界沒定義，這兩件事比抽象設計更優先。

# 二、哪一條假設從頭到尾沒人檢查過

## `deliver --key` 的跨回合冪等其實沒有帳本

同 key 同內容＝Already、異內容＝Conflict 這個說法不成立：aggregate 成功後會刪掉投遞檔，沒有耐久
receipt ledger，下次重送 `K` 時沒有舊內容可比。

所以最小 Deliver 只承諾：驗證 payload、建立唯一同目錄 temp、write-all、rename 到 queue。key 可以
留作檔名／correlation 提示，但**沒有 ledger 不宣稱跨回合去重**。真遇到重送事故，要嘛另養 ledger，
要嘛把去重範圍明確縮到「檔案還留在 queue 時」。

## 沒人實測 LLM CLI 是否真像一個純函式

三場一直假設把 prompt 送進某支 CLI 就得到完整、穩定、可解析的 tool call；session、streaming、
schema、截斷、取消、exit code、Ctrl-C 後狀態都沒有用真 CLI 驗證。**首支 CLI 是哪一支**還沒定，
它跑在全信任實驗裡還是會碰真實資源也沒定。

這個假設驗證前，events／calls、Effect 狀態與恢復 API 都可能在替不存在的 I/O 形狀設計。T5 的第一個
產物是觀察紀錄：CLI 在每個成功、失敗與中斷點實際留下什麼。

## failure 與 trust 的範圍一直沒定義

Ctrl-C、hard kill、斷電是不是同一個承諾；T5 是全信任實驗，還是模型能碰真實檔案、網路與憑證。
沒有這兩條邊界，「durable」「可恢復」與 capability 都各自想像不同的故障／威脅模型。

---

# 六、有沒有漏掉比上面全部都重要的事

有兩塊，都排在抽象設計之前。

## 模型輸出的執行權與威脅模型

translator 若把模型輸出的任意 argv 直接交給 POSIX 執行，prompt injection 就取得使用者的檔案、網路、
憑證與命令權限。所有程式跑同一 UID 時，capability 只是約定，擋不住這件事。

首版最小邊界：**具名 tool allowlist → 固定 argv 映射**；未知工具停住，視威脅模型再加人工核准或
OS sandbox。使用者要先說 T5 是全信任玩具，還是會碰真實資料與憑證，才知道哪一層必要。

## 一條真的可執行、可殺死、可觀察的 golden slice

先跑真 CLI 並注入 crash：實際跑模型→工具→模型，在每一步記：

- 哪個檔一旦 rename 就是事實；
- Ctrl-C、hard kill、斷電各留下什麼；
- `.runi` 何時擋住重啟，人工要處理什麼；
- CLI 的 stdout、streaming、exit、截斷與 tool-call schema 實際長什麼；
- 哪一段 temp＋rename／掃檔／補投真的重複到值得進 core。

> **先跑出可殺死、可觀察的 loop；除 deliver 外，讓重複痛點再申請進 core。**
