# Janet 綁定發現

這份是把 aos 檔案協定從 Janet 1.41.2 接起來時的實測紀錄。它不是新條款；綁定能修的已做最小修正，必須改 spec、schema 或 Python 原型才能收掉的裂縫留在下面。

- **外部語言沒有「父地正在跑的那一格」**｜依據：S-07-09～S-07-13、S-07-54～S-07-57｜**卡在哪**：呼叫記錄必填父地、tick、series、step，但一支普通 Janet 行程沒有這四樣，結果落點也沒有可當原點的地｜**怎麼繞**：綁定在暫存目錄合成一塊 workspace，記錄固定填 `tick:0`、`series:"janet"`、`step:"call"`｜類別：spec 沒講｜擋路程度：擋路
- **純寫檔就能做的邊界其實很清楚**｜依據：S-07-09、S-07-14～S-07-20、S-07-33～S-07-44、S-08-12～S-08-22｜**卡在哪**：設定檔與版面、呼叫記錄、投遞物、結果與狀態三態、一筆 pending 登記全都是已定義的 JSON 與改名，外語言不需要 aos API｜**怎麼繞**：Janet 直接依 schema 寫檔，只把「推進與管行程」留給執行引擎｜類別：多餘的動作｜擋路程度：小
- **推一格、跑到閒著與管 daemon 非得 shell 出去**｜依據：S-06-01、S-06-16、S-07-02、S-07-27、S-08-06｜**卡在哪**：只把 JSON 放好不會讓一塊地走、也不會生成或收屍子行程；要在 Janet 重做就等於重寫 exec／run／daemon 引擎｜**怎麼繞**：`inst` 叫原型 `exec`，同步 `call` 叫 `run --until idle`，脫節呼叫的起停與查詢叫 `daemon`｜類別：多餘的動作｜擋路程度：擋路
- **同步外語言呼叫跟條款的「父每格帶子走一格」不是同一件事**｜依據：S-06-31、S-07-02｜**卡在哪**：Janet 呼叫方沒有父串與時鐘，無法停在 call 步上逐格帶子；寫檔也不能取代 exec｜**怎麼繞**：綁定直接阻塞等 `aos run <子> --until idle`，只保留最後的三態語意｜類別：spec 沒講｜擋路程度：擋路
- **Janet 的 flush 不是 spec 要的 fsync**｜依據：S-07-33、S-07-66、S-08-22｜**卡在哪**：Janet 1.41.2 只有 `file/flush`，沒有檔案 `fsync`、也沒有資料夾 `fsync`，所以改名雖然原子，斷電時仍不符合發布保證｜**怎麼繞**：現在用同目錄 `flush → rename`；要完整合規必須加 native helper，或這三種寫入也叫原型代做｜類別：多餘的動作｜擋路程度：擋路
- **脫節呼叫的登記表正本裝不下重建環境所需資料**｜依據：S-07-13、S-07-27、S-08-13、S-08-66、`registry.schema.json`｜**卡在哪**：daemon 之後才起子地，非得有 `result`、`parent`、`args` 才能重建 `AOS_RESULT`、`AOS_CALLER`、`AOS_ARG_*`；schema 只明訂 `ext.result`，沒定 args 放哪，原型卻只讀頂層 `result`、`args`｜**怎麼繞**：綁定同時寫 `ext.result`、`ext.args` 與原型要的頂層副本，故能跑但整份 registry 過不了 schema｜類別：spec 沒講｜擋路程度：擋路
- **原型的 daemon 登記表本身也不過正式 schema**｜依據：S-08-13、S-08-15、S-08-18、S-08-64～S-08-66、`registry.schema.json`｜**卡在哪**：原型會在頂層加 schema 禁止的 `daemon_pid_start`；Janet 用 `nil` 表示 JSON null 時又會直接少鍵，必填的 `pid_start`、`land_id`、`budget` 會不見｜**怎麼繞**：Janet 已改用 spork/json 的 `:null` 並補 `land_id`、`runner`；`daemon_pid_start` 要由 spec/schema 收編或由原型移除｜類別：spec 沒講｜擋路程度：擋路
- **`await` 的格數上限沒法直接搬到外語言**｜依據：S-07-22｜**卡在哪**：`max_ticks` 數的是父串經過幾格，普通 Janet 程式沒有格，只能數時間｜**怎麼繞**：`aos/await` 收 `max-ms`，每 100 ms 讀一次三態，逾時仍用 `await_timeout`｜類別：spec 沒講｜擋路程度：煩
- **結果落點要先有父資料夾才能安全驗 realpath**｜依據：S-07-55、S-07-57、S-07-70｜**卡在哪**：落點本來就尚未存在，父資料夾也不在時 `realpath` 無法展開 symlink；先 mkdir 再查又可能已在父地外留下東西｜**怎麼繞**：綁定要求父資料夾先存在，展開後確定還在父地才收下｜類別：多餘的動作｜擋路程度：煩
- **呼叫鏈在 async 交給 daemon 之後斷掉了**｜依據：S-07-47～S-07-49、S-07-27｜**卡在哪**：同步子行程可用 env 帶 `AOS_CALL_CHAIN`，但 async 是 daemon 後來另起的 run，登記表沒有呼叫鏈欄，原型也不重建它｜**怎麼繞**：目前沒繞，綁定只能靠使用者不造環；spec 必須定呼叫鏈存進 call 記錄還是 registry ext，原型也要讀｜類別：spec 沒講｜擋路程度：擋路
- **同一個 id 並行投遞時沒有「不覆蓋的 rename」**｜依據：S-07-33、S-07-39、S-07-44｜**卡在哪**：兩個投遞者可同時看到正式檔不在，然後 POSIX `rename` 的後一個靜默蓋掉前一個；收件匣數量上限也有同樣競爭，Janet 沒有 `renameat2(RENAME_NOREPLACE)`｜**怎麼繞**：單一 Janet 行程先查再改名只能擋一般重複；要封住多語言並行寫者，spec 必須加共用收件匣鎖、O_EXCL 預留檔，或明訂 no-replace rename｜類別：看不見的狀態｜擋路程度：擋路
