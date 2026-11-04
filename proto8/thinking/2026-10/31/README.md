# proto8 討論紀錄：2026-10-31

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-31 aos-var（已收回）→ parts 能否組出來（待議）](aos-var/README.md) | 使用者 10-31 傍晚先提「現在的 aos parts 感覺不倫不類。是否可以有個 aos-var，也就是類似變數定義與取用的方式」，隨即收回（「其實 $ref,env 本身就有變數定義與取用的功能，硬要再一個 aos var 其實不是很好」）；定：不疊新機制；**待議改為 parts 組合化**——parts 能否用 aos-exec＋`$ref`／`$env`＋現成東西組出來（存＝JSON map 或同名 symlink、查＝`$ref` 或直接 aos-exec、env＝`.env`、改＝aos-json／ln；多出的只剩集中表、fallback 膠水、驗證與錯誤碼），待對 aos-exec 契約核對；會動到 parts 的 C-74 定位（條文不改），收斂時交 fable；＋round 重切草圖（待議） |
| [2026-10-31 parts 組合化與 round 重切：收斂（fable）](parts-round/README.md) | fable 照原則收斂兩個待議題（可翻案、程式與條文沒動；對 C++ aos-exec 實跑 10 案核對契約）：**題 A** parts 現在做的「名字→路徑＋每槽 env＋`$env`／`$ref`」aos-exec 本來就會（C-72／N-61 JSON 物件當資料夾、`.env` key 放指示詞、字串轉向、`檔#/指標`），只有「註冊檔→固定名字」查找順序與「沒掛」判定是 parts 本體→格式退成 aos-exec 格式的約定、`aos-parts` 縮成 `which`／`run` 薄殼、env 改預設不蓋（N-58）；**題 B** 照四項判準重判五格三弱一中（一格一叫被 ask_round、aos-listen、P-20 續跑、38 案測試吃著）、queue 格是外部介面、兩個佐證一半成立一不足→不重切，吸收 `--on-empty` 改 argv；**匯流** 草圖的因果不成立但 parts 退成約定獨立成立；**衝突三條**（C-74 10-31 加註的層級、C-51 加註 vs 決定 16 的 fallback、重切 vs 10-30 薄殼決定）與**方向題兩題**（parts.json 要不要併進單一 agent.json、日後重切的門檻）等使用者；實作計畫 A 題四步、B 題零步；**11-01 使用者已裁**：parts 改列 agent 慣例層約定、以刪掉 aos-parts 為目標，註冊檔與固定名字共存，round 不重切（使用者要深思），parts.json 不併，門檻只當參考、比技術棧優缺點；A 題 11-01 已做（aos-parts 刪了、沒留殼，`--on-empty` 改 argv） |
