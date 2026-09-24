← [agent](README.md)｜[spec 總導航](../README.md)｜送件怎麼包牢：[aos-agent access.md](../aos-agent/access.md)｜牢本身：[aos-jail](../aos-exec/aos-jail.md)

# 3.5 `access.json`：工具關進牢裡看得到哪些資料夾（09-24 access-impl）

```json
{"_metainfo": {"_type": "agent_access", "_version": 1},
 "mounts": {"ws": "workspace", "ref": {"$opt": "ro", "$val": "~/docs"}},
 "cwd": "ws",
 "net": false}
```

**有這個檔＝這個家的工具一律關牢**（`_jail: false` 的那支除外，[§3.3](info.md)）；**檔不存在＝不關牢**，照舊在 agent 家跑、碰得到跑它的人碰得到的所有檔。

## 位置

`<家>/access.json`；`info.json` 可有 `access` 欄（路徑字串，可用指示詞，相對 agent 家）指到別處。
`access` 欄明寫了、檔卻不在＝`AccessInvalid`（不當成「不關牢」，免得打錯字就放行）。

## 欄位

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `_metainfo` | 物件 | 可省 | 有寫就要 `_type: agent_access`、`_version: 1`（整數，bool 不算） |
| `mounts` | 物件 | `{}` | key＝牢裡名字，掛在 `/work/<名>`；值＝路徑 |
| `cwd` | 字串 | 起點 `/work` | 工具在牢裡的起點＝`/work/<cwd>`；要是 `mounts` 裡的名字 |
| `net` | bool | `false` | `true`＝共用主機網路（連得到本機服務、區網，不只是「能下載」） |

- 頂層其他 key＝`AccessInvalid`（抓 `mount`、`network` 這類手誤）。頂層要是字面物件。
- 名字：`[a-z0-9_-]+`（所以不會是 `.`、`..`）。
- 值：路徑字串、指示詞（`$env`／`$ref`／`$fmt`，解完是字串），或選項物件 `{"$opt": "ro", "$val": …}`（唯一選項 `ro`，`$val` 必帶、可再是指示詞）。沒寫 `ro`＝可寫。
- 路徑怎麼算：先解指示詞（**中心＝agent 家**，`$env` 用跑 tick 那格的環境，跟解工具 `_meta` 同一套）→ `~` 展開 → 相對的算 agent 家 → realpath。**要存在而且是資料夾**。
- `cwd`、`net`、`_metainfo` 也可以用指示詞，解完型別要對。

## 錯誤

錯一律「代號: 白話」，白話帶 access 檔路徑與欄位位置（例如 `access 檔 /home/u/amy/access.json 的 mounts.ws：…`）：

- 格式錯、路徑不在、指示詞解不過＝`AccessInvalid`（指示詞原本的代號寫在白話裡）。
- access 檔本身不是 JSON＝`JsonSyntax`，帶「第 N 行第 M 欄」；讀不到＝`ReadFailed`。
- 可寫的 mount 碰到信任資料＝`AccessUnsafe`（下面）。
- 家裡沒 bwrap＝`NoBwrap`（送件時才查，[aos-agent access.md](../aos-agent/access.md)）。

## 信任資料：工具永遠寫不到

會決定「權限」或「跑什麼」的東西。集合 T 的每一項都收：引用的路徑途中**每一個符號連結本身**（上層資料夾解開後的位置）＋最終 realpath——只保護目標不夠，連結放在可寫的地方，工具就能把連結換成別的檔。

- access 檔本身＋它 `$ref` 到的每個檔；`info.json`＋它 `$ref` 到的檔；
- 人格檔、記憶檔；`tools` 列到的每個檔與資料夾、合併後每個工具檔；每支工具程式（`_meta.argv[0]` 含 `/` 者，照 `_meta` 的 cwd 算）realpath 所在的資料夾；工具 `_meta` 裡字面寫的 `$ref` 檔；
- **aos 自己在牢外跑的程式**：這份 proto5 的 `cli/`（`aos-jail` 在這裡）與 `lib/`（`aos-jail`、`aos-agent` import 的模組）。可寫 mount 蓋到它們，工具就能在下一件關牢之前改掉關牢的程式。
- 家裡的 `state.json`、`tick.json`、`.tick.lock`、`paused`、`resumed`、輸入（`state.input` 指的，預設 `input.json`）、`waits` 的門檔、`work/`、`log/`、`tools/`、`prompts/`。

