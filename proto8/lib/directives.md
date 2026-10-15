# 指示詞 lib（`aos_directives.py`）

← [proto8/lib](README.md)｜下一份：[inst](inst.md)

讓 JSON 裡某一格的值「從別處來」。一個檔、一個入口：

```python
from aos_directives import resolve, DirectiveError
out = resolve(doc, base_dir)   # doc＝parse 好的 JSON；base_dir＝相對檔名的基準路徑
                               # 選填 ident＝doc 從哪來（檔案的 realpath），錯誤訊息用它指出是哪份檔
```

整份 JSON 一層層全部解掉，回一份新的（原本那份不動）。`base_dir` 整趟都用它，進了別的檔也不換。

兩種指示詞（兩個都寫了只看 `$ref`，其餘 key 忽略）：

```jsonc
{"$ref": "other.json#/a/0"}          // 讀一份 JSON 的某一格；"" 是目前這份；位置也可寫成 "$at": "/a/0"
{"$ref": "#../x"}                    // ./ ../ 從這個指示詞所在的位置算
{"$env": "HOME"}                     // 讀環境變數
```

取回來的東西裡如果還有指示詞，照它所在的那份檔、那個位置接著解。繞回自己（指到正在解的位置或它的上層）＝`ReferenceCycle`。
錯了一律丟 `DirectiveError`，代號七種，寫在檔頭。

命令列 TARGET 的 `檔#/位置` 也在這裡（三支程式共用）：`split_target(target)` → (檔, 位置)、`target_id(realpath, 位置)` → id、`locate(root, 位置, ident)` → 那一格的原值；`resolve(..., at=位置)` 只解那一格。

三支程式一個手感：`aos_inst.py x.json`、`aos_loop.py x.json`、`aos_daemon.py x.json`，命令列都只有一個引數，Python 的 `run(path)` 也一樣；相對路徑一律從呼叫者的 cwd 算。

**`檔#/位置`**（10-13 D1）：TARGET（含 `run(path)`、daemon 指令的 `id`）後面可以接 `#/位置`，只用那份檔裡那一格；`#` 後面是 JSON pointer，寫法同 `$ref`。〔註：10-15 列為規範＝[N-35](../NORMS/01-總則.md)。〕
- 遇到第一個 `#` 就切，檔名含 `#` 的不支援。位置只認 `/` 開頭（不是＝`ReferencePointerInvalid`）；空的或只有 `/`＝整份。位置像檔案系統：`/` 是根、空段落忽略（`/a/`＝`/a`），`$ref` 也一樣（10-13 使用者定甲）；所以名字是空字串的 key 指不到。
- id＝realpath ＋ `#` ＋ 位置（正規化過：`.`／`..` 消掉、`~0`／`~1` 重新轉義）；沒位置或 `#/`＝純 realpath。同一份檔兩個位置＝兩個 id。
- 指到的值不是物件＝`FieldType`；走不到＝`ReferencePointerInvalid`。錯誤訊息帶路徑。
- 那一格是整份檔的視窗、不是切下來：裡面 `$ref` 的位置照整份檔算（`#/` 是檔的根、`../` 可以摸到旁邊）。
- inst 的 TARGET 是資料夾：先照現有規矩找 inst.json 再套位置。退出碼／`run()` 只說自己有沒有出錯（只有 0／非 0 是確定的，其他數字只供參考）；子程式的碼只寫進 inst.json 的 `exit` 檔。
