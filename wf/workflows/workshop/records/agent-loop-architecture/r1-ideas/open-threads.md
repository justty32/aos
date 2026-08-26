# R1：還沒收攏的

> 還在生長的想法、大家問出來的問題、明顯的坑。

## 還在生長的想法

**CLI 名字與函式簽名尚未對齊。**`aos core deliver`、`aos deliver WORLD --to PATH`、
`deliver_instruction(path, json, opts)` 與 `deliver_at(rootfd, target, json, opt, receipt)` 表達的是同一
原語，但 world 從 cwd、路徑還是 root fd 傳入，正好受前一場 World 選擇影響。`key` 是否必填、
receipt 要含哪些欄位，也仍未成形。

**`publish` 要不要公開尚未成形。**工程師與架構師希望 cursor／整個 event directory 也能共用
原子發布；研究人員與開發者只要求 effect／deliver 內部正確發布。若公開，需說清它發布的是一個
檔、一個已寫好的 temp directory，還是含多檔的 transaction；若不公開，腳本更新 cursor 仍會
重寫一次同類協定。

**capture／invoke 屬於 core 還是 provider adapter，工程師明確標記沒把握。**core 可以通用地記
command、stdout、stderr、exit 與 unknown；但 request ID 查詢、provider idempotency key、回收
既有 response，必然依賴各家 CLI。邊界可能是 core 管效果日誌，adapter 管 provider 對帳。

**effect 是否包所有有副作用的 tool，還沒回答。**要接工具的開發者直接問這一題；若只包 LLM，
付費 API、寄信、部署等工具仍會落入同一個「做了但沒記下」空窗。若全部包，effect 就會成為比
agent 更底層、也更需要穩定的 core 契約。

**parallel tools 的 join 時機未定。**研究人員不確定 kernel 尾聲是否要等所有平行 tool；這會
決定 cursor／event commit 是每個結果各自推進，還是 barrier 後一次發布。

**耐久的承諾等級未定。**四位都提到檔案與目錄 fsync，但工程師與研究人員問的是要不要承諾
斷電後仍在；要接工具的開發者不確定 POSIX 目錄 fsync 是保證還是盡力。`--durable` 若存在，
規格必須把「只保證 rename 可見性」與「承諾 power-loss durability」分開。

## 大家問出來的問題

| 問題 | 誰問的 | 它卡住什麼 |
|---|---|---|
| hard kill 也要能自動恢復嗎，還是只保優雅 Ctrl-C？ | 資深工程師 | 決定 effect wrapper 是否要額外 supervisor／子行程協定；無論如何，遠端已收而本機未記仍只能是 unknown |
| unknown 預設停住，還是自動重付費？ | 資深架構師；其餘三位也各自要求 unknown 不自動重跑 | 決定最危險的預設行為，以及是否必須提供人工 recover |
| LLM CLI／provider 是否一定有 idempotency key 或 request ID 查詢？ | **四位都問到或標記不確定** | 沒有時不能自動把 unknown 恢復成 done，只能交給人 retry／adopt |
| `--durable` 是否承諾斷電後仍存在？目錄 fsync 是保證還是盡力？ | 工程師、研究人員、開發者 | 決定 deliver／publish 的跨平台契約重量 |
| capture／invoke 應在 core，還是 provider adapter？ | 工程師 | 決定 core API 是只記通用外部效果，還是也理解供應商對帳 |
| 有副作用的 tool 是否也必須走 effect？ | 要接工具的開發者 | 決定 unknown／冪等保護只涵蓋模型費用，還是涵蓋所有不可隨便重做的動作 |
| kernel 尾聲是否等待 parallel tools 全部 join？ | 研究人員 | 決定 event／cursor 的提交粒度與下一回合何時可見 |

## 明顯的坑

- **直接用 shell 把 JSON 寫進 `inst.tempd`，把投遞繼續留成口頭約定**。**四位獨立地都把這列為
  第一個該收進 core 的原語**：短寫、撞名、半寫、重送與耐久選項不該每支腳本各做一次。

- **先呼叫 LLM，成功後才開始記 call。**若付費後、落盤前 crash，本機連「曾經嘗試過」都不知道；
  四位都要求先發布 request／key，再啟動外呼。

- **把 `unknown` 自動當失敗重跑**。**四位獨立地都警告**：這可能重複付費，也可能把有副作用
  的工具做兩次。只有 provider 冪等或可查回結果時才有安全自動路徑。

- **把 rename 說成 exactly-once 或斷電耐久。**rename 只保本機發布時不露半份；遠端效果是否
  發生是另一個故障域，檔案／目錄是否 fsync 又是另一層承諾。

- **cursor 先前進，response／event 後提交。**四位版面雖不同，都要求 cursor 只指 commit；
  反過來會讓重啟後跳過一個其實沒有完整結果的回合。

- **core 開始理解 prompt、tool call、final 或 agent 身分**。**四位獨立地都把 core 邊界壓在
  deliver、publish、effect 與恢復狀態**；agent 語意留給 driver／adapter，否則 T5 還沒用腳本
  驗證重複點，C++ 介面就先定死。

- **把無效輸入發布成正常 instruction，再等 aggregate 收拾。**四位都要求 deliver 在 rename 前
  拒絕；`.bad` 是隔離繞過 API 的壞檔，不是正常錯誤處理路徑。

- **把前一場未拍板的 A／B、World、kernel 或 UUID 偷寫進 agent ABI。**前三位保留兩種 queue
  位置，開發者採子世界版本；四位都讓 driver 只依賴可推一步的 world，沒有把自己的版本寫成
  使用者已拍板。
