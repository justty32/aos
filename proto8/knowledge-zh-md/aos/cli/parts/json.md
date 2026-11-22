# `knowledge/aos/cli/parts/json.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/parts/json.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/parts/json.md#/…` 對的就是它。改請改正本，再照 [README](../../../README.md) 的做法跟上這份。

---

**`#/aos-json: read and edit aos JSON files`**

# aos-json：讀和改 aos 的 JSON 檔

用 `FILE#/POINTER` 指到任何一個值；只有你要求時才會跟著 `$ref` 走。agent 用 json 工具（`json_get`、`json_ls`、`json_search`、`json_len`、`json_set`、`json_add`、`json_del`、`json_multi_get`、`json_multi_set`；有 $ref/$env 的檔案用 `jsonx_get`、`jsonx_ls`、`jsonx_search`、`jsonx_set`、`jsonx_add`、`jsonx_del`、`jsonx_multi_get`、`jsonx_multi_set`）；aos-json 是給 shell 和腳本用的。它也能讀 `.md` 檔（`get`、`ls`、`where`、`peek`、`search`；`get --tree FILE.md` 把整個檔印成一個 JSON 值），但從不寫入 .md 檔；路徑規則在 `aos/tools/json_get.md#/JSON tools: reading markdown`。

**`#/Reading`**

# 讀

```sh
aos-json get c.json#/a/b                  # 1
aos-json get --follow --str c.json#/r/y   # hi      (r is {"$ref": "other.json#/x"})
aos-json get --resolve c.json#/e          # "/home/me"   (e is {"$env": "HOME"})
aos-json peek c.json                      # one level; big children folded
aos-json where c.json#/r/y                # c.json#/r, then other.json#/x/y
```

沒加 `--follow` 時，穿過 `$ref` 的指標＝`PointerMissing ... add --follow to go through it`。不存在的指標＝`PointerMissing`。`peek --depth N` 展開更多層。`ls [--long] [--depth N] [--offset N] [--limit N] FILE#/PTR` 列出子項；`search --key K --value JSON [--contains] [--up] [--limit N] FILE#/PTR` 找鍵或值（給 `--key`、`--value` 或兩個都給；`--up` 看的是上層，不能和 `--follow` 或 `--resolve` 一起用）。`env --prefix P` 設定 `$prefix`。更多旗標：跑 `aos-json SUBCOMMAND --help`。

**`#/Writing`**

# 寫

```sh
aos-json set c.json#/a/c '[1,2]'
aos-json set --str c.json#/a/s 'plain text'
aos-json set --parents c.json#/n/m 1      # without --parents: PointerMissing
aos-json add c.json#/a/d 7                # like set, but KeyExists if it is already there
aos-json append c.json#/a/c 3
aos-json merge c.json#/a '{"b": 9}'
aos-json del c.json#/n
echo '{"/a/b": 5, "/z": true}' | aos-json batch c.json
aos-json env --path /x c.json#/h HOME     # writes {"$env": "HOME", "$path": "/x"}
aos-json ref --move c.json#/a parts.json  # moves the value to parts.json, leaves {"$ref": "parts.json"}
```

寫入什麼都不印（`add` 會印出它寫在哪）。VALUE 從 argv 來，省略時從 stdin 來。每個改到的檔案都是原子寫入（先寫暫存檔，再改名）。`--check` 會拒絕會增加問題的修改。沒加 `--follow` 時，穿過 `$ref`/`$env` 的寫入＝`FollowMissing`。`--raw`（set、add、append、del）把路上遇到的 `$ref`/`$env` 物件當成一般物件（`aos-json set --raw c.json#/r/k 1` 會在 `$ref` 旁邊加上 k）；不能和 `--follow` 一起用（`ArgumentsBad`）。

**`#/Checking`**

# 檢查

```sh
aos-json check c.json        # exit 0: no problems
aos-json check bad.json      # exit 10, one line per problem:
# bad.json#/k: DirectiveBad $ref gone.json cannot be read (file not found: /.../gone.json)
```

它檢查參照、指示詞（directive）的形式和 exec 的形式。`--env` 也會回報沒設定的環境變數。
