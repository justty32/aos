// pack.hpp：【pack】endpoint 能力包（11-05 feat-proto 件 2、件 3）——kernel.json 的 endpoints 一組＝一個包（代號就是能力名：smart-high、stupid-fast…）。
//
//   一組的形狀（全選填，除 url＋model 或 exec）：
//     {"url", "model", "key", "exec", "fixed": {釘死的取樣參數}, "slots", "budget": {"max_calls", "max_tokens"},
//      "speed": "fast"／"normal"／"slow", "cost", "context", "summary", 其他…}
//   kernel 看的（PACK_KEYS）：exec（跑誰，serve 的 pick 看）、slots（這包同時幾封在飛）、budget（這包每窗上限；窗＝kernel 的 budget.window）、
//     speed（排序：同級、同 deadline 時快的先；沒寫＝normal）——這四個拿掉後才交給 endpoint 函數（strip_pack）。
//   交給函數的：url、model、key、fixed 與其他（cost／context／summary 函數不看、無害）。
//   parse_pack   讀 slots／budget／speed（已解指示詞的那組）；壞了丟 CfgBad（呼叫的人回那封信）
//   strip_pack   拿掉 exec、slots、budget、speed
//   fixed_clash  信的 request 撞到包釘死的：request 寫了 fixed 裡的 key、或包有 model 而 request 寫 model＝回 RequestBad 的原因；沒撞＝nullopt
//                （C-56 寫什麼就做什麼：釘死的不給信蓋，也不默默蓋過信；換參數＝換代號）。fixed 不是物件＝CfgBad
//   read_packs   kernel.json 的 endpoints 每組先換一層、只解 slots／budget／speed／cost／context／summary（其他指示詞〔key 的 $env…〕不解）：
//                給「在飛幾封」「窗」用；某組解不開或壞了＝記 error（那組的信 pick 時照樣回錯）
//   window_of    窗 $AOS_STACK/endpoints.json 的內容：{代號: {speed, cost?, context?, slots?, summary?}}（不含 url／key／fixed／exec；壞的那組＝{"error": "代號 原因"}）
#pragma once

#include "common/common.hpp"

#include <map>
#include <optional>
#include <string>

namespace aos::llm_kernel {

struct Pack {
    std::optional<long long> slots;
    std::optional<long long> max_calls;
    std::optional<long long> max_tokens;
    int speed = 1;                    // 0 fast、1 normal、2 slow（排序用，小的先）
    std::string speed_name = "normal";
    Json attrs = Json::object();      // 窗裡那幾格（speed、cost、context、slots、summary）
    std::optional<std::string> error; // read_packs：這組解不開或壞了（"代號 原因"）
};

Pack parse_pack(const Json& group, const std::string& name);
Json strip_pack(Json group);
std::optional<std::string> fixed_clash(const Json& group, const Json& request, const std::string& name);
std::map<std::string, Pack> read_packs(const Json& endpoints, const std::map<std::string, std::string>& dirs);
Json window_of(const std::map<std::string, Pack>& packs);

}  // namespace aos::llm_kernel
