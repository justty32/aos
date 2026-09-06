# 2026-09-06 整合試玩

## 結果

- 用 manager 模板開 boss，也用 coder 模板開一個獨立 coder。兩邊都能載入，沒有未知工具包警告。
- 第一次 boss 生出的 kid 只把 coder 寫在人格裡，沒有傳 `template`。spawn 又錯把模板工具包蓋成父的工具包，所以 kid 沒有 `fs`。
- 修好模板工具包優先權，也把提示寫清楚後重跑。kid 載到 `mailbox`、`fs`、`code`、`self`、`jobs`、`toolsmith`。
- kid 在自己的資料夾寫出 `fib.py`，實跑退出碼是 0。輸出是 1、1、2、3、5、8、13、21、34、55。
- kid 把結果寄回 boss。boss 讀信後把完整輸出回報給使用者。最後只註銷這次開的 boss 與 coder。

## 做的時候的坑

- `spawn(template="coder")` 沒明給 `packs` 時，舊實作仍會抄父的工具包。模板看似載入，實際能力卻被蓋掉。
- 模型不會只因使用者說「coder 小孩」就一定填 `template`。kids 的提示要明講這個對應。
- kid 有信箱包時應正常回話交給自動轉寄。這次模型反而用 `fs.write` 直接寫父信箱；鏈有走通，但多繞了路。

## 補完回話轉寄後再玩一次

- 子身分提示與回話轉寄原本綁在 `kids` 包。coder 模板沒有這包，所以把兩件事移到 agent 共用層。
- 重開 boss 與 coder 後再送同一句。kid 正常回答，回答先落自己的 outbox，再自動進父的 `inbox/kid-kid/`。
- 父讀完轉寄信後回使用者。父的 `inbox/kid/` 沒有模型手寫的捷徑信，完整六段鏈都走到了。
