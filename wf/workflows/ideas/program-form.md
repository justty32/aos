# 在 aos 上寫程式的形式：檔案是 atom，資料夾是 list

← [ideas](README.md)｜上游 [turing-to-os](turing-to-os.md)｜[WORKFLOWS](../../WORKFLOWS.md)

**使用者原話（2026-09-01）**：「關於在這個 aos 上寫程式這塊，其實就是類似 lisp，只是 lisp
的原語是 atom。但 aos 的程式載體就是資料夾，原語就是檔案。所以囉，要寫 aos 的程式，那個
抽象其實只有 lisp 有能力承載。」

這條是 [turing-to-os §四](turing-to-os.md)（檔案系統同時是記憶體與程式的載體）往下一層的
展開，也是缺口 `G20`（方便人寫程式）的實質內容。

## 對應關係

| lisp | aos |
|------|-----|
| **atom**——原語，不可再分 | **檔案** |
| **list**——複合、可巢狀 | **資料夾** |
| S-expression 是程式的載體 | 資料夾是程式的載體 |

巢狀那一格是對得最準的：資料夾可以裝資料夾，就像 list 可以裝 list。

## 這一步把同像性搬了家

workshop 那場（[lisp-in-aos](../workshop/records/lisp-in-aos.md) 第 10 點）否定過「JSON
陣列＝S-expression」，結論是**同像性來自 macro 與 eval 讀同一種 form，不是來自長得像括號**。

本條主張的不是那件事。它說 **S-expression 是資料夾樹本身**，JSON 只是檔案的內容格式之一
——同像性的落點從 JSON **搬到了檔案系統**。

所以缺口 `G24` 是**被改寫，不是被解決**：要問的不再是「JSON 是不是同像」，而是
**「資料夾樹是不是同像」**——macro 與 eval 是不是讀同一棵樹。這個問題還沒問過。

## 「只有 lisp 有能力承載」是排他性主張

這句話不是偏好表述，是**排他**：其他語言的抽象承載不了這個東西。它的可證偽版本是——
**說得出別的語言為什麼不行**（是缺了同像性？缺了 macro？還是缺了「程式即資料」這個立場）。
目前沒展開，記在這裡當作一條待補的論證，不是已成立的前提。

## 邊緣狀況（我挖的，不是裁決，等使用者判）

1. **list 有序，資料夾無序。** cons 的順序是本體的一部分；資料夾裡的檔案**沒有順序**，靠
   檔名排序是慣例不是語意。求值順序要靠什麼決定？這是這組對應裡最直接的一道裂縫。
2. **檔案比較像 binding，不像 atom。** atom 只有值；檔案有**名字＋內容**兩樣。若檔名是
   symbol、內容是 value，那一個檔案其實是一個 binding（或一個 cons），不是 atom。
   「原語就是檔案」可能需要再說一次是指哪一半。
3. **哪一棵樹正在被求值。** eval 要分得出「這份是碼」與「這份正在跑」——就是缺口 `G07`。
   同像性讓兩者同型，反而讓這件事更難，不是更容易。
4. **quote 從哪裡來。** 已知現有機制**不能**直接當 lisp 的 quote 用
   （[pre-agent-loop-core R1](../workshop/records/pre-agent-loop-core/r1.md)），要走 lisp
   就得另有機制。資料夾模型下，quote 是什麼形狀？

## 相關

- [turing-to-os](turing-to-os.md)——上游：三要件、agent loop ＝ CPU、檔案系統即記憶體
- [cpu-to-os-gaps.json](cpu-to-os-gaps.json)——`G20`（方便人寫程式）、`G24`（同像性）、`G07`（程式與行程的分界）、`G14`（程式的可命名性）
- [call-format](call-format.md)——CLI 呼叫＝Lisp 呼叫的序列化（argv 是 list、旗標是 keyword）
- [workshop／lisp-in-aos](../workshop/records/lisp-in-aos.md)——同像性在 JSON 上不是免費的
