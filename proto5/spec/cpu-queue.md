# CPU 共用佇列格式（第 1 版）

← [proto5 README](../README.md)｜程式：[aos-cpu](aos-cpu.md)｜payload：[llm-cpu](llm-cpu.md)、[tool-cpu](tool-cpu.md)

一個 CPU 是一個資料夾，接收已解好的請求，結果寫到交件者指定的檔案。
共用協議只管交件、認領、收屍與結果，不解 payload、不讀 agent。

## 1. 資料夾與身分

```text
cpu/
  info.json              {"_metainfo":{"_type":"<由 CPU 指定>","_version":1}}
  requests/<name>.json    排隊
  running/<name>.json     已認領
  done/<name>.json        已處理的原始請求（成功與失敗都保留）
  bad/<name>.json         讀不出合法共用欄位的請求
  .queue.lock            檔案轉移短鎖
```

只有 info 必填，交件／tick 建立缺少的四個目錄。只掃第一層 `.json` 檔名，忽略 `.tmp`。
_type 由 CPU 種類指定；_version 只認整數 1，布林不算。
info 已知欄位依 [agent](agent.md) 規則解指示詞，中心是 CPU 家；頂層、metainfo、
type/version 都可以解 `$ref`／`$env`，不認 `$opt`，未知欄位忽略。

錯誤沿用 `AgentError`：缺 info／metainfo／type 或 type 不符為 `NotAnAgent`；metainfo 非物件或
缺 version 為 `MetainfoInvalid`；版本不合為 `UnsupportedVersion`；讀檔、JSON、頂層形狀分別為
`ReadFailed`、`JsonSyntax`、`NotAnObject`。指示詞錯誤沿用原代號。

## 2. 請求與結果

每份請求是 JSON 物件，共用欄位 result 必填：無 NUL、能以作業系統檔名編碼表示的絕對路徑字串。
送件時驗父目錄已存在，否則拒收 `ReadFailed`；送件後父目錄仍可能被移走。
其他欄位由 CPU 自己定義。請求與結果不解指示詞。

壞 JSON／UTF-8、非物件、非法 result 路徑無法安全回覆，從 requests 或 running 搬到
bad/<name>.json，stderr 一行，繼續找下一份；當次 tick 最後回 1。
**只要共用欄位合法，壞 payload 一律認領後回 `BadPayload`，再搬 done**，不留在排頭擋住整顆 CPU。

成功共同欄位為 `ok:true`，額外欄位依 CPU。失敗固定三格：

```json
{"ok":false,"code":"BadPayload","msg":"請求內容不合格式"}
```

code 是代號字串、msg 是白話字串。共用收屍用 `Reaped`；各 CPU 另用 `UnknownModel`、
`Timeout`、`EngineFailed`、`BadPayload` 等代號，細分見各自格式。
結果沒有 request name／id；交件者不得把多個未完成工作送到同一結果路徑。

name 是含 `.json` 的單一檔名，不接受路徑。requests／running／done 三處任一已有同名就拒收
`ReadFailed`，不覆蓋。bad 是隔離區，不參加這三處的同名保護。
請求與結果以同目錄唯一 `.tmp` 寫完整 JSON，再 replace，沒有 fsync／斷電持久化保證。

## 3. 鎖、收屍與完成

交件、認領、收屍、完成都用 `.queue.lock` 的 POSIX flock 短鎖；執行 payload 時不持鎖。
rename 本身會覆蓋目標，同名檢查與搬移要在同一把鎖裡。
多個 CPU 進程可同時處理不同請求；不用這把鎖的外部寫入者不在競態保證內。

認領時刷新 mtime，再從 requests 搬到 running，排隊時間不算執行時間。
running 的 mtime 年齡嚴格大於執行期限加 30 秒就收屍；不殺原程序。
已有結果便保留，沒有才寫 `ok:false, code:Reaped`，再搬原請求到 done。
完成時核對 running 的 device/inode 與 done 同名；已被收屍或換檔的遲到回覆直接丟棄。

正常完成或收屍若結果發布遇到 OSError，stderr 一行、請求仍搬 done，當次 tick 回 1。
不留 running 重複失敗，也不讓這份單阻塞後面的單；但交件者收不到結果，可能一直等。
execute 的非預期例外仍留 running，待之後收屍。

## 4. 故障界線

結果發布與搬 done 不是交易。崩在兩步之間，收屍保留已存在結果，包含可能屬於新請求的結果，
不能覆蓋它。若 agent 已收走結果，舊 running 之後仍可能回填失敗，被當成新一輪結果；
沒有關聯欄位就無法分辨。正常完成發布也假定同一結果路徑只有一份工作；不同請求互撞不提供
exactly-once 或歸屬保證。完整情境與後續評估見 [findings](../../proto5.1/notes/findings.md)。
