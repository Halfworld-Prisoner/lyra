# UTAGE ADV —— 推进对话 API 侦察报告(静默点击,不动真实鼠标)

侦察方式:**只读**。Mono.Cecil 0.11.4 从 `D:\Unity阅读器\payload\il2cpp_x64\BepInEx\core\Mono.Cecil.dll`
载入 Windows PowerShell 5.1;原始转储脚本在 `D:\Unity阅读器\docs\_probe\`。

---

## 0. 三个必须先纠正的事实

| # | 事项 | 结论 |
|---|---|---|
| 1 | **`D:\Unity阅读器\payload\il2cpp_x64\BepInEx\interop\Assembly-CSharp.dll` 不是 AnaDos 的** | 它是 **Astatos** 的。里面 **没有任何 `Utage*` 类型**。证据见 §4。 |
| 2 | **AnaDos 真正的安装位置** | `D:\Program Files\AnaDos`(不在 Steam 库下),Unity 6000.3.6f1 / IL2CPP x64,**当前没有装 BepInEx**(所以没有任何 interop)。 |
| 3 | **UTAGE 不在独立的 `Utage.dll` 里** | 两个游戏都是 **内联编译进 `Assembly-CSharp.dll`**。只有 *Knights College 2* 才有独立的 `Utage.dll`。 |

---

## 1. 已核实(KnightsCollege / Mono)

装配件:`D:\Steam\steamapps\common\KnightsCollege\KnightsCollege_Data\Managed\Assembly-CSharp.dll`
(961,536 字节,`Assembly-CSharp, Version=0.0.0.0`,730 个顶层类型)

`FullName` 含 `Utage` 的类型 **842** 个;命名空间 `Utage`、`UtageExtensions`,
另有全局命名空间的 `UtageUgui*`(`UtageUguiMainGame` / `UtageUguiTitle` / `UtageUguiConfig` …)。
完整类型清单 + 122 个重点类型的全部成员见 **`KnightsCollege-utage.md`**(4853 行)。

### 1.1 `Utage.AdvEngine : UnityEngine.MonoBehaviour`
```
public AdvDataManager        DataManager           { get; }
public AdvScenarioPlayer     ScenarioPlayer        { get; }
public AdvPage               Page                  { get; }
public AdvSelectionManager   SelectionManager      { get; }
public AdvMessageWindowManager MessageWindowManager { get; }
public AdvBacklogManager     BacklogManager        { get; }
public AdvConfig             Config                { get; }
public AdvSystemSaveData     SystemSaveData        { get; }
public AdvSaveManager        SaveManager           { get; }
public AdvGraphicManager     GraphicManager        { get; }
public AdvEffectManager      EffectManager         { get; }
public AdvUiManager          UiManager             { get; }
public SoundManager          SoundManager          { get; }
public CameraManager         CameraManager         { get; }
public AdvTime               Time                  { get; }
public AdvParamManager       Param                 { get; }
public bool IsStarted          { get; }
public bool IsLoading          { get; }
public bool IsEndScenario      { get; }
public bool IsPausingScenario  { get; }
public bool IsEndOrPauseScenario { get; }
public bool IsSceneGallery     { get; }
public bool IsWaitBootLoading  { get; }
public void StartGame(); public void StartGame(string scenarioLabel);
public bool ResumeScenario(); public void JumpScenario(string label);
public void EndScenario(); public void QuickSave(); public bool QuickLoad();
public void StartSceneGallery(string label); public void OpenLoadGame(AdvSaveData);
public System.Collections.IEnumerator LoadChapterAsync(string url); public bool ExitsChapter(string url);
```
* `private void OnClicked()` 的 IL **只有一条 `ret`** —— 空方法,不是点击入口。
* **没有 `IsWaitInput`**;`AdvEngine` 上不存在这个成员。

### 1.2 `Utage.AdvPage : UnityEngine.MonoBehaviour` ← 推进对话的核心
```
public bool IsWaitInputInPage        { get; }        // = IsWaitingInputCommand
public bool IsWaitIntputInPage       { get; }        // 引擎拼写错误,同上
public bool IsWaitingInputCommand    { get; set; }   // ★ setter 是 public
public bool IsWaitingIntputCommand   { get; }        // 拼写错误别名
public bool IsWaitTextCommand        { get; }
public bool IsWaitBrPage             { get; }        // 等翻页点击
public bool IsWaitPage               { get; }
public bool IsShowingText            { get; }
public bool IsSendChar               { get; }        // 打字机还在推字
public bool IsSavePoint              { get; }
public string ScenarioLabel          { get; }
public int  PageNo                   { get; }
public AdvEngine Engine              { get; }
public AdvPageEvent OnTrigInput      { get; }        // UnityEvent<AdvPage>
public AdvPageEvent OnBeginPage / OnBeginText / OnChangeText / OnEndText / OnEndPage
                  / OnChangeStatus / OnTrigWaitInputInPage / OnTrigWaitInputBrPage { get; }
