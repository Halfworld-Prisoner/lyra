/* EventToken.h —— Windows SDK 头文件的最小替代实现
 *
 * WebView2.h 会 #include "EventToken.h",而 MinGW-w64 不带这个头文件
 * (它属于 Windows SDK / MSVC)。这里按 SDK 的定义补上,内容与系统一致。
 */
#ifndef _EVENTTOKEN_H_
#define _EVENTTOKEN_H_

typedef struct EventRegistrationToken
{
    __int64 value;
} EventRegistrationToken;

#endif /* _EVENTTOKEN_H_ */
