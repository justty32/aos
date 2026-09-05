# DOORMAN — 門房第一級的原型

一支獨立腳本 `proto/doorman.py`，照 [spec 13](../wf/workflows/spec/13-doorman-l1.md) 做「門房第一級」：
站在資料夾樹前面看檔案動靜，**只看不擋**。它盯著一個根目錄底下的地
（＝裡面有 `.aos/layout.json` 的資料夾）出生跟死亡，出事就在本子記一筆、順手把
`$AOS_HOME/.aos/registry.json` 那一筆改對，然後**什麼都不做**。

跟 `proto/aosp/` 沒有任何 import 關係，是一支自己能跑的腳本；但登記表、鎖、原子寫
三樣都跟 `proto/aosp/` 一模一樣，不是第二套。

## 怎麼跑

```sh
python3 proto/doorman.py <根目錄> [--home <AOS_HOME>]
```

沒給 `--home` 就吃 `$AOS_HOME`，再沒有就是 `~`。**測試跟玩的時候一律把家指到暫存目錄**，
不要弄髒真的 `~`。

```sh
export AOS_HOME="$(mktemp -d)"
mkdir -p /tmp/work
python3 proto/doorman.py /tmp/work &          # 門房在背景盯著
python3 proto/aos.py init /tmp/work/proj      # 生一塊地
python3 proto/aos.py daemon ls                # 登記表上馬上看得到它，state=stopped
rm -rf /tmp/work/proj                         # 殺掉它
python3 proto/aos.py daemon ls                # 那筆變 stopped 且 ext.died_at 有值
cat "$AOS_HOME/.aos/doorman.jsonl"            # 本子：一行 born、一行 gone
```

| 旗標 | 幹嘛的 |
|---|---|
| `--home <路徑>` | 家在哪（登記表、鎖、本子都住這的 `.aos/`） |
| `--depth N` | 往根目錄底下找幾層地，預設 2（S-13-31 不准遞迴整棵樹，所以要有上限） |
| `--poll` | 不用 inotify，直接輪詢 |
| `--poll-ms N` | 輪詢間隔／inotify 的保底巡邏間隔，預設 1000 毫秒 |
| `--once` | 掃一遍就退出（測試跟「保底對帳」用） |
| `--for-ms N` | 跑這麼多毫秒就自己退出（測試用） |
| `--strict-birth` | 照 S-13-47：出生只認 `layout.json` 的原子改名（**預設不開**，理由見下面第 2 條） |
| `--strict-layout` | 照 `layout.schema.json` 嚴格檢查：沒有 `land_id` 就 `born_invalid`（**預設不開**，理由見第 3 條） |
| `--tmpfs-note` | 只印一句 tmpfs 上 inotify 有沒有效的實測結果，不搬任何東西 |
| `--quiet` | 不印過程 |

停它就 Ctrl-C 或 `kill`（收 SIGINT／SIGTERM，收完把 watch 收乾淨才走）。

## 用的是 inotify，不是輪詢

**用 inotify。** Python 標準庫沒有這東西，所以用 `ctypes` 直接綁 libc 的
`inotify_init1` / `inotify_add_watch` / `inotify_rm_watch`，事件從 fd 用 `os.read` 讀出來、
`struct` 自己拆（`select` 等事件）。整支腳本仍然是純標準庫，不用裝任何套件。

退回輪詢有兩種情況，兩種都會先在本子記一筆 `fallback` 再繼續做事（S-13-32／S-13-33）：

1. **綁不上 libc 或 `inotify_init1` 失敗**（不是 Linux、被 sandbox 擋掉）。
2. **watch 數量爆掉**（`inotify_add_watch` 回 `ENOSPC`，就是 `/proc/sys/fs/inotify/max_user_watches` 到頂）。

退回之後門房**不會結束**，只是改用每 `--poll-ms` 掃一遍磁碟，生死照樣寫進本子跟登記表。
`--poll` 是手動選輪詢，這種是自己選的、不記 `fallback`。

**inotify 只是門鈴，判定生死靠掃描。** 收到事件就馬上掃一輪（而不是照事件字面推論），
所以事件漏了、佇列爆了（`IN_Q_OVERFLOW`）、門房剛重啟，下一輪巡邏都會補回來。
這也是 S-13-19 說的兩條路：門房通知是快路，巡邏是保底。

盯哪些地方（S-13-30／S-13-31）：根目錄本身、根目錄底下 `--depth` 層以內的每個目錄、
以及每個目錄底下已經存在的 `.aos/`。**不遞迴整棵樹**。

## tmpfs

