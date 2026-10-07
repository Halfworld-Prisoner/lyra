// StoryHook.cs —— 精准挂"剧情文本"的方法(针对使用 UguiNovelText 的 ADV/视觉小说)
//
// 背景:
//   XUnity.AutoTranslator 只挂钩 Unity 标准文本组件(UGUI/TMP/NGUI…),
//   而这类游戏用的是一个自绘文本组件 UguiNovelText(自带 UguiNovelTextGenerator),
//   所以 XUnity 只能抓到菜单,抓不到对话框里的剧情。
//
// 做法(先静态分析 Assembly-CSharp.dll,再精准挂钩,不撒网、不碰引擎内部,避免把游戏搞崩):
//   只挂这些类型上的文本方法:
//     UguiNovelText / NovelText / MessageWindow / AdvMessageWindow / ScenarioPlayer
//   方法名白名单:
//     set_Text / set_text / SetText / set_RenderText / ApplyText / ChangeText /
//     UpdatePageText / SetLine / AddText / set_Message / SetMessage / ShowMessage
//   且必须有 string 或 char[] 参数。
//   收到的文本按 "类型\t方法\t文本" 追加到 BepInEx\storyhook.log,读词工具读它即可。
//
// 编译:
//   csc /target:library /out:StoryHook.dll StoryHook.cs ^
//       /r:BepInEx.dll /r:0Harmony.dll /r:UnityEngine.dll /r:UnityEngine.CoreModule.dll
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using BepInEx;
using HarmonyLib;
using UnityEngine;

namespace GtrStoryHook
{
    [BepInPlugin("gtr.storyhook", "GTR Story Hook", "14.0.0")]
    public class StoryHook : BaseUnityPlugin
    {
        static StreamWriter _w;
        static readonly object _lk = new object();
        static readonly Dictionary<string, int> _count = new Dictionary<string, int>();
        static volatile bool _done = false;
        static int _round = 0;

        static long _bytes = 0;

        static void Log(string s)
        {
            lock (_lk)
            {
                try
                {
                    if (_w == null) return;
                    string line = "# " + s;
                    _w.WriteLine(line);
                    _bytes += line.Length * 2;          // 大致按 UTF-16 估
                    if (_bytes > 1500 * 1024) TrimLog();  // 超过 1.5MB 就清空重建
                }
                catch { }
            }
        }

        /// <summary>日志瘦身:关掉旧文件、清空、重开(我们持有句柄,只有我们能做)。</summary>
        static void TrimLog()
        {
            try
            {
                if (_w != null) { _w.Flush(); _w.Dispose(); _w = null; }
                string p = Path.Combine(Paths.BepInExRootPath, "storyhook.log");
                _w = new StreamWriter(p, false, new UTF8Encoding(false));
                _w.AutoFlush = true;
                _w.WriteLine("# 日志超过 1.5MB,已自动清空(旧内容不再需要)");
                _bytes = 0;
            }
            catch { }
        }

