# 14 合規檢查表
← [入口](README.md)

02～13 每一條「必須」與「禁止」，這裡都對一個檢查。建議條不列。表太長，拆成三份：本份是入口加 02～06，[14b](14b-conformance.md) 是 07～09，[14c](14c-conformance.md) 是 10～13 與「測不到的必須」。

一共 742 條，685 條對到機器跑得動的檢查，57 條只能人工看。條款以 2026-09-05 15:03 的 spec 為準。

## 怎麼跑這些檢查

一個檢查一個資料夾，名字就是條款編號：

```
t/S-02-01/
  land/          ← 這個檢查用的一塊地的種子（原稿、設定、要用的假程式）
  run.sh         ← 建地 → 跑指令 → 看檔，三段
```

`run.sh` 一律三段：把 `land/` 複製到一個乾淨的暫時資料夾、對它跑 `aos …`、看檔或看退出碼。退 0 就算過。跑整批就是每個 `run.sh` 跑一遍、數有幾個非 0。

檢查只有三種寫法，表裡分別記成 **存在**、**回傳**、**schema**；真的三種都不是的記 **人工**，句子裡會說機器為什麼測不了。

**存在**（看檔在不在）——S-12-11：

```sh
aos init "$W" && test -f "$W/.aos/layout.json" && test -f "$W/.aos/config.json"
```

**回傳**（看退出碼或 stdout）——S-02-01：

```sh
mkdir -p "$W/notaland"; aos exec "$W/notaland"; test $? -eq 4
```

**schema**（拿產出的 json 去對 schema）——S-05-01：

```sh
aos exec "$W" && check-jsonschema --schemafile schemas/series.schema.json "$W/.aos/series.json"
```

`check-jsonschema` 只是舉例，任何一支會 draft 2020-12 的驗證器都行。世界層設定要指 `config.schema.json` 的 `#/$defs/world`，不是頂層。

## 02 版面

