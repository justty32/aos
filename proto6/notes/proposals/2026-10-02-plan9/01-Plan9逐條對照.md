# 一、Plan 9 的核心想法，逐條對照 aos 現況

← [提案入口](README.md)｜下一份：[Linux 上的工具](02-Linux上的工具與代價.md)

每條分兩段：**Plan 9 真的這樣做**（憑記憶整理，細節請對 Plan 9 第四版 manual 或 9front）、**aos 現在在哪裡**。評語用三個字：已經是、半路、不是。

## 對照表

| Plan 9 的想法 | Plan 9 真的這樣做 | aos 現況 | 評 |
|---|---|---|---|
| 一切皆檔案 | `/proc/N/{ctl,status,note,wait,ns,fd}`、`/net/tcp/N/{ctl,data}`、`/dev/{cons,time,draw}`，連環境變數都是 `/env/名字` | tick 的表、鎖、擋板、紀錄全是檔；daemon 的控制與訊息是 socket＋JSON；daemon 執行期狀態在記憶體 | 半路 |
| ctl 檔寫字串控制 | `echo kill > /proc/N/ctl`、`echo stop`、`pri 13`；一次 write 一個指令，空白分隔，不是 JSON | `aos-ctl wake a` 送 `{"wake":"a"}`；cgroup 模組寫 `cgroup.kill` 已經是這招 | 半路 |
| status 一行固定欄位 | `/proc/N/status` 固定寬度欄位 | daemon stdout 的 `inst=a exit=0 ms=812` 正是這格式，只是沒放成檔 | 半路 |
| 沒有 ioctl | 所有控制走 ctl 檔或寫 `/dev/consctl` | 沒有 ioctl；但有 SIGHUP（reload）、SIGTERM（退出）這兩個「訊號當指令」 | 半路 |
| clone 檔開連線 | open `/net/tcp/clone` → read 得號碼 N → 寫 ctl `connect host!port` → 讀寫 `N/data` | 沒有對應；LLM 呼叫目前直接打 HTTP（agent 提案的 `aos-llm`） | 不是 |
| 每個行程自己的 namespace | `rfork(RFNAMEG)`、`bind`、`mount`、union dir（`-a`／`-b`／`-c`）、`/lib/namespace` 一行一個指令、`RFNOMNT` 鎖死 | 任務的「視野」靠環境變數（`AOS_DAEMON_*`）告訴它 socket 在哪，再靠資料夾權限擋；沒有 namespace | 不是 |
| 權限＝看不看得到＋伺服器自己查 uname | 沒有 root、沒有 setuid；namespace 裡沒有的就用不了；檔案伺服器看 attach 的 uname 與 mode | T-08「能寫 tasks.json、能連 socket 就是那個身分」——精神一樣，手段是 Unix 的資料夾權限與帳號模組 | 半路 |
| 9P 是唯一協議 | 核心與所有伺服器只講 9P；fid、qid、Twalk／Tread／Twrite／Tflush | 三種協議並存：JSON-over-socket（ctl、mq）、SEQPACKET 傳 fd（root 端）、檔案（其餘） | 不是 |
| 服務都是檔案伺服器 | rio、factotum、plumber、acme、upas/fs、webfs、cs 全是 user-space 檔案伺服器，`/srv` 布告欄 post 出去讓人 mount | 唯一的常駐程式 daemon 不是檔案伺服器 | 不是 |
| blocking read 當事件 | `/proc/N/wait`、plumber port、acme `event`、`listen` 的 open 都是 read 擋到有事 | 沒有；叫醒靠 socket 送 `wake`，等結果靠下一格再看 | 不是 |
| 一次 write 一則訊息 | pipe 保留 write 邊界；ctl 一次 write 一個指令 | mq 一條連線一封信，效果一樣 | 已經是 |
| 檔案存在與否就是狀態 | `/srv/name` 在就能 mount；`DMEXCL` 檔當鎖 | `tick-blocked`、`tasks-blocked`、`tick.lock` | 已經是 |
| 短命程式讀寫長命伺服器 | `cat`、`echo`、`9p read acme/index` | tick、exec、ctl、mq 都短命；daemon 長命 | 已經是 |
| 文字協議、沒有 JSON | 一切是行與空白分隔；錯誤是 `errstr` 字串 | aos 用 JSON 當通用格式（使用者前提）；錯誤是 `{"ok":false,"error":"stopped"}` | 不是（刻意的） |
| 沒有 symlink，用 bind | `bind /a /b` 取代連結與 `$ref` 這類「指到別處」 | `$ref` 指示詞做同一件事，但在 JSON 層 | 半路 |
| 沒有 PATH，`/bin` 是 union | `bind -a /386/bin /bin` | 用 PATH | 不是 |

