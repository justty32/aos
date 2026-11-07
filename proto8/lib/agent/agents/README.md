# agents — 生、問、收自己的子 agent，保留公開宣告的子帳。

`ask` 等待結束時（含失敗）與 `rm` 移除前，同步子帳到工具小格的 `observed/<名>/`；`say` 不同步。

子 stack 取自已登記的 children 紀錄；帳只透過各層 `interfaces.json` 的 `aos-observed.file` 找，保留相對路徑及觀測宣告，讓孫抄本也能再被抄走。同步不到的部分少算，不影響工具原本結果。呼叫端把這次抄本位置記進 `tool.child`。

`new` 在套用 `files` 後寫入新定義的 `_metainfo.json#/lineage`，保留其他 metadata 鍵；沒有 metadata 檔就建立。`reason` 可選 `specialize`、`split`、`fix`、`manual`，預設 `manual`；`review` 是選填字串。`from` 與 `review` 原樣保存，不解析或改寫路徑；完全由 `files` 建立、沒有 `from` 時，`lineage.from` 為 `null`。複製來源已有的 lineage 會換成這次出生紀錄；`add` 不改定義。

```json
{"op":"new","name":"linker","path":"defs/linker","from":"defs/place_lead","reason":"split","review":"reviews/3/review.json"}
```
