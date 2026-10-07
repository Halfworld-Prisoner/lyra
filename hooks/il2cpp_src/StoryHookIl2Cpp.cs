// StoryHookIl2Cpp.cs —— 给 IL2CPP 游戏自己的文本挂钩插件(v3:分档挂钩)
//
// 血泪教训(AnaDos / Unity 6000.3 实测,三次崩在同一处 coreclr.dll +0x1d1fdd):
//   v1 挂了 UnityEngine.UI.Text.set_text —— 引擎内部高频方法,切场景时会在已销毁对象上
//      再设一次文本 → 原生异常穿过 托管↔原生 跳板 → 闪退(90 秒)。
//   v2 改成"只挂游戏/框架类型,跳过 UnityEngine.*/System.*" —— 跨边界异常清零了,但还是
//      110 秒闪退:因为 TMPro 也算引擎框架,一样参与 UI 销毁。
//   v3 结论:**只挂游戏自己的高层文本入口**(本地化包装 / Utage 指令 / 对话框),别碰引擎。
//      这类方法一句台词才调一次,不在销毁流程里,既稳又干净。
//
// 档位写在 <游戏>\BepInEx\storyhook_mode.txt(缺省用下面 default 那一档):
//   gameonly  只挂游戏/框架自己的类型(最稳,推荐)
//   tmpro     再加上 TMPro
//   all       连 UnityEngine.* 也挂(最危险,只在确实读不到时才试)
//   args=string | any     只挂含 string 参数的方法(默认)/ 字符数组也挂
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using BepInEx;
using BepInEx.Unity.IL2CPP;
using HarmonyLib;

namespace GtrStoryHookIl2Cpp
{
    [BepInPlugin("gtr.storyhook.il2cpp", "GTR Story Hook (IL2CPP)", "3.0.0")]
    public class StoryHookIl2Cpp : BasePlugin
    {
        static StreamWriter _w;
        static readonly object _lk = new object();
        static readonly Dictionary<string, int> _count = new Dictionary<string, int>();
        static volatile bool _done;
        static readonly Stopwatch _clock = Stopwatch.StartNew();
        const long MAX_LOG = 1500 * 1024;

        // ---- 档位 ----
        static string _profile = "gameonly";   // gameonly / tmpro / tmpro_setonly / all
        static bool _anyArgs = true;           // 是否连 char[] 之类也挂(默认挂,能多抓到打字机式推字)

        // 只挂这些方法名(各种文本框架的设置入口)
        static readonly string[] NAMES =
        {
            "SetCharArray", "SetText", "set_text", "set_Text", "SetChars",
            "ApplyText", "SetTextInternal", "SetMessage", "set_Message",
            "ShowMessage", "SetContent", "SetLines", "SetLine", "SetWord",
            // 角色名相关(名字框被清空时要能传出去,见 Pre 里的说明)
            "set_NameText", "SetNameText", "set_CharacterLabel", "set_NameLabel", "SetName"
        };