```
$ python3 proto/doorman.py --tmpfs-note
.aos/ 在 tmpfs 時 inotify 一樣有效：在 /dev/shm（tmpfs）原子改名放進 layout.json，
IN_MOVED_TO 收到；同一份測試在 /home/lorkhan（ext4，磁碟）收到，兩邊行為一樣。
```

這是真的量出來的，不是抄來的：`--tmpfs-note` 每次都當場在 tmpfs 上建一個暫存目錄、
裝一個 watch、把 `layout.json` 原子改名進去，看 `IN_MOVED_TO` 有沒有回來，再在磁碟上做一次對照。
它**不會**搬任何東西（S-13-38 的開關是 `aos init --tmpfs`，不是門房的事）。

順帶一提：這台機器的 `/tmp` 本身就是 tmpfs，所以整套 `doorman-tests` 其實一直都跑在 tmpfs 上。

## 本子（事件檔）長什麼樣

`$AOS_HOME/.aos/doorman.jsonl`，一行一個 json，只往後加、不改舊的。用 `O_APPEND` 單次
`write` 加上 `fsync` 寫進去，多支一起寫也不會把行寫爛。

```json
{"at":"2026-09-05T07:53:43.277Z","kind":"born","event":"born","path":"/tmp/work/proj","ext":{"trigger":"inotify:moved_to","land_id":"3f2a…"}}
{"at":"2026-09-05T07:54:10.031Z","kind":"gone","event":"gone","path":"/tmp/work/proj","ext":{"trigger":"inotify:delete_self","orphan_pid":40530}}
{"at":"2026-09-05T07:54:10.560Z","kind":"gone","event":"gone","path":"/tmp/work/proj","ext":{"trigger":"reap","killed_pid":40530}}
```

| 欄 | 意思 |
|---|---|
| `at` | 門房記這一筆的時刻，ISO 8601 UTC 含毫秒（不是事件本身發生的時刻） |
| `kind` | 事件短代碼。使用者指定的欄名 |
| `event` | 跟 `kind` 同值。spec 的 `doorman-log.schema.json` 用這個欄名，兩個一起寫 |
| `path` | 真實路徑（realpath）。生死事件記的是**那塊地的根** |
| `ext` | 可有可無的擴充：`trigger`（哪個 inotify 事件或 `sweep` 觸發的）、`land_id`、`orphan_pid`、`killed_pid`、`why`、`warn` |

短代碼目前用到三個（S-13-13 的六個裡，第一級只做生死）：

- `born`：一塊地誕生，登記表補一筆。
- `born_invalid`：`layout.json` 讀不到或不合格 → **不登記**，只記這一行。
- `gone`：登記表某筆的路徑（或它的 `.aos/`）不見了。孤魂補完刀會再記一行 `gone`，`ext.trigger` 是 `reap`。
- `fallback`：退回輪詢時記一筆。
- （`write` 記帳、`inbox` 門鈴是第一級沒做的兩項，S-13-14 說記帳排第二、S-13-15 說門鈴只是建議。）

**寫的順序是先本子、再登記表**（S-13-08）。鎖被別人佔住而寫不進登記表時，本子上那一筆已經在了，
不會變成「事情發生過但完全沒紀錄」。這件事有測試釘著
（`test_event_lands_in_the_notebook_before_the_registry`）。

## 動登記表的規矩

- 跟 daemon **共用同一把鎖** `$AOS_HOME/.aos/registry.lock`：`O_EXCL` 建檔、裡面寫
  `{"pid","at"}`、持鎖者死了就把鎖收回來——協定跟 `proto/aosp/fsutil.py` 的 `Lock`
  一字不差（S-08-21／S-13-37）。沒有發明第二把鎖。
- 寫是原子的：`registry.json.tmp` → `fsync` → `rename` → `fsync` 目錄（S-08-22）。
- **出生**：補一筆 `state:"stopped"`，`pid`／`pid_start`／`clock`／`budget`／`parent` 全 `null`
  （S-13-22／S-08-27）。**不起時鐘**——這就是主編裁的矛盾 #2：門房只登記，起鐘還是父或使用者的事。
  實測過：`aos daemon start` 只起 `pending` 的筆，門房登的這筆它不會碰。
- **死亡**：那筆標 `state:"stopped"`、`pid`／`pid_start` 清 `null`、`ext.died_at` 記時間、
  `ext.died_by` 記 `"doorman"`。
