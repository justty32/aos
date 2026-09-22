# aos_cpu：共用佇列程式規範

← [proto5.1 README](../README.md)｜格式：[cpu-queue](cpu-queue.md)｜實作：[aos_cpu.py](../lib/aos_cpu.py)

共用層不建立背景 worker，payload 由各 CPU 的 execute 處理。

## API

```python
load(dir, cpu_type, env=None)
queue_lock(dir)
submit(dir, name, request)
tick(dir, execute, *, timeout_ms=None, reap_error=None)
```

load 讀驗 info，回 dir 絕對路徑與 metainfo。submit 只驗共用欄位與 result 父目錄，
CPU 身分由呼叫者先 load；成功回發布路徑，同名拒收 AgentError `ReadFailed`。
queue_lock 是交件／認領／完成共用的短鎖，進入時建立缺少的佇列目錄。

execute 接請求 dict、回結果 dict，在認領後自行把壞 payload 轉成 `BadPayload` 結果。
timeout_ms 是從請求取得毫秒期限的函式，沒給用 120000；reap_error 可指定收屍結果的 msg，
code 一律 Reaped。tool CPU 以它提供固定「結果不明」文字。

## 一次 tick

1. 在鎖內掃全部 running。共用欄位讀驗失敗就搬 bad、記一行 stderr，繼續下一份；
   合法請求依期限收屍，done 已有同名跳過。
2. requests 按檔名排序，跳過 running／done 同名。壞共用欄位同樣搬 bad、繼續找；
   第一份可用請求刷新 mtime，再 rename 到 running，記住 device/inode。
3. 解鎖執行 execute，最多一份。
4. 再拿鎖核對 running 的身分與 done 同名。已被收屍或換檔就丟棄回覆；
   否則原子寫結果，再搬 done。寫結果的 OSError 印 stderr，仍搬 done。

隔離與結果發布失敗的診斷前綴是 `aos-cpu:`，每份失敗只印一行。
本次隔離壞單或結果發布失敗，最後回 1，即使同格也做完另一份單。
沒有上述錯誤時，有執行或收屍回 0，完全沒事回 101。家／佇列 I/O 等無法繼續的錯誤
丟 AgentError；execute 非預期例外往外傳、請求留 running。
