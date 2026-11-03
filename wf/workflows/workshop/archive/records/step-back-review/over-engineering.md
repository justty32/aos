← [三場研討會的回頭審視](README.md)

本檔收第**一**、**三**、**五**題：哪些機制走得太前面、砍掉之後由誰承擔、什麼出現時再重開。

# 一、「多位獨立提出」會不會其實是共同偏見

**會，而且不只一條。** 四位都是系統／架構／OS／外掛契約背景，擅長先找 crash window、所有權、
提交與升級問題；「四位獨立提出」是訊號，不是需求已存在的證據。

## 共同偏見一：把「agent 多走幾回合」過早類比成 Linux 行程

從「普通 instruction 可以呼叫另一個 `aos exec`」一路實體化成 lane、root 行程、proc-table、capability、
receipt、promotion、join、可搬身分與跨 lane commit。這些機制回答「很多耐久行程同時存在時怎麼管」，
但目前沒有第二個 world、共享 writer 或活搬需求。

## 共同偏見二：把故障分析直接排成近期產品功能

[agent loop 的 R2](../agent-loop-architecture.md) 的 Publish → Deliver → Effect，反映的是重視 WAL、
斷電、多檔交易與外部副作用，不代表 T5 已證明需要公開 API。**Publish 與 Effect 收回**，回到「腳本
反覆痛再升 core」。**Deliver 保留**：現有三步交接裡投遞沒有函式，腳本現在就得重寫唯一 temp＋rename。

## 後果

篇幅花在未出現的第二世界、活搬、平行工具與 exactly-once；沒有先固定一支真 LLM CLI、跑完一次
模型→工具→模型，也沒有先決定模型輸出能不能碰檔案、網路與憑證。收回的是這些系統問題的**時間順位**，
不是說它們永遠不存在。

---

# 三、這東西還簡潔嗎：是哪一步開始長歪的

使用者反覆說的是：

> **複用、簡潔，是目標。**

> **CPU 做的事情非常簡單：取出下個指令，執行，然後繼續取指令。**

**exec 本身仍可保持簡單**：彙整、claim、套本地 kernel、執行、release。長歪的是周邊把還沒發生的
workflow 問題提早做成耐久 OS ABI。

| 還算簡單、可保留 | 開始長歪的延伸 |
|---|---|
| 單一 world 的 `.aos`、本地單層 kernel、`inst.json`／tempd／`.runi` | kernel 分層繼承、父政策與多層版本現場 |
| 普通 instruction 呼叫另一個命令 | 把呼叫關係固定成 lane／root／proc-table／capability／promotion 的通用行程樹（**主要長歪點**） |
| 唯一 temp＋rename 的原子投遞 | 公開檔／目錄 Publish、跨 filesystem 與斷電 durability 契約（Publish 先降為 Deliver 內部 helper） |
| `.runi` 留住本地未完成批次 | 通用 Effect／recover 想替所有 provider 與副作用做恢復（延後；unknown 暫歸 adapter／人） |
| 串行 driver 決定要不要投下一批 | 平行 join、barrier、跨 lane commit 與 exactly-once receipt（目前沒有平行 workload） |

已收下的 `kernel.json` 不否定，收窄回**每個 world 自己的序言／尾聲**。否定的是：agent loop 一次都
沒跑之前，就讓 kernel 繼承、行程親緣、可搬身分與外部效果變成標準的一部分。

---

# 五、有沒有哪個問題其實不存在

尺度：**一個人的專案、`core/inst` 剛落地、agent loop 還沒跑過一次。**

| 目前先當作不存在／不承諾 | 現在有什麼證據 | 砍掉後由誰負責 | 什麼出現時再重開 |
|---|---|---|---|
| 同一 OS 行程推多世界、World multiplex | 還沒有第二個 world | 一次只跑一個 `aos exec <folder>` | 啟動成本或協調需求真的要求同一行程同時持有兩個 world |
| lane／proc-table／root capability／跨 lane commit | 沒有多 lane、共享 writer 或惡意子行程 | driver 依序呼叫；同一使用者權限下先當守約工具 | 第二個長壽 world、共享寫入或必須強制隔離的執行者出現 |
| 活搬、UUID、`slot@generation`、路徑與身分分離 | 沒有活搬，也沒有 stale receipt 誤投 | 用路徑定位；移動視為停機後另開，不承諾續接 | 真正要帶著未完成 join／receipt 搬，或同名重建收錯結果 |
| job→lane promotion、A／B scheduler 可替換 | 連一條 agent loop 都沒跑過 | 首版不分 job／lane；driver 只投下一批 | 某個工作真的需要跨回合等待、獨立 queue 與恢復 |
| 平行工具 join／barrier | 首版可串行，沒有平行工具 workload | driver 一次只叫一個工具 | 串行成為實測瓶頸，或模型一次 tool calls 必須並行 |
| 分層 kernel／父政策 | 單機單人，沒有大量子世界要同步政策 | 每個 world 一份本地 kernel，由人／腳本更新 | 多份 kernel 實際漂移，且重複升級已成痛點 |
| 通用 Effect 與 exactly-once 外呼 | remote unknown 是真問題，但尚無一支 CLI 的實際故障資料 | provider adapter 記 attempt；unknown 停住交給人 | 同一套 run／resolve 在兩個 adapter 以上重複，且狀態能脫離 provider 語意 |
| Deliver 的跨回合 key 去重 | aggregate 會刪檔，現在沒有 ledger 可支持承諾 | Deliver 只保原子發布；caller 自己避免重送 | 真正發生重送，並能定義 ledger 壽命與清理政策 |

「不存在」是**現在不把預測寫成 ABI**，不是永遠不做。共同門檻：先有第二個實例、一次實際事故，
或至少兩支腳本重複同一段難寫機制，再讓它申請進 core。