- **孤魂補刀**：路徑不在了、`pid` 還活著 → 先停掉那支行程再改登記表（S-13-17）。
  判活要 `pid` 跟 `pid_start` 兩欄都吻合（S-08-68），對不上就**不動它**——那個編號已經被系統
  發給別人了，砍下去是砍無辜的人。殭屍不算活著（S-08-90）。
  停的方式：對整個行程群組先 SIGTERM 再 SIGKILL（S-08-77，同步子孫才不會變孤兒繼續改檔案）。
  除了「停掉這支行程」以外**什麼都不做**。
- **同一塊地反覆生死只有一筆**（S-08-11）：登記表以 `path` 為主鍵，重生就更新那一筆、
  把 `died_at` 清掉改記 `ext.reborn_at`，不會長出第二筆。而且重生時**不覆寫**別人（`aos run`／daemon）
  寫進去的 `clock`。
- **不碰任何一塊地的 `.aos/`**（S-13-09）。有測試釘著（`test_doorman_never_touches_a_land_dot_aos`）。

## 測試

```sh
python3 -m unittest discover proto/doorman-tests
```

38 個，全綠，大約 9 秒。分三份：

- `test_doorman.py`：在同一支行程裡直接呼叫 `Doorman`，快而穩。出生／死亡／本子格式／
  不重複登記／孤魂補刀／不砍無辜 pid／鎖與原子寫／不碰地的 `.aos/`。
- `test_doorman_live.py`：真的把 `doorman.py` 當一支程式起起來，inotify 跟輪詢兩條路各跑一遍
  生死流程，另外驗 CLI（`--tmpfs-note`、`--once`、錯誤訊息有沒有指路）。
- `test_doorman_interop.py`：退回輪詢那條路，加上「`aos init` 建的地 → 門房登記 → `aos daemon ls`
  讀得懂」的接縫測試（`aos.py` 跑不起來就 skip，因為 `proto/aosp/` 另一隊在改）。

沒有任何一個測試會碰到真的 `~`：家一律是 `tempfile.mkdtemp()`。

---

# spec 沒講到的地方

照使用者的三種量法分：**多餘的動作**（一件事要敲好幾次）／**看不見的狀態**（壞了或在等，
但畫面上看不出來）／**錯誤不指路**（報錯了但沒說下一步）。再加一種：**spec 沒講**
（行為根本沒定義，只能自己選一邊）。

## 1. 本子的檔名跟欄名有兩套，只能挑一邊

S-13-11 說本子是 `$AOS_HOME/.aos/doorman.log`，S-13-12 說每行要過
`doorman-log.schema.json`——那份 schema 的欄名是 `event`，而且
`"additionalProperties": false`。這次交代下來的規格是 `doorman.jsonl`，欄名 `kind`。
兩邊**互相排斥**：照 schema 寫就不能有 `kind`，照交代寫就不合 schema。

我先兩個欄名都寫（同值），檔名用 `doorman.jsonl`。這只是拖時間，不是解法：
真正要決定的是「本子是給誰讀的」——`.log` 這個副檔名會讓人以為是可以隨便截斷的日誌，
但 S-13-51 又要 daemon 去讀它當控制訊號來源，那它其實是一份**資料**。
我傾向 `.jsonl` 加 `additionalProperties: true`。

*類別：spec 沒講。擋路程度：煩。*

## 2. S-13-47「出生只認原子改名」有競態，實測會漏掉地

S-13-47 說門房只准認一個出生事件：`.aos/layout.json` 以原子改名出現（`IN_MOVED_TO`）。
問題是 **watch 必須在那次改名之前就已經裝在 `<地>/.aos/` 上**，而 `.aos/` 是跟這塊地
一起被建出來的。`aos init` 那幾行（`mkdir` → `mkdir .aos` → 寫 tmp → `rename`）跑完只要幾毫秒，
門房根本來不及在中間插進去裝 watch。

實測結果就是這樣：開了 `--strict-birth` 之後，一口氣建出來的地**永遠不會被登記**，
而且本子上一行都沒有——地在那裡、登記表上沒有、沒有任何錯誤訊息。
測試 `test_strict_birth_misses_a_land_created_in_one_shot` 就是把這個漏洞釘起來的。

所以預設**不開** `--strict-birth`：判生死靠掃描，inotify 只當門鈴。
spec 要嘛放寬 S-13-47（承認掃描也算數），要嘛規定 `aos init` 要先建好空的 `.aos/`、
等一拍再改名（等於要求所有建地的人配合門房），要嘛承認這條只是「快路的觸發條件」、
保底仍然是巡邏。第三種最誠實。

*類別：看不見的狀態。擋路程度：擋路。*

## 3. `aos init` 不寫 `land_id`，嚴格照 S-13-49 會一塊地都登記不了