**家本身不在 T**，所以 `家/workspace` 可以可寫。

規則：可寫 mount M 跟 T 的任一項 t——`M == t`、M 是 t 的祖先、t 是 M 的祖先——就是 `AccessUnsafe`（「ws 可寫、但包含 …」或「ws 可寫、但位在 … 裡面」）。唯讀 mount 不查。
所以 **`self`（＝整個家）只能 ro**；共用工具夾只能 ro（可寫就能對所有用它的 agent 下毒）。想讓 agent 寫東西：掛一個家外的資料夾，或家裡明確的子資料夾（例如 `./notes`，一樣要過這條規則）。

## 生效時機

- aos-agent 在**建 act 批那一刻**解一次、存成快照（[state.md §4.3](state.md) 的 `batch.access`），同批每件、崩了重送都用它。所以改表＝**下一批**生效，不用重 start。
- **正在跑的工具不會被收回權限。** 要馬上撤：`aos-agent pause`（不再送新批）；還在排隊的用 `aos-kernel rm <工作名>` 取消；已經在跑的 `rm` 只丟回音、不殺行程——只能等它跑完（`_timeout_ms` 到了 kernel 會砍）或手動 kill。`aos-agent stop` 也不停已送出的工具。

## 擋不住的（明講、不處理）

- **socket／FIFO**：mount 裡有 Unix socket，唯讀也擋不住連它、請牢外服務代做事。`aos-agent check` 對 mount 頂層掃到會 warn；別把含服務 socket 的資料夾掛進去。
- **`net: true`** 共用主機網路：連得到本機 LiteLLM、kernel 以外的任何本機服務與區網。
- **硬連結**：有人事先在可寫資料夾裡建好指到信任資料的硬連結，realpath 看不出來。
- **換連結的時間差**：檢查之後、下一批之前才被換掉的符號連結（下一批會再查一次）。
- **資源上限**（磁碟、輸出大小、行程數、記憶體）：bwrap 不給。
- **同一批平行的工具**共用同一個可寫資料夾，同時寫同一個檔照樣互蓋；有先後的要分兩批。
- **`/opt/tool`**：工具程式（`argv[0]` 含 `/`）所在的**整個資料夾**會唯讀掛進牢裡。程式放在 agent 家根目錄＝整個家（info、state、work）牢裡都讀得到；`check` 會 warn。程式請放在只有程式的資料夾（例如 `tools/<包>/`）。
- **受控串流**：aos-exec 在牢外開好的 stdin／stdout／stderr fd 帶進牢裡；檔名從 `/proc/self/fd` 看得到。不保證模型永遠看不到真路徑，只保證工具的路徑是穩定的別名。

## 限制（信任資料收不全的地方）

- `$ref` 的收集是「盡量」：access 檔與 `info.json` 裡**解得開**的指示詞會收到它們讀的每個檔（含 `$fmt` 變數裡的 `$ref`）；解不過的格子略過。
- access 檔與 `info.json` 裡字面寫的 `$ref` 檔名另外照上面的方式收（連結本身也保護）；**解出來**才知道的檔名（`$fmt` 拼的）只收 realpath。
- 工具 `_meta` 裡的 `$ref` 只收**字面寫在 `_meta` 裡**的檔名（以 agent 家與 `_meta` 的 cwd 各算一次）；`$ref` 到的檔裡再 `$ref` 的、`$fmt` 拼出來的檔名收不到。
  **後果**：這種檔若放在可寫 mount 裡，工具能改它；它要是決定 `stderr`／`exit` 之類的路徑，下一次 aos-exec 會在**牢外**照改過的路徑開檔寫入——信任資料的保護就破了。`_meta` 請只 `$ref` 到家裡或唯讀的地方，別再層層 `$ref`。
- 工具程式只收 `argv[0]`；`["python3", "tools/x.py"]` 這種把腳本放在參數裡的，腳本不算信任資料，而且牢裡的起點不是 agent 家，相對路徑的腳本會找不到——請把腳本寫成 `argv[0]`（加執行位與 shebang）。
