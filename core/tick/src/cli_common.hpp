#pragma once

#include <aos/tick.hpp>

#include <cstddef>
#include <string>
#include <vector>

namespace aos::tick::cli {

struct Args {
    Args(int argc, char *argv[]);
    std::vector<std::string> words;
};

bool take_folder(std::vector<std::string> &words, std::size_t &index,
                 std::string &folder);

Instant now_seconds();

struct RunSpec {
    std::vector<std::string> argv;
    std::string ask;
};

bool parse_run(const std::vector<std::string> &words, std::size_t &index,
               RunSpec &run);

void print_table(const std::vector<std::string> &headers,
                 const std::vector<std::vector<std::string>> &rows);
std::string run_text(const Run &run);

bool load_context(const std::string &folder, loop::Layout &layout, Paths &paths,
                  Config &config, std::string &error);

}  // namespace aos::tick::cli
