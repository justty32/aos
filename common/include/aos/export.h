#pragma once

/* aos 只支援 POSIX 平台，所以不必處理 __declspec。整個專案編譯時帶
 * -fvisibility=hidden，這個屬性是把符號放回動態符號表的唯一入口：公開標頭裡
 * 宣告的每一個函式都要標上 AOS_API，否則外部連得到標頭卻連不到實作。 */

#if defined(AOS_STATIC)
#define AOS_API
#elif defined(__GNUC__)
#define AOS_API __attribute__((visibility("default")))
#else
#define AOS_API
#endif