| 條款 | 檢查怎麼做 | 種類 | 用什麼 |
|---|---|---|---|
| S-02-01 | 對沒有 `.aos/` 的資料夾跑 exec | 回傳 | `aos exec` 退 4 |
| S-02-02 | 跑完一格，頂層檔名清單沒多出東西 | 存在 | 前後各 `ls` 一次 |
| S-02-03 | 同 S-02-02 | 存在 | 同上 |
| S-02-03 | 「人不手改」沒有東西擋 | 人工 | 只是規範，沒有防護機制 |
| S-02-04 | 檔案＝名字，是說法 | 人工 | 沒有可觀察的差別 |
| S-02-05 | 家也有 `.aos/layout.json` | 存在 | 看檔 |
| S-02-06 | 一塊地看不到外面 | 人工 | 沒有掛載或沙箱可打 |
| S-02-07 | 可見性不是權限 | 人工 | 沒有對應介面 |
| S-02-08 | 登記表那筆沒有另發的 id 欄 | schema | registry.schema.json |
| S-02-09 | 刪掉地，對帳後那筆消失 | 回傳 | `aos daemon ls` |
| S-02-10 | `aos mv` 後舊路徑不在、新的在 | 回傳 | `aos daemon ls` |
| S-02-11 | 直接 `mv`，對帳清掉舊筆 | 回傳 | 同上 |
| S-02-12 | 用 symlink 登記，表裡是真實路徑 | 回傳 | `aos daemon ls` |
| S-02-13 | 一條路徑一個 writer | 人工 | 要靜態分析程式碼 |
| S-02-14 | `.aos/` 下的路徑都在 02 那張表裡 | 存在 | `find .aos` 比對 |
| S-02-15 | 記憶的判準 | 人工 | 沒有機器判得出的界線 |
| S-02-16 | `.aos/series.json` 被 git 忽略 | 回傳 | `git check-ignore` 回 0 |
| S-02-17 | 帳簿也被忽略 | 回傳 | `git check-ignore` 回 0 |
| S-02-18 | init 產的 `.gitignore` 片段跟正本一樣 | 回傳 | `diff` |
| S-02-19 | `.aos/tools/` 沒被忽略 | 回傳 | `git check-ignore` 回非 0 |
| S-02-20 | `.aos/` 下沒有自製的版本目錄 | 存在 | 同 S-02-14 |
| S-02-21 | `layout_version` 在 | schema | layout.schema.json |
| S-02-22 | 每份 schema 的必填都含 `format_version` | 回傳 | 掃 `schemas/*.json` |
| S-02-23 | 每份 schema 頂層 `additionalProperties` 是 false | 回傳 | 同上 |
| S-02-23 | `layout.json` 塞怪欄位 | 回傳 | `aos exec` 退 3 |
| S-02-24 | 使用者層設定的欄位表 | schema | config.schema.json |
| S-02-25 | 世界層多一欄就不過 | schema | config.schema.json 的 `#/$defs/world` |
| S-02-26 | 世界層 `max_parallel` 比使用者層大 | 回傳 | `aos check` 退 3 |
| S-02-27 | 沒設時 `llm_world` 是家的 `.aos/llm` | 回傳 | `aos config get llm_world` |
| S-02-28 | `reap_after_ms` 設小，巡邏後子地被清 | 存在 | 看目錄 |
| S-02-29 | `inbox_max` 預設 1000 | 回傳 | `aos config get inbox_max` |
| S-02-30 | 地裡有子地但沒 `call` 步，子地不動 | 存在 | 子地沒有 `.aos/series.json` |
| S-02-31 | 同 S-02-30 | 存在 | 同上 |
| S-02-32 | 一份接力棒放得下兩條串 | schema | series.schema.json |
| S-02-33 | 只有一份進度檔 | 存在 | 同 S-02-14 |
| S-02-34 | 跑一半改原稿，模板檔位元組不變 | 回傳 | 前後 `sha256sum` |
| S-02-35 | exec 一格、離開、再 exec，游標接著走 | 回傳 | 讀 `cursor` |
| S-02-36 | OS 只保證三件事 | 人工 | 是範圍宣示 |
| S-02-37 | 摘要與砍舊交給應用 | 人工 | 同上 |
| S-02-38 | 把 `layout_version` 改成不認得的 | 回傳 | 退 3，且有停止原因檔 |
| S-02-39 | `aos migrate` 只印訊息 | 回傳 | 前後 `sha256sum` 一樣 |
| S-02-40 | `land_id` 是 32 hex，init 後不再變 | schema | layout.schema.json |
| S-02-41 | 搬地後對帳是刪那筆，不是改 `path` | 回傳 | 讀登記表 |
| S-02-42 | init 時 `layout.json` 最後才改名就位 | 回傳 | `strace -e rename` 的順序 |
| S-02-43 | `aos mv` 後游標還在、`ext.moved_from` 是舊路徑 | 回傳 | 讀兩個檔 |
| S-02-44 | LLM 世界有 `.aos/units.json`，agent 有 `.aos/usage.json` | 存在 | 看兩個檔 |
| S-02-45 | tmpfs 重建當從頭跑 | 人工 | 要真的斷電或重開機 |
| S-02-46 | 那四樣不在 tmpfs 上 | 回傳 | `stat -f` 看檔案系統 |
| S-02-47 | `units` 沒填 `timeout_ms` 時當 300000 | 回傳 | 讀落檔的 `aos llm` 指令 |

## 03 原稿與編譯

