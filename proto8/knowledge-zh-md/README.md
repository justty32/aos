# 知識庫的中文映照版：給人看，正本是 `proto8/knowledge/`

> **先看這段**：這一夾是給人看的**中文映照版**，正本是 `proto8/knowledge/`（跟本夾並排在 `proto8/` 底下）。給 agent 讀的仍是正本，改這裡不會回寫正本。這一夾放在 `knowledge/` 外面，是為了 agent 用 grep 查知識庫時不會撈到中文重複的一份（使用者 11-21 傍晚要求）。使用者 11-22：「可以的話我是希望knowledge zh md能夠跟上最新的。」所以每份檔頭都寫著它跟到正本的哪個 commit，照下面「怎麼找出過期的頁」查得出哪幾頁落後。

← [proto8/knowledge](../knowledge/README.md)｜最早的做法、拿不準的詞見 [thinking 09-知識庫中文映照版](../thinking/2026-11/21/md與json尋址-1121/09-知識庫中文映照版.md)｜11-22 照新的 md 知識庫整份重做、盤點與待定的一題見 [thinking 知識庫中文版同步-1122](../thinking/2026-11/22/知識庫中文版同步-1122.md)

正本的每一頁在這裡對一份同名的 `.md`（`aos/me.md` → [aos/me.md](aos/me.md)；夾的 `_index.json` → `_index.md`），共 158 份。正本的 `README.md` 與 `docs/` 本來就是中文、寫給人看的，不映照。每個子夾的 `README.md` 是本夾自己加的，正本那邊沒有。

## 一頁長怎樣

- **檔頭**：一行標題、一段 `> 正本：…，跟到正本 commit 某某`、一條 `---`。那個 commit 是正本這頁最後一次改動；它之後正本又改過，這份就過期了。
- **`aos/` 那一庫和根的 `_description.md`**：英文譯成繁體中文白話；鍵名、指令、旗標、路徑、程式碼、錯誤代號照原樣。標題也譯，每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址：別頁寫的 `aos/body.md#/Brain, tools, hooks, screen`，就對到 `aos/body.md` 裡標著 `#/Brain, tools, hooks, screen` 的那一節。段落、清單、表格、程式碼區塊跟正本一對一。
- **`wf/` 那一庫**：正本本來就是中文，照抄，標題就是尋址。
- **夾的 `_index.md`**：正本是 json 表，這裡寫成清單，一項「`名字`: 一句話」，名字是本夾裡的檔名或子夾名，讓 `index_view`／`index_check` 讀得出來（使用者 11-21「幫我處理，重寫」）。正本的鍵指到某頁某一節的，名字寫那個檔名，項尾註明「正本的鍵是 …」；有二次導航的，項尾寫「（index：…）」。

## 從這裡看起

| 先看 | 是什麼 |
|---|---|
| [_description.md](_description.md) | 整個知識庫的一段簡介 |
| [aos/_description.md](aos/_description.md) | aos 一頁說完：八個詞、五條規則 |
| [aos/_index.md](aos/_index.md) | aos 這一庫每頁一句話 |
| [aos/cli/_index.md](aos/cli/_index.md)、[aos/tools/_index.md](aos/tools/_index.md) | 指令、工具各一句話 |
| [aos/eca_reading.md](aos/eca_reading.md)、[aos/troubleshooting.md](aos/troubleshooting.md) | eca 該讀哪些頁；常見的失敗怎麼查 |
| [wf/_description.md](wf/_description.md) | wf 那一庫（本來就是中文） |

## 怎麼找出過期的頁

在 repo 的 `proto8/` 跑（只讀，不改檔）：

```sh
cd ~/repo/aos/proto8
find knowledge-zh-md -name '*.md' ! -name README.md | sort | while read -r z; do
  e=knowledge/${z#knowledge-zh-md/}; [ -e "$e" ] || e=${e%.md}.json
  [ -e "$e" ] || { echo "gone    $z"; continue; }
  h=$(grep -om1 '跟到正本 commit `[0-9a-f]*`' "$z" | grep -o '[0-9a-f]\{7,\}')
  [ -z "$h" ] && { echo "no-hash $z"; continue; }
  [ -n "$(git log --format=%h "$h"..HEAD -- "$e")" ] && echo "stale   $z (since $h)"
done
find knowledge -name '*.md' -o -name '_index.json' | grep -v -e '^knowledge/README.md$' -e '^knowledge/docs/' | while read -r e; do
  z=knowledge-zh-md/${e#knowledge/}; z=${z/%_index.json/_index.md}; [ -e "$z" ] || echo "missing $z"
done
```

`stale`＝正本在檔頭那個 commit 之後又改過；`missing`＝正本有、這裡還沒有；`gone`＝正本已經沒有這頁（這裡的那份先別刪，列出來問使用者，刪檔要他本人說）。什麼都沒印就是全部跟上。

## 怎麼跟上一頁

1. `git diff <檔頭的 commit> HEAD -- proto8/knowledge/<頁>`，看正本改了哪幾行。
2. 只改譯文裡對應的那幾行，其餘不動；正本加了或改了標題，連同前一行的 `#/…` 一起改。
3. 檔頭的 commit 換成 `git log -1 --format=%h -- proto8/knowledge/<頁>`。
4. 正本新增的頁：照「一頁長怎樣」新寫一份，夾的 `_index.md` 加一項。
5. 譯完對一下形狀：標題的層級與個數、反引號個數、程式碼圍欄、表格列數、清單項數要跟正本一樣。

用詞照 [11-21 的用詞表](../thinking/2026-11/21/md與json尋址-1121/09-知識庫中文映照版.md#翻譯拿不準的詞)，例如 stock template 一律譯「內建範本」。

什麼時候跟、由誰跟：每天收工時 eca-aos 跑上面的查法，有過期就派一條線一次補齊（使用者 11-22「都先按照推薦」；規矩寫在 [wf user/02「收工」](../../wf/workflows/common/user/02-交接與收工.md#收工)）。
