#pragma once

// 線路格式：把要送出去的東西組成 JSON，把收回來的東西拆成 Reply。
//
// 這一層**完全不碰網路**，全是純函式加一個累積器。分出來的理由很實際：
// LLM 端點的錯有九成是「送出去的形狀不對」或「回來的形狀跟想的不一樣」，
// 而那兩件事都不需要連線就能驗。tests/llm_test.cpp 因此一個 socket 都不開。

#include "aos/llm/caps.hpp"
#include "aos/llm/message.hpp"
#include "aos/llm/params.hpp"
#include "aos/llm/reply.hpp"
#include "aos/llm/tool.hpp"

#include <expected>
#include <map>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace aos::llm {

// 組一次 request body 需要的全部東西。
struct PayloadInput {
    std::string_view model;
    std::span<const Message> messages;

    // 空的就整個不送 tools 欄位。送一個空陣列有些端點會嫌。
    std::span<const ToolSchema> tools = {};

    // "auto" / "none" / "required"，或一整段 JSON（指定某個 function）。
    // 空字串代表不送。
    std::string_view tool_choice = {};

    bool stream = false;

    // nullptr 等於「什麼旋鈕都不調」。
    const Params* params = nullptr;
};

// 組出 request body。會失敗是因為 params.extra 或圖片路徑可能是壞的，
// 那些錯誤在送出去之前就該講清楚。
[[nodiscard]] std::expected<std::string, std::string>
build_payload(const PayloadInput& input);

// 非串流：整包回應 → Reply。拆不動就把原因放進 reply.err，不丟例外。
[[nodiscard]] Reply parse_completion(std::string_view body);

// 串流：SSE 是一行一行來的，而且一段 TCP 資料**常常切在半行中間**，
// 所以要有個東西記得上一段剩下什麼。這就是它存在的唯一理由。
//
//   StreamAccumulator accumulator;
//   for (每段收到的位元組) {
//       for (const auto& part : accumulator.feed(bytes)) { 印出 part.text; }
//   }
//   Reply reply = accumulator.finish();
class StreamAccumulator {
public:
    struct Part {
        PartKind kind;
        std::string text;
    };

    // 吃一段原始位元組，吐出這一段裡**新出現**的文字。沒湊滿一行就回空的。
    [[nodiscard]] std::vector<Part> feed(std::string_view bytes);

    // 收完了，把累積的東西組成 Reply。呼叫之後不要再 feed。
    [[nodiscard]] Reply finish();

    // 端點回了看不懂的東西時記在這裡；finish() 會把它放進 reply.err。
    [[nodiscard]] bool broken() const { return error_.has_value(); }

private:
    void eat_line(std::string_view line);

    std::string pending_;  // 還沒湊成一整行的位元組
    std::string text_;
    std::string reasoning_;
    std::string finish_reason_;
    std::optional<Usage> usage_;
    std::map<int, ToolCall> calls_;  // 依 index 拼；串流的 id/name 只來一次
    std::optional<std::string> error_;
    bool saw_done_ = false;
};

// url 可以是 base url，也可以是完整的 /chat/completions，統一成 base url。
[[nodiscard]] std::string normalize_base_url(std::string_view url);

// 再把尾巴的 /v1 拿掉，得到 proxy 的根位址（/model/info 這種管理端點掛在那）。
[[nodiscard]] std::string root_url(std::string_view url);

// 一張圖 → OpenAI image_url 要的那個字串。http(s) 原樣回傳，
// 本機檔案讀進來轉成 base64 data URI。讀不到檔案是錯誤。
[[nodiscard]] std::expected<std::string, std::string>
image_data_url(std::string_view path_or_url);

// LiteLLM proxy /model/info 的回應 → 每顆模型的能力表。
// 拆不動就回空的 —— 「問不到」跟「不知道」是同一件事，不值得為它丟例外。
[[nodiscard]] std::vector<std::pair<std::string, Caps>>
parse_model_info(std::string_view body);

}  // namespace aos::llm
