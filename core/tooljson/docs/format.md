# tooljson 格式與 S1 C++ 實作

`aos::tooljson` 讀取格式版本 `0.1.0` 的 tool spec。這個階段只負責讀取、驗證、
登記 `_type`，以及把模型參數展開成 argv／stdin；**不會啟動任何行程**。

一份 spec 是 OpenAI function tool 加上一個只供執行端使用的 `_extra`：

```json
{
  "type": "function",
  "function": {
    "name": "resize",
    "description": "把圖片縮到指定寬度",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string"},
        "width": {"type": "integer"}
      },
      "required": ["path"]
    }
  },
  "_extra": {
    "_version": "0.1.0",
    "_type": "exec",
    "exec": ["../resize"],
    "argv": {
      "path": {"position": 1},
      "width": {"position": 2, "flag": "--width"}
    }
  }
}
```

## 外殼

外殼只解讀 `_extra._version` 與 `_extra._type`。版本必須完全等於 `0.1.0`；
0.x 期間不猜測向下相容。`_type` 是開放集合，不是列舉；不認得時，詳細錯誤訊息
會列出目前 registry 裡的全部名稱。C++ 版只內建 `exec`，所以 `python` 是不認得的
壞檔，這是跨語言契約要求的行為。

最外層可以是一個 tool object 或非空 array。同一檔案內的 `function.name` 不得重複；
一次依序讀多個檔案時則比照 `PATH`，先出現的名稱獲勝，但後面的檔案仍會完整驗證。

`Spec::schema_json()` 只留下 `type` 與 `function`，不會把 `_extra` 送給模型；
`Spec::extra_json()` 則把原始 `_extra` object 序列化為 UTF-8 JSON 字串。

載入時會先驗執行端共同依賴的 schema 形狀：

- `function.name` 必須是非空字串，`description` 若存在必須是字串。
- `parameters` 若存在必須是 object，且 `type` 只能是 `object`。
- `properties` 必須把非空參數名映到 schema object。
- `required` 必須是無重複的非空字串 array，每個名稱都要存在於 `properties`。

其他 JSON Schema 關鍵字不由這一層改寫或擴充，原樣保留給模型端。

## 開放 registry 與 JSON 邊界

第三方以 `register_type()` 登記 parser。parser 收到 `const Spec &`，可用
`extra_json()` 取得 `_extra` 字串，驗證自己的格式後回傳一個 `Body`。body 只須提供：

- `run(args_json) -> std::string`：成功與錯誤都用字串回傳。
- `target() -> std::string`：指向本地檔案時回絕對路徑，沒有則回空字串。

同名 parser 後登記者覆蓋先登記者。內建 `exec` 也是呼叫同一個公開登記入口，
沒有硬編碼在外殼裡。

公開標頭刻意不出現 nlohmann 型別。第三方跨函式庫邊界只收送 JSON 字串，因此不會
被綁到 aos 建置時使用的 nlohmann 版本。內建 parser 位於 `src/`，可透過內部標頭
直接讀取已解析的 JSON，省掉重複解析；這是只限函式庫內部的效能取捨，不是公開 ABI。

`Spec` 以 pimpl 保存已解析 JSON 與 body，複製時只複製 shared pointer，可安全放進
`std::vector` 或名稱索引。配置失敗仍可能丟出 `std::bad_alloc`；壞 spec 則回
`SpecState` 與詳細訊息，不以 C++ 例外表示。

`Spec::stale()` 會在 `_extra.source.sha256` 與 body 的 `target()` 都可用時，讀取目前
檔案並比較 SHA-256；相同回 `false`、不同回 `true`。metadata 不完整、target 不存在
或檔案讀不到時回 `std::nullopt`，表示「不知道」，不把它誤判成已變更。

## `exec` 配方的載入期驗證

S1 會完整解析下列配方，但 `ExecBody::run()` 固定回
`Error: exec execution is not implemented in S1`，不會 fork 或 exec。

- `exec`：非空字串 array。第一項含 `/` 時相對於 JSON 所在資料夾轉成絕對路徑；
  不含 `/` 時原樣保留，留給日後的 `$PATH` 查找。`exec[1:]` 是固定引數，不翻路徑。
- `argv`：object。每個 key 必須存在於 `properties`，binding 只接受
  `position`、`flag`、`separate`、`repeat`，型別分別為整數、字串、boolean、boolean。
- `stdin`：`null` 或只有 `param` 的 object；參數名必須存在。
- `stdout.clip`：`head` 或 `tail`；預設 `head`。
- `stderr.mode`：`merge`、`ignore` 或 `only`；預設 `merge`。
- `ok_exit`：整數 array；省略或空 array 時使用 `[0]`。
- `timeout`：大於零的有限秒數；預設 60。
- `cwd`：`null` 或非空路徑字串；相對路徑以 JSON 所在資料夾為中心轉成絕對路徑。
- `limits`：參數名到限制 object 的映射。只接受 `max_bytes`、`min`、`max`；
  `max_bytes` 是非負整數，`min`／`max` 是有限數字，且 `min` 不得大於 `max`。
- `source`：若存在必須是 object；其中 `size` 是非負整數、`mtime` 是整數、
  `sha256` 是字串。欄位不完整仍可載入，但 `stale()` 會回「不知道」。

## 模型參數展開

`expand_args()` 收一個 JSON object。成功時回空字串並填入 `ExpandedArgs`；模型給錯
參數時回 `Error: ...` 字串，呼叫端應把它直接當 tool message 送回模型，而不是丟例外。

展開規則如下：

1. 字串會依 schema 的 `integer`、`number`、`boolean` 嘗試轉型；轉不動會明確報錯。
2. 明確的 `null` 等同缺席。required 缺少、不認得的參數都會報錯。
3. 先依 `position` 由小到大排序，同號再依參數名的 Unicode 碼位排序；不使用 JSON
   object 的出現順序。
4. 沒有 `flag` 時只放值；非 boolean 且有 `flag` 時放旗標和值；boolean flag 只有
   真值時放旗標，不帶值。`separate: false` 會合成 `--name=value`。
5. array 只有 `repeat: true` 才接受，並逐項展開；否則回錯誤。
6. `stdin.param` 指定的參數不進 argv，而是序列化到 `stdin_text`。
7. 字串不切割、不加引號；數字與 boolean 使用 JSON 字面。這一層不經過 shell。
8. `max_bytes` 以 UTF-8 bytes 計算。任何單一 argv 項目超過 131072 bytes 都拒絕，
   不需要另外宣告 limits。

## 文字收尾

`decode_output()` 遇到任何 NUL byte 時只回
`(binary output, N bytes, not shown)`；其餘內容以 UTF-8 解讀，無效序列換成 U+FFFD。
`clip_output()` 超過限制時可保留 head 或 tail，並在截斷處標明省略的 Unicode 字元數。

## CLI

S1 提供兩個完全離線的操作：

```text
aos tooljson list  <spec.json>
aos tooljson check <spec.json>
```

`list` 在驗證成功後逐行印出名稱與 description；`check` 只驗證。壞檔會把詳細訊息印到
stderr 並回非零。`run` 尚未存在，留給後續執行階段。
