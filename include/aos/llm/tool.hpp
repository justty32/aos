#pragma once

// 一個「工具」的兩半：給模型看的 schema，和真的去做事的那一端。
//
// 這兩半必須名稱完全配對 —— 模型只會照 schema 裡的 name 開口，dispatch 少一個
// 就變成「它要的東西沒人接」。所以配對檢查放在組裝的當下（merge_tools），
// 而不是等第一次 tool call 才發現。
//
// schema 存成一整段 JSON 文字而不是 nlohmann::json：nlohmann 只 PRIVATE 連進
// aos_core，公開標頭露出它的話，所有下游都得跟著找得到那個標頭。

#include <algorithm>
#include <expected>
#include <format>
#include <functional>
#include <map>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace aos::llm {

// 給模型看的那半邊：一整個 OpenAI tool object 的 JSON 文字，長這樣
//   {"type":"function","function":{"name":...,"description":...,"parameters":{...}}}
// name 另外抽出來，是為了配對檢查與 dispatch 查表時不必重新剖析 JSON。
struct ToolSchema {
    std::string name;
    std::string json;
};

// 真的去做事的那半邊：收模型給的那包 arguments（JSON object 文字），回一個字串。
//
// **錯誤也是字串，不丟例外** —— 這個回傳值會直接變成送回模型的 tool message。
// 模型讀到「text 太長了，65536 上限」是能自己重試的，讀到例外只會整條斷掉。
using ToolFunction = std::function<std::string(std::string_view arguments_json)>;

// 一組配對好的工具。Bot 拿的就是這個。
struct ToolSet {
    std::vector<ToolSchema> schemas;
    std::map<std::string, ToolFunction, std::less<>> dispatch;

    [[nodiscard]] bool empty() const { return schemas.empty(); }

    // 找不到回 nullptr；呼叫端該把「模型叫了一個不存在的工具」當成正常情況處理，
    // 那是模型的錯，不是程式的錯。
    [[nodiscard]] const ToolFunction* find(std::string_view name) const {
        const auto match = dispatch.find(name);
        return match == dispatch.end() ? nullptr : &match->second;
    }
};

// 把幾組工具併成一組。撞名是錯而不是先到先贏 —— 安靜挑一個只會讓人找不到另一個。
[[nodiscard]] inline std::expected<ToolSet, std::string>
merge_tools(std::vector<ToolSet> sources) {
    ToolSet merged;
    for (ToolSet& source : sources) {
        for (const ToolSchema& schema : source.schemas) {
            if (schema.name.empty()) {
                return std::unexpected{std::string{"工具的 name 不可以是空的"}};
            }
            if (!source.dispatch.contains(schema.name)) {
                return std::unexpected{std::format(
                    "工具 {} 只有 schema 沒有執行端，模型叫了會沒人接", schema.name)};
            }
            const auto clash = std::ranges::find(merged.schemas, schema.name,
                                                 &ToolSchema::name);
            if (clash != merged.schemas.end()) {
                return std::unexpected{std::format("工具名稱重複：{}", schema.name)};
            }
            merged.schemas.push_back(schema);
        }
        if (source.dispatch.size() != source.schemas.size()) {
            return std::unexpected{std::string{
                "schema 與 dispatch 的名稱對不起來，數量就已經不同"}};
        }
        for (auto& [name, function] : source.dispatch) {
            if (!function) {
                return std::unexpected{std::format("工具 {} 的執行端是空的", name)};
            }
            merged.dispatch.insert_or_assign(name, function);
        }
    }
    return merged;
}

// 手寫 schema 的建構器。
//
// python 那邊是 inspect.signature 加 type hints 反射出來的（func_schema.py），
// C++ 沒有那種東西，所以走 tooljson.Tool 的那條路：schema 是手寫的。這其實不算
// 退步 —— description 和 enum 本來就是寫給模型看的，簽名裡從來就沒有那些資訊。
//
// property_json 直接是 JSON Schema 的一段 object 文字，不發明第二套 DSL：
// enum、minimum、items 都照 JSON Schema 寫，不用等這裡支援。
class ToolBuilder {
public:
    explicit ToolBuilder(std::string name) : name_{std::move(name)} {}

    ToolBuilder& describe(std::string text) {
        description_ = std::move(text);
        return *this;
    }

    ToolBuilder& parameter(std::string parameter_name, std::string property_json,
                           bool required = false) {
        properties_.emplace_back(std::move(parameter_name),
                                 std::move(property_json));
        if (required) {
            required_.push_back(properties_.back().first);
        }
        return *this;
    }

    // 最常見的那幾種的捷徑；再花俏的就自己寫 property_json。
    ToolBuilder& text_parameter(std::string parameter_name,
                                std::string description, bool required = false) {
        return parameter(std::move(parameter_name),
                         std::format(R"({{"type":"string","description":{}}})",
                                     quote(description)),
                         required);
    }

    ToolBuilder& integer_parameter(std::string parameter_name,
                                   std::string description,
                                   bool required = false) {
        return parameter(std::move(parameter_name),
                         std::format(R"({{"type":"integer","description":{}}})",
                                     quote(description)),
                         required);
    }

    [[nodiscard]] ToolSchema build() const {
        std::string properties;
        for (const auto& [key, value] : properties_) {
            if (!properties.empty()) {
                properties += ',';
            }
            properties += std::format("{}:{}", quote(key), value);
        }
        std::string required;
        for (const std::string& key : required_) {
            if (!required.empty()) {
                required += ',';
            }
            required += quote(key);
        }
        return ToolSchema{
            .name = name_,
            .json = std::format(
                R"({{"type":"function","function":{{"name":{},"description":{},)"
                R"("parameters":{{"type":"object","properties":{{{}}},)"
                R"("required":[{}]}}}}}})",
                quote(name_), quote(description_), properties, required),
        };
    }

private:
    // 只夠用在自己組的這幾個字串上：JSON 的最小逃脫規則。真正的 payload 編碼
    // 走 nlohmann，不會走到這裡。
    [[nodiscard]] static std::string quote(std::string_view text) {
        std::string out{'"'};
        for (const char character : text) {
            switch (character) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default: out += character;
            }
        }
        out += '"';
        return out;
    }

    std::string name_;
    std::string description_;
    std::vector<std::pair<std::string, std::string>> properties_;
    std::vector<std::string> required_;
};

}  // namespace aos::llm