`layout.schema.json` 把 `land_id` 列為 **required**（32 個小寫 hex）。
S-13-49 說 `layout.json` 不合它的 schema 就**禁止登記**，只記一筆 `born_invalid`。
但今天 `proto/aos.py init` 寫出來的是 `{"format_version":1,"layout_version":1}`——沒有 `land_id`。
兩條合起來的結果是：**今天所有的地都是 `born_invalid`，門房一塊都不登記**，
本子上只會堆一排「不合格」，而且不會告訴任何人是哪一欄不合格、該怎麼修。

我的處理：`format_version`／`layout_version` 不對才判 `born_invalid`；`land_id` 缺了或格式不對
只在 `ext.warn` 留一句、照樣登記（`land_id` 記 `null`）。要照 spec 嚴格走就下 `--strict-layout`，
有測試證明那樣會全部被擋掉。

順帶三個 spec 沒講的：`born_invalid` 之後**誰去修**？要不要**重試**（同一塊壞地每輪掃描
都記一行，本子會被洗版——我改成只在狀態變化時記）？以及**「不合 schema」到底要不要驗到底**
（第一版原型不可能塞一個 JSON Schema 驗證器進純標準庫，我只驗了骨架）。

*類別：錯誤不指路。擋路程度：擋路。*

## 4. 孤魂補刀怎麼補，13 章只寫了兩個字「停掉」

S-13-17 說「必須先把那個行程停掉（孤魂補刀），再改登記表」。沒說：
用哪個訊號、對 `pid` 還是對整個行程群組、等多久、殺不掉（權限不夠、卡在 D state）算不算數。

08b 那邊的全停流程（S-08-45／S-08-46）是先投一則 `stop` 進 `<地>/.aos/control/`、等 10 秒再 SIGKILL。
**這條路在門房這裡走不通**：地都不在了，`.aos/control/` 跟著不在了，信沒地方投。
所以門房只能直接送訊號——但 spec 從來沒明說這個例外。

我選：對行程群組先 SIGTERM 等 0.5 秒、再 SIGKILL 等 0.5 秒（行程群組是照 S-08-77 的精神，
同步子孫才不會變孤兒繼續改檔案）。殺不掉時我照樣把那筆標 `stopped`，但**不寫** `ext.killed_pid`，
本子上只留 `orphan_pid`——至少看得出來「有一支殺不掉的還在跑」。

*類別：spec 沒講。擋路程度：擋路。*

## 5. 補完刀那份 `killed` 狀態檔誰寫？兩章打架，結果是沒人寫

S-08-48／S-08-78 說得很清楚：被殺掉的脫節子地寫不出結果，**必須**在那筆的 `ext.result`
指的落點旁補一份 `<結果落點>.status.json`，`reason` 填 `killed`；S-08-49 還特地把理由寫進 spec——
不補的話，父的 `await` 會一直等一個永遠不會來的結果。

但 S-13-08 說門房收到事件只准做兩件事（記本子、必要時更新登記表），S-13-09 再補一刀：
**禁止改任何一塊地的 `.aos/`**。父的結果落點就在父那塊地上。

於是：門房殺了孤魂 → 沒有人代寫狀態檔 → 父永遠掛在 `await`。
08 章把代寫派給了 daemon，可是這一刀是門房動的，daemon 下次對帳時看到的是一筆
已經 `stopped`、`pid` 是 `null` 的登記，它沒有理由再去代寫。

我照 13 章辦（不發明「補刀」以外的動作），所以這個洞**原型裡是真的開著的**。
要補的話有三條路：門房把「該代寫」記進本子讓 daemon 去做（最合 S-13-08 的精神）、
或把補刀整件事讓給 daemon（門房只記 `gone`）、或給門房開一個「只准寫狀態檔」的例外。
我建議第一條。

*類別：看不見的狀態。擋路程度：擋路。*

## 6. `died_at` 沒有欄位可以放，而且 daemon 下次對帳就會把它刪掉

兩件事疊在一起：

一、`registry.schema.json` 的 entry 是 `additionalProperties: false`，**沒有 `died_at` 這一欄**，
唯一能塞的地方是 `ext`；可是 S-08-66 又把 `ext` 的約定鍵定死成三個
（`result`、`exec_id`、清理紀錄）。我寫進 `ext.died_at`／`ext.died_by`／`ext.killed_pid`／`ext.reborn_at`，
這是自己加的，spec 得認一下。