        /// <summary>这个方法是不是"设置角色名"的。</summary>
        static bool IsNameMethod(MethodBase m)
        {
            string n = m != null ? m.Name : "";
            return n.IndexOf("NameText", StringComparison.OrdinalIgnoreCase) >= 0
                || n.IndexOf("CharacterLabel", StringComparison.OrdinalIgnoreCase) >= 0
                || n.IndexOf("NameLabel", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        // 这些命名空间一律不碰(引擎内部 / 系统 / 第三方库)
        static readonly string[] SKIP_PREFIX =
        {
            "UnityEngine.", "Unity.", "Il2CppSystem.", "System.", "Microsoft.",
            "Mono.", "Newtonsoft.", "Antlr4.", "Vuplex.", "Sirenix.", "CartoonFX.",
            "ThreeDISevenZeroR.", "Il2CppInterop.", "HarmonyLib.", "BepInEx.",
            "DG.Tweening", "Unity.Mathematics", "Unity.Burst"
        };

        public override void Load()
        {
            string logPath = Path.Combine(Paths.BepInExRootPath, "storyhook.log");
            ReadProfile();
            try
            {
                _w = new StreamWriter(logPath, false, new UTF8Encoding(false));  // 每次开游戏重开一份
                _w.AutoFlush = true;
            }
            catch { }
            Log.LogInfo("StoryHook(IL2CPP) v3 启动,档位:" + _profile + (_anyArgs ? " + 数组参数" : " 只要 string")
                       + ",日志:" + logPath);
            W("# IL2CPP 版插件 v3 启动 · 档位 " + _profile + (_anyArgs ? " + 数组参数" : " 只要 string"));

            var th = new Thread(delegate ()
            {
                for (int i = 0; i < 300 && !_done; i++)
                {
                    Thread.Sleep(2000);
                    try { TryPatch(i); } catch (Exception e) { W("# 出错: " + e.Message); }
                    try { if (!_clickPatched) PatchSilentClick(); } catch (Exception e) { W("# 静默推进挂载出错: " + e.Message); }
                }
            });
            th.IsBackground = true;
            th.Start();
        }

        // ================================================================
        //  静默推进:让游戏**自己在内部**点一下"下一句",真实鼠标一动不动
        // ----------------------------------------------------------------
        //  依据(实测反编译 UTAGE,详见 docs/_probe/UTAGE-advance-report.md):
        //   · UTAGE 的左键推进**不走 UnityEngine.Input**(那是 icall,补托管代理也没用),
        //     它走 UI EventSystem → AdvUguiManager.OnPointerDown → OnInput。
        //     所以"伪造鼠标按键"这条路对推进剧情无效,IL2CPP 上还属于已知崩溃类。
        //   · 真正的入口:AdvPage.InputSendMessage() + AdvUiManager.IsInputTrig = true
        //     —— 这正是 UTAGE 自己给"回车/滚轮"用的那套(AdvUguiManager.Update 的 IL)。
        //   · IsInputTrig 每帧在 AdvUiManager.LateUpdate 里清零 ⇒ 必须在 **Update 阶段**设,
        //     所以这里把请求挂在 **Utage.AdvUguiManager.Update 的 Postfix** 上
        //     (目标是 UTAGE 自己的方法,不是 TMPro / 引擎模块那些会闪退的类型)。
        //   · 两个标志都是一帧脉冲,一次调用只推进一步,不会一路 skip。
        // ================================================================
        static bool _clickPatched;
        static string _clickSeq = "";
        static long _clickNextPoll;

        static void PatchSilentClick()
        {
            Type tUi = FindGameType("Utage.AdvUguiManager") ?? FindGameType("Utage.AdvUiManager");
            if (tUi == null)
            {
                _clickPatched = true;                 // 不是 UTAGE:别再重试,自动退回鼠标点击
                W("# 静默推进:这个游戏没有 Utage.AdvUguiManager,自动点击会走鼠标(不影响读数)");
                return;
            }
            MethodInfo mi = null;
            for (Type t = tUi; t != null && mi == null; t = t.BaseType)
                mi = t.GetMethod("Update", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (mi == null)
            {
                _clickPatched = true;
                W("# 静默推进:AdvUguiManager 上找不到 Update,自动点击会走鼠标");
                return;
            }
            var harmony = new Harmony("gtr.storyhook.il2cpp.click");
            harmony.Patch(mi, null, new HarmonyMethod(typeof(StoryHookIl2Cpp).GetMethod(
                "ClickPostfix", BindingFlags.Static | BindingFlags.Public)), null);
            _clickPatched = true;
            W("# 静默推进已就绪:挂上 Utage.AdvUguiManager.Update(点下一句不会动鼠标)");
        }

        /// <summary>每帧跑一次(Update 阶段);只做一次很便宜的时间判断,0.2 秒才看一次文件。</summary>
        public static void ClickPostfix(object __instance)
        {
            try
            {
                long now = _clock.ElapsedMilliseconds;
                if (now < _clickNextPoll) return;
                _clickNextPoll = now + 200;
                PollClickRequest(__instance);
            }
            catch { }
        }

        static string HookDir()
        {
            try { return Paths.BepInExRootPath; } catch { return null; }
        }

        static void PollClickRequest(object uiInstance)
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
            try { ok = TryAdvance(uiInstance, out why); }
            catch (Exception e) { why = "调用出错:" + e.Message; }
            try { File.WriteAllText(Path.Combine(dir, "_聆阅_点击回执.txt"), (ok ? "ok" : "fail") + "\t" + why, new UTF8Encoding(false)); } catch { }
            W("# 静默推进 " + (ok ? "成功:" : "失败:") + why);
        }

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

        static object Prop(object o, string name)
        {
            if (o == null) return null;
            try
            {
                PropertyInfo p = o.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.Instance);
                return p == null ? null : p.GetValue(o, null);
            }
            catch { return null; }
        }

        static bool TryAdvance(object ui, out string why)
        {
            why = "";
            if (ui == null) { why = "拿不到 UTAGE 界面管理器"; return false; }
            object eng = Prop(ui, "Engine");
            if (eng == null) { why = "拿不到 AdvEngine"; return false; }
            object started = Prop(eng, "IsStarted");
            if (started is bool && !(bool)started) { why = "剧情还没开始"; return false; }
            object sel = Prop(eng, "SelectionManager");
            if (sel != null)
            {
                object w = Prop(sel, "IsWaitInput");
                if (w is bool && (bool)w) { why = "正在等你选选项,这次不推进(避免替你选)"; return false; }
            }
            object page = Prop(eng, "Page");
            if (page == null) { why = "拿不到 AdvPage"; return false; }
            MethodInfo send = page.GetType().GetMethod("InputSendMessage",
                BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic);
            if (send == null) { why = "这个 UTAGE 版本没有 InputSendMessage"; return false; }
            send.Invoke(page, null);
            try
            {
                PropertyInfo tr = ui.GetType().GetProperty("IsInputTrig", BindingFlags.Public | BindingFlags.Instance);
                if (tr != null && tr.CanWrite) tr.SetValue(ui, true, null);
            }
            catch { }
            why = "UTAGE 内部推进(鼠标没动)";
            return true;
        }

        static void ReadProfile()
        {
            try
            {
                string f = Path.Combine(Paths.BepInExRootPath, "storyhook_mode.txt");
                if (!File.Exists(f)) return;
                foreach (string raw in File.ReadAllLines(f))
                {
                    string line = raw.Trim();
                    if (line.Length == 0 || line[0] == '#') continue;
                    int eq = line.IndexOf('=');
                    if (eq < 0)
                    {
                        _profile = line.ToLowerInvariant();
                        continue;
                    }
                    string k = line.Substring(0, eq).Trim().ToLowerInvariant();
                    string v = line.Substring(eq + 1).Trim().ToLowerInvariant();
                    if (k == "profile" || k == "mode") _profile = v;
                    else if (k == "args") _anyArgs = (v == "any");
                }
            }
            catch { }
        }

        static void W(string s)
        {
            lock (_lk)
            {
                try
                {
                    if (_w == null) return;
                    _w.WriteLine(string.Format("# [t={0:0.0}s] {1}", _clock.Elapsed.TotalSeconds, s));
                    if (_w.BaseStream.Length > MAX_LOG) Trim();
                }
                catch { }
            }
        }

        /// <summary>日志超过 1.5MB 就砍掉前半,免得把硬盘写满(读取端按行尾跟随,不怕截断)。</summary>
        static void Trim()
        {
            try
            {
                _w.Flush();
                string p = ((FileStream)_w.BaseStream).Name;
                _w.Dispose();
                string[] all = File.ReadAllLines(p, Encoding.UTF8);
                int keep = all.Length / 2;
                var sb = new StringBuilder();
                for (int i = all.Length - keep; i < all.Length; i++) sb.AppendLine(all[i]);
                File.WriteAllText(p, sb.ToString(), new UTF8Encoding(false));
                _w = new StreamWriter(p, true, new UTF8Encoding(false));
                _w.AutoFlush = true;
            }
            catch { }
        }

        static bool Skipped(string tn)
        {
            if (_profile != "all")
            {
                for (int i = 0; i < SKIP_PREFIX.Length; i++)
                    if (tn.StartsWith(SKIP_PREFIX[i], StringComparison.Ordinal)) return true;
            }
            // TMPro 属于引擎框架,默认不挂 —— 实测挂上它的 set_text 后游戏会在读盘/切场景时
            // 闪退(80 秒)。tmpro_setonly 档允许挂 TMPro,但跳过 set_text(见 SkipMethod)。
            if (_profile == "gameonly" && tn.StartsWith("TMPro.", StringComparison.Ordinal)) return true;
            return false;
        }

        /// <summary>tmpro_setonly 档:TMPro 只挂"主动设置文本"的方法,不挂属性 setter。
        /// 属性 setter(set_text)是引擎自己在布局/销毁时也会调的,是实测的崩溃源。</summary>
        static bool SkipMethod(string tn, string mn)
        {
            if (_profile == "tmpro_setonly" && tn.StartsWith("TMPro.", StringComparison.Ordinal))
                return mn == "set_text" || mn == "set_Text";
            return false;
        }

        static void TryPatch(int round)
        {
            if (_done) return;
            var pre = new HarmonyMethod(typeof(StoryHookIl2Cpp).GetMethod("Pre",
                BindingFlags.Static | BindingFlags.Public));
            int patched = 0, asmN = 0, typeN = 0, skipN = 0;
            var done = new List<string>();

            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                string an = asm.GetName().Name;
                if (asm.IsDynamic) continue;
                if (an.StartsWith("System") || an == "mscorlib" || an == "netstandard") continue;
                if (an.StartsWith("BepInEx") || an.StartsWith("0Harmony")) continue;
                asmN++;
                Type[] types;
                try { types = asm.GetTypes(); } catch { continue; }
                typeN += types.Length;
                foreach (var t in types)
                {
                    if (t == null || t.ContainsGenericParameters) continue;
                    // 只关心文本相关类型,避免挂到成千上万个方法上
                    string tn = t.FullName ?? t.Name;
                    if (tn.IndexOf("Text", StringComparison.OrdinalIgnoreCase) < 0 &&
                        tn.IndexOf("Message", StringComparison.OrdinalIgnoreCase) < 0 &&
                        tn.IndexOf("Dialog", StringComparison.OrdinalIgnoreCase) < 0 &&
                        tn.IndexOf("Label", StringComparison.OrdinalIgnoreCase) < 0 &&
                        tn.IndexOf("Story", StringComparison.OrdinalIgnoreCase) < 0 &&
                        tn.IndexOf("Scenario", StringComparison.OrdinalIgnoreCase) < 0 &&
                        tn.IndexOf("Adv", StringComparison.OrdinalIgnoreCase) < 0 &&
                        tn.IndexOf("Localiz", StringComparison.OrdinalIgnoreCase) < 0) continue;
                    if (Skipped(tn)) { skipN++; continue; }

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
                        var ps = m.GetParameters();
                        if (ps.Length == 0 || ps.Length > 6) continue;
                        bool nameOk = false;
                        foreach (var n in NAMES) if (m.Name == n) { nameOk = true; break; }
                        if (!nameOk) continue;
                        if (SkipMethod(tn, m.Name)) continue;
                        bool argOk = false;
                        foreach (var p in ps)
                        {
                            var pt = p.ParameterType;
                            if (pt == typeof(string)) { argOk = true; break; }
                            if (_anyArgs &&
                                (pt == typeof(char[]) ||
                                 pt.Name == "Il2CppStructArray`1" || pt.Name == "Il2CppArrayBase`1" ||
                                 pt.Name == "Il2CppReferenceArray`1" ||
                                 typeof(IEnumerable).IsAssignableFrom(pt)))
                            { argOk = true; break; }
                        }
                        if (!argOk) continue;
                        try
                        {
                            new Harmony("gtr.storyhook.il2cpp." + tn + "." + m.Name).Patch(m, prefix: pre);
                            patched++;
                            if (done.Count < 40) done.Add(tn + "." + m.Name);
                        }
                        catch (Exception e)
                        {
                            if (done.Count < 40) done.Add("×" + tn + "." + m.Name + "(" + e.Message + ")");
                        }
                    }
                }
            }

