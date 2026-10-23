// main.cpp：aos-schema 的入口：`aos-schema SCHEMA檔 < doc.json`
//
// 從 stdin 讀一份 JSON（空＝{}），用 SCHEMA檔 驗，stdout 印一行
//   {"valid": true/false, "problems": [{"pointer": ..., "message": ...}, ...]}
// 驗不過也退 0——那是資料，不是錯。工具自己出錯（參數不對、檔讀不到、JSON 壞、schema 壞）
// 才往 stderr 印 {"error": {"code", "msg"}}、退 1。沒有其他旗標。
// 讀 stdin、印結果、印錯誤都用 aos-util（aos/io.hpp）。
#include "aos/schema.hpp"

#include "aos/io.hpp"

#include <exception>

using namespace aos::schema;

int main(int argc, char** argv) {
    try {
        if (argc != 2) {
            throw Error{code::Usage, "用法：aos-schema SCHEMA檔 < doc.json"};
        }
        nlohmann::json schema = load_file(argv[1]);
        aos::Json doc = aos::read_stdin();
        std::vector<Problem> problems = validate(schema, doc);

        // aos::Json 是 ordered_json：key 照寫的順序印（valid 在前、pointer 在前）
        aos::Json list = aos::Json::array();
        for (const Problem& p : problems) {
            list.push_back({{"pointer", p.pointer}, {"message", p.message}});
        }
        return aos::emit({{"valid", problems.empty()}, {"problems", list}});
    } catch (const Error& e) {
        return aos::emit_error(e);
    } catch (const std::exception& e) {
        return aos::emit_error(Error{code::Internal, e.what()});
    }
}
