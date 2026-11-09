// hello.hpp：樣板小專案的公開標頭——別的小專案寫 #include <aos/hello.hpp> 就拿得到。
#pragma once

#include <string>

namespace aos::hello {

// 回一行 JSON 文字：{"hello":"impl_cpp"}。
std::string greeting();

}  // namespace aos::hello
