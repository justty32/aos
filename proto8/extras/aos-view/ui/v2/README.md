# 全景頁 v2（前端）

React + Tailwind，build 成 `dist/`，由同一支後端程式在第二個 port 提供（見 `../../API.md` 的 B1）。原始碼在 `src/`。

## 怎麼操作

| 想做的事 | 怎麼做 |
|---|---|
| 收／開左欄、右欄 | `[`、`]`，或欄頂的 « » |
| 調欄寬 | 拖左欄和中欄之間、中欄和右欄之間的直線；右欄裡「往來」和打字區之間的橫線可以上下拖。雙擊線＝回預設。線被選到時（Tab 到它）方向鍵一次動 16 px |
| 調字級 | 頁首右邊的 A− / A＋（13–18 px 六檔），點中間的數字回預設 14。不用 Ctrl+= / Ctrl+-，那是瀏覽器自己的縮放 |
| 換中間分頁 | `w` 部門牆、`m` 地圖、`t` 待辦 |
| 在地圖上走 | 方向鍵或 h/j/k/l 到那個方向最近的一塊；Enter 進房間（人身上＝開打字區）；Backspace 回上一層 |
| 地圖折疊 | 房間名字前的 ▾／▸ 或游標停在房間上按 **Space**＝折起／打開那一間；折起來是一格：名字、人數、裡面最壞的燈。工具列「全部折疊」「全部展開」「自動」（自動＝照畫面大小自己折，預設）。整間公司只有一個房間時，全部折疊會留它開著、折它裡面的 |
| 找人、下命令 | Ctrl+K。直接打名字＝跳過去說話；開頭加「信」「加人」「擴充」「電力」＝跳過去並換成那種打字區；「決定」＝開下一張要你決定；「地圖」「牆」「待辦」＝換分頁 |
| 對選中的人說話 | `/` 跳到打字區，Ctrl+Enter 送出 |

欄寬、打字區高度、字級存在這台瀏覽器的 localStorage（key `page.sizes`），地圖折疊存在 `page.mapFold`；讀不到（無痕視窗等）就用預設，不影響使用。欄寬是 CSS 變數 `--left-w`、`--right-w`、`--composer-h`，字級是根字級，整頁一起縮放。

## 建置與測試

**`dist/` 不進 git**（使用者 11-17「建置成品不進git，現有的都清掉」；`.gitignore` 擋著）：repo 裡只有原始碼，要看 v2 頁就得自己在當地建一次。沒建的話 `aos-view serve` 照樣起、第一個 port（舊頁）照常，第二個 port 不開，stderr 印一行：

```
aos-view: warning: port 8768 not opened: <...>/ui/v2/dist has no index.html (the page is not built; build it first: see <...>/ui/v2/README.md)
```

要什麼：**Node 24**（家機建的那版是 24.19.0；vite 8 至少要 20.19，`node --test` 直接跑 `.ts` 要靠 Node 的型別剝除，22.18 起才不用旗標），不用 npm 帳號。套件版本寫死在 `package.json`（vite 8.3.5、react 19.2.4、tailwindcss 4.3.0、typescript 5.9.3 …）。

步驟（不要在活樹建；在 repo 的工作樹或暫存複本都行，`node_modules/` 也不進 git）：

```sh
cd proto8/extras/aos-view/ui/v2
npm install          # 有網路時；沒網路的機器用 ./vendor.sh 從本機兩個專案抄 node_modules（路徑寫在 vendor.sh 開頭）
npm test             # node --test src/**/*.test.ts
npm run build        # check-src → tsc --noEmit → vite build（寫 dist/，先清空）→ check-dist（JS gzip ≤ 250 KB、index.html 不能有 inline script）
```

建在暫存複本時，把複本的 `dist/` 整夾抄到要用的那份 aos-view 旁邊（`<aos-view 所在夾>/ui/v2/dist/`；裝在樹裡的是 `~/aos-home/ws/tools/aos-view/ui/v2/dist/`），或在 aos-view 的 `config.json` 用 `ui_ports` 指過去（`[{"port": 8768, "dir": "<dist 的絕對路徑>"}]`）。換了原始碼要重建一次；`aos-view` 不會自己建。

（11-17 拿掉追蹤時這台公司 WSL 沒有 node，上面的指令照 `package.json` 寫、**沒在這台實建過**。）

試看：`python3 ../../tests/demo_v2.py 8769 8770`（先 unset 所有 AOS_*；假資料，不碰活樹），開 http://127.0.0.1:8770/ 。
