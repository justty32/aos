# 轉交提案（未拍板，不自行改規格／roadmap）

R2 把候選功能收成三項，但**還沒有替使用者把它們排進 roadmap，也沒有定下公開 API**。等拍板
的是：

1. **是否按 Publish → Deliver → Effect 的順序成為前三項基礎 `aos core` 功能。**四位在「只能
   做三樣」時全部選中這三項；Publish 統一完整發布，Deliver 補現存投遞缺口，Effect＋resolve
   處理昂貴外呼的 done／unknown。要由使用者決定它們是在 T5 腳本之前先做，還是讓 T5 先用
   腳本驗證簽名後再排進 roadmap。

2. **Publish 是否公開，以及公開到哪一層。**需拍板只作 Deliver／Effect 的內部底座，還是提供
   `aos core publish`／`publish_at` 給 cursor、event、tool result 共用；同時決定接收 temp/source
   還是 payload、檔案與目錄是否都支援、是否限制同 filesystem，以及 `--durable` 對 fsync 與
   斷電的承諾。

3. **Deliver 的 key 與 receipt 契約。**需拍板 key 是否必填、由 caller 還是 core 產生、唯一範圍
   是 BASE／world／跨 world，以及 Already／Conflict 的判定；receipt 至少要讓 crash 後能辨認
   同一次投遞是否已發布。CLI namespace、payload 上限與 target 傳法也仍待定。

4. **Effect 的通用邊界與 resolve 動作。**需拍板它只包 LLM，還是包所有有副作用的 command；
   unknown 是否一律停住；人工動作收成 retry、lost／abandon、adopt／import 哪幾個狀態。provider
   查詢與 idempotency 仍由 adapter 處理，不放進 core。

5. **平行 join／turn reconcile 先留腳本，還是成為下一個 core 候選。**工程師只提出
   `effect_join(keys)`，開發者只指出 event／cursor／receipt／next delivery 的 barrier；兩人都還
   沒證明它們能完全脫離 agent 語意。可由使用者選擇現在排規格，或照 T5 原意先讓腳本硬做，等
   重複形狀出現再收。

6. **T5 的 agent 專用部分繼續留在腳本。**四位都排除 prompt、對話裁切、provider／tool parser、
   final、stop／budget；這些不是待加入 core 的漏項。前一場的 World、kernel、A／B／C、路徑或
   UUID 也仍未拍板，本場三項原語不替[前一場紀錄](../four-open-choices-tradeoffs.md)作決定。
