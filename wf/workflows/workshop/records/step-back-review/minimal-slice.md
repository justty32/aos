# 四、從第一原理重來，會長出同一套東西嗎

← [三場研討會的回頭審視](README.md)

> 本檔是第 **四** 題：四位各自從第一原理重推，長出來的最小版本與 golden slice 的實際順序。

**四位獨立地從頭推，都長出幾乎同一個最小版本，而且沒有長回 lane／proc-table／Effect。**只
保留使用者指定的三個前提：「資料夾是世界／一回合是一批指令／`rename` 是唯一的原子操作」，
再加已拍板的本地 kernel，得到的是：

```text
<world>/.aos/{kernel.json, inst.json, inst.tempd, .runi}
aos exec <world>
aos deliver <world> -
driver 腳本 + 真 LLM CLI + 一個受限工具
```

最小 golden slice 的實際順序是：

1. driver 腳本組 prompt，呼叫一支**已指名**的真 LLM CLI。
2. response 先寫 temp，再 rename 成完整結果。
3. translator 只接受具名工具，把它映射到預先固定的 argv；未知工具停住。
4. `aos deliver` 把工具 instruction 原子投進 queue；`aos exec` 推一回合。
5. 工具結果同樣 temp＋rename，再 Deliver 回 driver／模型。
6. 模型回 final 時不投遞下一批，loop 自然停止。

crash 時沿用 `.runi` 停住，不自動假裝恢復遠端效果。腳本可以寫 attempt／response 日誌，但先不
宣告那套檔名是 core ABI。逐點 kill 這條三回合鏈，記錄哪一步重複、哪一步難寫、哪一步無法判定，
才決定下一個 core 原語。

四位版本的差異只在命令叫 `aos deliver` 還是 `aos core deliver --to BASE -`，以及 state 檔的
名字；**沒有一位從第一原理重新推導出公開 Publish、通用 Effect、UUID、promotion 或 process
manager 是首版必需。**
