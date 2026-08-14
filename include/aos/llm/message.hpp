#pragma once

// 對話裡的一則訊息，以及模型開口要的一次工具呼叫。
//
// 這一層刻意只有資料，沒有行為：Bot 的記憶、送出去的 payload、從回應拆回來的
// 東西，三者用的是同一種形狀，才不會出現「歷史裡的 tool_calls 跟 API 收的長得
// 不一樣」這種對不起來的問題。

#include <string>
#include <vector>

namespace aos::llm {

// 模型要你去做的一件事。
//
// arguments 保持成**原始的 JSON 文字**，不先剖析成結構：小模型和被 max_tokens
// 切斷的一步都會吐出壞掉的 JSON，在這裡剖析失敗就等於把它整個弄丟。誰要用誰去
// 剖析，剖析不動時至少還看得到模型原本寫了什麼。
struct ToolCall {
    std::string id;
    std::string name;
    std::string arguments;

    bool operator==(const ToolCall&) const = default;
};

// 一次工具執行的結果，餵回去等於跟模型說「你要的那個跑出了這些」。
struct ToolResult {
    std::string call_id;
    std::string content;
};

// 一則訊息。role 是 "system" / "user" / "assistant" / "tool"。
struct Message {
    std::string role;
    std::string content;

    // 本機路徑或 http(s) 網址，只有 user message 用得到。組 payload 時本機檔案會
    // 轉成 base64 data URI，網址原樣送。
    std::vector<std::string> images;

    // assistant 一邊說話一邊開口要工具時才有。**這一則寫回歷史時一定要連它一起
    // 寫**，形狀要跟 API 收的一模一樣，不然下一步送 tool 結果會被打回票。
    std::vector<ToolCall> tool_calls;

    // role == "tool" 時，指出這是在回哪一次呼叫。
    std::string tool_call_id;

    bool operator==(const Message&) const = default;
};

}  // namespace aos::llm
