// find.hpp：【find】一跳（hop）——XXX → 走進去、讀 .env、挑入口、判種類（10-21 ideas § 4～§ 7；N-59、N-61、N-62）。內部標頭。
//
//   find.cpp      hop：定工作區 → 認出 XXX（locate：資料夾、檔、檔#/指標、補 .json）→ 建 stack、export AOS_WS／AOS_STACK →
//                 走進資料夾（或檔所在的資料夾）：設 AOS_CF／AOS_CD／AOS_CO、cd、讀那裡的 .env、旗標蓋回 →
//                 資料夾：照「當下的」$AOS_ENTRY 一段段走、沿路的資料夾都走進去，挑到資料夾就再走進去、一路往下，
//                 挑到檔（或補 .json）為止（走回走過的資料夾＝EntryBad）→ 交給 classify 判種類 → 重設 AOS_CF／AOS_CD／AOS_CO
//                 （最後讀的那一份 .env 自己設了就不蓋）。entry_name 也在這
//   classify.cpp  classify：實際的檔＋指標 → 種類。有 +x＝可執行檔；沒有就當 JSON 讀（跳過第一行 #!、照 #/ 取值）：
//                 沒 argv 的物件＝當資料夾（套它的 .env key、旗標蓋回、取 [$AOS_ENTRY]，一路往下）；
//                 陣列＝argv、有 argv 的物件＝單子、字串＝轉向（交給下一跳）。字串轉向繞圈＝EntryBad（跨跳記在 Chain）
// 對應 proto8/bin/aos-exec 的 locate、find、hop。
#pragma once

#include "common/common.hpp"

#include <set>
#include <string>
#include <vector>

namespace aos::exec {

// 字串轉向走過的位置（"實際檔#指標"），撞到同一個＝繞圈（跨跳都用同一條）。
struct Chain {
    std::vector<std::string> keys;
};

// 這一跳的旗標。apply＝每讀完一份 .env（檔或 JSON 的 .env key）就把旗標給的值蓋回去（旗標 ＞ .env，N-58）：目前只有 --ws。
// dotenv_override＝--dotenv-override（10-22）：這一跳讀的每份 .env 都蓋掉已有的；不往下傳。
struct Layer {
    bool flag_ws = false;
    std::string ws;
    bool dotenv_override = false;
    void apply() const;
};

// 一跳。spec 的相對路徑從 base 算；ws_flag＝這一跳的 --ws（沒給＝"-"）、dotenv_override＝這一跳的 --dotenv-override
// （轉向後的跳一律 "-"、false）。
Found hop(const std::string& spec, const std::string& base, const std::string& ws_flag, bool dotenv_override,
          Chain& chain);

// classify 的結果：種類＋值、入口在檔裡的指標（AOS_CO）、最後讀的那份 JSON .env key 設過的名字（一份都沒讀＝沒有）。
struct Classified {
    Kind kind = Kind::Executable;
    Json doc;
    std::string at;
    bool read_env = false;
    std::set<std::string> names;
};

// file＝實際的檔（realpath）、pointer＝`#` 後面（沒寫＝空；寫了一定是 / 開頭）。
Classified classify(const std::string& file, const std::string& pointer, Chain& chain, const Layer& layer);

}  // namespace aos::exec