        // 只挂这些类型(名字里含其中之一,用于 UTAGE 这类已知引擎)
        static readonly string[] TYPE_HINTS =
        {
            "UguiNovelText", "NovelText", "MessageWindow", "AdvMessageWindow",
            "ScenarioPlayer", "AdvScenario",
            // 文本框架:很多游戏(Unity 2022 + TMP)的对白就挂在 TMP 组件上
            // 气泡/世界空间文字常用这两个
            "UnityEngine.TextMesh", "TextMesh", "TextMeshPro", "TMP_Text",
            "TMPro.TextMeshPro", "TMPro.TMP_Text", "UnityEngine.UI.Text", "TMPro.TMP_InputField",
            "UnityEngine.UI.InputField"
        };
        // 只挂这些方法名 —— 第二个数组是"自研文本系统"常用的名字
        // (三相奇谈这类原创引擎没有 UTAGE,但从反汇编能看出它用这些名字设置文本)
        static readonly string[] METHOD_WHITELIST =
        {
            "set_Text", "set_text", "SetText", "set_RenderText", "ApplyText", "ChangeText",
            "UpdatePageText", "SetLine", "AddText", "set_Message", "SetMessage", "ShowMessage",
            "set_CurrentText", "SetCurrentText", "SetPageText", "set_PageText",
            "set_NameText", "SetNameText", "set_CharacterLabel",
            // TMP 走这条最多:很多游戏的对白是通过 SetCharArray 写进文本框的
            // (IL2CPP 版就是靠它才读到对白;Mono 版之前漏了,导致半截能读、完整那句读不到)
            "SetCharArray", "SetTextArray", "SetChars", "set_text", "SetText",
            "SetTextInternal", "SetVertexText"
        };
        static readonly string[] METHOD_WHITELIST2 =
        {
            "SetContent", "UpdatePageContent", "SetLines", "SetWord", "SetCharacter",
            "ShowLine", "ShowLine2", "ShowLine3", "ChangeText2", "ChangePage",
            "SetStringArray", "SetDialogue", "ShowDialogue", "SetSentence", "UpdateText"
        };
        // 只挂这些类型名(自研系统的类名通常带这些词)
        static readonly string[] TYPE_HINTS2 =
        {
            "Page", "Dialogue", "Message", "Text", "Script", "Scenario", "Story",
            "Novel", "Adv", "Talk", "Chat", "Lines"
        };
        // "剧情数据类":这些类里的字符串基本上就是剧情本身(三相奇谈实测:
        // StoryBook / StoryBookLine / StoryStatement / StoryTeller 就是它的剧本结构)
        static readonly string[] STORY_TYPES =
        {
            // 留空:实测三相奇谈的剧本类(StoryBook/StoryStatement/StoryTeller)
            // 只提供脚本参数与求值中间量,挂上它们会把日志刷到几万行,
            // 而真正的对白走的是 UnityEngine.UI.Text / TMP —— 挂那些就够了。
        };

        static bool IsStoryType(string tn)
        {
            foreach (var h in STORY_TYPES)
                if (tn.IndexOf(h, StringComparison.OrdinalIgnoreCase) >= 0) return true;
            return false;
        }

        void Awake()
        {
            string logPath = Path.Combine(Paths.BepInExRootPath, "storyhook.log");
            _w = new StreamWriter(logPath, false, new UTF8Encoding(false));
            _w.AutoFlush = true;
            Logger.LogInfo("StoryHook v14 启动,日志: " + logPath);
            Log("v14 启动");
            try
            {
                // 程序集一加载就试一次(游戏自己的 Assembly-CSharp 是启动后才载入的)
                // (不再监听 AssemblyLoad:并发扫描会拖死游戏)
            }
            catch { }
            // 再加一个后台线程兜底轮询(不依赖 Unity 的 Invoke/协程,最稳)
            var th = new Thread(delegate ()
            {
                for (int i = 0; i < 300 && !_done; i++)
                {
                    Thread.Sleep(2000);
                    try { TryPatch("轮询"); } catch (Exception e) { Log("出错: " + e.Message); }
                }
            });
            th.IsBackground = true;
            th.Start();
        }

