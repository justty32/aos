# R1：還沒收攏的

> 還在生長的想法、大家問出來的問題、明顯的坑。

## 還在生長的想法

- **CLI 名字與函式簽名尚未對齊。**`aos core deliver`、`aos deliver WORLD --to PATH`、
  `deliver_instruction(path, json, opts)` 與 `deliver_at(rootfd, target, json, opt, receipt)` 是同一
  原語；world 從 cwd、路徑還是 root fd 傳入，受前一場 World 選擇影響。`key` 是否必填、receipt 要含
  哪些欄位，也仍未成形。
- **`publish` 要不要公開尚未成形。**若公開，要說清發布的是一個檔、一個已寫好的 temp directory，還是
  含多檔的 transaction；若不公開，腳本更新 cursor 仍會重寫一次同類協定。
- **capture／invoke 屬於 core 還是 provider adapter。**core 可以通用地記 command、stdout、stderr、exit
  與 unknown；request ID 查詢、provider idempotency key、回收既有 response 必然依賴各家 CLI。可能的
  邊界：core 管效果日誌，adapter 管 provider 對帳。
- **effect 是否包所有有副作用的 tool。**只包 LLM 的話，付費 API、寄信、部署等工具仍落入同一個
  「做了但沒記下」空窗；全部包的話，effect 就成為比 agent 更底層、也更需要穩定的 core 契約。
- **parallel tools 的 join 時機未定。**kernel 尾聲是否等所有平行 tool，決定 cursor／event commit 是
  每個結果各自推進，還是 barrier 後一次發布。
- **耐久的承諾等級未定。**要不要承諾斷電後仍在、POSIX 目錄 fsync 是保證還是盡力。`--durable` 若存在，
  規格必須把「只保證 rename 可見性」與「承諾 power-loss durability」分開。

## 大家問出來的問題

| 問題 | 它卡住什麼 |
|---|---|
| hard kill 也要能自動恢復嗎，還是只保優雅 Ctrl-C？ | 決定 effect wrapper 是否要額外 supervisor／子行程協定；無論如何，遠端已收而本機未記仍只能是 unknown |
| unknown 預設停住，還是自動重付費？ | 決定最危險的預設行為，以及是否必須提供人工 recover |
| LLM CLI／provider 是否一定有 idempotency key 或 request ID 查詢？ | 沒有時不能自動把 unknown 恢復成 done，只能交給人 retry／adopt |
| `--durable` 是否承諾斷電後仍存在？目錄 fsync 是保證還是盡力？ | 決定 deliver／publish 的跨平台契約重量 |
| capture／invoke 應在 core，還是 provider adapter？ | 決定 core API 是只記通用外部效果，還是也理解供應商對帳 |
| 有副作用的 tool 是否也必須走 effect？ | 決定 unknown／冪等保護只涵蓋模型費用，還是涵蓋所有不可隨便重做的動作 |
| kernel 尾聲是否等待 parallel tools 全部 join？ | 決定 event／cursor 的提交粒度與下一回合何時可見 |

## 明顯的坑

- **直接用 shell 把 JSON 寫進 `inst.tempd`，把投遞繼續留成口頭約定。**這是第一個該收進 core 的原語：
  短寫、撞名、半寫、重送與耐久選項不該每支腳本各做一次。
- **先呼叫 LLM，成功後才開始記 call。**付費後、落盤前 crash，本機連「曾經嘗試過」都不知道；要先發布
  request／key，再啟動外呼。
- **把 `unknown` 自動當失敗重跑。**可能重複付費，也可能把有副作用的工具做兩次；只有 provider 冪等或
  可查回結果時才有安全自動路徑。
- **把 rename 說成 exactly-once 或斷電耐久。**rename 只保本機發布時不露半份；遠端效果是否發生是另一個
  故障域，檔案／目錄是否 fsync 又是另一層承諾。
- **cursor 先前進，response／event 後提交。**cursor 只指 commit；反過來會讓重啟後跳過一個其實沒有
  完整結果的回合。
- **core 開始理解 prompt、tool call、final 或 agent 身分。**core 邊界壓在 deliver、publish、effect 與
  恢復狀態；agent 語意留給 driver／adapter，否則 T5 還沒用腳本驗證重複點，C++ 介面就先定死。
- **把無效輸入發布成正常 instruction，再等 aggregate 收拾。**deliver 在 rename 前拒絕；`.bad` 是隔離
  繞過 API 的壞檔，不是正常錯誤處理路徑。
- **把前一場未拍板的 A／B、World、kernel 或 UUID 偷寫進 agent ABI。**driver 只依賴可推一步的 world。
