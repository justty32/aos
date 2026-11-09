// hello.cpp：greeting() 的實作——用 nlohmann-json 組一個物件再 dump 成一行，證明 vcpkg 的相依接得上。
#include "aos/hello.hpp"

#include <nlohmann/json.hpp>

namespace aos::hello {

std::string greeting() {
    nlohmann::json out = {{"hello", "impl_cpp"}};
    return out.dump();
}

}  // namespace aos::hello
