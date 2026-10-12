# proto8-1/demo — 用 daemon 跑一棵 tasks 樹

← [proto8-1](../README.md)｜daemon：[proto8/lib](../../proto8/lib/README.md)｜daemon 自己的 demo：[proto8/demo](../../proto8/demo/README.md)

拿 [aos-seq／aos-par／aos-if／aos-not](../README.md) 組一段像真的的流程，丟給 proto8 的 daemon 跑，目的是看這套原語**實際寫起來缺什麼、哪裡繞**（最後一節）。

```
python3 proto8-1/demo/run.py
```

從哪裡跑都行，約 3.5 秒。只用 Python 標準庫和 `sh`、`cat`、`sleep`；看行程數那段讀 `/proc`，所以要 Linux。

## 場景

「上線前檢查」：服務要第 3 次檢查才會好。

```
pipeline = seq  reset  retry  work  finish
retry    = if   (not check)  again          ← 檢查沒過才跑 again；過了＝沒 ELSE＝0
again    = seq  budget  pause  retry        ← 指回 retry 自己，就是重試迴圈
work     = par  report  notify              ← 兩件事一起做
```

| 步驟 | 做什麼 | 怎麼傳值 |
|---|---|---|
| `reset` | `tries` 寫 0，清掉上次的產物 | — |
| `check` | `tries` 加一；到了 `READY_AT` 次就印版本號、回 0，不然回 1 | 版本號寫到 `probe.out`（stdout） |
| `budget` | `tries` 到了 `MAX_TRIES` 就回 3（放棄） | — |
| `pause` | `sleep 0.3` | — |
| `report`、`notify` | 讀版本號，各寫一行（各 sleep 0.5，看得出是並行） | stdin＝`probe.out`，stdout＝`report.txt`／`notify.txt` |
| `finish` | 把兩份接起來，加上試了幾次 | 寫 `summary.txt` |

參數：最上層 `pipeline/inst.json` 的 `envs` 給 `MAX_TRIES`、`READY_AT`，一路繼承下去；`check`、`budget` 的 argv 用 `{"$env": "READY_AT"}`／`{"$env": "MAX_TRIES"}` 拿成 `$1`。

跑三個實例（一個跑完才 add 下一個，它們共用同一個 work 資料夾）：

- `pipeline`：MAX_TRIES=4 → 第 3 次過，並行兩件、收尾，`last_code` 0。
- `pipeline-fail`：argv 用 `{"$ref": "pipeline/inst.json#/argv"}` 借同一棵樹，MAX_TRIES=2 → 重試用完，`last_code` 3，`work`／`finish` 都沒跑。
- `pipeline-broken`：同一棵樹，**忘了給 READY_AT** → 看錯誤從哪裡冒出來（見發現 1）。

## 檔案

- `run.py`：mktemp 開暫存資料夾（`ctl/` 控制資料夾、`work/` 步驟間傳的檔、`log` 收 stderr），起 daemon（cwd＝本資料夾、PATH 前面加 `../bin`），一個個 `add`、每 0.2 秒 `get` 等到 done，印 `last_code`、log、work 裡的檔；旁邊一條執行緒每 50ms 數一次活著的 tasks 程式。最後 SIGTERM daemon、等它結束，再刪暫存資料夾。
- `daemon.json`：`control_dir` 寫成 `{"$env": "DEMO_CTL"}`。
- `pipeline/inst.json`（最上層）和 `pipeline/*/inst.json`（11 個步驟，一個資料夾一個）、`pipeline-fail/inst.json`、`pipeline-broken/inst.json`。

## 會看到什麼

