# 2026-10-24 fsm 格的 exec：能不能寫「相對於這格」

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)

起因：看 agent-dan 的 `fsm.json`（[2026-10-23 腦的工具呼叫](2026-10-23-tool-calls.md)），think、act 兩格的 `exec` 寫死成 `"fsm.json#/states/think/body"`。

## 使用者原文（整理版，10-24）

- 「fsm.json中，states.think.exec的內容，爲何不能用指示詞：AOS_CO/exec呢？」
- 看完下面三條路之後：「先改成不寫死檔名的寫法。然後這三條路...感覺除了1我勉強可接受外，其他都不太好」

## 結論（跟 AI 討論後）

**為什麼現在不能寫 `AOS_CO` 再接 `/exec`**：

- `AOS_CO` 是 aos-exec **每跳都重設**的「入口在那份 JSON 裡的位置」（N-57）。loop 跑 `fsm.json` 時，aos-exec 挑的是 `fsm.json` 的 `_entry`，所以 aos-fsm 拿到的 `AOS_CO` 是 `/_entry`，不是 think 那格（實測：`printenv AOS_CO` 印 `/_entry`）。fsm 解格的 `exec` 時，這個值跟正在解的那格無關。
- `AOS_CO` 只是指標、不帶檔名；單靠它拼不出 aos-exec 認得的 `檔#/指標`。
- 指示詞不做字串內插：一個 `$env` 只換一個變數，`$path` 是照字面接上去的字串（N-45），沒辦法把 `AOS_CF` 和 `AOS_CO` 兩個變數拼在一起。

**現在就能用、不寫死檔名的寫法**：`{"$env": "AOS_CF", "$path": "#/states/think/body"}`。aos-fsm 10-23 晚起會解格的 `exec`（[table.cpp](../impls/aos-fsm/src/table/table.cpp)、N-45），`AOS_CF` 在 fsm 那一跳就是 `fsm.json` 的絕對路徑，`$path` 以 `#` 開頭直接接上。檔名不寫死，但格的位置（`#/states/think/body`）還是寫死的。

**三條「相對於這格」的路**（都還沒做）：

1. **fsm 解格之前，把 `AOS_CO` 設成那格的位置**（例 `/states/think`），格裡就能寫 `$env: AOS_CO` 加 `$path`。卡點：`AOS_CO` 不帶檔名，還是得另外接 `AOS_CF`，而指示詞拼不了兩個變數；`AOS_CO` 是 aos-exec 定義的（N-57），讓 fsm 在解指示詞時改它的意思，撞 N-57 與 N-45；`states` 若用 `$ref` 拆到別的檔，那格真正所在的檔不是 `AOS_CF`，要擴 `resolve_shallow` 記下每格出自哪份檔。
2. **`exec` 收相對寫法**，例 `"#body"` 表示「這格的 `body`」。卡點：N-36（fsm 只看名字跑格，不管格裡的事）、C-56（多一種只在這裡成立的寫法）。
3. **`exec` 直接放內嵌單子**（物件）。卡點：翻 10-21 計畫 F2 的代定（`exec` 只收字串，[2026-10-21-plan](2026-10-21-plan.md)）；撞 N-36（fsm 不碰格的內容）、N-28（loop／daemon 的 `exec` 同義、只收 aos-exec 的目標）、N-25（單子只由 aos-exec 跑）。

## 決定

- 先把 agent-dan 的 think、act 改成 `{"$env": "AOS_CF", "$path": "#/states/<名>/body"}`（10-24 做了，[demo/README § agent-dan](../demo/README.md)）。
- 路 1 使用者「勉強可接受」，**未定、不動工**；路 2、3 使用者覺得不太好。

## 未決

- 要不要走路 1（掛在 [NORMS 待定](../NORMS/08-待定.md)「相對於這格的 exec」）。
- 其他 demo（agent-bob、cathy、agent-ann、daemon、tick）也寫死檔名，要不要一起改成 `$env: AOS_CF` 寫法，使用者還沒說。