| 條款 | 檢查怎麼做 | 種類 | 用什麼 |
|---|---|---|---|
| S-03-01 | 同 S-03-04 | 回傳 | 同上 |
| S-03-02 | 原稿不是 json | 回傳 | 退 3 |
| S-03-03 | 原稿放進 `.aos/` 不被讀 | 存在 | `.aos/program/` 是空的 |
| S-03-04 | 同一份原稿編兩次 | 回傳 | 兩次 `sha256sum` 相同 |
| S-03-05 | 步裡沒有夾子地的欄位 | schema | program.schema.json |
| S-03-06 | 兩個模板同名 | 回傳 | 退 3 |
| S-03-07 | 加 `_comment` 後編出來的檔不變 | 回傳 | `sha256sum` |
| S-03-08 | 模板裡沒有 `interface` 或型別欄 | schema | program.schema.json |
| S-03-09 | 拿 `frame` 當參數名 | 回傳 | 退 3 |
| S-03-10 | 原稿的 `kind` 四選一 | schema | source.schema.json |
| S-03-11 | 四種引數寫法都收 | schema | 同上 |
| S-03-12 | 內嵌動作被提成自己一步 | 回傳 | 數 `steps` 長度 |
| S-03-13 | `{"from":"x"}` 編成 `${frame}/x` | 回傳 | 讀模板檔 |
| S-03-14 | 提上來的步名是 `<外層>__<序號>` | 回傳 | 讀模板檔 |
| S-03-14 | 原稿步名含 `__` | 回傳 | 退 3 |
| S-03-15 | 步名叫 `end` | 回傳 | 退 3 |
| S-03-16 | 前後相依的兩步不併成一步 | 回傳 | 同 S-03-12 |
| S-03-17 | `use` 成環 | 回傳 | 退 3 |
| S-03-18 | 巢狀深度 9 | 回傳 | 退 3 |
| S-03-19 | `mode` 只收 sync 與 async | schema | source.schema.json |
| S-03-20 | `result` 省略時編成 `${frame}/<步名>` | 回傳 | 讀模板檔 |
| S-03-21 | `select` 指的檔第一行變成下一步 | 回傳 | 讀 `cursor` |
| S-03-22 | 第一行寫不存在的步名 | 回傳 | `fail_reason` 是 `bad_select` |
| S-03-23 | `select` 與 `then` 都寫，走 `select` | 回傳 | 讀 `cursor` |
| S-03-24 | 每個模板一個檔 | 存在 | 看 `.aos/program/` |
| S-03-25 | 模板的 `kind` 三選一 | schema | program.schema.json |
| S-03-26 | 模板裡的 `inst` 壞掉 | 回傳 | 退 3 |
| S-03-27 | 模板裡 `inst.id` 等於步名 | 回傳 | 讀模板檔 |
| S-03-27 | 落檔的檔名是 32 個小寫 hex | 存在 | 看 `.aos/ticks/1/insts/` |
| S-03-28 | 被當引數的步有 `stdout`、沒有 `expect` | 回傳 | 讀模板檔 |
| S-03-29 | 原稿多一個怪欄位 | 回傳 | 退 3 |
| S-03-30 | 必填缺、步名重複 | 回傳 | 退 3 |
| S-03-31 | `then` 指到不存在的步 | 回傳 | 退 3 |
| S-03-32 | `use` 的引數對不上 | 回傳 | 退 3 |
| S-03-33 | 拒絕時 stderr 提到原稿檔與步名 | 回傳 | `grep` stderr |
| S-03-34 | 拒絕後 `.aos/program/` 一個檔都沒有 | 存在 | 看目錄 |
| S-03-35 | 閒著被 exec，模板與接力棒都出現 | 存在 | 看兩個檔 |
| S-03-36 | 同 S-02-34 | 回傳 | 同上 |
| S-03-37 | 沒有 `main` 模板 | 回傳 | 退 3 |
| S-03-38 | 檔頭 `source_hash` 等於原稿的 sha256 | 回傳 | 比對 |
| S-03-39 | 只動 mtime、內容沒變，還是重編一次 | 回傳 | 模板檔的 mtime 變新 |
| S-03-40 | 父開一個沒有 `main.aos.json` 的資料夾 | 存在 | 落點旁狀態檔 `no_source` |
| S-03-41 | 編譯失敗時沒有半份 program | 存在 | 父那邊狀態檔 `compile_error` |
| S-03-42 | run 期間沒開過頂層原稿 | 回傳 | `strace -e openat` |
| S-03-43 | `select` 指的檔不在、或第一行空白 | 回傳 | 那步失敗，`bad_select`，游標沒走 `then` |

## 04 指令

