#include <aos/loop.hpp>

#include "fs.hpp"

#include <charconv>
#include <chrono>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <limits>
#include <nlohmann/json.hpp>
#include <system_error>
#include <utility>
namespace aos::loop {
namespace {
std::int64_t read_every_ms(const std::string &text) {
    const auto document = nlohmann::json::parse(text, nullptr, false);
    if (document.is_discarded()) return 0;
    const auto value = document.find("every_ms");
    if (value == document.end()) return 0;
    if (value->is_number_unsigned()) {
        const auto milliseconds = value->get<std::uint64_t>();
        if (milliseconds <=
            static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
            return static_cast<std::int64_t>(milliseconds);
        }
        return 0;
    }
    if (!value->is_number_integer()) return 0;
    const auto milliseconds = value->get<std::int64_t>();
    return milliseconds > 0 ? milliseconds : 0;
}

bool parse_milliseconds(const std::string &text, std::int64_t &value) {
    const char *begin = text.data();
    const char *end = begin + text.size();
    const auto result = std::from_chars(begin, end, value);
    if (result.ec != std::errc{}) return false;
    const char *cursor = result.ptr;
    while (cursor != end && (*cursor == ' ' || *cursor == '\t' ||
                             *cursor == '\r' || *cursor == '\n')) {
        ++cursor;
    }
    return cursor == end;
}

std::int64_t current_epoch_ms() {
    const auto now = std::chrono::system_clock::now().time_since_epoch();
    return std::chrono::duration_cast<std::chrono::milliseconds>(now).count();
}

}  // namespace

bool every_due(const Layout &layout, const std::string &stem,
               std::int64_t every_ms, std::int64_t now_ms) {
    if (every_ms <= 0) return true;
    std::string text;
    std::string read_error;
    const std::string path = fs::join(fs::join(layout.every, ".last"), stem);
    if (!fs::read_file(path, text, read_error)) return true;
    std::int64_t last_ms = 0;
    if (!parse_milliseconds(text, last_ms)) return true;
    if (now_ms < last_ms) return false;
    return static_cast<std::uint64_t>(now_ms) -
               static_cast<std::uint64_t>(last_ms) >=
           static_cast<std::uint64_t>(every_ms);
}

bool mark_every_delivered(const Layout &layout, const std::string &stem,
                          std::int64_t now_ms, std::string &error) {
    const std::string directory = fs::join(layout.every, ".last");
    if (!fs::mkdir_p(directory, error)) return false;
    return fs::write_atomic(fs::join(directory, stem),
                            std::to_string(now_ms) + "\n", error);
}

std::vector<wire::Inst> aggregate(const Layout &layout, std::uint64_t turn,
                                  std::string &error,
                                  std::size_t *every_count) {
    error.clear();
    if (every_count != nullptr) *every_count = 0;
    const auto deliveries = fs::list_json_files(layout.inbox, error);
    if (!error.empty()) return {};
    const auto recurring = fs::list_json_files(layout.every, error);
    if (!error.empty() || (deliveries.empty() && recurring.empty())) return {};
    const std::string destination_dir = insts_dir(layout, turn);
    std::vector<wire::Inst> insts;
    if (!deliveries.empty() && !fs::mkdir_p(destination_dir, error)) return {};
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

    const std::int64_t now_ms = current_epoch_ms();
    for (const std::string &source : recurring) {
        std::string text;
        if (!fs::read_file(source, text, error)) return insts;
        const std::string stem = fs::basename_sans_json(source);
        const std::int64_t every_ms = read_every_ms(text);
        if (every_ms > 0 && !every_due(layout, stem, every_ms, now_ms)) {
            continue;
        }

        if (!fs::mkdir_p(destination_dir, error)) return insts;
        const std::string id = stem + "-" + std::to_string(turn);
        const std::string destination = fs::join(destination_dir, id + ".json");
        if (!fs::write_atomic(destination, text, error)) {
            return insts;
        }

        std::string parse_error;
        auto inst = wire::parse_inst(text, id, parse_error);
        if (!inst) {
            std::fprintf(stderr, "aos run: 跳過 %s: %s\n",
                         destination.c_str(), parse_error.c_str());
            continue;
        }
        inst->id = id;
        if (!fs::write_atomic(destination, wire::to_json_text(*inst), error)) {
            return insts;
        }
        if (every_ms > 0 &&
            !mark_every_delivered(layout, stem, now_ms, error)) {
            return insts;
        }
        insts.push_back(std::move(*inst));
        if (every_count != nullptr) ++*every_count;
    }
    return insts;
}

}  // namespace aos::loop
