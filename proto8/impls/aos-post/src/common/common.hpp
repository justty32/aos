// common.hpp：【common】aos-post 跨元素共用的小東西（內部標頭，不對外）。
//
//   is_dir      是不是資料夾（跟著捷徑走）
//   names_in    一個資料夾裡的名字，照名字排序；. 開頭的不算（N-05：讀的人不讀 . 開頭的）。讀不了＝空
//   drop        丟掉一封已經在 tmp/ 的信（整個資料夾刪掉；刪不乾淨不算錯——殘骸留在 tmp/，處理者本來就不看）
//   move        rename 一封信；成功 true、ENOENT／ENOTEMPTY／EEXIST（不在、被別人搶先）false、其他錯丟 WriteFailed
#pragma once

#include "aos/post.hpp"

#include <string>
#include <vector>

namespace aos::post {

using aos::Error;
using aos::Json;

bool is_dir(const std::string& path);
std::vector<std::string> names_in(const std::string& dir);
void drop(const std::string& path);
bool move(const std::string& from, const std::string& to);

}  // namespace aos::post