        static bool TryPatch(string from)
        {
            if (_done) return true;
            _round++;
            var pre = new HarmonyMethod(typeof(StoryHook).GetMethod("Pre",
                BindingFlags.Static | BindingFlags.Public));
            int patched = 0, asmN = 0, typeN = 0;
            var done = new List<string>();
            bool sawType = false;
            var names = new List<string>();

            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                string an = asm.GetName().Name;
                if (asm.IsDynamic) continue;
                asmN++;
                // 扫游戏自己的程序集 + 文本框架程序集(Assembly-CSharp / TMP / UGUI)。
                // 扫全部程序集时 GetTypes() 会在某个程序集上挂死(实测卡住不动),所以只挑这几个。
                bool wantAsm = an == "Assembly-CSharp" || an.StartsWith("Assembly-CSharp") ||
                               an.IndexOf("Novel", StringComparison.OrdinalIgnoreCase) >= 0 ||
                               an.IndexOf("TextMeshPro", StringComparison.OrdinalIgnoreCase) >= 0 ||
                               an == "UnityEngine.UI" || an == "UnityEngine.TextRenderingModule";
                if (!wantAsm) continue;
                Type[] types;
                try { types = asm.GetTypes(); } catch { continue; }
                typeN += types.Length;
                foreach (var t in types)
                {
                    if (t == null || t.ContainsGenericParameters) continue;
                    string tn = t.FullName ?? t.Name;
                    bool typeOk = false;
                    foreach (var h in TYPE_HINTS)
                        if (tn.IndexOf(h, StringComparison.OrdinalIgnoreCase) >= 0)
                        { typeOk = true; break; }
                    // 自研文本系统:类名里带 Text/Page/Dialogue/Scenario… 也算候选
                    // (只在游戏自己的程序集里这么做;文本框架程序集必须精确匹配,否则会挂上成百上千个方法)
                    bool isGameAsm = an == "Assembly-CSharp" || an.StartsWith("Assembly-CSharp") ||
                                     an.IndexOf("Novel", StringComparison.OrdinalIgnoreCase) >= 0;
                    bool typeOk2 = false;
                    if (isGameAsm)
                        foreach (var h in TYPE_HINTS2)
                            if (tn.IndexOf(h, StringComparison.OrdinalIgnoreCase) >= 0)
                            { typeOk2 = true; break; }
                    if (!typeOk && !typeOk2) continue;
                    sawType = true;
                    if (names.Count < 30) names.Add(tn);
                    MethodInfo[] ms;
                    try
                    {
                        ms = t.GetMethods(BindingFlags.Public | BindingFlags.NonPublic |
                                          BindingFlags.Instance | BindingFlags.Static |
                                          BindingFlags.DeclaredOnly);
                    }
                    catch { continue; }
                    foreach (var m in ms)
                    {
                        if (m.IsAbstract || m.ContainsGenericParameters) continue;
                        if (m.GetParameters().Length > 4) continue;      // 参数太多的大概率不是设文本
                        bool nameOk = false;
                        foreach (var w in METHOD_WHITELIST)
                            if (m.Name == w) { nameOk = true; break; }
                        if (!nameOk)
                            foreach (var w in METHOD_WHITELIST2)
                                if (m.Name == w) { nameOk = true; break; }
                        // 剧情数据类:里面带字符串参数的方法基本都在搬运剧情(构造/赋值/添加)
                        bool storyType = IsStoryType(tn);
                        if (!nameOk && storyType)
                        {
                            foreach (var pp in m.GetParameters())
                            {
                                var pt = pp.ParameterType;
                                if (pt == typeof(string) || pt == typeof(char[]) ||
                                    pt == typeof(string[]))
                                { nameOk = true; break; }
                            }
                        }
                        if (!nameOk) continue;
                        // 参数允许是任意类型:UTAGE 的 set_Text(TextData) 参数不是 string,
                        // 但里面装着台词,Pre 里用反射取出来。
                        try
                        {
                            new Harmony("gtr.storyhook." + tn + "." + m.Name).Patch(m, prefix: pre);
                            patched++;
                            if (done.Count < 40) done.Add(tn + "." + m.Name);
                        }
                        catch (Exception e)
                        {
                            Log("挂钩失败 " + tn + "." + m.Name + " : " + e.Message);
                        }
                    }
                }
            }

            if (!sawType)
            {
                if (_round % 5 == 1)
                    Log(string.Format("[{0}] 第 {1} 轮:程序集 {2} 个、类型 {3} 个,还没看到目标类型",
                                      from, _round, asmN, typeN));
                return false;
            }
            Log(string.Format("[{0}] 第 {1} 轮找到目标类型 {2} 个:{3};挂上 {4} 个方法:{5}",
                              from, _round, names.Count, string.Join(" | ", names.ToArray()),
                              patched, string.Join(" | ", done.ToArray())));
            Log("v14 挂上 " + patched + " 个方法");
            _done = patched > 0;
            return _done;
        }

