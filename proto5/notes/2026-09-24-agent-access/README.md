← [notes 索引](../README.md)｜[proto5 README](../../README.md)

# agent 的權限與工作環境：提案（2026-09-24）

**只是提案**：沒改程式、沒改規範。要使用者拍的在 [§7](#7-要使用者拍的)。

| 檔 | 內容 |
|---|---|
| 本檔 | 需求、主軸、六題的答案、建議方案 |
| [contract.md](contract.md) | 完整版的契約：誰何時讀表、牢裡看得到什麼、哪些東西工具永遠改不到 |
| [options.md](options.md) | 幾種做法比一比（逃逸路徑表） |
| [env-flow.md](env-flow.md) | 環境變數怎麼流到工具、哪些不該給 |
| [examples.md](examples.md) | 一步步的操作與每種情境要改幾處 |
| [experiment.md](experiment.md)（腳本 [exp/](exp/)） | 小實驗：指示詞做得到哪、bash 逃不逃得出去、bwrap 能不能用 |
| [review-task.md](review-task.md)／[review-astra.md](review-astra.md) | astra 唯讀審查（必修 10 條已改進本提案，見 §8） |

## 需求

amy 的家是 `./amy`；amy 的**工具**能碰指定資料夾（例如 `./workspace/`），碰不到 amy 自己。設定要**常改、好改**：今天換 `./other-workspace`、明天又准碰 `./amy`。
另外兩個案例：共用工具夾 `./util-tools/*.json` 給好幾個 agent 用、amy 可以替工具取別名；workspace 有別名——amy 永遠覺得自己在 `ws/`，實際從 `~/ws-A` 換到 `~/ws-B`，工作邏輯不用換。

**主軸（使用者 09-24 補）**：這些都是「工具存取的別名／映射」，用**指示詞**表達。本提案照這個走：映射一律寫成指示詞；隔離（bwrap）是「指示詞之外加的一道牆」。

## 1. 邊界怎麼定

**一份映射表** `amy/access.json` 寫「amy 看到的名字 → 真的資料夾」：

```json
{"mounts": {"ws": "../workspace", "util": {"$opt": "ro", "$val": "../util-tools"}}, "cwd": "ws"}
```

值可以是任何指示詞（`$env`／`$ref`／`$fmt`），`$opt: "ro"`＝唯讀。表裡沒列的，工具看不到——包括 amy 自己的家。

**指示詞本身擋不住東西**，它只決定工具從哪開始、帶什麼環境。實驗 2：bash 工具照樣 `cat ../amy/secret.txt`、讀絕對路徑、走符號連結、印出 `AOS_KERNEL_HOME` 與金鑰。比了四種牆（[options.md](options.md)）：

| 做法 | bash 關得住？ | 路徑穩定成別名？ | 成本 |
|---|---|---|---|
| 只有指示詞 | 否 | 否 | 0 |
| (a) 工具層檢查（base 包已有） | 否（read 等擋得住） | 否，錯誤訊息印真路徑 | 每支工具自己做 |
| (b1) chdir＋清環境變數 | 否 | 否 | 很小 |
| (b2) bwrap：每次跑工具開一個只掛表裡資料夾的小世界 | **是** | **是**（永遠 `/work/ws`） | 這台已裝，一次 1.3 ms |

**建議 (c)＝指示詞寫映射 ＋ bwrap 當牆 ＋ 工具層檢查給好懂的錯誤。** 牢裡只有三類東西：表裡的資料夾、固定的執行環境（`/usr` 等唯讀）、aos-exec 在牢外開好的三條串流（[contract §2](contract.md#2-牢裡看得到的東西只有三類)）。
擋不住的明講：資料夾裡的 Unix socket、開了網路後的本機服務、人事先佈置的硬連結、沒有資源上限、同批工具互蓋同一個檔。保證的是「路徑是穩定的別名」，**不是**「模型永遠看不到真路徑」。
**沒有 bwrap 的機器，關牢的工具一律拒跑**，不偷偷降級。

## 2. 設定放哪、怎麼改

- **放 agent 家的 `access.json`**（`info.json` 可加 `access` 欄指到別處）。不塞進 `info.json`：改映射不用碰人格與模型，指令也好原子改寫。
- **不用重啟，下一批生效**：tick 每格重讀 `info.json` 與工具檔（[aos-agent §2](../../spec/aos-agent/tick.md)），映射表在**送一批工具時解一次**、整批用同一份（[contract §1](contract.md#1-誰解什麼時候解送件時解一次整批同一份快照)）。已經送出、排隊中、崩潰重送的那批用舊的；正在跑的工具不會被收回權限（要馬上撤的做法也在 contract §1）。
- **指令**（完整版）：`aos-agent access ls｜set NAME PATH [--ro] [--cwd]｜rm NAME --target DIR`；`rm` 目前的 `cwd` 會拒絕，要先 `set 別的 --cwd`。手編 JSON 也行。`aos-agent check` 多驗表、重疊規則與 bwrap。
- 「今天不准碰 ./workspace、明天准」＝一個指令或一行（[examples 例 1](examples.md#例-1今天不准碰-workspace改碰-other-workspace)，每種情境改幾處在 examples 末表）。
- **工具永遠寫不到「信任資料」**：映射表與它 `$ref` 的檔、`info.json`、工具檔與程式、整個 agent 家。可寫的映射跟它們重疊（同位置、祖先、子孫）＝這批工具跑不起來（[contract §3](contract.md#3-信任資料工具永遠不能寫到)）。所以共用工具夾只能唯讀掛，開放 `self` 預設也是**唯讀**（contract §4）。

## 3. 共用工具夾＋別名

- **共用現在就行**：`tools` 直接列 `"../util-tools/bash-edit-a.json"` 或整個資料夾（實驗 3）；也能 `{"$ref": "../shared/where.json#/util_tools"}` 取一個**路徑字串**（實測可行），共用夾搬家時改那一份就好（examples 例 5）。
- **改工具名現在不行**，要規範加選項：`tools` 元素寫 `{"$opt": {"as": {"bash-edit-a": "edit-a"}}, "$val": 路徑}`（另有 `only` 挑幾條）。這就是指示詞的 `$opt`（選項由宿主規範定），衝突在 agent 規範現在寫「沒有欄位吃 `$opt`」，要改；aos-agent 與 `aos-llm call` 共用讀工具的程式，兩邊看到同一個名字。
- **模型看不到檔名**，只看到 `function.name`：「amy 看到 `edit-a.json`」實際是「amy 看到 `edit-a` 這個工具」。
- **路徑相對誰**：`_meta` 的 `cwd` 裡的 `$ref` 相對 agent 家（所以共用檔會自動找**各自**的表，實驗 1 #3）；寫了 `cwd` 之後，其他欄位的相對 `$ref` 改以新的 cwd 為中心。完整版不用管：程式路徑由 aos-agent 交給 `aos-jail --tool`，牢裡掛到 `/opt/tool`。
- **撞名**：改名後撞名＝`ToolInvalid`，照現行「同名」規則列兩邊並講是改名造成的；`as` 寫了檔裡沒有的名字也算錯。

## 4. workspace 別名

- chdir＋相對路徑：`pwd`、錯誤訊息漏真路徑；記憶裡一有 `/home/u/ws-A/…`，換成 ws-B 後 bash 還會照舊路徑寫 ws-A——**換掉的 workspace 其實還碰得到**。
- symlink：`realpath` 看得穿，base 的 read 還會拒絕連結指出根目錄。不採用。
- **mount namespace（bwrap）**：牢裡永遠 `/work/ws`，換 ws-B 只改表的一行，工具看到的路徑一個字不變（實驗 2d、4）。**採用**。
- 記憶：工具路徑都是 `ws/…`，沒有舊路徑要清；換 workspace **不清記憶、不自動通知**，內容換了要她知道就 `say` 一句。

## 5. 環境變數

工具跑在它那顆 cpu 上，**整包繼承 cpu 的環境**（＝開 daemon 那一刻的終端環境＋kernel.json 的 envs）。照 proto5 README 的開機步驟，`AOS_KERNEL_HOME` 在開 daemon 前就 export，所以工具通常拿得到它——拿到就能往 kernel 丟工作、叫別的池（含 llm 池）替它跑。圖與清單在 [env-flow.md](env-flow.md)。
工具只給 `PATH`、牢裡的 `HOME`、`LANG`、工作根目錄；`AOS_*`、模型金鑰、`SSH_AUTH_SOCK` 一律不給。最省：每支工具 `_meta.envs` 寫 `clear`（現有指示詞做得到）；bwrap 再 `--clearenv`，而且根本不掛 K 與 llm.json。

## 6. 建議方案

**指示詞寫映射，bwrap 當牆。** 一份 `access.json` 說「amy 看到什麼名字、對到哪、能不能寫」；aos-agent 送工具時把它解好，交給小包裝 `aos-jail` 開一個只有這些資料夾的小世界。
理由：使用者要的是別名，mount namespace 是唯一讓別名**真的成立**的做法；牆與設定是同一份表，改一行同時改映射與邊界；這台現成、1.3 ms。

**最小版（現在的 proto5，不改 aos 程式）**——實驗 4 已跑通：`amy/access.json`＝`{"ws": "/home/u/ws-A"}`；base 的 `tools/base.json` 七支工具的 `_meta.argv` 前面接 bwrap 參數，其中 `--bind {"$ref": "access.json#/ws"} /work/ws`；`envs` 寫 `clear`；base 的 `config.json` 寫 `{"root": "/work/ws"}`。
限制：只有一個 ws；要加別的資料夾得改七條 argv；沒有改名、沒有 `access` 指令；**只有 base 七支關牢**，其他工具不受保護；`/etc` 等掛法照 contract §2 收緊。工作：base 隊的 `tools add` 多一個 `--jail`，約半天。

**完整版（新版 aos-agent）**：

| 改什麼 | 檔 | 量 |
|---|---|---|
| 映射表格式、信任資料與重疊規則、`self` 預設唯讀 | 新 `spec/agent/access.md`；`agent/layout.md`、`agent/info.md`（`access` 欄；舊程式會忽略） | 小 |
| 送件時解表、存 `batch.access`、把工具包成 `aos-jail …`；`AccessUnsafe` | `aos-agent/send.md` §5.1～5.3、`agent/state.md` §4.3；`lib/aos_agent_batch.py` | 中 |
| `tools` 元素的 `$opt`：`as`、`only`（兩端共用、來源資訊放內部結構不送模型） | `agent/info.md` §3、§3.3、`agent/errors.md`；`lib/aos_agent_home.py`、`aos_agent_batch.py` | 中 |
| 新程式 `aos-jail`：照參數組 bwrap（不讀表）、掛 `/opt/tool`、清環境、沒 bwrap 退 126 | 新 `spec/aos-jail/`；`lib/aos_jail.py`＋`cli/aos-jail`＋測試 | 中（約 150 行） |
| `aos-agent access ls/set/rm`；`check` 驗表、重疊、bwrap | `aos-agent/cli.md`、`cli-check.md`；`aos_agent_cli.py`、`aos_agent_check.py`、新 `aos_agent_access.py` | 中 |
| base 包：根目錄可由環境變數給、錯誤訊息印別名 | `proto5/tools/README.md`、`tools/base/_common.py` | 小（另一隊） |

約 2～3 天（含測試與一輪試玩）。跟 proto5-2 不衝突：它只改 kernel／daemon 的池，工具環境仍是「池的環境＋`_meta.envs`」。
**對齊 base 工具包**：他們的工作根目錄＝`config.json` 的 `root`（預設 `<家>/workspace`），bash 關不住（他們自己寫明）。不要他們改做法，只要根目錄可由環境變數覆蓋、`OutsideRoot`／`RootMissing` 別印真路徑。注意他們預設的 `<家>/workspace` 在 agent 家裡：完整版要映射它，得先過信任資料的重疊規則（它自己不含信任資料就行，但 bash 看不到家其餘部分）。

## 7. 要使用者拍的

| # | 題目 | 我的預設 |
|---|---|---|
| 1 | 沒有 bwrap 的機器 | 關牢的工具**拒跑**，模型看到「跑不起來：沒有 bwrap」、`check` 標 bad |
| 2 | 開放 amy 自己 | `self` 一律**唯讀**；要她寫就另映射一個家外的資料夾（例 `amy-notes`） |
| 3 | 牢裡預設有沒有網路 | **沒有**；表裡 `"net": true` 打開（打開＝共用主機網路，本機 LiteLLM 也連得到） |
| 4 | 工具改名的寫法 | `tools` 元素 `{"$opt": {"as": {原名: 新名}}, "$val": 路徑}`，另有 `only` |
| 5 | 映射表放哪 | agent 家的 `access.json`；`info.json` 的 `access` 欄可指別處 |
| 6 | 改表何時生效 | **下一批**（送件時解一次、整批同一份）；正在跑的不收回 |

## 8. 審查改了什麼

astra 必修 10 條：沒 bwrap 統一拒跑（1）；信任資料與重疊規則（2）、`self` 改預設唯讀（3）、受控串流列為例外（4）、牢裡三類資源與不整份掛 `/etc`、socket 與網路（5）→ [contract.md](contract.md)；生效時機改成「送件時快照、下一批」（6）；`rm` 目前 cwd 要拒絕、各情境手續表（7）→ examples；aos-jail 不讀表、由 aos-agent 給參數、牢外 cwd 與牢內 `--chdir` 分開（8）；共用夾搬家的例子（9）；`$opt` 兩端共用、來源資訊不送模型（10）。建議 4 條也照改（實驗結論範圍、環境流向措辭、check 分內外、平行與資源限制）。
