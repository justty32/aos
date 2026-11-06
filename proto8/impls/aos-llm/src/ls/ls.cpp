// ls.cpp：【ls】讀窗、印表（說明見 ls.hpp）。
#include "ls/ls.hpp"

#include "aos/util/files.hpp"

#include <cstdio>

namespace aos::llm {

Json ls_window(const Mailbox& mb) {
    std::string path = aos::join(aos::dirname(mb.root), "endpoints.json");
    std::optional<Json> w;
    try {
        w = aos::read_json(path);
    } catch (const std::exception&) {
        w = std::nullopt;
    }
    if (!w || !w->is_object()) {
        throw Error{code::EndpointsMissing, path + " is missing or unreadable (has the llm kernel run yet?)"};
    }
    return *w;
}

// 值原樣印：字串去引號、其他（數字等）用 JSON 寫法；缺＝-。
static std::string cell(const Json& pack, const char* k) {
    if (!pack.contains(k)) {
        return "-";
    }
    const Json& v = pack.at(k);
    return v.is_string() ? v.get<std::string>() : v.dump();
}

void ls_print(const Json& window, bool json) {
    if (json) {
        std::printf("%s\n", aos::dumps(window).c_str());
        std::fflush(stdout);
        return;
    }
    for (auto it = window.begin(); it != window.end(); ++it) {
        const Json& p = it.value();
        if (p.is_object() && p.contains("error")) {
            std::printf("%s\terror:\t%s\n", it.key().c_str(), cell(p, "error").c_str());
            continue;
        }
        std::printf("%s\t%s\t%s\t%s\t%s\t%s\n", it.key().c_str(), cell(p, "speed").c_str(), cell(p, "cost").c_str(),
                    cell(p, "context").c_str(), cell(p, "slots").c_str(), cell(p, "summary").c_str());
    }
    std::fflush(stdout);
}

}  // namespace aos::llm