| 條款 | 檢查怎麼做 | 種類 | 用什麼 |
|---|---|---|---|
| S-04-01 | 底下不再有更小的一格 | 人工 | 是定義，沒有可觀察的差別 |
| S-04-02 | 模板裡的與落檔的過同一份 schema | schema | inst.schema.json |
| S-04-03 | 同 S-04-02 | schema | 同上 |
| S-04-04 | `argv` 寫成一整條命令列字串 | schema | 同上，不過 |
| S-04-05 | `id` 缺 | schema | 同上，不過 |
| S-04-05 | 同一格兩筆撞 `id` | 回傳 | 整格退 3 |
| S-04-06 | `env` 蓋過繼承來的同名變數 | 回傳 | 指令印出來比對 |
| S-04-07 | `env_inherit` 是布林 | schema | inst.schema.json |
| S-04-07 | 設 false 時看不到父的變數 | 回傳 | 指令印 `env` |
| S-04-08 | 省略 `cwd` 時 `pwd` 是地的根 | 回傳 | 看 stdout |
| S-04-09 | 三條流是路徑字串 | schema | inst.schema.json |
| S-04-10 | 省略時三條流落在預設路徑 | 存在 | 看 results 目錄 |
| S-04-11 | `stdout` 指到開不了的地方 | 回傳 | 結果檔的 `spawn_error` 非 null |
| S-04-12 | `timeout_ms` 比 run 給的長 | 回傳 | 整格退 3 |
| S-04-13 | 逾時做在 run 那層 | 人工 | 要讀程式碼分層 |
| S-04-14 | 帶 `footprint` 照跑，欄位原樣落檔 | 回傳 | 讀落檔的指令 |
| S-04-15 | 同 `exclusive` 名的兩筆分兩格 | 存在 | 兩個格號目錄各一筆 |
| S-04-16 | `ext` 以外多一欄 | schema | inst.schema.json，不過 |
| S-04-17 | 超長 `argv` 照收 | schema | 同上，過 |
| S-04-18 | 六個欄位都收 `{"b64":…}` | schema | 同上 |
| S-04-19 | `b64` 物件多一個鍵 | schema | 同上，不過 |
| S-04-20 | 沒有第二套綁定層 | 人工 | 是「不做什麼」 |
| S-04-21 | 一筆崩掉，同格別筆照樣有結果檔 | 存在 | 看 results 目錄 |
| S-04-22 | 指令是一支真行程 | 回傳 | 指令自己讀 `/proc/self` |
| S-04-23 | 同格 A 寫的檔 B 讀不到 | 回傳 | 讀 B 的 stdout |
| S-04-24 | 一筆壞的整格不跑，訊息指出哪筆哪欄 | 回傳 | 退 3、`grep` stderr |
| S-04-25 | 一筆非零，其他筆照樣跑完 | 存在 | 同 S-04-21 |
| S-04-26 | 三樣不可能寫成指令 | 人工 | 是說明，沒有可打的介面 |
| S-04-27 | LLM 不准當指令 | 人工 | 沒說誰檢查；`sh -c` 就繞過了 |
| S-04-28 | 結果檔只有那四件事 | schema | result.schema.json |
| S-04-29 | 結果檔沒有「做成沒做成」的欄 | schema | 同上 |
| S-04-30 | 每筆指令都有一份結果檔 | 存在 | 看 results 目錄 |
| S-04-31 | 跑不起來那筆也有結果檔 | 回傳 | `spawn_error` 非 null |
| S-04-32 | `exit_code` 與 `signal` 不同時非 null | 回傳 | 讀結果檔，schema 沒卡 |
| S-04-33 | `stdout` 欄是路徑不是內容 | schema | result.schema.json |
| S-04-34 | 時間戳格式 | schema | 同上 |
| S-04-35 | 指令印得出那七個變數 | 回傳 | 看 stdout |
| S-04-36 | `AOS_TMP` 目錄跑完不見了 | 存在 | 看 `tmp/` |
| S-04-37 | 子地印得出另外三種變數 | 回傳 | 看 stdout |
| S-04-38 | `env` 寫 `AOS_LAND` 也蓋不掉 | 回傳 | 看 stdout |
| S-04-39 | 兩筆宣告的 `footprint.writes` 相交 | 回傳 | 整格退 3 |
| S-04-40 | 從收件匣直接跑的指令 | 回傳 | `AOS_SERIES` 空、`AOS_FRAME` 等於 `AOS_TMP` |

