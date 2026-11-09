// hello_test.cpp：ctest 跑的小測試範例——退 0＝過、非 0＝不過；照這個樣子在 TESTS 加別的測試檔。
#include <iostream>
#include <string>

#include <nlohmann/json.hpp>

#include "aos/hello.hpp"

int main() {
    int failed = 0;
    auto check = [&failed](bool ok, const std::string &what) {
        if (!ok) {
            std::cerr << "hello_test: FAIL " << what << '\n';
            ++failed;
        }
    };

    // greeting() 吐的是合法 JSON，parse 得回來。
    auto j = nlohmann::json::parse(aos::hello::greeting());
    check(j["hello"] == "impl_cpp", "greeting parses back");

    // nlohmann 本身 parse／dump 來回一次。
    auto k = nlohmann::json::parse(R"({"a": 1, "b": [true, null]})");
    check(k["b"].size() == 2, "parse array");
    check(k.dump() == R"({"a":1,"b":[true,null]})", "dump round-trip");

    if (failed == 0) {
        std::cout << "hello_test: ok\n";
    }
    return failed == 0 ? 0 : 1;
}