```
[ 0.1s] → 01-add.json  {"op": "add", "id": "pipeline"}
[ 1.8s]      ok   {"id": "pipeline/inst.json", "state": "done", ..., "runs": 1, "last_code": 0, "last_error": null}
[ 1.8s]    取樣看到最多 7 支 tasks 程式同時活著：aos-seq → aos-if → aos-seq → aos-if → aos-seq → aos-if → aos-not
[ 1.8s]                   check 第 1 次：還沒好
[ 1.8s]                   check 第 2 次：還沒好
[ 1.8s]                   check 第 3 次：好了
[ 1.8s]    summary.txt  報告：v1.4.2 檢查通過
[ 1.8s]                 通知：v1.4.2 可以上線
[ 1.8s]                 共試了 3 次
[ 2.7s]    last_code ＝ 3                          ← pipeline-fail
[ 2.7s]                   budget：試了 2 次（上限 2），放棄
[ 2.7s]    probe.out                               ← 空的：失敗那次把它蓋掉了
[ 3.3s]    last_code ＝ 125                        ← pipeline-broken
[ 3.3s]                 EnvironmentVariableMissing: …/proto8-1/demo/pipeline/check/inst.json:/argv/4 的 $env 找不到變數 READY_AT
[ 3.3s]                 OpenFailed: 串流開不了：[Errno 2] No such file or directory: '/tmp/aos-demo-…/work/probe.out'
[ 3.3s]                 OpenFailed: 串流開不了：[Errno 2] No such file or directory: '/tmp/aos-demo-…/work/probe.out'
[ 3.5s] daemon 結束，退出碼 0
```

行程數是取樣，每次跑看到的可能少一兩支。

## 寫起來的發現

照嚴重程度排。前兩條會**默默給錯的結果**，其他是繞或缺。