            if (patched == 0)
            {
                if (round % 5 == 1)
                    W(string.Format("第 {0} 轮:程序集 {1} 个、类型 {2} 个,尚未挂到方法(等 Il2CppInterop 生成代理程序集)",
                                    round, asmN, typeN));
                return;
            }
            W(string.Format("挂上 {0} 个方法(跳过引擎/系统类型 {1} 个):{2}",
                            patched, skipN, string.Join(" | ", done.ToArray())));
            _done = true;
        }

        public static void Pre(MethodBase __originalMethod, object[] __args)
        {
            if (__args == null) return;
            bool nameMethod = IsNameMethod(__originalMethod);
            for (int i = 0; i < __args.Length; i++)
            {
                string s = ToText(__args[i]);
                if (string.IsNullOrEmpty(s))
                {
                    // ★名字框被**清空**也要上报(写成空文本):读取端靠它知道
                    // "这一句没有名字",否则会把上一句的角色名一直沿用到旁白上。
                    if (nameMethod) Report(__originalMethod, "");
                    continue;
                }
                s = s.Replace("\r", " ").Replace("\n", " ").Replace("\t", " ").Trim();
                if (s.Length < 2)
                {
                    if (nameMethod) Report(__originalMethod, s);
                    continue;
                }
                Report(__originalMethod, s);
            }
        }