## 05 接力棒

| 條款 | 檢查怎麼做 | 種類 | 用什麼 |
|---|---|---|---|
| S-05-01 | 接力棒過 schema | schema | series.schema.json |
| S-05-02 | 沒有批狀態欄、沒有第二個檔 | schema | 同上 |
| S-05-03 | exec 結束後進度在檔裡 | 存在 | 看 `series.json` |
| S-05-04 | 同 S-05-01 | schema | 同上 |
| S-05-05 | 拔掉收件匣，串照樣往前 | 回傳 | 讀 `cursor` |
| S-05-06 | `format_version` 是 1 | schema | series.schema.json |
| S-05-07 | `batch_id` 是 32 hex，整批不換 | 回傳 | 跑幾格比對 |
| S-05-08 | `aos reset --all` 後換了新的 | 回傳 | 前後比對 |
| S-05-09 | 載入那一刻 `tick` 是 0 | 回傳 | 讀檔 |
| S-05-10 | 跑一格 `tick` 加一、那個格號目錄在 | 存在 | 看 `.aos/ticks/` |
| S-05-11 | 串 id 是 32 hex | schema | series.schema.json |
| S-05-12 | `template` 對得上 program 裡的檔 | 回傳 | 比對檔名 |
| S-05-13 | `cursor` 是步名不是數字 | schema | series.schema.json |
| S-05-14 | `regs` 是名字對字串 | schema | 同上 |
| S-05-14 | 別條串引用不到這條的名字 | 回傳 | 那一步失敗 |
| S-05-15 | 五個內建名換成真值，查不到的算失敗 | 回傳 | 看 stdout 與 `status` |
| S-05-16 | `parent` 必有 | schema | series.schema.json |
| S-05-17 | `resources` 只當參考 | 人工 | 排程沒有可觀察的差別 |
| S-05-18 | 不是 failed／stopped 卻有 `fail_reason` | 回傳 | 讀檔，schema 沒卡這條 |
| S-05-19 | 接力棒多一個怪欄位 | 回傳 | 退 3 |
| S-05-20 | `status` 四選一 | schema | series.schema.json |
| S-05-21 | 誕生是 running，走到 end 變 done | 回傳 | 讀檔 |
| S-05-22 | 沒地方跳變 failed，收到停變 stopped | 回傳 | 讀檔 |
| S-05-23 | failed 的串再 exec 還是 failed | 回傳 | 讀檔 |
| S-05-24 | 不是 running 的串不推游標、不產指令 | 回傳 | 讀檔加看 insts 目錄 |
| S-05-25 | 結束碼非 0 但 `expect` 檔在，算成功 | 回傳 | 讀 `cursor` |
| S-05-26 | 四種情形各跑一次 | 回傳 | 讀 `cursor` 與 `status` |
| S-05-27 | 呼叫記錄先寫；sync 停在原地、async 立刻成功 | 回傳 | 看 `.aos/calls/` 與 `cursor` |
| S-05-28 | 三態各跑一次，超過 `max_ticks` | 回傳 | `fail_reason` 是 `await_timeout` |
| S-05-29 | `then` 三種寫法各走一次 | 回傳 | 讀 `cursor` |
| S-05-30 | 同 S-03-23 | 回傳 | 同上 |
| S-05-31 | 有 `on_fail` 就跳過去，還是 running | 回傳 | 讀檔 |
| S-05-32 | 沒 `on_fail` 就停在原地、寫停止原因檔 | 存在 | 看 `.aos/stopped.json` |
| S-05-33 | 載入後只有一條串，跑 main | 回傳 | 讀檔 |
| S-05-34 | 跑完 `call` 步，串數沒變 | 回傳 | 數 `series` 長度 |
| S-05-35 | 所有串的 `parent` 都是 null | 回傳 | 讀檔 |
| S-05-36 | done 的串還留在陣列裡 | 回傳 | 數長度 |
| S-05-37 | 指令跑完 `tmp/<id>/` 不見了 | 存在 | 同 S-04-36 |
| S-05-38 | 開串時堆疊框在，串 done 那格不見了 | 存在 | 看 `.aos/frames/` |
| S-05-39 | failed 的串的堆疊框還在 | 存在 | 同上 |
| S-05-40 | 寫接力棒有 rename、沒有就地改 | 回傳 | `strace -e trace=rename,renameat` |
| S-05-41 | 沒拿到鎖的第二支 exec | 回傳 | 退 75 |
| S-05-42 | 外面直接改 `series.json` | 人工 | 沒有東西擋外部寫 |
| S-05-43 | 接力棒不合 schema | 回傳 | 退 3，insts 目錄沒開 |
| S-05-44 | 空陣列或全 done 時 run 的收場 | 回傳 | `reason` 是 `no_new_insts` |
| S-05-45 | 有 failed 時 run 的收場 | 回傳 | 退 5、`reason` 是 `failed` |
| S-05-46 | `recent_ids` 在，最多 1000 個 | schema | series.schema.json |
| S-05-47 | 同一個投遞 id 投兩次只跑一次 | 回傳 | 數 insts 目錄 |
| S-05-47 | 控制那邊的去重不共用這一欄 | 回傳 | 同 id 的 stop 照收 |
| S-05-48 | tmpfs 上去重不算保證 | 人工 | 要真的斷電或重開機 |
| S-05-49 | 那一步成功後 `fail_streak` 歸零 | 回傳 | 讀接力棒 |
| S-05-50 | 停在 `await` 或同步 `call` 的串算在等 | 回傳 | run 不停 |
| S-05-51 | 同一步連三次失敗 | 回傳 | stopped，`repeat_fail` |
| S-05-52 | `on_fail` 那步又壞 | 回傳 | failed，`fail_reason` 兩層 |
| S-05-53 | `calls` 是步名對 call id | schema | series.schema.json |
| S-05-54 | `await_ticks` 是步名對整數 | schema | 同上 |
| S-05-55 | sync 停在原地五格，呼叫記錄只有一筆 | 存在 | 數 `.aos/calls/` |
| S-05-56 | 每格 `await_ticks` 加一，跟 `max_ticks` 比的是它 | 回傳 | 讀接力棒 |
| S-05-57 | 游標離開那一步，兩個鍵都不見了 | 回傳 | 讀接力棒 |
| S-05-58 | `.aos/` 下沒有第二個去重檔 | 存在 | 同 S-02-14 |
| S-05-59 | 暫存器的值裡放 `${land}` | 回傳 | 落檔裡原樣留著，沒有再換一次 |
| S-05-60 | `${llm_world}` 由 exec 填，地沒開家的設定檔 | 回傳 | stdout 與 `strace -e openat` |
| S-05-61 | 同步子閒著了、落點卻沒檔也沒狀態檔 | 回傳 | 那步失敗 `no_result`，子沒被再點名 |

