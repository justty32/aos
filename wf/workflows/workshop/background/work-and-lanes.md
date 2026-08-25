# 名詞表：工作、lane 與升格
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### process（行程／核心行程／子行程）

**白話**：研討會裡的「行程」不一定是一個 PID；它想說的是「這件工作有自己的地方、可以分開推進」。
**嚴格**：記錄中未定案的產品層實體；候選定義是有身分、私有狀態、queue、owner 與生命週期的可排程工作，不等同 `fork()` 後的 OS 子行程。
**在 aos 裡具體是什麼**：這個抽象目前不存在，是提案；現存的只有 `aos exec` 自身與它 `fork`/`exec` 的 POSIX 子行程，不要把兩者完全對應。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) 想把長期工作與父子拓樸說清楚；[回頭審視](../records/step-back-review.md) 後又把這整組通用行程機制延後。

### lane（巷道／私有執行線）

**白話**：一件工作有自己的待辦堆、做到哪裡和故障現場，可以不跟父工作綁在同一回合內。
**嚴格**：有獨立 queue、claim/鎖、cursor、私有狀態與恢復邊界的可排程實體；「長」本身不構成 lane，需要獨立等待、反覆收件或恢復才構成。
**在 aos 裡具體是什麼**：目前不存在，是提案；`.aos/lanes/<id>/`、子 world 自帶 `.aos/` 等都是研討候選，未進 [aos-folder](../../../../docs/aos-folder.md)。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) 的開發者用 world/lane/process 把原先混在一起的概念拆開；[回頭審視](../records/step-back-review.md) 認為目前沒有第二個實例，所以暫緩。

### job（一次性工作；別名 task／work item）

**白話**：就是父工作拿到後做完、交結果的一件事，自己沒有另一條長期待辦隊伍。
**嚴格**：一次性、不可變的 request envelope，由父回合領取執行並產生 result/receipt；沒有私有 queue、kernel 或獨立恢復生命週期。
**在 aos 裡具體是什麼**：作為命名的 `jobs/<id>/` 目前不存在，是提案；現在最接近的現物是 `inst.json` 中的一筆 instruction，但兩者尚未被規格宣告為同物。
**為什麼會冒出這個詞**：使用者在[核心行程場](../records/core-process-and-subprocess.md) 要求把模糊的 `func` 拆成 job 與 lane，避免每件小事都背一套完整行程機制。

### promotion（升格；job → lane）

**白話**：一件原本打算當場做完的小事，做到一半發現得有自己的待辦堆和恢復點，就把它升成獨立工作。
**嚴格**：把 job 的輸入快照與身分原子物化成 lane，保留原 correlation ID，並在原 job 留下 `promoted_to` 或 join handle 的單向狀態轉換。
**在 aos 裡具體是什麼**：目前不存在，是提案；[回頭審視](../records/step-back-review.md) 明確把它退回「真有工作需要獨立 queue 與恢復時再開」。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) R2 想同時保留輕量 job 與耐久 lane，所以提出「需要跨回合等待時才升格」。

