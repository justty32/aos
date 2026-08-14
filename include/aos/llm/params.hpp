#pragma once

// 一次呼叫要帶的生成參數。
//
// 只做一件事：把**有設定的**欄位吐成 JSON，沒設定的一律不送，讓 proxy 跟模型自己
// 用它們的預設值。送一個猜出來的預設值過去，等於偷偷替使用者做了決定。

#include <optional>
#include <string>
#include <vector>

namespace aos::llm {

struct Params {
    std::optional<double> temperature;
    std::optional<double> top_p;
    std::optional<int> max_tokens;
    std::optional<int> seed;
    std::vector<std::string> stop;
    std::optional<double> presence_penalty;
    std::optional<double> frequency_penalty;

    // 直接併進 request body 最上層的一段 JSON object 文字，例如
    //   {"reasoning_effort":"high"}
    // 非標準的鍵要自己包一層，端點怎麼收就怎麼寫：
    //   {"extra_body":{"chat_template_kwargs":{...}}}
    //
    // 它**蓋不掉** model / messages / stream 這三個 —— 那三個是引擎自己在管的，
    // 組 payload 時最後才寫。理由是踩過：extra 裡塞了 stream 會讓「用哪條路收」
    // 和「實際回來的是什麼」分岔，症狀是收到一個看不懂的東西。
    std::string extra;

    bool operator==(const Params&) const = default;
};

}  // namespace aos::llm