public float SkippedSpeed            { get; }

public void InputSendMessage();                      // ★ 等价于"玩家点了一下"
public void UpdateText();
public bool CheckSkip();  public bool EnableSkip();  public bool CheckReadPage();
public float ToSkippedTime(float time);
public void BeginPage(AdvScenarioPageData); public void EndPage(); public void Clear();

private bool IsInputSendMessage();
private void UpdateWaitInput();   private void ToNextCommand();
private void UpdateSendChar();    private void EndSendChar();  private void SendChar(float);
```

**IL 语义(逐条读出)**

```
AdvPage::InputSendMessage()      =>  isInputSendMessage = true;      // 一行,无副作用
AdvPage::IsInputSendMessage()    =>  isInputSendMessage || CheckSkip();
AdvPage::UpdateWaitInput():
    if (Config.IsAutoBrPage && !SoundManager.IsPlayingVoice()
        && waitingTimeInput >= Config.AutoPageWaitTime) { ToNextCommand(); return; }   // 自动模式
    if (IsInputSendMessage()) {
        if (isInputSendMessage) OnTrigInput.Invoke(this);
        if (Config.VoiceStopType == 1) SoundManager.StopVoiceIgnoreLoop();
        ToNextCommand(); return;
    }
    waitingTimeInput += Engine.Time.DeltaTime;
AdvPage::UpdateText():
    LastInputSendMessage = false;
    switch (Status) {
        case PageStatus.SendChar            (1): UpdateSendChar(); LastInputSendMessage = isInputSendMessage; break;
        case PageStatus.WaitInputInPage     (3): UpdateWaitInput(); break;
        case PageStatus.WaitInputBrPage     (6): UpdateWaitInput(); break;
        case PageStatus.WaitEffectOnInputInPage (2): UpdateWaitEffectOnInput(); break;
        case PageStatus.WaitEffectOnEndPage (5): UpdateWaitEffectOnEndPage(); break;
        case PageStatus.OtherCommandInPage  (4): break;
    }
    isInputSendMessage = false;          // ★★ 每帧末尾清零 → 一次点击 = 一帧脉冲
AdvPage::UpdateSendChar() 也走 IsInputSendMessage()  → 第一次输入 = 立刻显示完整文本
```

**`Utage.AdvPage/PageStatus`(已核实)**
```
None = 0 · SendChar = 1 · WaitEffectOnInputInPage = 2 · WaitInputInPage = 3
OtherCommandInPage = 4 · WaitEffectOnEndPage = 5 · WaitInputBrPage = 6
```
**`Utage.AdvCommandWaitType`**:`ThisAndAdd = 0 · PageWait = 1 · InputWait = 2 · Add = 3 · NoWait = 4`
**`Utage.VoiceStopType`**:`OnNextVoice = 0 · OnClick = 1`

> **关键安全性结论**:`isInputSendMessage` 在 **每次 `UpdateText()` 的末尾都被清成 `false`**,
> `AdvUiManager.IsInputTrig` 在 **每次 `AdvUiManager.LateUpdate()` 都被清成 `false`**。
> 所以 `InputSendMessage()` / `IsInputTrig = true` 都是**一帧脉冲**,和真实点击一样是"点一下走一步",
> **不会**变成"每帧狂点、一路 skip 到底"。`AdvPage.IsSendChar` 可以区分当前是哪一段:
> 为真 ⇒ 这一下是"推完打字机";为假 ⇒ 这一下是"进下一句"。

### 1.3 `Utage.AdvUiManager : UnityEngine.MonoBehaviour`(抽象)+ `Utage.AdvUguiManager`
```
// AdvUiManager
public bool IsInputTrig                  { get; set; }   // ★ setter 是 public
public bool IsInputTrigCustom            { get; set; }
public bool IsPointerDowned              { get; }
public PointerEventData CurrentPointerData { get; private set; }
public AdvEngine Engine                  { get; }
public virtual void OnPointerDown(PointerEventData data);
public void ClearPointerDown();          // CurrentPointerData = null; IsInputTrig = false;
public void HideMessageWindow();  public void ShowMessageWindow();
protected virtual void LateUpdate();     // 每帧 ClearPointerDown() + IsInputTrigCustom = false
public abstract void Open();  public abstract void Close();
public enum UiStatus { Default = 0, Backlog = 1, HideMessageWindow = 2 }

