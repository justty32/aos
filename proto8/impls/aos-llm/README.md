# aos-llm

`aos-llm - 寄請求信進 LLM kernel 的信箱、收回信`（NAME，C-54 R1）

**一句話：`aos-llm send|recv|ask|regret`——問腦的基礎工具：把一份請求（OpenAI 形狀的 messages／tools＋代號）寫成一封信丟進 `$AOS_LLM_KERNEL` 信箱，由 kernel（[aos-llm-kernel](../aos-llm-kernel/README.md)）排隊、跑它自己的 endpoint 函數、照信封的 `reply_to` 寄回信；這支再把回信的 `message` 印出來。**
定位同 [aos-post](../aos-post/README.md)：基礎工具、IPC 的語法糖，跟 aos proc 關聯不深，proc 自己拿它組（使用者 11-04 晚「aos llm,tool這兩個，我希望他們的定位是跟aos post一樣，作為基礎工具」）。aos-post 管「一封信怎麼寄、怎麼認領」，aos-llm 只多知道「請求信的 body 長怎樣、回信怎麼認、錯怎麼印」。
11-04 由 `aos-llm-send`（寄一張單子、等回信、原樣交回）改名改寫。一個 lib（`lib/libaos-llm.a`，沒有公開標頭）加一支薄命令列（`bin/aos-llm`）。連 aos-llm-kernel 的公開標頭（信箱與信的格式）與 aos-post 的庫。全家慣例見 [impls/README.md](../README.md)。

像寄信問醫生：`send` 是把問題寫好丟進郵筒、留個回郵地址就走（之後再來看信箱）；`recv` 是去信箱看回信到了沒；`ask` 是站在郵筒旁邊等回條；`regret` 是信還在郵筒裡就抽回來。找哪位醫生只寫代號，醫生的地址、電話只有櫃台（kernel）知道。

```sh
export AOS_LLM_KERNEL=$PWD/st/mailbox                        # kernel 的信箱（N-63 ②）
B='{"endpoint": "fake", "request": {"messages": [{"role": "user", "content": "hi"}]}}'
N=$(echo "$B" | aos-llm send --reply-to $AOS_STACK/llm_box) # 非同步：寄完馬上回，印信件名稱
aos-llm recv $AOS_STACK/llm_box $N; echo $?               # 還沒到：10
aos-llm recv $AOS_STACK/llm_box $N                        # 到了：{"role": "assistant", "content": "FAKE ANSWER to: hi"}
echo "$B" | aos-llm ask --priority high                   # 同步：寄、等、印 message
```

**stdin 是整份 body**（隊長 11-04 定案：設計稿寫「stdin＝request.json」，[03 § 1](../../thinking/2026-11/04/think-as-function/03-呼叫端.md) think 寫的 `request.json` 就是 body 的形狀）：`{"endpoint"?: 代號, "request": {"messages": [...], "tools"?, ...}, "priority"?}`——代號、請求、優先度都由呼叫端自己組，aos-llm 原樣當信的 `body` 寄出（只有 `--priority` 有給時蓋掉 `priority`）。

設計與決定見 [thinking 2026-11-04 think-as-function](../../thinking/2026-11/04/think-as-function/README.md)（§ 5 在 [02/01](../../thinking/2026-11/04/think-as-function/02-設計-信與kernel/01-endpoint函數-aos-llm-kernel形態.md)）。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法等](docs/01-用法等.md) | 用法；元素；錯誤代號；建置與測試；已知限制 |

<a id="用法"></a>
<a id="元素"></a>
<a id="錯誤代號"></a>
<a id="建置與測試"></a>
<a id="已知限制"></a>
