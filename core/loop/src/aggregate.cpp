#include <aos/loop.hpp>

#include "fs.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

namespace aos::loop {

std::vector<wire::Inst> aggregate(const Layout &layout, std::uint64_t turn,
                                  std::string &error) {
    error.clear();
    const auto deliveries = fs::list_json_files(layout.inbox, error);
    if (!error.empty() || deliveries.empty()) return {};

    const std::string destination_dir = insts_dir(layout, turn);
    if (!fs::mkdir_p(destination_dir, error)) return {};

    std::vector<wire::Inst> insts;
    for (const std::string &source : deliveries) {
        const std::string destination =
            fs::join(destination_dir,
                     fs::basename_sans_json(source) + ".json");
        if (std::rename(source.c_str(), destination.c_str()) != 0) {
            error = "無法搬移 " + source + ": " + std::strerror(errno);
            return insts;
        }

        std::string text;
        if (!fs::read_file(destination, text, error)) return insts;
        std::string parse_error;
        auto inst = wire::parse_inst(text,
                                     fs::basename_sans_json(destination),
                                     parse_error);
        if (!inst) {
            std::fprintf(stderr, "aos run: 跳過 %s: %s\n",
                         destination.c_str(), parse_error.c_str());
            continue;
        }
        insts.push_back(std::move(*inst));
    }
    return insts;
}

}  // namespace aos::loop