// AdvUguiManager : AdvUiManager   ← 本作实际使用的具体类
public virtual void OnInput(BaseEventData data);          // ★★ 真正的"点击"入口
public virtual void OnPointerDown(BaseEventData data);    // 左键过滤后转调 OnInput
protected virtual void Update();
public AdvUguiMessageWindowManager MessageWindow { get; }
```

**`AdvUguiManager.OnInput` 的 IL 反编译语义(这就是"一次左键"的全部行为)**

```csharp
public virtual void OnInput(BaseEventData data) {
    switch (Status) {
        case UiStatus.Default:                       // 0
            if (Engine.Config.IsSkip) { Engine.Config.ToggleSkip(); return; }
            if (IsShowingMessageWindow && !Engine.Config.IsSkip)
                Engine.Page.InputSendMessage();       // ← 推进
            if (data == null) return;
            if (!(data is PointerEventData ped)) return;
            base.OnPointerDown(ped);                  // CurrentPointerData = ped; IsInputTrig = true;
            return;
        case UiStatus.Backlog:            return;     // 1:什么都不做
        case UiStatus.HideMessageWindow:  Status = UiStatus.Default; return;   // 2:恢复对话框
    }
}
```

**`AdvUguiManager.OnPointerDown(BaseEventData)`**:`if (data is PointerEventData ped && ped.button != InputButton.Left) return; else OnInput(data);`
即 **左键过滤 → OnInput**。

**`AdvUguiManager.Update()` 的 IL 语义(键盘回车 / 滚轮路径 —— 与真实点击等价)**

```csharp
bool trig = (Engine.Config.IsMouseWheelSendMessage && InputUtil.IsInputScrollWheelDown())
            || InputUtil.IsInputKeyboadReturnDown();
