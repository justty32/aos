← [入口 dotenv-格式比較](../dotenv-格式比較.md)｜涵蓋：選項 X「拿掉 aos 的 `.env`、改在 argv 鏈上接 s6-envdir（或 envdir／chpst -e）」——少掉什麼、多出什麼、刪除工作量、跟 (a) 的關係｜上一份 [03-替代方案與建議](03-替代方案與建議.md)

使用者 10-22 追加：「Hmmm，甚至有可能，有了s6-envdir之後，我們甚至不需要.env了。但還是先調查吧」。這一份把它當成跟 [02](02-aos現況與工作量.md) 的 U／M／Q 並列的一個選項，只調查。

# 1. 三種程度

| 選項 | 內容 |
|---|---|
| (X1) 全拿掉 | `.env` 檔與 JSON 物件的 `.env` key 都不要；要設環境變數就在入口的 argv 前面接 `s6-envdir dir`（或 `envdir`、`chpst -e`），或把它放在 aos-exec 外面 |
| (X2) 只拿掉 `.env` 檔 | 留 JSON 物件的 `.env` key（它是 C-51／C-72「資料夾＝物件」那套的一部分，不靠 dotenv 格式） |
| (X3) 都留（現況） | `.env` 管 PATH 這種要接舊值的，祕密與拿掉變數交給 envdir（[aos-exec-s6-runit 01 § 1](../aos-exec-s6-runit/01-直接呼叫-環境與鎖.md) 原本的建議） |

# 2. 拿掉之後少掉什麼（逐條對照）

| 現在靠 `.env` 的規則 | 條文 | 改成 envdir 之後 |
|---|---|---|
| `${名字}` 展開，`PATH=${AOS_CD}/bin:${PATH}` 接舊值 | N-59 第 4 件「`.env` 的值」、ideas 10-21 § 4.2 E5 | **做不到**：envdir 的值照字面、不展開。使用者 10-21 要 `.env` 的第一個理由就是 PATH（「主要是PATH的問題」）。替代只剩：入口是單子時用 `envs` 加 `{"$env": "PATH", "$prefix": "絕對路徑/bin:"}`（前綴要寫死）、或寫一支小殼（少用 sh） |
| 每走進一層就讀那層的 `.env`，`sub/run` 沿路都讀 | N-59 第 4 件「走進一層」「讀完才挑」 | envdir 只在寫了它的那條鏈上作用；沒有「走到哪讀到哪」 |
| `.env` 設的 `AOS_ENTRY` 對這一層挑入口有作用 | N-59 第 4 件、N-57、ideas 10-21 § 5 | **做不到**：envdir 寫在入口裡，入口已經挑完了。只有放在 aos-exec 外面（`s6-envdir d aos-exec X`）才影響挑入口 |
| 沒 `argv` 的 JSON 物件的 `.env` key（可放指示詞、一路往下） | N-59 第 4 件、N-61、C-73 | X1 沒了；X2 留著 |
| `$env` 指示詞讀得到 `.env` 設的值 | ideas 10-21 § 4.2 E1、N-59 第 4 件「一直有效到真正開跑」 | argv 陣列的指示詞在 exec 之前就解了，**讀不到** envdir 設的值；envdir 之後的子程式才看得到 |
| `.env` 可改 `AOS_*`（含 `AOS_CF`／`AOS_CD`／`AOS_CO`，最後一份設了就不蓋） | N-57、N-59 第 4 件「挑完重設」 | envdir 在 aos-exec 之後才跑，改的只給子程式；「最後一份不蓋」那條整條不需要 |
| 優先順序 旗標 ＞ `.env` ＞ 外面 ＞ 預設 | N-58 | 變回 旗標 ＞ 外面 ＞ 預設 |
| 錯誤 `.env 讀不到`／`.env 壞`（不印值） | N-60 | 不需要；envdir 自己出錯退 111（[03 § 5](../aos-exec-s6-runit/03-借形狀.md)），對 aos 是「其他非 0」 |
| 隱藏檔的例外：讀 `.env` | N-05、C-51 | 例外可刪 |
| 轉向到同資料夾重讀、`PATH` 疊兩層；loop 每拍重讀 | N-59 第 4 件、bin/README | 這些「接受的怪現象」一起消失 |
| 可執行檔入口（`+x` 的程式、殼）也能吃到 `.env` | N-59 第 4 件 | 要嘛入口改寫成 argv 陣列接 envdir，要嘛程式自己設 |

