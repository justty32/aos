#include "cli_common.hpp"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <stdexcept>

namespace aos::tick::cli {

Args::Args(int argc, char *argv[]) {
    if (argc < 0 || argv == nullptr) throw std::invalid_argument("命令列參數無效");
    words.reserve(argc > 1 ? static_cast<std::size_t>(argc - 1) : 0);
    for (int index = 1; index < argc; ++index) {
        if (argv[index] == nullptr) throw std::invalid_argument("命令列參數無效");
        words.emplace_back(argv[index]);
    }
}

bool take_folder(std::vector<std::string> &words, std::size_t &index,
                 std::string &folder) {
    std::error_code code;
    if (index < words.size() &&
        std::filesystem::is_directory(words[index], code)) {
        folder = words[index++];
        return true;
    }
    folder = loop::current_folder();
    return false;
}

Instant now_seconds() {
    return std::chrono::duration_cast<std::chrono::seconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}

bool parse_run(const std::vector<std::string> &words, std::size_t &index,
               RunSpec &run) {
    run = {};
    if (index >= words.size()) return false;
    if (words[index] == "--ask") {
        if (index + 2 != words.size() || words[index + 1].empty()) return false;
        run.ask = words[index + 1];
        index = words.size();
        return true;
    }
    if (words[index] != "--" || index + 1 >= words.size()) return false;
    run.argv.assign(words.begin() + static_cast<std::ptrdiff_t>(index + 1),
                    words.end());
    index = words.size();
    return true;
}

void print_table(const std::vector<std::string> &headers,
                 const std::vector<std::vector<std::string>> &rows) {
    std::vector<std::size_t> widths(headers.size());
    for (std::size_t column = 0; column < headers.size(); ++column) {
        widths[column] = headers[column].size();
    }
    for (const auto &row : rows) {
        for (std::size_t column = 0;
             column < headers.size() && column < row.size(); ++column) {
            widths[column] = std::max(widths[column], row[column].size());
        }
    }
    const auto print_row = [&](const std::vector<std::string> &row) {
        for (std::size_t column = 0; column < headers.size(); ++column) {
            if (column != 0) std::fputs("  ", stdout);
            const std::string value = column < row.size() ? row[column] : "";
            std::fwrite(value.data(), 1, value.size(), stdout);
            if (column + 1 < headers.size()) {
                for (std::size_t pad = value.size(); pad < widths[column]; ++pad) {
                    std::fputc(' ', stdout);
                }
            }
        }
        std::fputc('\n', stdout);
    };
    print_row(headers);
    for (const auto &row : rows) print_row(row);
}

std::string run_text(const Run &run) {
    if (!run.argv.empty()) {
        std::string text = "argv:";
        for (const auto &word : run.argv) text += " " + word;
        return text;
    }
    if (!run.ask.empty()) return "ask: " + run.ask;
    return "（空）";
}

bool load_context(const std::string &folder, loop::Layout &layout, Paths &paths,
                  Config &config, std::string &error) {
    layout = loop::layout_of(folder);
    paths = paths_of(layout);
    if (!read_config(paths.config_file, config, error)) return false;
    if (!valid_zone(config.tz)) {
        error = "時區不合法: " + config.tz;
        return false;
    }
    return true;
}

}  // namespace aos::tick::cli