switch (Status) {
    case 0: if (InputUtil.IsMouseRightButtonDown()) { Status = 0; return; }
            if (!disableMouseWheelBackLog && InputUtil.IsInputScrollWheelUp()) { Status = Backlog; return; }
            ...
    case 2: if (IsShowingMessageWindow) Engine.Page.UpdateText();
            ...
            if (trig) { Engine.Page.InputSendMessage(); IsInputTrig = true; }   // ★ 引擎自己的"假点击"
}
```

> **结论:UTAGE 自己把"回车/滚轮下滚"实现为
> `Page.InputSendMessage() + UiManager.IsInputTrig = true`。
> 这就是最忠实的静默推进配方。**

### 1.4 等待输入的判定(问题 5 的答案)
```
Utage.AdvSelectionManager.IsWaitInput   { get; set; }   // ★ 选项菜单在等选择 —— 此时绝不能点
Utage.AdvPage.IsWaitInputInPage         { get; }        // = IsWaitingInputCommand
Utage.AdvPage.IsWaitingInputCommand     { get; set; }
Utage.AdvPage.IsWaitBrPage              { get; }        // 等翻页
Utage.AdvUiManager.IsInputTrig          { get; set; }   // AdvCommandWaitInput 读的就是它
Utage.AdvWaitManager.IsWaiting          { get; internal; }
Utage.AdvConfig.IsSkip / IsAutoBrPage   { get; set; }
Utage.AdvEngine.IsEndScenario / IsPausingScenario / IsEndOrPauseScenario / IsLoading / IsStarted
```
`AdvPage.IsWaitInputInPage` 的 getter IL 就是 `return IsWaitingInputCommand;` —— 两者完全等价。

### 1.5 输入层(问题 2 的答案)
`Utage.InputUtil`(static,完整成员):
```
public static bool IsMousceRightButtonDown();   // 引擎拼写错误
public static bool IsMouseRightButtonDown();
public static bool IsInputControl();
public static bool IsInputScrollWheelUp();
public static bool IsInputScrollWheelDown();
public static bool IsInputKeyboadReturnDown();  // 引擎拼写错误
public static bool EnableWebGLInput();
private static float wheelSensitive;
```
**没有左键 getter。**

全装配件对 `UnityEngine.Input::*` 的调用点共 **37** 处,UTAGE 只占这些:

| 调用方 | 目标 | 用途 |
|---|---|---|
| `Utage.InputUtil::IsMouseRightButtonDown` | `UnityEngine.Input::GetMouseButtonDown` | **右键** |
| `Utage.InputUtil::IsInputControl` | `UnityEngine.Input::GetKey` ×2 | Ctrl |
| `Utage.InputUtil::IsInputScrollWheelUp/Down` | `UnityEngine.Input::GetAxis` | 滚轮 |
| `Utage.InputUtil::IsInputKeyboadReturnDown` | `UnityEngine.Input::GetKeyDown` | 回车 |
| `Utage.SystemUi::Update` / `Utage.QuitButton::Update` | `UnityEngine.Input::GetKeyDown` | 调试/退出 |

其余全在 UnityChan / Live2D 示例代码里。

> **UTAGE 用的是:老式 `UnityEngine.Input`(仅右键/滚轮/Ctrl/回车)
> + Unity UI EventSystem(`IPointerClickHandler` / `PointerEventData`)负责左键推进。
> 全装配件 0 处引用新版 Input System。**

`Utage.AdvClickEvent : MonoBehaviour, IPointerClickHandler, IAdvClickEvent`
`Utage.IAdvClickEvent.AddClickEvent(bool isPolygon, StringGridRow row, UnityAction<BaseEventData> action)` /
`RemoveClickEvent()` —— 这是"点画面上的图形对象"用的,**不是**推进对话用的。

### 1.6 单例 / 管理器(问题 3 的答案)
* 扫描全装配件的 **static 字段/属性中类型为 `Utage.AdvEngine` 的** → **0 个**。
* `Utage.AdvEngine` **没有静态实例成员**。
* UTAGE 里确实有 `private static X instance` + `public static X Instance` 的类型,但只有这些:
  `CustomProjectSetting`、`LanguageManagerBase`、`ApplicationEvent`、`AssetFileManager`、
  `SoundManager`、`CloudBuildManifest`、`DebugPrint`、`SystemUi`、`WrapperMoviePlayer`
  —— **`AdvEngine` / `ScenarioManager` / `AdvManager` 都不在其中**。
* 持有 `AdvEngine` 引用的实例字段(可用于间接拿引擎):
  `Utage.AdvPage.engine`、`Utage.AdvUiManager.engine`、`Utage.AdvMessageWindowManager.engine`、
  `Utage.AdvSelectionManager.engine`、`Utage.AdvScenarioPlayer.engine`、`Utage.AdvConfig`(无)、
  `Utage.AdvUguiMessageWindow.engine`、以及全局命名空间的
  **`UtageUguiMainGame.Engine { get; }`**(`public AdvEngine Engine`)。

> **拿到实例的唯一可靠办法:`UnityEngine.Object.FindObjectOfType<Utage.AdvEngine>()`**
> (Unity 6 可用 `FindFirstObjectByType<AdvEngine>()` / `FindAnyObjectByType<AdvEngine>()`),
> 或 `Resources.FindObjectsOfTypeAll<Utage.AdvEngine>()`。
> 拿到 `AdvEngine` 之后,`Page` / `UiManager` / `SelectionManager` 都是 public getter,不用再找。

---

## 2. 已核实(AnaDos / IL2CPP)

* 路径:`D:\Program Files\AnaDos`(`anados.exe`,679,824 B;`GameAssembly.dll`,68,711,936 B)。
* `anados_Data\app.info` = `Habbit` / `AnaDosR`。Unity **6000.3.6f1**,IL2CPP x64。
* `anados_Data\il2cpp_data\Metadata\global-metadata.dat` = 13,822,928 字节,
  magic `0xFAB11BAF`,metadata version **39**,字符串表 20,483 条,类型定义 16,298 个,
  images / assemblies 各 104 个。
* **当前该目录下没有 `BepInEx`、没有 `dotnet`、没有 `winhttp.dll`** —— 挂钩模块已被卸载。
* `anados_Data\ScriptingAssemblies.json` 列出 151 个装配件,
  游戏自己的只有 **`Assembly-CSharp.dll`** 和 **`Assembly-CSharp-firstpass.dll`**
  —— **没有 `Utage.dll`**,⇒ UTAGE 内联在 `Assembly-CSharp.dll` 里。

### 2.1 元数据原文命中次数
`Utage` 1434 · `AdvCommand` 329 · `AdvEngine` 29 · `AdvMessageWindow` 22 · `InputUtil` 13 ·
`AdvPage` 12 · `AdvBacklog` 10 · `AdvClickEvent` 9 · `IsInputTrig` 8 · `InputSendMessage` 7 ·
`AdvScenarioPlayer` 6 · `AdvUguiManager` 4 · `AdvUiManager` 3

### 2.2 逐个精确名核对(全部 PRESENT)
类型:`AdvEngine` `AdvScenarioPlayer` `AdvScenarioThread` `AdvPage` `AdvUiManager` `AdvUguiManager`
`AdvMessageWindowManager` `AdvUguiMessageWindowManager` `AdvCommandWaitInput` `AdvCommandWaitBase`
`AdvCommand` `AdvCommandText` `AdvSelectionManager` `AdvBacklogManager` `AdvUguiBacklogManager`
`AdvClickEvent` `IAdvClickEvent` `InputUtil` `AdvEngineStarter` `AdvConfig` `AdvScenarioPageData`
`AdvWaitManager` `AdvPageController` `AdvParamManager` `AdvSaveManager` `AdvGraphicManager`
`AdvMessageWindow` `AdvUguiMessageWindow` `UguiBackgroundRaycastReciever` `AdvCustomCommandManager`
`AdvScenarioLabelData` `AdvDataManager`

成员:`InputSendMessage` `IsInputSendMessage` `IsWaitInputInPage` `IsWaitIntputInPage`
`IsWaitingInputCommand` `IsWaitingIntputCommand` `IsSendChar` `IsWaitBrPage` `OnTrigInput`
`UpdateText` `UpdateWaitInput` `ToNextCommand` `CheckSkip` `EnableSkip` `CheckReadPage`
`BeginPage` `EndPage` `OnPointerDown` `OnInput` `OnPointerClick` `ClearPointerDown`
`IsInputTrig` `IsInputTrigCustom` `IsPointerDowned` `CurrentPointerData` `LateUpdate`
`IsMousceRightButtonDown` `IsMouseRightButtonDown` `IsInputControl` `IsInputScrollWheelUp`
`IsInputScrollWheelDown` `IsInputKeyboadReturnDown` `IsWaitInput` `IsEndScenario` `IsPausing`
`IsSkip` `IsAuto` `ToggleSkip` `IsAutoBrPage` `AutoPageWaitTime` `IsMouseWheelSendMessage`
`IsAutoSave` `SkippedSpeed` `JumpScenario` `StartScenario` `ResumeScenario` `EndScenario`
`Pause` `Resume` `AddClickEvent` `RemoveClickEvent` `Open` `Close` `HideMessageWindow`
`ShowMessageWindow` `Clear`

**缺失(仅 KnightsCollege 的新版才有):`SkipSpeed`(KC 里是拼错的 `SkipSpped`)、
`GetMessageWindowManagerCreateIfMissing`。**

> ⇒ **AnaDos 的 UTAGE 与 KnightsCollege 是同一代(或极接近),上面 §1 的 API 与 IL 语义可直接套用。**

### 2.3 证据等级说明
* **已核实**:UTAGE 存在、在 `Assembly-CSharp.dll`、上述**名字**都在元数据字符串池里、
  两个游戏类型数/成员名集合一致。
* **推断(高置信度)**:名字到"哪个类型"的绑定(如 `Utage.AdvEngine.Page`、`Utage.AdvPage.InputSendMessage`)。
  依据:`Utage` 命名空间 token 出现 1434 次 + 全部类型名与成员名齐备 + 与 KC 同代。
  想 100% 坐实,装一次 BepInEx 6 看生成的 interop 即可(见 §6)。

---

## 3. 输入层 & 单例 —— 一句话总结

| 问题 | 答案 |
|---|---|
| 左键推进走哪条路? | Unity UI **EventSystem** → `AdvUguiManager.OnPointerDown(BaseEventData)`(左键过滤)→ `AdvUguiManager.OnInput(BaseEventData)` |
| 老式 `Input` 用在哪? | 只有右键 / 滚轮 / Ctrl / 回车,全在 `Utage.InputUtil` |
| 新版 Input System? | **完全没用**(0 处引用)。KC2 的 `Utage.dll` 才有 `IInputStrategy` + `UtageInputSystem.dll` |
| 有静态单例吗? | **没有**。`AdvEngine` 无任何静态实例成员 |
| 怎么拿实例? | `Object.FindObjectOfType<Utage.AdvEngine>()` |
| `AdvEngine.IsWaitInput` 存在吗? | **不存在**。等价物是 `AdvSelectionManager.IsWaitInput` / `AdvPage.IsWaitInputInPage` |

---

## 4. 你给的 interop 路径是错的(证据)

`D:\Unity阅读器\payload\il2cpp_x64\BepInEx\interop\Assembly-CSharp.dll`(4,748,288 B):
* `FullName` 含 `Utage` 的类型:**0 个**。
* 命名空间:全局 1472 个、`story` 7 个、`Il2CppSystem.Runtime.CompilerServices` 2 个、
  `Il2CppMicrosoft.CodeAnalysis` 1 个。
* 唯一带 `Adv` 的类型:`story.storyMaster/_AutoModeAdvance_d__210`、`story.Story_Skip/_AutoAdvanceDialogue_d__12`。
* `assembly-hash.txt` = `d1327ed430cf77f1033207d2a6b993c0`
  —— 与 **`D:\Steam\steamapps\common\Astatos\BepInEx\interop\assembly-hash.txt` 完全相同**。
* `D:\Unity阅读器\payload\il2cpp_x64\BepInEx\ErrorLog.log` 首行:
  `Setting breakpad minidump AppID = 1430970` → **Astatos**。
* `D:\Steam\steamapps\common\Astatos\_聆阅_已安装清单.json` 里
  `"pack": "...\payload\il2cpp_x64"`,即 Astatos 用的正是这份 payload。

⇒ 这份 interop 是 **Astatos 的**(Astatos 用的是它自己的 `story` 命名空间引擎,**不是 UTAGE**)。
AnaDos 的 interop 目前**根本不存在**,因为它现在没装 BepInEx。

---

## 5. 排序后的推荐方案(两套后端通用)

> 前提:两个后端的 UTAGE 推进入口**完全一样**,所以**同一套逻辑两边都能用**,
> 只有"怎么编译/引用"不同。

### 🥇 Option A —— 直接调用 public 方法(推荐)
**调用什么**:`AdvPage.InputSendMessage()` + `AdvUiManager.IsInputTrig = true`
(= UTAGE 自己给回车/滚轮用的那套);或更高层的 `AdvUguiManager.OnInput(...)`。

**怎么拿实例**:`Object.FindObjectOfType<Utage.AdvEngine>()` → `engine.Page` / `engine.UiManager`。

**崩溃风险:最低**。全程只有 public 托管调用,不打补丁、不碰引擎模块、不碰 `Input`、
不移动光标。唯一的雷是**选项菜单**——`AdvSelectionManager.IsWaitInput` 为真时点击会**选中选项**,
必须先判断并跳过。

```csharp
// ---------- Mono(KnightsCollege)。Unity 6 的 IL2CPP 版把 FindObjectOfType 换成
// ---------- FindFirstObjectByType / FindAnyObjectByType,其余一模一样。
using UnityEngine;
using Utage;

