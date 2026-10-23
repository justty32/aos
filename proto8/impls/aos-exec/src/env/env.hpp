// env.hpp：【env】環境變數——工作區與 stack、`.env`（ideas 10-19 § 17、§ 19；10-21 ideas § 4～§ 7；分類照 P-39）。內部標頭。
//
//   env.cpp      setup_ws_stack：WS 規則（旗標 ＞ $AOS_WS ＞ cwd）、AOS_STACK（沒設＝$AOS_WS/.aos/，mkdir -p、轉絕對、結尾 /），
//                export AOS_WS、AOS_STACK——工作區在不在、建 stack、轉絕對路徑只在這裡做（N-59 第 1 件）
//   dotenv.cpp   load_env：讀 資料夾/.env 逐行套進環境（10-22 起 dotenv 基礎子集、預設不蓋）；json_env：沒 argv 的
//                JSON 物件裡的 `.env` key；env_value：`=` 後面那段（引號、註解、去空白）；set_env：一個 `名字=值`（只展開 ${名字}）
// 對應 proto8/bin/aos-exec 的 hop 開頭幾行、set_env、load_env、json_env。PATH 不動（ideas § 24）。
#pragma once

#include "common/common.hpp"

#include <set>
#include <string>

namespace aos::exec {

// ws＝旗標 --ws 的值（沒給＝"-"）。"-"／空＝沿用 $AOS_WS，沒設用 "."。不是資料夾 WsMissing。
// 回工作區的絕對路徑（旗標給的才要在每讀完一份 .env 後蓋回去，呼叫者自己記）。
// 注意：WS 的檢查在找 XXX 之前、建 stack 在找 XXX 之後（同 bin 版的錯誤順序），所以拆成兩個。
std::string check_ws(const std::string& ws_flag);
void setup_stack(const std::string& ws);   // AOS_STACK＋export AOS_WS、AOS_STACK；建不了 MkdirFailed

// 讀 dir/.env（沒有＝什麼都不做），回 .env 設過的名字。讀不到、壞都是 DotenvBad（只印檔名和行號、不印值）。
// override 假＝開始讀這份檔時環境裡已有的名字那一行跳過（格式照驗）；同一份檔裡同名照樣後者贏（10-22）。
std::set<std::string> load_env(const std::string& dir, bool override);

// JSON 物件的 `.env` key：{"名字": 值}，照順序套；值可放指示詞（$ref 從 ref_base 算），解完不是字串的那一項靜默跳過；
// 解完不是物件＝整個跳過。指示詞解不開、名字不合、${名字} 沒設＝DotenvBad（只印位置 where）。回設過的名字。
// 格式不變（引號、註解那些 JSON 自己有，不套），只套蓋不蓋（同 load_env，10-22）。
std::set<std::string> json_env(const Json& env, const std::string& where, const std::string& ref_base, bool override);

}  // namespace aos::exec
