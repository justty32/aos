#pragma once

// 這個端點加這顆模型，做得到哪些事。
//
// 答案有三種：true、false、**nullopt（proxy 沒說，就是不知道）**。三態不能壓成
// 兩態 —— 把「不知道」當成「不行」會在本地就把使用者擋死，當成「行」則會讓一個
// 明確的 false 失去意義。
//
// 能力掛在引擎上而不是掛在 bot 上，因為「能不能看圖」是端點加模型的性質，
// 跟這個 bot 是誰無關。
//
// 只有明確 false 才擋呼叫；不擋的那幾項純粹是情報：值不值得去讀 reasoning、
// 要不要為了前綴快取排訊息順序。
//
// 來源是 proxy 的 /model/info，**它會說謊**（實測過兩個方向的謊報都有），
// 所以建引擎時可以整格覆寫掉。

#include <expected>
#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace aos::llm {

struct Caps {
    std::optional<bool> tools;           // 叫不叫得動工具（會擋）
    std::optional<bool> tool_choice;     // 能不能指定 tool_choice（會擋）
    std::optional<bool> parallel_tools;  // 一步能不能吐多個呼叫
    std::optional<bool> vision;          // 讀不讀得懂圖（會擋）
    std::optional<bool> reasoning;       // 會不會思考（不表示每次都想）
    std::optional<bool> json_schema;     // 收不收 response_format 的 schema
    std::optional<bool> caching;         // 有沒有前綴快取

    // 名字打錯**不會安靜地變成「不知道」**：那正是 litellm drop_params 那個坑的
    // 翻版 —— 一個明明有給的設定被吃掉，然後花很久才發現。所以回錯誤。
    [[nodiscard]] std::expected<std::optional<bool>, std::string>
    get(std::string_view name) const;

    // override 裡有值的欄位優先，其餘沿用 remote。
    [[nodiscard]] static Caps overlay(const Caps& remote, const Caps& override_);

    [[nodiscard]] static std::span<const std::string_view> names();

    bool operator==(const Caps&) const = default;
};

}  // namespace aos::llm
