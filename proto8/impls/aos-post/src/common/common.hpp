// common.hpp：【common】aos-post 跨元素共用的小東西（內部標頭，不對外）。
//
//   is_dir      是不是資料夾（跟著捷徑走）
//   need_dir    信箱的一格要是資料夾，不是丟 MailboxMissing（入口檢查，C-53 (a)）
//   make_dir    沒有就建（已經有＝沒事）；建不了丟 MkdirFailed
//   names_in    一個資料夾裡的名字，照處理順序（sort_letters）；. 開頭的不算（N-05：讀的人不讀 . 開頭的）。讀不了＝空
//   drop        丟掉一封已經在 tmp/ 的信（整個資料夾刪掉；刪不乾淨不算錯——殘骸留在 tmp/，處理者本來就不看）
//   is_dir／make_dir 直接用 aos-util；rename 操作用 explicit aos::move，避免 ADL 歧義
#pragma once

#include "aos/post.hpp"
#include "aos/files.hpp"

#include <string>
#include <vector>

namespace aos::post {

using aos::Error;
using aos::Json;

using aos::is_dir;
using aos::make_dir;
void need_dir(const std::string& path);
std::vector<std::string> names_in(const std::string& dir);
void drop(const std::string& path);

}  // namespace aos::post
