#pragma once

// 一步的結果。串流與否都是它。
//
// 為什麼只有一種回傳型別：模型完全可以一邊說「好，我幫你查一下」一邊叫工具。
// 只要回傳值有「文字」和「工具呼叫」兩條路，實作就一定會挑一條走，那句話就進了
// 歷史卻沒人看得到 —— 畫面上一片空白，然後工具突然跑起來。所以 text 和 calls
// 同時存在，永遠都給。
//
// 錯誤也在裡面而不是丟例外：串流的錯誤發生在「開始收」之後，早就出了呼叫端的
// try 範圍，硬要用例外就會變成錯誤有兩個住處。ask() 永遠回一個 Reply。

#include "aos/llm/message.hpp"

#include <asio/awaitable.hpp>

#include <functional>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::llm {

// 這一步花了多少 token。
//
// cached 是命中前綴快取的部分（送出去的開頭一字不差才會有），reasoning 是思考燒
// 掉的。兩個都常常缺，**缺就是 nullopt 而不是 0** —— 分不開「沒有」和「是零」的
// 話，就沒辦法驗證快取到底有沒有命中。
struct Usage {
    std::optional<int> prompt;
    std::optional<int> completion;
    std::optional<int> total;
    std::optional<int> cached;
    std::optional<int> reasoning;

    bool operator==(const Usage&) const = default;
};

// 串流時吐出來的是哪一種字。
//
// 思考跟答案分開給，而不是把 <think> 塞進答案裡：最常見的用法就是把收到的字直接
// 印給使用者看，混在一起等於把模型的內心戲印到人臉上。
enum class PartKind { think, answer };

// 串流的收件端。給了它就是串流，沒給就是一次收完。
//
// 是 awaitable 而不是普通 callback，因為它十之八九要寫進某條 Session，
// 而那是非同步的 —— 逼呼叫端在同步 callback 裡塞一條非同步寫入只會更難寫對。
using PartHandler =
    std::function<asio::awaitable<void>(PartKind kind, std::string_view text)>;

struct Reply {
    // 它說了什麼。
    std::string text;

    // 它要你去做什麼。text 有東西時 calls 照樣可能有東西。
    std::vector<ToolCall> calls;

    // 它想了什麼。沒想就是空的 —— **那是正常的**，混合式思考模型自己決定要不要
    // 想，不想的那次回應裡根本沒有 reasoning 欄位，不是管線斷了。
    //
    // 思考不寫回歷史（DeepSeek 這類 API 不收送回去的 reasoning_content），
    // 所以 bot 記得自己說過什麼，但不記得當時為什麼那樣想。
    std::string reasoning;

    // 為什麼停：
    //   "stop"        正常講完
    //   "length"      **話被 max_tokens 切斷了**，不是錯誤，要不要接下去是你的決定
    //   "tool_calls"  它要你去跑工具
    // 空字串代表對方沒說（或整步還沒開始就斷了）。
    std::string finish_reason;

    std::optional<Usage> usage;

    // 壞了沒。有值的時候其餘欄位可能是半成品（串流講到一半斷線）。
    std::optional<std::string> err;

    // 出錯時是 false。這是逼呼叫端看一眼 err 的唯一手段 —— 不看的話只會拿到一個
    // 空的 text，然後花很久才想到要查哪裡。
    [[nodiscard]] explicit operator bool() const { return !err.has_value(); }

    // 這一步有沒有真的講出東西。分得開「模型沒話說」和「話還沒開始就斷線」：
    // 前者 finish_reason 是 "stop" 加空字串，後者是什麼都沒有。
    [[nodiscard]] bool spoke() const {
        return !text.empty() || !calls.empty() || !finish_reason.empty();
    }
};

}  // namespace aos::llm