1. **`if (not X) Y` 沒寫 ELSE，X 起不來會被當成「成功」。** `retry = aos-if not-check again`：check 起不來時，aos-not 印錯、回 125（不反過來），aos-if 只看到「條件非 0」＝不成立，沒 ELSE 就回 0。也就是**檢查根本沒跑，retry 卻回成功**，流程繼續往下。demo 的 `pipeline-broken` 就是這樣：錯在 check，`last_code` 125 是後面 `report` 開不了 `probe.out` 才「碰巧」攔下來的；要是 work 不讀 probe.out，整條會回 0。根源：「自己出錯 127／126／125」只在**那一層**算數，往上一層就只是一個非 0 的碼，if 分不出「條件不成立」和「條件那支程式壞了」。安全寫法是 `aos-if check ok again`，但得多一個 `["true"]` 的空步驟。
2. **失敗的那次會把上一次好的 stdout 蓋掉。** stdout 是跑之前就開檔（覆寫），check 每試一次就清空一次 `probe.out`。`pipeline-fail` 跑完 `probe.out` 是空的。這個 demo 剛好是「最後一次成功才往下走」所以沒出事，但如果想「沒過就沿用上一次的值」就做不到；要嘛 append（就得自己找最後一行），要嘛 check 寫暫存檔、成功才改名（又要 shell）。
3. **重試（一個概念）要 5 個 inst 檔＋一個計數檔＋一個 reset 步驟。** retry、not-check、again、budget、pause 各一個資料夾；次數只能用 `tries` 檔＋ sh 算術；pipeline 開頭還得有 reset 把它歸零（不然 daemon 重跑或另一個實例會接著上次的數）。整棵樹 12 個 inst 檔，換成 sh 大概 10 行。
4. **每重試一次，行程樹深兩層，而且都是 Python。** 自己指自己是真的遞迴，不是迴圈：試到第 3 次時同時活著 7 支 tasks 程式（seq → if → seq → if → seq → if → not），每支一個 Python 直譯器。MAX_TRIES 寫 100 就是 200 層；忘了 budget 就是無限長下去，直到資源用完。`pipeline` 的 sleep 加起來 1.1 秒，跑完要 1.7 秒，多出來的大多是起 Python。
5. **最上層 `last_code` 看不出是哪一步、什麼原因。** fail 回 3 是 budget 的碼；check 自己是 1，但被 budget 蓋掉了，「真正的失敗原因」丟了。broken 回 125，可能是任何一層的「自己出錯」，也可能是某個子程式自己回 125。只能去翻 stderr。daemon 的 `get` 也沒有「哪一步」的資訊。
6. **沒有 finally。** 想要「不管成敗都收尾、但保留原本的碼」：`if main finish (seq finish false)` 會把碼變成 1；seq／if／not 這三支只會把碼壓成「0／非 0」或「第一個非 0」，原本的碼帶不過去。demo 只好讓 finish 只在成功時跑（`pipeline-fail` 沒有 summary）。
7. **（已修，10-12：`resolve()`／`parse()` 加 `ident`，load 給 inst.json 的 realpath）錯誤訊息不講是哪個檔。** `EnvironmentVariableMissing: <input>:/argv/4 的 $env 找不到變數 READY_AT`——14 個 inst 檔裡哪一個？是 aos_inst 的 `parse()` 用 `resolve(doc, base_dir)` 解，指示詞 lib 只知道 `<input>`。巢狀起來就要自己猜（這裡是 check 的，得從 `argv/4` 和變數名自己推；log 裡也沒寫是哪支 tasks 程式印的）。
8. **stderr 預設接 /dev/null，每一層都要寫 `stderr_inherit: true`。** 11 個步驟寫了 10 次（pause 沒寫）。中間有一層漏了，下面所有的錯（包括 tasks 自己的「代號: 白話」）就全部無聲消失。最上層還得指定一個檔，daemon 本身不收子程式的輸出。
9. **相對路徑全部從「呼叫者的 cwd」算，不是從 inst.json 所在的資料夾。** tasks 的 TARGET、`$ref` 的檔名、`cwd` key 都是。所以 daemon 的 cwd 一定要是 demo 資料夾，每個 tasks 的 argv 都要寫 `pipeline/xxx`；整棵樹改個名字就得改 5 個檔（再加兩個變體的 `$ref`），換個 cwd 起 daemon 就全部 `NotFound`。而 leaf 想在別處（work）跑，又只能靠 `{"$env": ...}` 把 cwd 拉走。
10. **指示詞沒有字串拼接。** 想在 envs 寫 `PATH = <bin>:$PATH` 做不到（`$env` 只能拿整個值）；想把 log 寫到 `$DEMO_WORK/log` 也做不到。只好讓 run.py 從外面把 PATH、`DEMO_LOG` 整條準備好塞給 daemon。用絕對路徑寫 argv[0] 則 inst.json 就綁死在這台機器的 repo 位置。
11. **變體只能借整個欄位，不能「繼承再改一個 key」。** `pipeline-fail` 用 `$ref` 借 argv，但 `stderr`、`stderr_append` 得照抄一次；沒有「整份拿過來、只蓋 envs」的寫法。反過來，參數只能從最上層的 envs 一路往下漏，所有子孫都看得到、沒有範圍。
12. **兩個實例會撞在同一個 work。** 步驟間傳值靠檔名（`tries`、`probe.out`），而 work 資料夾來自 daemon 的環境變數，又不能拼接（第 10 條），所以要每個實例自己一個 work，只能在 daemon 起來前就替每個實例備好一個環境變數。demo 只好一個跑完才 add 下一個。par 的兩個分支也一樣：寫同一個 stdout 檔會互蓋，得各寫各的再用 sh `cat` 接起來；stdin 也只能接一個檔。
13. **「先全部驗過才跑」只驗一層。** aos-seq 起來時只讀它自己的 4 個 TARGET；`again` 裡的 `budget` 拼錯字，要等第一次檢查失敗、跑到那層才會發現（這時已經跑了 reset 和一次 check；回 125，跟第 5 條一樣看不出是哪層）。巢狀的好處（不用新語法）同時也是這個代價。
14. **daemon 的 `times` 不能當重試用。** `times: 4` 是「固定跑 4 次」，第 1 次成功了照樣再跑；沒有「失敗才再跑」。所以重試只能做在 tasks 樹裡（第 3、4 條）。daemon 這邊要知道跑完了，也只能自己每 0.2 秒 `get` 一次，沒有等待或通知。
15. **小地方**：重試之間要等，只能多一個 `sleep` 步驟；`add` 一個資料夾 id，回覆和 `get` 都變成 `…/inst.json`（比對 id 要先轉）。

沒發現 proto8/lib 或 proto8-1/lib 的程式 bug：上面都是照文件寫的行為，只是寫起來的後果。

**處理（10-12）**：第 7 條已修。第 1、2、6 條（if 吃掉「條件壞了」、stdout 被蓋、沒有 finally）維持現狀：tick-tock 定了「甲」（就是時鐘，不包任務），不需要「tock 一定要跑」；使用者也說控制流原語多半不必要、以後控制流可能都在 argv[0] 的程式裡，原語不再加。第 3、4、14 條算「要 while／retry」的證據，原語先不加。第 8、9 條碰 inst 的基本規則（沒寫的串流接 /dev/null、基準是呼叫者 cwd），第 10、11 條是指示詞（不做字串拼接），維持現狀。
