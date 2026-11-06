# aos-post

`aos-post - 投遞：把一封信寄進信箱、處理者一封封認領`（NAME，C-54 R1）

**一句話：`aos-post 子命令 [FLAGS...] 信箱 [信件名稱]`——NORMS [N-16](../../docs/NORMS/05-基礎設施-窗/05-N-16.md)的標準投遞：寄信人 `send` 把一封信放進信箱的 `new/`，處理者 `take`／`take-all` 一封封拿進 `cur/`、`see` 讀信、`done` 收掉（要回信就照信裡的 `reply_to` 投一封回去），還沒被拿走的寄信人可以 `regret` 撤回。**
aos-post 是 aos 體系跨行程交流（IPC）的語法糖、基底工具：跟 aos proc 的關聯不深，proc 自己拿它組出想要的效果（[thinking 11-03 aos-post](../../thinking/2026-11/03/aos-post/README.md)）。
一個 lib（`lib/libaos-post.a`，公開標頭 `include/aos/post.hpp`，aos-daemon 的信箱模式、aos-llm-kernel、aos-llm 連它）加一支薄命令列（`bin/aos-post`）。連 aos-util、aos-lock（有順序的投遞）。全家慣例見 [impls/README.md](../README.md)；最早的設計見 [thinking 10-29 medium-plan § 二](../../thinking/2026-10/29/medium-plan/README.md)。

像公司的收發室：寄件人在後面的桌上（`tmp/`）把信封好，封好才放進待收籃（`new/`）；收件人把信從籃子拿到自己桌上（`cur/`）就算簽收，簽收了寄件人就抽不回來；辦完撕掉，或歸檔（`archive/`）。掛號信（有序）永遠先收，平信（無序）排在後面。

```sh
aos-post init box                                   # 建 box/tmp new cur
echo '{"procs_added": {"bob": "../agents/bob"}}' | aos-post send box      # 印信件名稱
aos-post take-all box                               # 一行一個信件名稱（照處理順序）；沒有退 10
aos-post see box                                    # 讀 cur/ 照處理順序第一封；好信印 letter.json、壞信退 1
aos-post done box                                   # 收掉那一封（--keep 進 archive/）
```

函式庫另有兩個低層操作（公開契約見 `aos/post.hpp`）：

- `send_prepared(mb, letter, prepare)`：呼叫者先建完整信封；函式建 `tmp/.<id>`、呼叫非空 `prepare(tmp)` 放附檔，再寫 `letter.json` 並原子移進 `new/`。不做一般 `send` 的信箱可寫性、信封或名字檢查；prepare 丟 `Error`、寫檔或 rename 失敗會清暫存，rename 失敗一律 `WriteFailed`。
- `take(mb, name)`：建 `cur/` 後直接認領指定名字，不驗名字或 `new/`。信已不在或同名衝突回 `false`；其他 rename 錯丟 `WriteFailed`，建不了 `cur/` 丟 `MkdirFailed`。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法與元素](docs/01-用法與元素.md) | 用法；元素 |
| [02-錯誤代號等](docs/02-錯誤代號等.md) | 錯誤代號；建置與測試；已知限制 |

<a id="用法"></a>
<a id="元素"></a>
<a id="錯誤代號"></a>
<a id="建置與測試"></a>
<a id="已知限制"></a>