static AdvEngine FindEngine()
    => Object.FindObjectOfType<AdvEngine>();          // 每帧调用很贵 → 缓存起来,失效再取

static bool AdvanceOnce()
{
    var engine = FindEngine();
    if (engine == null || !engine.IsStarted) return false;

    var page = engine.Page;                  // public getter
    var ui   = engine.UiManager;             // public getter(AdvUiManager)
    if (page == null || ui == null) return false;

    var sel = engine.SelectionManager;       // ★ 别在选项菜单上点
    if (sel != null && sel.IsWaitInput) return false;

    page.InputSendMessage();                 // 第一次:推完打字机;第二次:进下一句
    ui.IsInputTrig = true;                   // 满足 AdvCommandWaitInput / WaitCustom / Movie / Video
    return true;
}
```

等价的"高层一行"(连 `CurrentPointerData` 一起模拟,更贴近真点击):

```csharp
var ugui = Object.FindObjectOfType<Utage.AdvUguiManager>();
if (ugui != null)
{
    var ped = new UnityEngine.EventSystems.PointerEventData(
                  UnityEngine.EventSystems.EventSystem.current);
    // OnInput 本身不读 button;若走 OnPointerDown 则要 button == Left(默认就是 Left)
    ugui.OnInput(ped);
}
```

**⚠ 时序(重要)**:`AdvUiManager.LateUpdate()` **每帧**都会
`ClearPointerDown()` → `IsInputTrig = false`。
所以必须在 **Update 阶段**设置它,同帧晚些时候被场景线程消费。放在自己的 `MonoBehaviour.Update()`
或 `AdvUguiManager.Update()` 的 postfix 里;放到 `LateUpdate` 里就晚了。
`InputSendMessage()` 没有这个问题(它只置一个 `bool`,由 `UpdateText()` 消费)。

**✅ 好消息(已核实)**:这两个标志都是**一帧脉冲**,不会累积:
* `AdvPage.isInputSendMessage` 在 `UpdateText()` 末尾无条件 `= false`;
* `AdvUiManager.IsInputTrig` 在 `AdvUiManager.LateUpdate()` 里 `= false`。
所以**每次调用 = 推进恰好一步**,不需要自己做"只点一次"的防抖(但仍建议节流,别每帧都点)。

**怎么验证成功**(见 §5.4)。

### 🥈 Option B —— Harmony 补丁,让引擎"以为被点了一下"
**补哪个**:**`Utage.AdvUguiManager.Update()` 的 Postfix**(一次性的 intent 标志)。

为什么选它:
* 它是 **UTAGE 自己的方法**(游戏装配件),不是引擎模块、不是属性 setter
  —— 正是本项目在 AnaDos 上踩过 3 次 `coreclr.dll +0x1d1fdd` 的那类**危险目标之外**的类别
  (见 `hooks\il2cpp_src\StoryHookIl2Cpp.cs` 开头的血泪教训、`docs\计划.md` §实战案例)。
* 它每帧只跑一次,且在 **Update 阶段**,天然早于 `AdvUiManager.LateUpdate()` 的清零。
* 它内部本来就是"回车/滚轮 → 推进"的地方,注入语义完全对齐。
* `protected virtual` 也能被 Harmony 打到(按名字找即可)。

```csharp
using HarmonyLib;
using Utage;