## 06 走一格與時鐘

| 條款 | 檢查怎麼做 | 種類 | 用什麼 |
|---|---|---|---|
| S-06-01 | 一次 exec 只推一格 | 回傳 | `tick` 只加一 |
| S-06-02 | 兩條串同一格都動 | 回傳 | 兩個 `cursor` 都變 |
| S-06-03 | 同 S-04-23 | 回傳 | 同上 |
| S-06-04 | 預算走滿時最後一格的結果檔是完整的 | 存在 | 看 results 目錄 |
| S-06-05 | 十五步的順序 | 人工 | 要讀程式碼或加追蹤點 |
| S-06-06 | 第二支 exec 退 75；出錯後鎖不留 | 回傳 | 退出碼與 `.aos/lock` |
| S-06-07 | 有 running 串時不重編 | 回傳 | 模板檔位元組不變 |
| S-06-08 | 別的地收到 `kind:"llm"` | 存在 | 進 `.aos/inbox/rejected/` |
| S-06-09 | 同 S-04-15 | 存在 | 同上 |
| S-06-10 | 同 S-04-24 | 回傳 | 同上 |
| S-06-11 | 落檔裡沒有 `${` | 回傳 | `grep` 落檔 |
| S-06-12 | 同 S-05-25 | 回傳 | 同上 |
| S-06-13 | 有 `expect`、結束碼 0 但檔不在 | 回傳 | 那一步失敗 |
| S-06-14 | 同 S-05-38 與 S-05-39 | 存在 | 同上 |
| S-06-15 | 兩件都沒有的那一格 | 回傳 | run 停，`no_new_insts` |
| S-06-16 | run 走幾格等於 exec 被叫幾次 | 回傳 | 比對 `tick` |
| S-06-17 | 三個旗標各跑一次 | 回傳 | 讀 `stopped.json` 的 `reason` |
| S-06-18 | 沒新指令、但還有串在等 | 回傳 | run 不停，`tick` 照加 |
| S-06-19 | 沒有第三種走法的旗標 | 回傳 | `aos run --help` |
| S-06-20 | `--budget 3` 走三格 | 回傳 | `reason` 是 `budget` |
| S-06-21 | 跑到一半投停，停在格邊界 | 回傳 | 讀 `stopped.json` 與結果檔 |
| S-06-22 | run 開始先刪舊的，停時寫新的 | 存在 | 看 `.aos/stopped.json` |
| S-06-23 | 同 S-05-45 | 回傳 | 同上 |
| S-06-24 | 十種收場的退出碼各對一次 | 回傳 | `aos run` 退出碼 |
| S-06-26 | `path` 沒放的程式叫不動 | 回傳 | 結果檔的 `spawn_error` |
| S-06-27 | 同 S-06-26，且沒有被跳過 | 存在 | 那筆有結果檔 |
| S-06-28 | 三層 timeout 各設一次，最短的贏 | 回傳 | 結果檔的 `timed_out` |
| S-06-29 | 逾時殺整個行程群組 | 回傳 | 子孫行程也不在 |
| S-06-30 | 沒有給程式讀時間的介面 | 回傳 | 那五個變數裡沒有時間 |
| S-06-31 | 同 S-05-27 | 回傳 | 同上 |
| S-06-32 | 同步子樹裡不准有 LLM | 人工 | 同 S-04-27，沒說誰檢查 |
| S-06-33 | 脫節那格父不等它 | 回傳 | 父的 `tick` 照加 |
| S-06-34 | 同 S-02-34 | 回傳 | 同上 |
| S-06-35 | `aos reset` 後模板換成新的 | 回傳 | `sha256sum` 比對 |
| S-06-36 | 只剩在等的串時，兩格之間睡那麼久 | 回傳 | 量兩格的時間差 |
| S-06-37 | 決定要停之前再掃一次收件匣 | 回傳 | 剛好投進去就再走一格 |
| S-06-38 | 指令跑到一半投停，停得下來 | 回傳 | 讀 `stopped.json` |
| S-06-39 | run 自成一個行程群組 | 回傳 | `ps -o pgid` |
| S-06-40 | 同 S-05-51 | 回傳 | 同上 |
| S-06-41 | 同 S-04-39 | 回傳 | 同上 |
| S-06-42 | 格跑到一半才到的結果留到下一格 | 回傳 | 讀 `cursor` |
| S-06-43 | 跑指令前有一個空的 `started` | 存在 | 看 `.aos/ticks/<N>/started` |
| S-06-44 | 造一個崩在半路的現場 | 回傳 | 兩種各一次，讀 `cursor` 與 `fail_reason` |
| S-06-45 | `--timeout 0` | 回傳 | 退 2 |
| S-06-46 | 同 S-03-42 | 回傳 | 同上 |
| S-06-48 | 鎖檔內容有 `pid` 與 `pid_start`；持有者死了鎖被收回 | 回傳 | 第二支退 0 不是 75 |
| S-06-49 | exec 判串 failed 那一刻就有停止原因檔 | 存在 | 看 `.aos/stopped.json` 的 `detail` |
| S-06-50 | 同 S-04-40 | 回傳 | 同上，且 `.aos/frames/` 沒新目錄 |
| S-06-51 | `env_inherit` false 加空 `path` | 回傳 | PATH 是 `/usr/bin:/bin` |
| S-06-52 | 互斥誰先跑照接力棒的串順序 | 回傳 | 比對兩格的落檔 |
| S-06-53 | 那三個寫者各造一次；`SIGTERM` 也寫得出來 | 存在 | 看 `.aos/stopped.json` |
| S-06-54 | `--until never` 閒著也不停 | 回傳 | `tick` 照加 |
| S-06-55 | 陳年控制信被搬到 `done/`，`op` 不認得的也是 | 存在 | 看兩個目錄與 stdout |
| S-06-57 | 五種條件同時成立時挑哪一個 | 回傳 | 讀 `stopped.json` 的 `reason` |
| S-06-58 | 最後一格把串推到 done | 回傳 | run 停，`no_new_insts`，`tick` 沒再加 |
| S-06-59 | 一支 run 跑到一半變閒著 | 回傳 | `batch_id` 沒換、模板檔位元組不變 |
| S-06-60 | 呼叫記錄只寫一筆；async 沒 daemon 就失敗 | 回傳 | 同 S-05-55 與 S-07-28 |
| S-06-61 | 同格落點重複、或三個檔已存在 | 回傳 | 整格退 3 |
| S-06-62 | 借父鐘的子地收得到控制信 | 回傳 | 那格不跑指令、串 stopped、信進 `done/` |