        /// <summary>这个方法是不是"设置角色名"的(名字框被清空时要能传出去)。</summary>
        static bool IsNameMethod(MethodBase m)
        {
            string n = m != null ? m.Name : "";
            return n.IndexOf("NameText", StringComparison.OrdinalIgnoreCase) >= 0
                || n.IndexOf("CharacterLabel", StringComparison.OrdinalIgnoreCase) >= 0
                || n.IndexOf("NameLabel", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        public static void Pre(MethodBase __originalMethod, object[] __args)
        {
            if (__args == null) return;
            bool nameMethod = IsNameMethod(__originalMethod);
            for (int i = 0; i < __args.Length; i++)
            {
                string s = null;
                if (__args[i] is string) s = (string)__args[i];
                else if (__args[i] is char[]) s = new string((char[])__args[i]);
                else if (__args[i] is string[]) s = string.Join(" ", (string[])__args[i]);
                else s = ExtractFrom(__args[i]);
                if (string.IsNullOrEmpty(s))
                {
                    // ★名字框被**清空**也要上报(写成空文本)。
                    // 以前这里直接 continue,读取端就收不到"这一句没有名字"的信号,
                    // 于是把上一句的名字一直沿用到旁白上(玩家实测:明明游戏里没名字)。
                    if (nameMethod) Report(__originalMethod, "");
                    continue;
                }
                string clean = s.Replace("\r", " ").Replace("\n", " ").Replace("\t", " ").Trim();
                if (clean.Length < 2)
                {
                    if (nameMethod) Report(__originalMethod, clean);
                    continue;
                }
                Report(__originalMethod, clean);
            }
        }

        static readonly Dictionary<Type, PropertyInfo[]> _propCache = new Dictionary<Type, PropertyInfo[]>();
        static readonly Dictionary<Type, FieldInfo[]> _fieldCache = new Dictionary<Type, FieldInfo[]>();
        static readonly List<string> _dumped = new List<string>();

        /// <summary>从任意对象里把文本抠出来(UTAGE 的 TextData 之类)。</summary>
        static string ExtractFrom(object o)
        {
            if (o == null) return null;
            var t = o.GetType();
            string[] names = { "OriginalText", "originalText", "ParsedText", "parsedText",
                               "Text", "text", "Message", "message", "Content", "content",
                               "Value", "value", "NameText", "nameText", "TextString" };
            PropertyInfo[] props;
            FieldInfo[] fields;
            lock (_lk)
            {
                if (!_propCache.TryGetValue(t, out props))
                {
                    props = t.GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    _propCache[t] = props;
                    fields = t.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    _fieldCache[t] = fields;
                    if (_dumped.Count < 20 && !_dumped.Contains(t.FullName))
                    {
                        _dumped.Add(t.FullName);
                        var ms = new List<string>();
                        foreach (var q in props) if (q.PropertyType == typeof(string)) ms.Add("P:" + q.Name);
                        foreach (var q in fields) if (q.FieldType == typeof(string)) ms.Add("F:" + q.Name);
                        Log("  可提取类型 " + t.FullName + " -> " + string.Join(", ", ms.ToArray()));
                    }
                }
                else
                {
                    _fieldCache.TryGetValue(t, out fields);
                }
            }
            foreach (var nm in names)
            {
                foreach (var q in props)
                    if (q.Name == nm && q.PropertyType == typeof(string) && q.CanRead)
                    {
                        try { var v = (string)q.GetValue(o, null); if (!string.IsNullOrEmpty(v)) return v; }
                        catch { }
                    }
                foreach (var q in fields)
                    if (q.Name == nm && q.FieldType == typeof(string))
                    {
                        try { var v = (string)q.GetValue(o); if (!string.IsNullOrEmpty(v)) return v; }
                        catch { }
                    }
            }
            return null;   // 取不到就返回 null,不要退化成类型名(会变成噪声)
        }
        static void Report(MethodBase m, string text)
        {
            string type = m.DeclaringType != null ? m.DeclaringType.FullName : "?";
            string key = type + "." + m.Name;
            lock (_lk)
            {
                int c;
                if (_count.TryGetValue(key, out c))
                {
                    // ★这里原来是 if (c > 2000) return; —— 同一方法累计 2000 次后**永久**停止写日志。
                    // 所有台词都走 UI.Text.set_text,所以游戏一玩到某个量就再也读不到剧情,
                    // 重启游戏(计数清零)又恢复 —— 就是玩家遇到的"读着读着不读了"。
                    // 现在不再截断:日志体积由 TrimLog(>1.5MB 自动清空)兜底。
                    _count[key] = c + 1;
                }
                else
                {
                    _count[key] = 1;
                    _w.WriteLine("# 首次命中 " + key);
                }
                try { _w.WriteLine(type + "\t" + m.Name + "\t" + text); }
                catch { }
            }
        }

        // ================================================================
        //  静默推进:让游戏**自己在内部**点一下"下一句",真实鼠标一动不动
        // ----------------------------------------------------------------
        //  依据(实测反编译 KnightsCollege 的 UTAGE,详见 docs/_probe/UTAGE-advance-report.md):
        //   · UTAGE 的**左键推进不走 UnityEngine.Input**,走的是 UI EventSystem
        //     (AdvUguiManager.OnPointerDown/OnInput)。所以"伪造鼠标按键"那条路
        //     对推进剧情**完全无效** —— 别走弯路。
        //   · 真正的入口是:AdvPage.InputSendMessage() + AdvUiManager.IsInputTrig = true,
        //     这正是 UTAGE 自己给"回车/滚轮下滚"用的那套(AdvUguiManager.Update 的 IL)。
        //   · IsInputTrig 每帧在 AdvUiManager.LateUpdate 里被清零 ⇒ **必须在 Update 阶段设**,
        //     所以这段代码挂在插件自己的 Update() 里。
        //   · 两个标志都是一帧脉冲(isInputSendMessage 在 UpdateText 末尾无条件清零),
        //     所以一次调用只推进**一步**,不会变成每帧狂点一路跳过。
        //   · 选项菜单(AdvSelectionManager.IsWaitInput)为真时**绝不点击** —— 那会替你选一个。
        //  用反射而不是引用游戏装配件:换一款游戏/换一个 UTAGE 版本都不用重编插件。
        // ================================================================
        static string _clickSeq = "";
        static long _clickNextPoll = 0;
        static readonly Stopwatch _clock = Stopwatch.StartNew();   // 静默推进的轮询计时
        static Type _engType;
        static PropertyInfo _pStarted, _pPage, _pUi, _pSel, _pSelWait, _pTrig;
        static MethodInfo _mSend;
        static UnityEngine.Object _engCache;

        void Update()
        {
            try
            {
                long now = _clock.ElapsedMilliseconds;
                if (now < _clickNextPoll) return;
                _clickNextPoll = now + 200;          // 每 0.2 秒看一次请求文件(别每帧做文件 IO)
                PollClickRequest();
            }
            catch { }
        }

        static string HookDir()
        {
            try { return Paths.BepInExRootPath; } catch { return null; }
        }

        static void PollClickRequest()
        {
            string dir = HookDir();
            if (string.IsNullOrEmpty(dir)) return;
            string req = Path.Combine(dir, "_聆阅_点击请求.txt");
            if (!File.Exists(req)) return;
            string seq;
            try { seq = File.ReadAllText(req).Trim(); } catch { return; }
            if (seq.Length == 0 || seq == _clickSeq) return;
            _clickSeq = seq;
            try { File.Delete(req); } catch { }
            string why;
            bool ok = false;
            try { ok = TryAdvance(out why); }
            catch (Exception e) { why = "调用出错:" + e.Message; }
            Ack(ok ? "ok" : "fail", why);
            Log("静默推进 " + (ok ? "成功:" : "失败:") + why);
        }

        static void Ack(string st, string why)
        {
            try
            {
                string dir = HookDir();
                if (string.IsNullOrEmpty(dir)) return;
                File.WriteAllText(Path.Combine(dir, "_聆阅_点击回执.txt"), st + "\t" + why, new UTF8Encoding(false));
            }
            catch { }
        }

        /// <summary>按全名在所有已加载装配件里找类型(游戏自己的 Assembly-CSharp 也在其中)。</summary>
        static Type FindGameType(string full)
        {
            try
            {
                foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    try
                    {
                        Type t = asm.GetType(full, false);
                        if (t != null) return t;
                    }
                    catch { }
                }
            }
            catch { }
            return null;
        }

        /// <summary>找场景里的实例(兼容不同 Unity 版本:FindObjectOfType / FindFirstObjectByType / 全扫描)。</summary>
        static UnityEngine.Object FindOne(Type t)
        {
            try
            {
                MethodInfo m = typeof(UnityEngine.Object).GetMethod("FindObjectOfType", new Type[] { typeof(Type) });
                if (m != null)
                {
                    var o = m.Invoke(null, new object[] { t }) as UnityEngine.Object;
                    if (o != null) return o;
                }
            }
            catch { }
            try
            {
                MethodInfo m = typeof(UnityEngine.Object).GetMethod("FindFirstObjectByType", new Type[] { typeof(Type) });
                if (m != null)
                {
                    var o = m.Invoke(null, new object[] { t }) as UnityEngine.Object;
                    if (o != null) return o;
                }
            }
            catch { }
            try
            {
                var all = Resources.FindObjectsOfTypeAll(t);
                if (all != null)
                {
                    foreach (var o in all)
                    {
                        var c = o as Component;
                        if (c != null && c.gameObject != null && c.gameObject.activeInHierarchy) return o;
                    }
                }
            }
            catch { }
            return null;
        }

        static bool TryAdvance(out string why)
        {
            why = "";
            if (_engType == null)
            {
                _engType = FindGameType("Utage.AdvEngine");
                if (_engType == null)
                {
                    why = "这个游戏不是 UTAGE 引擎(找不到 Utage.AdvEngine),静默推进用不了";
                    return false;
                }
                _pStarted = _engType.GetProperty("IsStarted");
                _pPage = _engType.GetProperty("Page");
                _pUi = _engType.GetProperty("UiManager");
                _pSel = _engType.GetProperty("SelectionManager");
            }
            var eng = _engCache;
            if (eng == null)
            {
                eng = FindOne(_engType);
                _engCache = eng;
            }
            if (eng == null) { why = "没找到正在运行的 UTAGE 引擎(可能还在标题画面)"; return false; }
            if (_pStarted != null)
            {
                object s = _pStarted.GetValue(eng, null);
                if (s is bool && !(bool)s) { why = "剧情还没开始"; return false; }
            }
            // ★ 选项菜单:绝不代点
            object sel = _pSel != null ? _pSel.GetValue(eng, null) : null;
            if (sel != null)
            {
                if (_pSelWait == null) _pSelWait = sel.GetType().GetProperty("IsWaitInput");
                if (_pSelWait != null)
                {
                    object wv = _pSelWait.GetValue(sel, null);
                    if (wv is bool && (bool)wv) { why = "正在等你选选项,这次不推进(避免替你选)"; return false; }
                }
            }
            object page = _pPage != null ? _pPage.GetValue(eng, null) : null;
            object ui = _pUi != null ? _pUi.GetValue(eng, null) : null;
            if (page == null || ui == null) { why = "UTAGE 的 Page/UiManager 还不可用"; return false; }
            if (_mSend == null)
                _mSend = page.GetType().GetMethod("InputSendMessage",
                    BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic);
            if (_mSend == null) { why = "这个 UTAGE 版本没有 InputSendMessage"; return false; }
            _mSend.Invoke(page, null);
            if (_pTrig == null) _pTrig = ui.GetType().GetProperty("IsInputTrig");
            if (_pTrig != null && _pTrig.CanWrite) _pTrig.SetValue(ui, true, null);
            why = "UTAGE 内部推进(鼠标没动)";
            return true;
        }
    }
}