[HarmonyPatch(typeof(AdvUguiManager), "Update")]
static class Patch_AdvUguiManager_Update
{
    static volatile bool _want;
    public static void Request() => _want = true;

    static void Postfix(AdvUguiManager __instance)
    {
        if (!_want) return;
        _want = false;                                  // 一次性
        var engine = __instance.Engine;                 // AdvUiManager.Engine { get; }
        if (engine == null) return;
        var sel = engine.SelectionManager;
        if (sel != null && sel.IsWaitInput) return;     // 选项菜单:放弃
        engine.Page.InputSendMessage();
        __instance.IsInputTrig = true;                  // public setter
    }
}
```

**更"像玩家按了回车"的替代目标**:`Utage.InputUtil.IsInputKeyboadReturnDown()`(static)——
前缀返回一次 `true`,剩下的事 `AdvUguiManager.Update()` 自己会做完(含 `IsInputTrig = true`)。
优点:只碰一个 static、语义最纯;缺点:它是 static,拿不到实例,得靠别处缓存引擎。

**更激进的替代**:前缀 `Utage.AdvPage.IsInputSendMessage()`(private)在标志位为真时返回 `true`
—— 让页面认为"输入到了"。但它同时被 `UpdateSendChar`/`UpdateText`/`UpdateWaitInput` 调用,
如果标志位不一次性,会**每帧瞬推全文**(等于强行 skip)。风险更高,只作后备。

**崩溃风险:低**。目标方法每帧一次、不在销毁流程里。仍建议先只打日志跑一轮再启用注入。

### 🥉 Option C —— 补 `UnityEngine.Input` 的鼠标 getter(**不推荐**)
**结论:两个后端都不该这么做,而且对"推进对话"根本无效。**

1. **打错了层(已核实)**:UTAGE 的左键推进**完全不经过 `UnityEngine.Input`**,
   它走 Unity UI **EventSystem**(`AdvUguiManager.OnPointerDown/OnInput`)。
   `Utage.InputUtil` 只用 `Input` 读**右键**、Ctrl、滚轮、回车。
   把 `Input.GetMouseButtonDown(0)` 改成返回 `true`,在两个游戏里**都不会推进任何对话**。
2. **Mono(KnightsCollege)**:技术上打得动(`UnityEngine.InputLegacyModule` 里的方法 Harmony 能补),
   但没有意义;唯一有意义的 `Input` 派生手段是 `Utage.InputUtil.IsInputKeyboadReturnDown()`
   —— 那已经是**UTAGE 的方法**而不是 `UnityEngine.Input`,安全性完全不同。
3. **IL2CPP(AnaDos):不要做。**
   * `UnityEngine.Input` 是 icall,托管侧只是转发壳。Il2CppInterop/Harmony 补的是**托管代理**,
     而 UTAGE 自己的原生代码是**直接调用原生实现**的——代理层的补丁对它**不可见/不可靠**。
   * 就算可见,`UnityEngine.InputLegacyModule` 属于**引擎模块**,正是本项目在 AnaDos 上
     **崩了 3 次**的那一类目标(引擎自己在销毁/切场景时也会调它)。
   * `Input` 被引擎每帧大量轮询,detour 频率极高、生命周期很长,是最容易把
     `托管↔原生` 边界异常带进 `coreclr` 的形态。
   ⇒ 若一定要"假按键"路线,IL2CPP 上也请补 **`Utage.InputUtil.IsInputKeyboadReturnDown()`**
     (游戏装配件的 static),并且**先只记日志**验证它真的被调用到,再启用返回值伪造。

### 5.4 三套方案共用的"验证成功"办法
1. **看页码**:每 0.5 s 打一次
   `engine.Page.ScenarioLabel` / `engine.Page.PageNo` / `engine.Page.IsSendChar` /
   `engine.Page.IsWaitInputInPage` / `engine.Page.IsWaitingInputCommand` /
   `engine.UiManager.IsInputTrig` / `engine.SelectionManager.IsWaitInput` / `engine.IsEndScenario`。
   推进成功 ⇒ `PageNo` 自增(或 `ScenarioLabel` 变化)。
2. **正向确认**:`AdvPage.OnTrigInput` 是 **public 的 `AdvPageEvent : UnityEvent<AdvPage>`**,
   `UpdateWaitInput()` 在吃到输入时 **恰好** `Invoke(this)` 一次 —— 挂上去就能拿到"注入被消费了"的铁证。
   同理 `AdvScenarioPlayer.OnBeginCommand` / `OnEndCommand`(`public AdvCommandEvent`,
   `UnityEvent<AdvCommand>`)可以看指令流是否前进。
3. **金丝雀补丁**:给 `Utage.AdvPage.ToNextCommand()`(private)加一个只记日志的 Postfix
   —— 它一响就说明真的推进了。
4. **确认"没动真实鼠标"**:本方案全程不调用 `SetCursorPos` / `SendInput` /
   `UnityEngine.Input`,所以可以断言 `UnityEngine.Cursor.position` 在推进前后**完全不变**。
   (与现有 Python 侧的 `core\autoclick.py` 形成对比——那个用的是 `SetCursorPos` + `SendInput`。)

### 5.5 排序
| 排名 | 方案 | 崩溃风险 | 说明 |
|---|---|---|---|
| 1 | **A**:`FindObjectOfType<AdvEngine>()` → `Page.InputSendMessage()` + `UiManager.IsInputTrig = true`(先判 `SelectionManager.IsWaitInput`) | **最低** | 纯 public 调用,零补丁,零引擎模块,零光标移动 |
| 2 | **B**:Harmony **Postfix `Utage.AdvUguiManager.Update()`**(或 Prefix `Utage.InputUtil.IsInputKeyboadReturnDown()`) | 低 | 目标是 UTAGE 自己的方法,正是引擎干这事的地方;一次性标志 |
| 3 | **C**:补 `UnityEngine.Input` 鼠标 getter | **无效 + 高** | 层错了(Mono 无效);IL2CPP 上还是已知崩溃类 |

---

## 6. AnaDos 的下一步(唯一的阻塞项)

AnaDos 现在没装 BepInEx,所以**拿不到精确签名的 interop**。要做的是:

1. 用现成脚本装:
   `powershell -ExecutionPolicy Bypass -File "D:\Unity阅读器\hooks\il2cpp_src\build_plugin.ps1" -GameDir "D:\Program Files\AnaDos"`
   (该机**没有 .NET SDK**——`dotnet --list-sdks` 为空——所以脚本用系统自带 `csc`
   对着游戏自带 `dotnet\` 里的 .NET 6 装配件编,这是一条已验证的路。)
2. **启动游戏一次**,Il2CppInterop 会生成
   `D:\Program Files\AnaDos\BepInEx\interop\Assembly-CSharp.dll`
   —— `Utage.*` 全部类型与**精确签名**都在这个文件里(**不在**独立的 `Utage.dll`,因为
   `ScriptingAssemblies.json` 里没有它)。
   然后 `Mono.Cecil` 一读即可把 §1 的签名逐条坐实。
3. 注入代理用 **`version`**(不要 `winhttp`):`config.py:80` 与 `docs\计划.md` 都记录了
   AnaDos 被 `winhttp.dll` 顶替后联网会坏。
4. 挂钩档位保持 **`gameonly` / `tmpro_setonly`**(`计划.md` §实战案例:挂
   `UnityEngine.UI.Text.set_text` / `TMPro.TMP_Text.set_text` 会在 80–110 秒
   `coreclr.dll +0x1d1fdd` 闪退)。

---

## 7. 产物清单(全部在 `D:\Unity阅读器\docs\_probe\`)
| 文件 | 内容 |
|---|---|
| `KnightsCollege-utage.md` | **主转储**:842 个 Utage 类型全名 + 122 个重点类型的字段/属性/方法完整签名(4853 行) |
| `AnaDos-interop-utage.md` | 你给的"AnaDos"interop 的转储 —— **0 个 Utage 类型**(反证它是 Astatos 的) |
| `anados-strings.txt` | AnaDos `global-metadata.dat` 抽出的 418,450 条 ASCII 串 |
| `anados-metadata-strings.txt` | 按字符串表索引读出的 20,483 条(索引基址未对齐,参考用) |
| `dump-utage.ps1` | 类型/成员枚举(Cecil) |
| `show-type.ps1` | 指定类型成员打印 |
| `il.ps1` | 指定方法 IL 反汇编(含 switch 目标解析) |
| `scan.ps1` | 调用点扫描 / 静态成员扫描 |
| `census.ps1` | 装配件命名空间普查 |
| `extract-strings.ps1` | 元数据 ASCII 串抽取 |
| `parse-metadata.ps1` | 元数据表试探解析 |

**未修改任何目标游戏目录下的文件**(全程只读)。
