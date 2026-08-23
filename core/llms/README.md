# core/llms — OpenAI 相容端點 client

`aos::llms` 把端點、模型與生成參數放在 `LLM`，把 system prompt、history 與 tools
放在 `Bot`。S3 只做非串流；`Bot::ask()` 不論成功或失敗都回 `Reply`，除
`std::bad_alloc` 外不讓例外穿出。錯誤由 `ReplyError` 的分類與訊息承載。

公開標頭是 `<aos/llms.hpp>`，JSON 一律以字串跨介面；nlohmann 與 libcurl 都只存在於
實作層。HTTP 可用 `Transport` 換成自訂函式，因此所有自動測試都用假的離線端點。

## 最小用法

```cpp
#include <aos/llms.hpp>
#include <cstdio>

int main() {
    aos::llms::Bot bot(
        aos::llms::LLM("deepseek-chat", "http://localhost:4000"),
        "請簡短回答。");
    aos::llms::Reply reply = bot.ask("你好");
    if (!reply) {
        std::fprintf(stderr, "%s\n", reply.err->message.c_str());
        return 1;
    }
    std::puts(reply.all_text().c_str());
}
```

`system` 不寫進 history，每次送出時才放在最前面；`Bot::reset()` 只清 history。
工具呼叫可同時帶文字，`pending_calls()` 會列出最後一輪仍待回填的呼叫。模型參數錯誤
或 HTTP／回應形狀錯誤時，這一輪已先寫入 history 的訊息會退回 checkpoint。

## Reply 與 S4 預留

`Reply` 有 `text`、`calls`、`reasoning`、`finish_reason`、`usage`、`err` 與
`checkpoint`。`calls[].args` 是尚未解析的合法 JSON 字串；模型給的參數不合法時
`args` 為空，原文放在 `args_raw`。

內部從一開始就使用可增量追加的答案／思考 buffer 與 `ToolCallAccumulator`；所有寫回
history 與關閉 transport 的動作只走 `finish()`。S3 的非串流回應在建好時立即吸收整包
並呼叫 `finish()`；S4 只需接上逐片餵入與 drain，不必改 `Reply` 的結果形狀或收尾規則。

## 能力、工具與 presets

能力值是 `std::optional<bool>`：`true`、`false`、不知道。只有明確 `false` 會擋圖片、
tools 或 tool choice；查 `/model/info` 失敗一律變成不知道。能力表按 `(root URL, key)`
快取，空表也會命中；設定改動後用 `LLM::clear_caps_cache()` 清掉。

`LLM::models()` 問的是**兩個**端點的聯集：`/model/info`（LiteLLM proxy 專屬，
名字加能力）與標準的 `/v1/models`（每個 OpenAI 相容端點都有，只有名字）。
只出現在後者的模型，能力就是「不知道」——那是實話，不是查失敗。少了 `/v1/models`
這一半，直接打 LM Studio 之類的端點會得到一片空白。

C++ 不移植 Python callable 反射。`normalize_tools()` 只收一組或多組
`ToolBundle{schemas_json, dispatch}`，並驗證 schema 與 dispatch 名稱完全相同、來源間
不可撞名。

[`presets.json`](presets.json) 只含 endpoint、model、parameters 與可省略的
description；能力仍向 proxy 查，不在 preset 重複維護。LiteLLM 設定與啟動腳本在
[`proxy/`](proxy/README.md)，它們不參與建置或安裝。

## 子命令

```text
aos llms ask [--model M | --preset P] [--system S] [--url U] [--key K] <prompt>
aos llms models [--url U] [--key K]
```

`--url` 預設 `http://localhost:4000`（也就是 [`proxy/`](proxy/README.md) 那個），
但 **proxy 不是必需品**——直接打任何 OpenAI 相容端點都行：

```bash
aos llms models --url http://localhost:1234/v1
aos llms ask --url http://localhost:1234/v1 --model qwen/qwen3.5-9b "你好"
```

`--preset` 自帶端點與參數，所以不能再配 `--model`／`--url`／`--key`，否則「這次到底
打到哪」會變成要讀原始碼才知道的事。

兩條成功路徑都會連到實際端點，因此不放進 ctest。`--stream` 留到 S4。