二、更麻煩的：S-13-18 說門房可以「標 `stopped`」或「整筆刪掉」，二選一；
但 08b 的 S-08-36／S-08-37 對 daemon 講的是**路徑不在就刪那筆登記**，沒有第二個選項。
所以門房好不容易標上的 `stopped` + `died_at`，**daemon 下一次對帳就會把整筆刪掉**，
死亡紀錄活不過一次 `aos daemon start`。想事後查「這塊地什麼時候死的」，
只剩本子那一行 `gone`——但那份本子沒有輪替規則（見第 9 條）。

同一件事兩章給不同預設，得挑一邊：要嘛登記表留墓碑（那 daemon 要改，而且 `aos daemon ls`
得能過濾掉墓碑），要嘛不留（那 `died_at` 這欄就不該存在，死亡紀錄只在本子）。

*類別：看不見的狀態。擋路程度：擋路。*

## 7. 監看範圍那兩條合起來是雞生蛋，而且「根目錄」這個東西 spec 裡沒有

S-13-30：監看登記表裡所有筆的 `path`，加上 `$AOS_HOME` 底下一層的子目錄。
S-13-31：禁止遞迴監看整棵樹，深處的地要被看見必須先進登記表。

合起來：一塊地要被看見出生，得先在登記表裡；要進登記表，得先被看見出生。
剛好躺在 `$AOS_HOME` 底下一層的地是唯一的例外。可是使用者的地根本不會住在家裡——
`~/work/proj/sub` 這種深度 3 的地，門房永遠看不到它出生。

而且這次交代的介面是「盯著**根目錄**底下所有地」，spec 裡從頭到尾沒有「根目錄」這個概念，
也沒說它跟 `$AOS_HOME` 是什麼關係（家可以在根目錄外面嗎？可以有兩個根目錄嗎？）。

我加了 `--depth`（預設 2）自己劃範圍，並且明講：超過這個深度的地，門房看不見。
spec 要嘛給「監看根」一個名字跟一個深度上限，要嘛承認第一級只服務淺的地。

*類別：多餘的動作（要人先手動登記，門房才看得見）。擋路程度：煩。*

## 8. `stopped` 一個字扛四種意思，門房又多塞了一種進去

S-08-29 講得很硬：`stopped` ＝「時鐘停了、地還在」，**禁止**當「地死了」用，
地死了是那筆被刪掉。可是 S-13-18 就是要門房把死掉的地標成 `stopped`。

結果 `aos daemon ls` 上，「跑完了」「被使用者停掉」「剛出生還沒有鐘」「地已經死了」
四種情況印出來都是同一個 `stopped`，得翻 `ext.died_at` 才分得出最後那種——
而 `ext` 在 `ls` 上是不印的。主編在 08 章自己也記了這個矛盾（「一個字通用、細節看 `clock` 與 `pid`」），
但那兩欄分不出「死了」跟「剛出生」：兩種都是 `pid: null`、`clock: null`。

至少 `aos daemon ls` 該把 `died_at` 印出來，不然門房做的事在畫面上完全看不見。

*類別：看不見的狀態。擋路程度：煩。*

## 9. 本子沒有游標、沒有輪替，daemon 每 5 秒重讀整份

S-13-51 說第一版 daemon 必須自己輪詢本子、建議 5 秒一次，S-13-52 說看到某地有 `inbox`
就替它重起一支 run。但 spec 沒說：daemon **記到哪一行**（沒有 offset、沒有游標檔、
行上也沒有單調遞增的 id，只有 `at` 時間戳，同一毫秒兩筆就分不出先後）、
本子多大要**換檔**、換掉的舊本子誰刪。

一台機器上的地一直生一直死，這個檔只會無限長，而 daemon 每 5 秒把它從頭讀一遍。
第一級只寫生死還好，等 S-13-24 的記帳（每個檔的每次寫入都記一筆）做進來就會爆掉。

*類別：多餘的動作。擋路程度：小（第一級），做記帳時變擋路。*

## 10. 退回輪詢之後怎麼回去，沒講

S-13-32 說碰到監看上限要記 `fallback` 並退回巡邏，S-13-33 說退回之後不准結束。
沒說的是：watch 空出來之後**要不要爬回 inotify**？`fallback` 是**只記一次**還是每輪都記
（每輪都記就是洗版）？退回巡邏之後 `--poll-ms` 該用多少（掃全樹的成本跟盯 watch 差一個量級）？

我的選擇：切換的那一刻記一次，之後就一路輪詢到死，不回頭。理由是「回頭」需要一個重試節奏，
而那個節奏 spec 沒給，自己編一個等於多一個沒人知道的行為。

*類別：spec 沒講。擋路程度：小。*
