// main.cpp：aos-hello 執行檔——印 greeting() 一行、退 0；只用來驗 build 鏈，核心程式由使用者自己寫。
#include <iostream>

#include "aos/hello.hpp"

int main() {
    std::cout << aos::hello::greeting() << '\n';
    return 0;
}
