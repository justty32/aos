#include "run.hpp"

#include <aos/tooljson.hpp>

#include <cstdio>
#include <new>
#include <stdexcept>
#include <string>
#include <vector>

namespace aos::tooljson {
namespace {

int usage(const char *program) {
    std::fprintf(stderr,
                 "usage: %s list  <spec.json>\n"
                 "       %s check <spec.json>\n",
                 program, program);
    return 2;
}

}  // namespace

int cli_run(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos tooljson";
    if (argc != 3 || argv == nullptr || argv[1] == nullptr ||
        argv[2] == nullptr) {
        return usage(program);
    }
    const std::string operation = argv[1];
    if (operation != "list" && operation != "check") {
        return usage(program);
    }

    try {
        std::vector<Spec> specs;
        std::string message;
        const SpecState state = load_all(argv[2], specs, message);
        if (state != SpecState::Ok) {
            std::fprintf(stderr, "%s: %s\n", program, message.c_str());
            return 1;
        }
        if (operation == "list") {
            for (const Spec &spec : specs) {
                const std::string name = spec.name();
                const std::string description = spec.description();
                if (description.empty()) {
                    std::printf("%s\n", name.c_str());
                } else {
                    std::printf("%s\t%s\n", name.c_str(),
                                description.c_str());
                }
            }
        }
        return 0;
    } catch (const std::bad_alloc &) {
        std::fprintf(stderr, "%s: out of memory\n", program);
        return 1;
    } catch (const std::length_error &) {
        std::fprintf(stderr, "%s: out of memory\n", program);
        return 1;
    }
}

}  // namespace aos::tooljson

extern "C" int aos_tooljson_cli_main(int argc, char *argv[]) {
    return aos::tooljson::cli_run(argc, argv);
}
