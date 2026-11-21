hook 點宣告裡「引入別處的宣告」該怎麼寫的規劃稿（線 top-1121-hpinclude，只出稿、沒改程式）：建議用 `$include` 鍵、值寫成 `{"$env": "AOS_HOME", "$path": …}`，跟 procs-kernel 與 tools.json 已有的寫法同一個樣子。

← [2026-11-21](../README.md)｜使用者原話：[hook-points-格式-使用者審-1121](../hook-points-格式-使用者審-1121.md) 第 1～5 則｜前情：[aos-hook-plan-1120/01 宣告格式](../../20/aos-hook-plan-1120/01-宣告格式.md)

## 結論

- **為什麼看不出 aos-loop 哪來**：`{"provider": "aos-loop"}` 只是 `hook_point.py` 裡一張寫死的表的鍵，路徑從程式自己的位置算，宣告上沒有任何線索（[01](01-現況.md)）。
- **他後來定的前提**：`interfaces.json` 的 `hook_points` 收三種值——字串（指到宣告檔）、陣列（每項帶 id）、物件（id 當鍵）；別家的點靠宣告內容裡的引入進來，不再在 `interfaces.json` 並列。
- **建議（甲）**：宣告裡寫 `"$include": {"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_points.json"}`。`$include` 是 hook 宣告的讀者自己認的鍵（跟 tools.json 的 `$override` 同一類），值是路徑或解成路徑的指示詞；`aos-directive` 會原封不動留著它、只把裡面的 `$env` 解開，所以跟指示詞相容；不改條文、不動 C++；動態連結（loop 那份改了不用重新編譯）。另列四種：直接用 `$ref`（相對路徑一搬就斷）、讓 `$ref` 收 `$env` 路徑（改 aos-directive 與 N-45）、新增 `$include` 指示詞原地展開（最像 #include，要改 N-45）、C 角括號（跟 C-56／P-31 衝突）（[03](03-候選寫法.md)、[03b](03b-候選寫法-續.md)）。
- **查實各鍵**：`block`、`change`、`condition`、`entry_keys` 會改變 hook 的行為；`fields` 只有 `env`／`type` 會；`phase`、`when`、`if_blocked`、`if_failed`、`provider` 只用來驗與列給人看；`subject`、`key`、`fired_in` 驗完沒人用；gdb 沒讀宣告（[02](02-各鍵程式讀不讀.md)）。
- **一份檔一個 provider**：引入寫進內容後，一份檔本來就會混著自己的點與引入的點；「誰說的」改記檔的路徑，provider 退成想寫才寫的說明（[05](05-一份檔一個provider.md)）。
- **新格式樣本**：loop 與 agent-fsm 兩份照他第 2 則改寫，放在 [樣本/](樣本/)，新舊並排說明在 [04](04-新格式樣本.md)。
- **施工兩刀**（程式與宣告同一刀換，proto8 不留舊格式）；排在 hook 第 6 刀（gdb 讀宣告）、第 7 刀之前；compact 的兩個新點建議排在之後（[06](06-施工與先後.md)）。
- **要他定四題**：引入怎麼寫、有行為的鍵讀不讀、動態還是靜態連結、物件寫法哪些鍵不是點（[07](07-要他定的題.md)）。**衝突十條**，其中「宣告檔不解指示詞」是現況就違反 N-45（[08](08-衝突.md)）。

## 目錄

| 份 | 一句話 |
|---|---|
| [01-現況](01-現況.md) | `{"provider": "aos-loop"}` 怎麼解析、誰讀宣告、指示詞收不收、`aos-directive` 實測 |
| [02-各鍵程式讀不讀](02-各鍵程式讀不讀.md) | 每個鍵讀不讀、讀來做什麼（行號）、會不會改變行為 |
| [03-候選寫法](03-候選寫法.md) | 前提與共同規則；甲 `$include` 鍵、乙 現成 `$ref` |
| [03b-候選寫法-續](03b-候選寫法-續.md) | 丙 `$ref` 收 `$env` 路徑、丁 新指示詞、戊 角括號；對照表與建議 |
| [04-新格式樣本](04-新格式樣本.md) | 舊鍵對新鍵、物件寫法哪些鍵不是點、ann 的三種寫法 |
| [樣本/](樣本/) | `loop_points.json`、`loop_points-陣列寫法.json`、`agent-fsm-hook_points.json`（只是範例，沒有程式讀） |
| [05-一份檔一個provider](05-一份檔一個provider.md) | provider 今天擔的三件事、各候選下怎麼落 |
| [06-施工與先後](06-施工與先後.md) | 兩刀動哪些檔；跟 hook 第 6、7 刀與 compact 第 4 刀的先後 |
| [07-要他定的題](07-要他定的題.md) | 四題，選項與後果 |
| [08-衝突](08-衝突.md) | 跟他的話、跟條文的十條 |
