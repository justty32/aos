# `knowledge/aos/cli/grow.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/grow.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# 函式成長

用 aos-grow 預覽函式搬移；真的跑會改寫設定，也可能搬移或刪除檔案。

```sh
aos-grow --dry-run up --to dir --name think --take brain.py fsm.json#/states/think/exec
aos-grow up --to file --name idle fsm.json#/states/idle/exec    # writes idle.json; the slot becomes "idle"
aos-grow --dry-run down fsm.json#/states/idle/exec             # back to inline; would remove idle.json
```

CALLER 指出設定裡說要跑什麼的那一格（slot）。up 把行內的指令搬到 NAME.json（`--to file`）或 NAME/_entry（`--to dir`），並把那一格改成 "NAME"；`--to` 必填。對已經是 `NAME`（旁邊有 `NAME.json`）的格子做 up，會把 `NAME.json` 搬到 `NAME/_entry`；這需要 `--to dir`。down 把只有 _entry 的資料夾縮成檔案，或把檔案縮回行內；那一格必須剛好是一個名字。共用的目標不能縮回行內。相對參照會改寫成指向同樣的地方。

`--name`（`-n`）是新名字；預設是那一格自己的名字（`.../states/think/exec` 得到 `think`），像 `/exec` 這樣的格子需要 `--name`。`--dry-run` 放在 up/down 前面或後面都行，什麼都不寫。`--take` 可以重複，只用於 `--to dir`，而且必須指出指令裡的一個路徑；那個檔案必須放在設定檔所在的資料夾。`TargetBad` 或 `NameBad` 要改正目標/名字，不是盲目重試。其他代號：`CfgMissing`、`CfgBad`、`WriteFailed`、`CommandUnknown`（見 aos/errors.json）。更多旗標：跑 `aos-grow up --help`。自己讀 AOS_CF/AOS_CD/AOS_CO 的程式可能會看到位置變了。
