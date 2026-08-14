#pragma once

// tooljson —— 讀一份 .json，取出要給模型看的工具定義，並且真的執行它。
//
// 一份 spec 就是「一個 OpenAI tool JSON」加一個 `_extra`：前半原封不動送給模型，
// 後半講怎麼把模型吐回來的那包參數變成一次實際的執行。
//
//   {
//     "type": "function",
//     "function": {"name": "resize", "description": "...", "parameters": {...}},
//     "_extra": {"_version": "0.1.0", "_type": "exec", "exec": ["./resize"], ...}
//   }
//
// 價值在「能力變成一份設定檔」：加一個工具不用重新編譯，放一個 .json 就好。
// 只是想在同一支程式裡用自己的 C++ 函式的話**不需要這一套** ——
// aos/llm/tool.hpp 的 ToolBuilder 就夠了。
//
//   auto tools = aos::tooljson::load_tools({"tools/resize.json"});
//   Bot bot{Llm{}, "請簡短回答。", *tools};
//
// `_extra` 裡只有 `_version` 和 `_type` 兩個保留鍵，其餘由 `_type` 決定。
// 內建的只有 `"exec"`（跑一個執行檔）。python 那邊還有 `_type: "python"`，
// 這裡沒有對應物 —— C++ 沒辦法照名字把一個函式從別的行程叫起來。
// 要加自己的執行方式就往註冊表登記，登記完就跟內建的平起平坐：
//
//   aos::tooljson::register_type("http", make_http_body);

#include "aos/llm/tool.hpp"

#include <expected>
#include <filesystem>
#include <functional>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace aos::tooljson {

// 這支只認得這個版本。0.x 期間 minor 就等於 major，認不得的一律拒絕，不猜。
inline constexpr std::string_view format_version = "0.1.0";

// 一個參數的宣告。從 function.parameters.properties 拆出來的。
struct Property {
    std::string name;

    // "string" / "integer" / "number" / "boolean" / "array" / "object"。
    // 沒宣告 type 就是空字串。
    std::string type;

    // 這個參數完整的 JSON Schema，原樣保留。
    std::string schema_json;
};

class Spec;

// 一個 `_type` 的執行端。
class Body {
public:
    Body() = default;
    virtual ~Body() = default;
    Body(const Body&) = delete;
    Body& operator=(const Body&) = delete;

    // 收模型給的那包 arguments（JSON object 文字），回一個字串。
    //
    // **錯誤也是字串，不丟例外** —— 這個回傳值會直接變成送回模型的 tool
    // message。模型讀到「找不到執行檔」還能自己換一步走，讀到例外只會整條斷掉。
    //
    // spec 是每次呼叫時傳進來的，body **不存一個指回去的指標**：
    // Spec 讀好之後會被搬進 shared_ptr（見 load_tools），存起來的那個指標
    // 就指到搬走後的殼上了。這種懸空只在搬家之後才發作，很難查。
    [[nodiscard]] virtual std::string run(
        const Spec& spec, std::string_view arguments_json) const = 0;

    // 這份 spec 指向的本地檔案。沒有就回空路徑。
    [[nodiscard]] virtual std::filesystem::path target() const { return {}; }
};

// 一份讀好、檢查過的 spec。
class Spec {
public:
    [[nodiscard]] const std::string& name() const { return name_; }
    [[nodiscard]] const std::string& kind() const { return kind_; }

    // 剝掉 `_extra` 的乾淨 OpenAI tool。**送進模型之前一定要剝** ——
    // 多一個未知的鍵，不同端點各有各的嫌法，不值得賭。
    [[nodiscard]] const std::string& schema_json() const { return schema_json_; }

    // `_extra` 整段，給 `_type` 自己的解析器讀。
    [[nodiscard]] const std::string& extra_json() const { return extra_json_; }

    [[nodiscard]] std::span<const Property> properties() const {
        return properties_;
    }
    [[nodiscard]] std::span<const std::string> required() const {
        return required_;
    }

    // .json 檔所在的資料夾。`_extra` 裡的相對路徑以它為中心。
    [[nodiscard]] const std::filesystem::path& directory() const {
        return directory_;
    }

    [[nodiscard]] std::string run(std::string_view arguments_json) const;

    // 給解析器與載入流程用；一般呼叫端不需要碰。
    void attach(std::shared_ptr<Body> body) { body_ = std::move(body); }
    [[nodiscard]] const Body* body() const { return body_.get(); }

    // 載入流程要填這些欄位，但填的方式不該變成公開介面 —— 讀好的 spec
    // 是唯讀的。所以開一道只給 spec.cpp 用的側門。
    friend struct SpecAccess;

private:
    std::string name_;
    std::string kind_;
    std::string schema_json_;
    std::string extra_json_;
    std::vector<Property> properties_;
    std::vector<std::string> required_;
    std::filesystem::path directory_;
    std::shared_ptr<Body> body_;
};

// 解析器：收一份還沒接上 body 的 Spec，回一個 body。
// 建構時發現 .json 寫錯就回錯誤字串 —— 那是設定錯，越早講越好。
using BodyParser = std::function<
    std::expected<std::shared_ptr<Body>, std::string>(const Spec&)>;

// 登記一個 `_type`。同名登記兩次就覆蓋，不擋。
void register_type(std::string kind, BodyParser parser);

// 目前登記了哪些 `_type`，排序後回傳。
[[nodiscard]] std::vector<std::string> registered_types();

// 讀一個檔案裡的所有 spec。最外層可以是一個 object，也可以是一個 array
// （相關的工具擺在同一個檔案比較好維護）。同檔撞名是錯，不是先到先贏。
[[nodiscard]] std::expected<std::vector<Spec>, std::string> load_all(
    const std::filesystem::path& path);

// 只要一個的方便寫法；檔案裡不只一個就是錯。
[[nodiscard]] std::expected<Spec, std::string> load(
    const std::filesystem::path& path);

// 一串 .json → 可以直接給 Bot 的 ToolSet。
// 跨檔撞名以先給的為準（比照 PATH）：參數的順序是呼叫端明確寫下的優先序。
[[nodiscard]] std::expected<llm::ToolSet, std::string> load_tools(
    std::span<const std::filesystem::path> sources);

}  // namespace aos::tooljson
