# 2026-10-01 草稿：最核心的 aos-daemon

← [筆記索引](README.md)｜[第二十批裁定篇末 10-01](verdicts/11-tick-as-unit.md#2026-10-01poc-默認一切正常)｜[daemon 拆分](2026-09-30-daemon-split-and-multi-daemon.md)｜[plan 第三段](../plan/README.md#第三段daemon-核心)

**草稿，未裁定。** 這份只是提案，spec、plan、程式都沒照它改。前提是現在這個極簡 `aos-tick`（10-01 版：碼只有 0／1／2、有同資料夾鎖、默認一切正常），再照同樣的「先做單純的」精神，把 spec 的「開格核心 A 組」砍到最小。

## 一句話

最核心的 daemon 就是「一個懂 node 清單的 cron」：讀一份設定檔，對清單上每個 node 照週期叫一次 `aos-exec <node>`，等它結束、記下結束碼、隔一個週期再叫。沒有 socket、沒有登記、沒有收屍。

## 最少要做的四件事

**知道有哪些 node。** daemon 要有一份清單才知道該叫誰。最簡單是設定檔裡寫死一份清單，改了就重開 daemon。這件砍不掉，沒有清單就沒有事做。

**照週期叫一格。** 每個 node 有自己的週期（`interval_ms`，毫秒）。上一格結束後隔一個週期再叫下一格，daemon 剛開起來時每個 node 先立刻跑一格。這是 daemon 存在的理由，砍了就什麼都不剩。

**同一個 node 不自己疊著叫。** daemon 替每個 node 最多只開一個子程序，還沒結束就不開下一個；不同 node 之間各跑各的、同時跑，一個卡住不拖累別人。tick 自己的鎖（像門把上的「使用中」牌子）已經保證同資料夾不會兩格一起跑，daemon 這條只是不白開程序。它也砍不掉，因為「等子程序結束」本來就是看結束碼必經的一步，順手就做到了。

**看結束碼、印一行。** 每格結束時印一行到 stdout，例如 `node=/n/a exit=0 ms=812`。結束碼（程式結束時交回的一張回條）怎麼解讀見下面。這是唯一看得到「各 node 跑得怎樣」的地方，砍了就等於瞎跑。

## spec A 組裡哪些先不做

跟 aos-tick 今天的簡化一樣分三種：留、砍（以後要再加回來）、默認不會發生（不寫處理，真發生就自然出錯）。

| spec 的東西 | 最核心版 |
|---|---|
| 定時開格（B-607 定期那段） | 留，週期從上一格結束起算、不補跑 |
| 頂層從設定載入（B-606） | 留，只剩這一條路，清單是平的、沒有上下層 |
| 看結束碼 | 留，但只印一行，不因此停 node（見下） |
| 不疊著開同一 node（B-601） | 留 |
| 擋板檔（B-607） | daemon 不看，交給 tick：有擋板 tick 自己回 2 |

| spec 的東西 | 最核心版 |
|---|---|
| 登記／解除／換父、覆蓋上層、身分額度（B-606） | 砍；清單只從設定來 |
| 叫醒（`node.wake`）、socket 與 IPC 封包、授權 | 砍；第一個值得加回來的就是叫醒 |
| 暫停／恢復（`node.pause`） | 砍；要停某個 node 就放擋板檔，tick 會回 2 |
| 通道與憑證（B-612，給格內任務的臨時通行證） | 砍；沒有 socket 就沒有通道 |
| runner 與收屍（B-601，替每格善後的保母） | 砍；改叫現成的 `aos-exec` |
| 收尾寬限、排空停機（B-604） | 砍；Ctrl-C 就直接退出（見下） |
| `state.json` 存讀、PID 提示檔、boot id、格次序號（B-603、B-607） | 砍；重開就是重讀設定、從頭來 |
| 事項（attention）、最近一格查詢 | 砍；只有 stdout 那一行 |
| 熱重載、helper、cgroup、訊息、`--firstdo-fsync` | 砍（本來就是部件或 POC 不做） |

| 默認不會發生 | 真發生時 |
|---|---|
| 開格失敗（找不到 `aos-exec`、權限不夠） | 照結束碼 1 那樣印一行，下個週期再試 |
| 兩個 daemon 管同一個 node（B-611 的排他鎖） | 不取鎖；兩邊輪流撞到 tick 的鎖、回 2，只是互相拖慢 |
| 設定檔讀不到或寫壞 | 自然丟錯、daemon 回 1 |

## 怎麼叫 aos-tick

**建議照使用者的圖像，叫 `aos-exec <node>`，不直接叫 `aos-tick`。** `aos-exec` 會找 `<node>/.aos/inst.json`，那份 inst 的 `argv` 第一個是 `aos-tick`。inst 的工作目錄預設就是 node 資料夾，所以 `argv` 寫 `["aos-tick"]` 不用帶 `--node`（tick 省略時用 `./`）。好處是 daemon 完全不必知道 tick 長什麼樣，「這個 node 怎麼跑」（環境變數、stderr 往哪、要不要包一層）全由 node 自己的 inst.json 決定；daemon 等於把 cron 換掉，node 那邊一個字都不用改。

**代價有三個。** 每個 node 要有兩份檔（`inst.json` 管怎麼跑、`tasks.json` 管跑什麼）。inst 的 stderr 預設接 `/dev/null`，tick 印的 `busy:`、`bad_table:` 會看不到，建議 daemon 帶 `aos-exec --stderr -`，讓 tick 的 stderr 直接進 daemon 的終端。最麻煩的是 `aos-exec` 自己的碼還沒照 0／1／2 慣例改：用法錯（例如 node 底下根本沒有 inst.json）回 2，會被看成「正常中斷」，跟 tick 的 busy 分不出來。

**直接叫 `aos-tick --node <node>` 是另一條路**：每個 node 只要一份 `tasks.json`，碼也乾淨。但 daemon 就綁死在 tick 上，跟 cron 的圖像不一致，node 想改跑法只能改 daemon。

node 清單從設定檔來，一份就好。最小長相（欄位名照 spec P-101，方便以後長大；spec 的其他欄位寫了也當不認得、忽略）：

```json
{
  "version": 1,
  "roots": [
    {"node_id": "/home/u/nodes/a", "interval_ms": 60000},
    {"node_id": "nodes/b", "interval_ms": 5000}
  ]
}
```

`node_id` 可以寫相對路徑，以設定檔所在的資料夾為準，daemon 開起來時轉成絕對路徑。`interval_ms` 這版必填：spec 允許省略、只靠叫醒，但最核心版沒有叫醒，省略就永遠不會跑。指令是 `aos-daemon --config F`（POC 先用獨立指令，`aos daemon` 子命令以後再接）。

## 怎麼看 0／1／2

**0（照表跑完或停格檔停下）**：照常，隔一個週期再叫。

**2（上一格還在跑、或有擋板檔）**：也照常，隔一個週期再叫，不停 node、不重試。這跟 spec 原本「75 當普通結束」是同一個意思，只是碼換成 2。擋板檔因此兼當「暫停」：人手放上去，這個 node 每個週期都回 2、什麼都不做；拿掉就恢復。

**1（tick 自己壞了，例如任務表格式錯）**：建議**不停 node**，印一行、隔一個週期照叫。理由是最核心版沒有「恢復」的按鈕，停了只能重開整個 daemon；而 tick 壞通常是有人把表寫錯，修好後下一格自己就好了。代價是壞著的 node 每個週期都會印一行錯。其他碼（`aos-exec` 的 125、126、127，被訊號殺的 128 以上）照結束碼慣例一律當 1 看，行裡照實印原碼。

## 跟現在的 aos-tick 哪裡對不太上

**tick 被殺時任務會留下來。** tick 開每一項時讓任務自成一個 session（自己一組，不跟 tick 同進退），tick 也沒有接 SIGTERM。所以 tick 被殺，正在跑的那一項還活著；tick 的鎖又不傳給任務，下一格拿得到鎖，就會跟這個舊任務同時跑。紀錄也會停在 `ended:false`。**建議現在不處理**：最核心版的 daemon 從不殺 tick（沒有逾時、沒有收尾），只要它開子程序時也讓子程序自成 session，Ctrl-C 就只打到 daemon、打不到 tick，這情況就不會因 daemon 而發生。等要加收尾時，再決定是讓 tick 收到 SIGTERM 時轉給正在跑的任務並等它，還是照 spec 做 runner。

**沒有逾時。** 任務卡住，那個 node 就一直卡著；daemon 不開它的下一格，但別的 node 照跑。`aos-exec` 有 `--timeout-ms`，但它只殺得到 tick 那一組，殺不到任務（同上一段），用了反而製造重疊。**建議現在不處理、也不帶 `--timeout-ms`**，卡住就靠人看 stdout 發現（某個 node 很久沒有新的一行）。

**任務在背景留下的程序沒人收。** 任務 `sleep 999 &` 之後結束，tick 不管、daemon 也不管，那個 `sleep` 就一直在。這在 spec 裡是 runner 的工作。**建議現在當成「默認不會發生」**，跟 plan 第一段「核心不清後代，測完自己殺」一致。

**鎖對 daemon 是好事。** tick 拿不到鎖回 2，daemon 當普通結束；兩個 daemon 誤管同一個 node、或有人手同時跑，都不會壞。不需要改。

**`aos-exec` 的碼。** 上面講過：用法錯回 2 會跟 tick 的 busy 撞在一起。**建議趁做 daemon 時一起把 `aos-exec` 的碼改成慣例**（用法錯 1、自己失敗 1，這本來就在 verdicts 待改清單上）；不改的話，node 少了 inst.json 會被當成「忙」默默跳過。

`AOS_DIRNAME` 不用另外處理：daemon 不讀 node 裡的任何檔，環境變數照常傳給 `aos-exec` 和 tick。

## 跟 cron + aos-exec 比，多了什麼

老實說幾乎沒有。cron 每個 node 一行 `* * * * * aos-exec /n` 就能做到同樣的事，tick 的鎖已經擋住重疊。最核心 daemon 多出來的只有：週期可以短於一分鐘、從上一格結束起算而不是對齊時鐘、清單在一個檔裡、所有 node 的結果印在同一個地方、卡住時不會每分鐘多開一個馬上回 2 的程序。這些都是方便，不是能力。

**第一個值得加的是叫醒**（像按門鈴：別人叫它現在就跑一格，不等週期）。這是 cron 根本做不到的事，也是 spec 裡上層叫醒下層、kernel 樹能動起來的前提。最小做法是開一個 socket，只收一種請求 `node.wake {node_id}`，不驗身分、只靠 socket 檔的權限；正在跑時合併成「跑完再跑一次」。第二個值得加的是收尾和收屍（tick 被殺時任務跟著走、格後清掉留下的程序），那時才需要動 tick 或做 runner。

## 要使用者裁定的點

- **叫 `aos-exec` 還是直接叫 `aos-tick`？** 建議 `aos-exec <node>`，照使用者的圖像，daemon 等於可以換掉 cron。後果：每個 node 兩份檔；要帶 `--stderr -` 才看得到 tick 的錯；最好同時把 `aos-exec` 的碼改成慣例。
- **tick 回 1 要不要停 node？** 建議不停，每個週期照叫、印一行。後果：壞掉的 node 會重複印錯；換來不需要「恢復」機制。
- **tick 回 2 怎麼辦？** 建議當普通結束、下個週期照叫，擋板檔兼當暫停。後果：daemon 不需要自己看擋板檔，也不需要 pause。
- **週期怎麼算？** 建議從上一格結束起算、不補跑漏掉的格，daemon 剛開時每個 node 立刻跑一格（照 spec B-607、B-603）。後果：週期是「間隔」不是「時刻表」，跑得慢的 node 實際頻率會變低。
- **Ctrl-C 時正在跑的格怎麼辦？** 建議 daemon 直接退出、不殺也不等（子程序自成 session，不受 Ctrl-C 波及）。後果：退出後那幾格會自己跑完；馬上重開也不會重疊，因為撞到 tick 的鎖會回 2。
- **第一版要不要有 socket？** 建議完全不要，連叫醒都等第二步。後果：第一版跟 cron 能力相同，只能觀察 tick 跑得對不對。
- **設定檔長相。** 建議沿用 spec 的 `version`／`roots`／`node_id`／`interval_ms`，`node_id` 可相對（以設定檔所在資料夾為準），`interval_ms` 必填，其他欄位忽略。後果：以後長回 spec 那份設定不用改名，但最核心版看到 `socket_path`、`identity_grant` 會默默不理。
- **`aos-exec` 的碼這輪要不要改？** 建議跟 daemon 一起改成 0／1／2。後果：從 proto5 複製來的 aos-exec 開始跟 proto5 分岔，測試要跟著改。
