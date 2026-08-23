# core/llms — OpenAI 相容端點 client

`aos::llms` 把端點、模型與生成參數放在 `LLM`，把 system prompt、history 與 tools
放在 `Bot`。非串流與 SSE 串流都由同一個 `Reply` 承載；`Bot::ask()` 不論成功或失敗
都回 `Reply`，除
`std::bad_alloc` 外不讓例外穿出。錯誤由 `ReplyError` 的分類與訊息承載。

公開標頭是 `<aos/llms.hpp>`，JSON 一律以字串跨介面；nlohmann 與 libcurl 都只存在於
實作層。完整回應可用 `Transport`、串流可用平行的 `StreamTransport` 換成自訂函式，
因此所有自動測試都餵罐頭 SSE 給假端點，完全離線。

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

## 串流 Reply

`Reply` 有 `text`、`calls`、`reasoning`、`finish_reason`、`usage`、`err` 與
`checkpoint`。`calls[].args` 是尚未解析的合法 JSON 字串；模型給的參數不合法時
`args` 為空，原文放在 `args_raw`。

串流 request 把 `Ask::stream` 設成 `true`。`ask()` 先回一個尚未啟動 transport 的
`Reply`，讓呼叫端在收資料前用 `set_sink()` 掛答案 sink；`all_text()` 才啟動同步的
push transport，收到完畢後回傳完整答案。一般 sink **只收到答案**，思考不會混進畫面；
需要即時拿兩者時另掛 `set_part_sink()`，由 `ReplyPart::Think`／`Answer` 區分：

```cpp
aos::llms::Ask ask;
ask.prompt = "寫首詩";
ask.stream = true;
auto reply = bot.ask(ask);
reply.set_sink([](std::string_view part) {
    std::fwrite(part.data(), 1, part.size(), stdout);
    std::fflush(stdout);
});
reply.all_text();
if (!reply) std::fprintf(stderr, "%s\n", reply.err->message.c_str());
```

SSE parser 會跨任意 callback 切割累積完整 event，`data: [DONE]` 結束；每個 chunk 都在
`Reply` 自己的保護範圍內防禦性拆解。`delta` 為 null、空 `choices`、欄位型別不符，
或只帶 usage 沒有 choices 的尾片都直接略過；真正的 JSON／transport 錯誤才寫進
`reply.err` 並收尾，不從 `all_text()` 逸出一般例外。串流 request 一律覆寫
`stream_options` 為 `{"include_usage":true}`。

tool call 碎片由 `delta.index` 分組，id、name 取各 index 後續出現的非空值，arguments
依到達順序串接，最後按 index 排序。收尾仍會把文字與 tool_calls 一起寫回 history；
只有工具沒有文字時，assistant message 的 `content` 是 JSON null。

所有正常收完、提前 `finish()`、串流錯誤與解構都走同一個可重複呼叫的 `finish()`。
若答案與工具皆尚未收到且 `finish_reason` 仍不存在，會退回 checkpoint；已收到半截內容
則保留，正常完成但答案為空也會寫入 assistant history。

這裡刻意比 Python 版多一層保證：C++ `Reply` 的解構子會確定呼叫 `finish()`。Python
避免在不確定的 GC 時點由 `__del__` 修改 history，所以「拿了 handler 卻完全不碰」會
漏收尾；C++ 解構時點固定，沒有同一個理由，提早離開 scope 會立刻關閉／退回，不留下
孤立的 user message。move assignment 也會先收掉原本持有的 Reply。

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
aos llms ask [--model M | --preset P] [--stream] [--system S] [--url U] [--key K] <prompt>
aos llms models [--url U] [--key K]
```

`--url` 預設 `http://localhost:4000`（也就是 [`proxy/`](proxy/README.md) 那個），
但 **proxy 不是必需品**——直接打任何 OpenAI 相容端點都行：

```bash
aos llms models --url http://localhost:1234/v1
aos llms ask --url http://localhost:1234/v1 --model qwen/qwen3.5-9b "你好"
aos llms ask --stream --url http://localhost:1234/v1 --model qwen/qwen3.5-9b "你好"
```

`--preset` 自帶端點與參數，所以不能再配 `--model`／`--url`／`--key`，否則「這次到底
打到哪」會變成要讀原始碼才知道的事。

`ask` 的非串流與串流成功路徑、`models` 成功路徑都會連到實際端點，因此 CLI 測試只驗
離線可走到的語法／配置錯誤；底層串流行為則全部用假 `StreamTransport` 驗證。