## 讀這張表的方法

```mermaid
flowchart LR
  A[已經是<br/>擋板檔、鎖檔、紀錄目錄、一次一封信、短命程式] --> B[半路<br/>ctl 與 status 的格式、訊號當指令、$ref、權限精神]
  B --> C[不是<br/>namespace、檔案伺服器、blocking read、clone、9P]
  C -. 要補的全在這 .-> D[daemon 變樹 ＋ 任務有自己的 namespace]
```

三件事看得出來：

1. **tick 這一層已經很 Plan 9**。第十六批「擋板檔只看存不存在」、第九批「紀錄拆小檔」、「`.aos/` 一個資料夾一個單位」——這些裁定本來就在往「介面是檔案」走，不是巧合，是 Unix 哲學自然長出來的。
2. **不像的地方全集中在 daemon**：它是唯一常駐的東西，而它跟外界講話的方式（socket、JSON、訊號、環境變數）正好是 Plan 9 全部不要的那幾種。
3. **namespace 這條整個沒有**。aos 現在用「環境變數告訴你路徑＋資料夾權限擋你」替代；Plan 9 會說「你看不到的路徑就不存在」。兩者的差別在 [05](05-agent與kernel的namespace.md) 細講。

## 兩個常被忽略的 Plan 9 事實

- **Plan 9 不是純文字**：`/dev/draw` 的 data 走二進位、stat 結構是二進位、AuthInfo 是二進位。「一切文字」是慣例不是鐵律，所以 aos「JSON 當通用格式」不算背離，只是把二進位例外換成 JSON 例外。
- **Plan 9 沒有變更通知**：沒有 inotify，只有 blocking read 跟比對 qid.version。所以「用檔案做事件」在 Plan 9 是靠伺服器刻意把某個檔做成「讀了會等」。這點在 Linux FUSE 上能做，但有坑（[02](02-Linux上的工具與代價.md)）。

## 跟 aos 的幾條原則對一下

| aos 原則 | Plan 9 怎麼看 |
|---|---|
| 默認一切正常、出錯讓程式自然丟錯 | 很合：Plan 9 的錯誤就是 `write` 失敗加一句字串，沒有錯誤碼體系 |
| 程式即 spec | 很合：`ls /proc/N` 就是行程的 spec；但「ctl 收哪些字串」還是得看 man page，跟「JSON schema」一樣要另外寫 |
| 反應速度是一格、不准背景程序繞過 tick | **衝突**：Plan 9 到處是 blocking read，一個程式「等到有事再動」是常態；要走 Plan 9 又守「一格」，得禁止任務在格內 block 等別人 |
| daemon 只是笨 cron | **衝突**：Plan 9 式 daemon 是檔案伺服器，不笨 |
| socket 666、權限靠資料夾 | 很合：Plan 9 的 `/srv` 也是「post 出去誰能 mount 看檔案 mode」 |
| 不准有 node | 中性：Plan 9 的「一個目錄＝一個東西」會讓「資料夾就是單位」更自然，node 這詞更不需要 |