## 這份檔自己的條款

- **S-14-01** 02～13 每一條「必須」與「禁止」必須在 14、[14b](14b-conformance.md)、[14c](14c-conformance.md) 三份裡至少對到一列；漏了就是這疊 spec 不合規。〔主編補〕
- **S-14-02** 新增或改寫一條「必須」時，必須在同一個 commit 補上或改掉它那一列。〔主編補〕
- **S-14-03** 一列的「種類」必須是**檔案存在**、**指令回傳**、**格式過 schema**、**人工**四者之一；寫成人工的必須在同一句裡說機器為什麼測不了。〔主編補〕
- **S-14-04** 判成人工的條款必須全部列進 [14c](14c-conformance.md) 的「測不到的必須」，一條一行，寫清楚缺什麼才測得到。〔主編補〕
- **S-14-05** 檢查禁止讀 `.aos/` 以外的使用者資料，也禁止連外；每個檢查必須在自己的暫時資料夾裡自足。〔主編補〕

## 待使用者拍板

- S-14-01 每條必須至少對一個檢查，漏了算 spec 不合規。
- S-14-02 新增或改寫必須條款要在同一個 commit 補檢查。
- S-14-03 檢查種類只有四種，人工要寫清楚理由。
- S-14-04 人工條款要全部進「測不到的必須」那一段。
- S-14-05 檢查只准動自己的暫時資料夾，不准連外。
- 矛盾：S-04-27、S-06-32、S-07-05、S-09-05、S-09-06 都禁止 LLM 出現在某處，卻沒有一條說誰檢查。S-09-58 與 S-11-53 只擋「登記成工具」，擋不住原稿裡直接寫 `argv: ["sh","-c","curl …"]`。這五條先判人工。
- 矛盾：[入口](README.md) 的「主編裁的矛盾」第 2 條寫「出生只登記成 `pending`」，但 S-08-27 與 S-13-22 已改成登記 `stopped`；第 6 條寫「exec 自己 detach 起 run」，但 S-07-28 與 S-08-28 已改成立刻失敗、寫 `no_daemon`。表照現在的條款寫，入口那張表要跟著改。

## 現況對照

今天沒有任何 conformance 測試：`wf/` 底下只有 wf-lint 那類文件檢查，`core/` 沒有對照這疊 spec 的測試目錄。這張表是要建的東西的清單，不是現況的描述。