        /// <summary>把参数转成文本:string / char[] / IL2CPP 的字符数组都能处理。</summary>
        static string ToText(object o)
        {
            if (o == null) return null;
            if (o is string) return (string)o;
            if (o is char[]) return new string((char[])o);
            if (o is StringBuilder) return o.ToString();
            if (o is IEnumerable)
            {
                var sb = new StringBuilder();
                foreach (var it in (IEnumerable)o)
                {
                    if (it is char) sb.Append((char)it);
                    else if (it is string) sb.Append((string)it);
                    else return null;          // 不是字符集合,别乱拼
                    if (sb.Length > 4000) break;
                }
                return sb.Length > 0 ? sb.ToString() : null;
            }
            return null;
        }

        static void Report(MethodBase m, string text)
        {
            string type = m.DeclaringType != null ? m.DeclaringType.FullName : "?";
            string key = type + "." + m.Name;
            lock (_lk)
            {
                // 注意:这里**不能**因为"调得太多"就永久闭嘴。
                // 旧版 Mono 插件就是加了 `if (c > 2000) return;`,结果游戏读了一会儿之后
                // 再也不出字(所有台词都走同一个方法,2000 次之后全被吞了)。
                int c;
                if (!_count.TryGetValue(key, out c))
                {
                    _count[key] = 1;
                    W("首次命中 " + key);
                }
                else _count[key] = c + 1;
                try
                {
                    _w.WriteLine(type + "\t" + m.Name + "\t" + text);
                    if (_w.BaseStream.Length > MAX_LOG) Trim();
                }
                catch { }
            }
        }
    }
}
