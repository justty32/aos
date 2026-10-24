// inline.cpp：【run】run_inline——exec 是物件（內嵌單子）時，行程內跑它（10-24；說明見 aos/loop.hpp 的 run_once）。
//
// 跟 aos-exec 跑 `檔#/指標` 指到的單子同一套（N-57、N-59）：
//   1. AOS_CF／AOS_CD／AOS_CO 設成單子的位置（寫著它的設定檔、那份檔的資料夾、它在檔裡的 JSON 指標），跑完還原成原本的
//      （loop 自己之後讀 ctl 的指示詞、下一次跑目標時看到的還是原本的）。AOS_WS、AOS_STACK 照現有的，只是相對路徑以呼叫者的
//      cwd 轉成絕對（AOS_STACK 結尾補 /），同樣跑完還原（10-24 審後補：單子的相對路徑從 AOS_CD 算，原樣給的話
//      `AOS_STACK=st aos-loop cfg/loop.json` 的單子寫到 cfg/st/，loop 自己的窗卻在 ./st/；經 aos-exec 跑時它們早被轉成絕對了，
//      N-59 第 1 件。不驗、不建——建 stack 只在 aos-exec）。.env 不讀
//      （loop 不是 aos-exec，不「走進」哪裡；它被 aos-exec 起來時那份 .env 已經套過了）
//   2. aos::exec::run_inst（aos-exec 跑單子用的同一個函式：先解指示詞、驗 10 個 key、交給 inst 的 libaos；
//      timeout_ms、grace_ms、訊號轉給整群都在裡面）。相對路徑的基準＝AOS_CD（同 aos-exec cd 進設定檔的資料夾），$ref 從 ref_base 算
//   3. 錯（EntryBad／DirectiveBad／LaunchFailed／Internal）訊息前面加「單子跑不起來：」往上丟（同 aos-exec 的 launch），
//      呼叫者印成自己的一行「程式名: 代號 原因」
// 為什麼可以在行程內 setenv：呼叫者是單執行緒（run_inst 的工人執行緒在它回來前就 join 了）。
#include "run/run.hpp"

#include "aos/files.hpp"

#include <chrono>
#include <cstdlib>
#include <optional>

namespace aos::loop {

namespace {

// 設幾個環境變數，出去時還原（原本沒有的 unsetenv）。
struct EnvSwap {
    std::vector<std::pair<std::string, std::optional<std::string>>> old;
    explicit EnvSwap(const std::vector<std::pair<std::string, std::string>>& vars) {
        for (auto& [k, v] : vars) {
            const char* o = std::getenv(k.c_str());
            old.emplace_back(k, o ? std::optional<std::string>(o) : std::nullopt);
            setenv(k.c_str(), v.c_str(), 1);
        }
    }
    ~EnvSwap() {
        for (auto& [k, v] : old) {
            if (v) {
                setenv(k.c_str(), v->c_str(), 1);
            } else {
                unsetenv(k.c_str());
            }
        }
    }
    EnvSwap(const EnvSwap&) = delete;
    EnvSwap& operator=(const EnvSwap&) = delete;
};

// 相對的 AOS_WS／AOS_STACK（有設、不是空的、不是 / 開頭）→ 以現在的 cwd 轉成絕對，加進 vars。
void absolute_ws_stack(std::vector<std::pair<std::string, std::string>>& vars) {
    for (const char* k : {"AOS_WS", "AOS_STACK"}) {
        const char* v = std::getenv(k);
        if (v == nullptr || v[0] == '\0' || v[0] == '/') {
            continue;
        }
        std::string abs = aos::abspath(v);
        if (std::string(k) == "AOS_STACK" && abs != "/") {
            abs += "/";   // 同 aos-exec 的 setup_stack
        }
        vars.emplace_back(k, abs);
    }
}

}  // namespace

Run run_inline(const Target& t) {
    using Clock = std::chrono::steady_clock;
    Clock::time_point t0 = Clock::now();
    std::string dir = aos::dirname(t.cf);
    std::vector<std::pair<std::string, std::string>> vars = {{"AOS_CF", t.cf}, {"AOS_CD", dir}, {"AOS_CO", t.co}};
    absolute_ws_stack(vars);
    EnvSwap env(vars);
    aos::exec::Result r;
    try {
        r = aos::exec::run_inst(*t.inst, dir, t.args, t.ref_base);
    } catch (const Error& e) {
        throw Error{e.code, "單子跑不起來：" + e.msg};   // 代號照舊分種類（同 aos-exec）
    }
    Run b;
    b.code = r.code;
    b.signal = r.signal;
    b.received = r.received;
    long long us = std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - t0).count();
    b.elapsed_ms = (unsigned long long)((us + 500) / 1000);
    return b;
}

}  // namespace aos::loop
