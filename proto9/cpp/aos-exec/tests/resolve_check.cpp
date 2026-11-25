// resolve_check.cpp: test-only helper -- read one JSON from stdin, resolve its directives with the brought-in directive code, print it (a slim copy of proto8's aos-directive command line).
//
//     resolve-check [--file FILE [--at POINTER]] < doc.json
//
// stdin empty = {}; --file FILE = the JSON was read from FILE (relative $ref from its folder, "#..." means FILE);
// --at POINTER = it is POINTER of FILE ("#./", "#../" count from there). Prints one line of JSON, exit 0;
// on error "resolve-check: error: CODE reason" on stderr, exit 1. Not installed; only tests/ use it.
#include "directive/directive.hpp"
#include "util/files.hpp"
#include "util/io.hpp"

#include <cstdio>
#include <exception>
#include <filesystem>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    try {
        std::vector<std::string> args(argv + 1, argv + argc);
        std::string file;
        std::string at;
        bool has_file = false;
        bool has_at = false;
        for (size_t i = 0; i + 1 < args.size(); i += 2) {
            if (args[i] == "--file") {
                file = args[i + 1];
                has_file = true;
            } else if (args[i] == "--at") {
                at = args[i + 1];
                has_at = true;
            } else {
                throw aos::Error{aos::code::ArgumentsBad, "unknown argument " + args[i]};
            }
        }
        if (args.size() % 2 != 0) {
            throw aos::Error{aos::code::ArgumentsBad, "flags take one value each"};
        }
        std::string text(std::istreambuf_iterator<char>(std::cin), {});
        aos::Json doc = aos::Json::object();
        if (text.find_first_not_of(" \t\r\n") != std::string::npos) {
            doc = aos::Json::parse(text, nullptr, false);
            if (doc.is_discarded()) {
                throw aos::Error{"InputBad", "stdin is not JSON"};
            }
        }
        aos::RefBase base{std::filesystem::current_path()};
        if (has_file) {
            std::string f = aos::abspath(file);
            base = aos::RefBase{aos::dirname(f), f};
        }
        if (has_at) {
            if (!has_file) {
                throw aos::Error{aos::code::ArgumentsBad, "--at needs --file (which file the pointer is in)"};
            }
            if (!at.empty() && !at.starts_with("/")) {
                throw aos::Error{aos::code::ArgumentsBad, "--at must be a JSON pointer (\"\" or /a/b), got " + at};
            }
            base.at = aos::pointer_tokens(at);
        }
        std::string out = aos::dumps(aos::resolve(doc, base));
        std::fputs((out + "\n").c_str(), stdout);
        return 0;
    } catch (const aos::Error& e) {
        return aos::fail("resolve-check", e);
    } catch (const std::exception& e) {
        return aos::fail("resolve-check", aos::code::Internal, e.what());
    }
}
