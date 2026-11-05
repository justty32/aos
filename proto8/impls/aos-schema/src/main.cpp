// main.cpp：aos-schema 的入口：`aos-schema SCHEMA檔 < doc.json`
//
// 從 stdin 讀一份 JSON（空＝{}），用 SCHEMA檔 驗，stdout 印一行
//   {"valid": true/false, "problems": [{"pointer": ..., "message": ...}, ...]}
// 驗不過也退 0——那是資料，不是錯。工具自己出錯（參數不對、檔讀不到、JSON 壞、schema 壞）
// 才往 stderr 印一行「aos-schema: 代號 原因」、退 1（11-04 起照 CONVENTION P-44；原本印 {"error": {"code", "msg"}}）。
// 沒有旗標：命令列照 P-44 用 aos::parse_cli 解（不認得的旗標＝FlagUnknown、`--` 結束旗標）。
// 讀 stdin、印結果用 aos-util（aos/io.hpp）。
#include "aos/schema.hpp"

#include "aos/cli.hpp"
#include "aos/io.hpp"

#include <cstdio>
#include <exception>

using namespace aos::schema;

static const char* const usage = "usage: aos-schema SCHEMA_FILE < doc.json";

static int fail(const Error& e) {
    std::fprintf(stderr, "aos-schema: %s %s\n", e.code.c_str(), e.msg.c_str());
    std::fflush(stderr);
    return 1;
}

int main(int argc, char** argv) {
    try {
        aos::Cli cli;
        try {
            cli = aos::parse_cli(std::vector<std::string>(argv + 1, argv + argc), {});
        } catch (const Error& e) {
            throw Error{e.code, std::string(usage) + " (" + e.msg + ")"};
        }
        if (cli.rest.size() != 1) {
            throw Error{code::ArgumentsBad, std::string(usage) + " (need exactly one SCHEMA_FILE)"};
        }
        nlohmann::json schema = load_file(cli.rest[0]);
        aos::Json doc = aos::read_stdin();
        std::vector<Problem> problems = validate(schema, doc);

        // aos::Json 是 ordered_json：key 照寫的順序印（valid 在前、pointer 在前）
        aos::Json list = aos::Json::array();
        for (const Problem& p : problems) {
            list.push_back({{"pointer", p.pointer}, {"message", p.message}});
        }
        return aos::emit({{"valid", problems.empty()}, {"problems", list}});
    } catch (const Error& e) {
        return fail(e);
    } catch (const std::exception& e) {
        return fail(Error{code::Internal, e.what()});
    }
}
