# CPU 共用佇列規範（第 1 版）

← [proto5.1 README](../README.md)｜payload：[llm-cpu](llm-cpu.md)、[tool-cpu](tool-cpu.md)

一個 CPU 是一個資料夾，接收已解好的請求，結果寫到交件者指定的檔案。共用層只有
`lib/aos_cpu.py`，不解析 payload、不讀 agent、不建立背景 worker。

## 1. 資料夾與身分

```text
cpu/
  info.json              {"_metainfo":{"_type":"<由 CPU 指定>","_version":1}}
  requests/<name>.json    排隊
  running/<name>.json     已認領
  done/<name>.json        完成的原始請求（成功與失敗都保留）
  .queue.lock            檔案轉移短鎖
```

只有 info 必填，交件／tick 建立缺少的三個目錄。只掃第一層 `.json` 檔名，忽略 `.tmp`。
`load(dir, cpu_type, env=None)` 讀驗 info，回 `dir` 絕對路徑與 `metainfo`。`_type` 由呼叫者指定；
`_version` 只認整數 1，布林不算。info 已知欄位依 [agent](agent.md) 規則解指示詞，中心是 CPU 家；
頂層、metainfo、type/version 都可以解 `$ref`／`$env`，不認 `$opt`，未知欄位忽略。

錯誤沿用 `AgentError`：缺 info／metainfo／type 或 type 不符為 `NotAnAgent`；metainfo 非物件或
缺 version 為 `MetainfoInvalid`；版本不合為 `UnsupportedVersion`；讀檔、JSON、頂層形狀分別為
`ReadFailed`、`JsonSyntax`、`NotAnObject`。指示詞錯誤沿用原代號。

## 2. 請求與結果

每份請求是 JSON 物件，共用欄位 `result` 必填：無 NUL 的絕對路徑字串，父目錄須已存在；
其他欄位由 CPU 自己定義。請求與結果不解指示詞。壞 JSON／UTF-8、非物件、非法 result 路徑
退讀驗錯誤並保留原檔，不猜結果目的地；合法共用欄位下的壞 payload 由各 CPU 規範決定。

結果共同欄位為 `ok` 布林；失敗為 `{"ok":false,"error":"原因"}`，成功額外欄位依各 CPU。
**結果沒有 request name／id**；交件者不得把多個未完成工作送到同一結果路徑。

`submit(dir, name, request)` 的 name 是**含 `.json` 的單一檔名**，不接受路徑。
三處 requests／running／done 任一已有同名就拒收 `ReadFailed`，不覆蓋；成功回發布路徑。
提交只驗共用欄位，CPU 身分由呼叫者先 `load` 驗證。以同目錄唯一 `.tmp` 寫完整 JSON，
再 `replace` 到 requests；結果也使用相同原子寫法，沒有 fsync／斷電持久化保證。

## 3. 鎖、認領與收屍

`queue_lock(dir)` 用 `.queue.lock` 的 POSIX `flock` 保護交件、收屍、認領、完成；
POSIX rename 本身會覆蓋目標，故檢查同名與搬移必須同一把鎖。執行工作時不持鎖，
可以讓多個 CPU 進程同時處理不同請求；不使用同一把鎖的外部寫入者不在競態保證內。

`tick(dir, execute, *, validate=None, timeout_ms=None)`：呼叫者先驗 CPU info，execute 接請求 dict、
回結果 dict；可選 validate 在認領前讀驗 payload，timeout_ms 是取得毫秒期限的函式，沒給預設
120000。流程：

1. 在鎖內掃全部 running；mtime 年齡**嚴格大於**期限／1000 + 30 秒即收屍。
   done 已有同名跳過。result 位置已被占用就保留；否則寫 ok:false，再搬原請求到 done。
2. requests 按檔名排序，跳過 running／done 同名，找第一份可認領的。先讀驗、刷新 mtime，
   再 rename 到 running；排隊時間不算執行時間。
3. 解鎖，`execute(request)`。
4. 再拿鎖，核對 running 的 device/inode 身分與 done 同名；已被收屍或換檔就丟棄遲到回覆。
   否則原子寫結果，再搬請求到 done。

有執行或收屍回 0，完全沒事回 101，讀驗／佇列與結果 I/O 失敗丟 `AgentError`。
結果寫失敗保留 running；execute 非預期例外也保留 running 供後續收屍。收屍不殺別的進程。

## 4. 故障界線

結果發布與搬 done 不是交易。崩在兩步之間，收屍保留已存在結果，包含可能屬於新請求的結果，
不能覆蓋它。若 agent 已收走結果，舊 running 之後仍可能回填失敗，被當成新一輪結果；
沒有關聯欄位就無法分辨。正常完成發布也假定同一結果路徑只有一份工作；不同請求互撞不提供
exactly-once 或歸屬保證。完整情境與只評估的後續方案見 [findings](../notes/findings.md)。