# 3. 多出什麼

- **好處**：一個變數一個檔，各自 `chmod`（C-64 借 Linux 權限，`.env` 一份檔做不到）；空檔＝拿掉（方向題 b 的 unset 直接解）；`-f` 整份檔是值（多行）；不用自己發明引號、跳脫；aos-exec 少一大段規則（C-56）。
- **外部依賴**：agent 資料夾要靠 s6／runit／daemontools 其中一個（方向題 d；demo 現在只靠 `/bin/sh` 與 python3）。Debian／Ubuntu 有套件（universe），Fedora 沒查到、要自己編（[aos-exec-s6-runit 04 § 4](../aos-exec-s6-runit/04-不適合-衝突-方向題-套件.md)）。
- **路徑**：`s6-envdir` 在 `/usr/bin`，照 PATH 找得到；但 execline 那 52 支（`envfile`、`importas` 等，想補「展開」時會用到的）在 `/usr/lib/execline/bin/`，**不在 PATH 上**，argv 裡要寫全路徑或自己加 PATH。daemontools 的 `envdir` 名字短、容易撞名。s6-envdir 預設只讀每個檔前 4096 bytes（`-L` 取消）。
- **寫法變長**：每個要設環境的入口都得是 argv 陣列並以 `s6-envdir` 開頭；同一組變數要給好幾格時，每格都要接一次（或放在最外面）。

# 4. 刪除的工作量

| | Python（bin） | C++（impls，推估） |
|---|---|---|
| 程式 | `aos-exec` 裡 `load_env`、`json_env`、`set_env` 與 `hop` 裡 `layer`／`names`／「最後一份不蓋」那幾段，約 80～100 行（30 處引用）；X2 留 `json_env`、`set_env` | `src/env/dotenv.cpp` 整支，`env.cpp`、`find.cpp` 的 `enter` 裡讀 `.env` 那段，代號 `EnvBad`、`EnvReadFailed`（在 `exec.hpp`，C++ 公開標頭；刪代號要確認沒人依賴） |
| 測試 | `test_exec_env.py` 37 個大多刪；其中測「一路往下、`AOS_CO`、繞圈」的十來個要改寫成不用 `.env`；其他 9 個測試檔有零星 `.env` 引用要看 | 同比例 |
| 條文與文件 | N-57、N-58、N-59 第 4 件（最大的一段）、N-60、N-61 提到 `.env` 處、N-05、C-51、CONVENTION P-39 一帶、bin/README、code map、demo `agent-ann/.env` | — |
| 判斷 | **刪比加大**：10-21 一整天、四輪改動長出來的規則要拆回去，兩版要再逐案比 | |

# 5. 跟 (a)「aos-exec 只用標準庫」的關係

**不衝突**。(a) 管的是 aos-exec 自己不叫外部程式替它做事；X 是把「設環境」這件事整個交給使用者，由使用者在**自己的 argv** 裡接 s6-envdir——aos-exec 只是照字面 exec 那條 argv，跟現在接任何程式一樣。要小心的反而是反方向：如果拿掉 `.env` 之後又想讓 aos-exec「幫忙找 `secrets/` 就自動接 s6-envdir」，那就違反 (a)。

# 6. 一句話

X1 最符合 KISS、也順便解了 unset 與多行，但**丟掉 `${}` 接 PATH 與「`.env` 改 `AOS_ENTRY`」兩件使用者 10-21 明確要過的事**，envdir 補不回來；X2 把這兩件留住——JSON `.env` key 的字串照樣展開 `${名字}`（`{"PATH": "${AOS_CD}/bin:${PATH}"}`），也在挑入口之前套（所以能改 `AOS_ENTRY`）——代價是要用的資料夾得把入口寫成 `_exec.json` 物件（`{".env": {...}, "_exec": [...]}`），少掉的是「一份純文字 `.env`」與它的格式問題（引號、多行那些就不必再談）。X2 的刪除量約是 X1 的一半（留 `json_env`、`set_env`、一路往下的套用邏輯）。要不要走、走到哪一級，使用者定。
