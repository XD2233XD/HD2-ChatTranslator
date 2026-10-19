# HD2 Chat Translator · 绝地潜兵 2 聊天翻译

给《HELLDIVERS™ 2》做的聊天翻译 mod，外加一个本地控制台。

下载：[最新 Release](https://github.com/XD2233XD/HD2-ChatTranslator/releases/latest)　作者：XD2233XD

## 它做什么

队友打了一句英文，聊天栏里会多出一行中文，前面带 `[EN]`。这行只有你本机看得到，不会发给别人。
系统消息不翻，比如谁加入了小队、谁离开了。

你自己打中文，大约一秒后会自动补一条 `[EN] ...` 发给队友。原话不动，队友看到的是两条消息。

游戏里的中文输入法有毛病。组字的时候会卡住移动，严重时直接把焦点弹出游戏。这点很烦。所以控制台里放了一个输入框：
用浏览器输入法打中文，点发送，控制台翻译完交给 mod，由游戏自己发出去。全程不碰游戏内 IME。

适配 Steam build 25480438 / EXE 1.8.46015.0。我在这个版本上实机跑过。
大版本更新后内存偏移可能变，mod 会退化成「译文留在输入框，按回车发」，不会把游戏搞崩。先能玩，再谈翻译质量。
如果游戏更新把聊天环、输入框或者控件槽的偏移挪了，mod 不会硬写，日志里会出现 `MSEND failed` 或 `INBOUND apply fault`，译文会留在输入框里，你按一下回车照样能发出去，只是自动补发没了。别着急。
重新找偏移的方法写在 `docs/参考-上游工作原理.md`。

## 怎么工作

```
游戏内 Lua mod（Bingus 加载器）
  ├─ 读聊天环 64 条记录：发送者、正文、类型
  ├─ 入站：正文发给本机控制台，翻译完写回那一行的正文属性（仅本机）
  ├─ 出站：译文写进聊天输入框，再置两个状态字节，游戏自己发送
  └─ 传输：内嵌 node 助手（HTTP keep-alive）连 http://127.0.0.1:8731/v1

控制台（Python，只用标准库）
  ├─ OpenAI 兼容端点 /v1/chat/completions，mod 只发 {kind,text,target,name}
  ├─ DeepSeek 或任意 OpenAI 兼容 API，Key 只存本机
  ├─ 语言识别、术语表、缓存、历史（SQLite）
  └─ 网页 UI：设置、术语表、记录、日志、安装诊断
```

翻译不在游戏进程里跑：游戏线程只做几次内存读写，网络请求、模型调用、缓存和历史都留给控制台，
所以真正会掉帧的是游戏自己重排聊天行，不是 mod。上游 `hd2-bilingual-chat` 也是这个取舍。
控制台只监听 127.0.0.1，API Key 放在 `console.json`，翻译请求从本机发出去，游戏进程里没有网络代码，所以关掉控制台以后游戏还能正常聊天，只是不再有翻译。

## 目录

```
HD2-ChatTranslator/
├─ mod/
│  ├─ src/chat_translator.lua      # 游戏内全部逻辑
│  ├─ tools/                       # 打包、Lua 编译检查、偏移核对
│  ├─ vendor/                      # Bingus Shared Loader v20（0BSD）
│  └─ dist/                        # 生成的 Arsenal 可导入 ZIP
├─ console/
│  ├─ app.py                       # 控制台入口
│  ├─ server.py                    # 本地 HTTP + OpenAI 兼容端点
│  ├─ translator.py                # 模型调用、语言识别、术语表、缓存
│  ├─ installer.py                 # 找游戏、装 Arsenal、读日志
│  ├─ install_manual.py            # 手动部署 patch_1 / patch_2、精确卸载
│  ├─ web/                         # 单页控制台
│  └─ tests/                       # 离线自测（不需要游戏，也不需要真 key）
├─ docs/                           # 工作原理、实机验证清单、Release Notes
├─ tools/watermark.py              # 水印、签名、打发布包
└─ build_release.ps1               # 一键构建发布包
```

## 下载与安装

Release 里的 `HD2ChatTranslator-1.0.0-win64.zip` 大约 12 MB。解压，双击 `HD2ChatTranslator.exe`。
不用装 Python。Node 有就用，没有会自动退回系统 `curl`，每条消息慢 0.2 秒左右，功能不变。一般够用。

刚打开控制台，先去设置里的「翻译服务」填 API Key。DeepSeek 或任意 OpenAI 兼容端点都行。
填完到概览做一次快速测试：输入 `sr`，应该出现 `[EN] 抱歉`。这一步能确认网络和 Key 都没问题。这步别省。

然后完全退出游戏。别最小化。控制台进「安装 / 诊断」，点「一键部署到游戏」。
它只写两个文件：`data\9ba626afa44a3aa3.patch_1` 是本 mod，`patch_2` 是 Bingus v20。语言包 `patch_0` 不碰。

不想用一键部署的话，也可以走 Arsenal：把 `mod/dist/HD2ChatTranslator-1.0.0.zip` 和
`mod/vendor/Bingus-Shared-Loader-v20.zip` 导入 [HD2 Arsenal](https://github.com/Orbit-Studios/hd2arsenal-release/releases)，
加载器放列表最后，Deploy。两种方式选一种。别同时用。卸载只删那两个 patch，不碰存档和语言包。

启动游戏后看这个文件：

```
%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\HD2ChatTranslator.log
```

正常的话，开头会出现：

```
START version=1.0.0 (HD2 Chat Translator)
WATERMARK author=XD2233XD id=HD2CT-XD2233XD-9c04daa02b4d4d67
CONFIG read=zh-CN send=en inbound=on outbound=on tag=code system=5/0
ARMED mode=mem ...
```

没有 `START`，说明加载器没加载。有 `START` 没有 `ARMED`，先确认自己是不是还在标题界面，再检查游戏版本是不是 25480438，最后才去看偏移，别一上来就改代码。
控制台的日志页可以直接看这个文件。能看见就行。

## 日常使用

控制台开着就行。关掉也不是不能聊天，只是翻译会失败并回滚。

自己发中文，等一秒左右，聊天栏会出现 `[EN] ...`。队友说英文，下面会多一行中文。
如果觉得吵，设置里可以单独关掉入站或出站。不想看就关掉。

### 输入法

最稳的办法是控制台发言。概览页有个输入框，中文输入法在这里正常用。打完点「翻译并发送到游戏」，
控制台翻译，写 `%LOCALAPPDATA%\HD2ChatTranslator\send.txt`，游戏内 mod 取走，写进聊天框，游戏自己发。
日志会依次出现 `OUTBOX send`、`SEND wrote`、`MSEND armed`、`MSEND ok`。得在飞船或任务里，标题界面发不出去。

控制台默认开着输入法守护：游戏到前台，它把游戏窗口的键盘布局切到英文 `00000409`，切回桌面再恢复，
所以游戏里按中文输入法也只会出字母，不会弹候选窗。设置里可以关，状态在安装页能看到。

如果还是会被弹出去，退出游戏，安装页点「改无边框窗口」。它会把 `user_settings.config` 里的
`fullscreen` 改成 `false`、`borderless_fullscreen` 改成 `true`，改之前留一份备份。改完要重启。

### 标注

默认只标源语言：`[EN] 前方有敌人`。你自己发出去的英文也带 `[EN]`，那是在说「这条是英文」。
两种含义容易混。设置里可以把入站标注改成 `[EN→CN]`，源和目标都写清楚；也可以只标目标 `[CN]`，或者关掉。

译文默认是独立一行，前面有 `↳`，由游戏自己排版，所以对齐正常；想贴回原行下面可以切到 `row` 模式，
代价是译文那行会从发送者名字下面开始，看着偏左。两种模式我都实机看过，最后留了 `line` 做默认。

### 黑话和缩写

`sr`、`sry` 直接出「抱歉」，`LOL` 出「哈哈」，`RR` 出「无后座力炮（RR）」。
整条消息精确命中词典时是 0ms，不花 token。组合句交给模型，比如
`sr my bad, need backup at my position` 会出「抱歉我的错，需要支援，来我位置」。

词典在 `console/slang.py`。想加词直接改，改完重启控制台。用户术语表会写进提示词，但内置精确命中排在术语表前面；
要覆盖 `sr` 这种词，得改词典本身。

### 设置项

| 项 | 说明 |
|---|---|
| 阅读语言 | 别人的话翻成什么，默认简体中文 |
| 发送语言 | 自己的话翻成什么，默认英语 |
| 入站标注方式 | `source` 只标源（默认）、`arrow` 源→目标、`target` 只标目标、`off` 关闭 |
| 入站显示方式 | `line` 本地独立一行（默认）、`row` 写回原行 |
| 翻译入站 / 出站 | 两个方向独立开关 |
| 出站前缀 | `auto` 用 `[EN]` / `[CN]`，也可以填固定字面量，`0` 表示不加 |
| 系统消息名单 / 前缀 | 命中就不翻译，默认 SYSTEM、系统、服务器等 |
| 调试聊天日志 | 把每条原始聊天行写进日志，用来核对系统消息特征 |
| 术语表 | 源术语对应译名，写进提示词 |

### 日志里看什么

先看日志。

```
OWN message ...            认出了自己的发言
TRANSLATE ok ...           译文回来了
MSEND ok ...               游戏真的取走输入框并发出
INBOUND translated ...     入站译文已写入
INBOUND skipped ...        同语言或系统消息，没翻
HELPER ...                 node 助手状态
PERF ours=...              mod 自己在这一帧的开销
```

## 验证情况

离线测试 18 项加 node 传输 1 项，全部通过。Lua 能在游戏自带的 `lua51.dll` 上编译；协议、标注、跳过、缓存、
黑话命中、ZIP 结构都有用例。

实机是在 Steam build 25480438 上跑的。Bingus v20 从 `patch_2` 加载，日志里能看到
`mods/hd2ct/chat_translator: loaded`，随后是 `START`、`ARMED`、`HELPER ready 0.10s`。

出站走的是控制台发言，日志如下：

```
OUTBOX send "[EN] Enemies ahead, need support"
SEND wrote
MSEND armed state=0x139b8 flag=0x1e0f
CHAT name="蓝牙一号" body="[EN] Enemies ahead, need support"
SEND verified ... after 16 ms
MSEND ok sent=1
```

入站写入链路用上游的 self-test 跑过：`need help` 那一行被撑到两行，`INBOUND height 17.0 -> 34.0`，
游戏里能看到中文。后来默认改成 `line` 模式：`INBOUND line ok=true`，聊天栏新增一条
`蓝牙一号: ↳ [EN] 前方接敌，现在需要支援`。这一版我目视确认过，对齐正常。

还有两件事没做。真实队友的网络消息没凑到样本，入站是用 `@peer` 调试注入跑的；
系统消息的真实发送者名和前缀也还要再收集。代码路径是同一套，但严格说，这两项仍算待验证。
验证步骤写在 `docs/实机验证清单.md`。

## 已知问题

把译文写进控制台发出的那种消息行时，游戏会在行上显示一个 ok 投递状态，译文那行会和它叠住，这是 `@peer` 测试打到 console 行才有的组合，普通聊天行没这个问题，真实入站也只写队友的普通行。不影响正常使用。

## 风险

它不注入 DLL，不改游戏 EXE，也不读写网络协议，只读写游戏自己的聊天 UI 内存并调用游戏自己的发送流程，所以从反作弊的视角看，它做的只是几次内存写和一个游戏本来就有的发送调用，但这仍然不是零风险的承诺。自己判断。
它终究是 mod，风险自负。上游在官方反作弊环境下测过，但没人能给你「绝对安全」的保证。

需要联网和模型额度。每条消息一次请求，正常 0.3 到 0.8 秒。游戏更新后偏移变了会降级，不会崩。
目前只在 Windows 10/11 x64 上验证过。

## 开发

```powershell
# Lua 编译检查（用游戏自带的 lua51.dll）
E:\Python312\python.exe mod\tools\lua_syntax_check.py mod\src\chat_translator.lua

# 重新打包
cd mod
E:\Python312\python.exe tools\pack_addon.py --src src\chat_translator.lua `
  --path mods/hd2ct/chat_translator --name "HD2 Chat Translator" `
  --guid 2dc3c7ca-4cdd-4cb1-b488-85dd9db483b3 --version 1.0.0 `
  --delivery HD2ChatTranslator --dist dist

# 控制台自测
cd ..\console
E:\Python312\python.exe tests\test_console.py
E:\Python312\python.exe tests\test_helper_transport.py
```

完整发布包用 `build_release.ps1 -Version 1.0.0` 构建，会生成 exe、mod ZIP、水印、签名和 SHA256。

## 水印与签名

作者 XD2233XD，水印 ID 是 `HD2CT-XD2233XD-9c04daa02b4d4d67`。每次构建会生成一个 build ID，
写进 PNG 元数据、ZIP 归档注释、manifest、Lua 源码注释和控制台页脚。包里的 `WATERMARK.json`
记录了每个文件的 SHA256。

`SHA256SUMS.txt` 用 ed25519 私钥签过，公钥是 `hd2ct_ed25519.pub`。验签：

```cmd
ssh-keygen -Y check-novalidate -n hd2ct -s SHA256SUMS.txt.sig - < SHA256SUMS.txt
```

应输出：

```
Good "hd2ct" signature with ED25519 key SHA256:8yTBFgrqbd19eOFZ2qwVUuvcP7BcQJqH4zIKy39Erhc
```

验签只能证明这个包和里面的文件是私钥持有人签出来的，证明不了代码有没有被别人改过再重签，也证明不了用起来一定安全，所以看到 Good signature 只是起点，后面还得自己看代码和来源。别只看签名。

## 许可与致谢

本项目用 MIT。底座是 [`Alkaid4521/hd2-bilingual-chat`](https://github.com/Alkaid4521/hd2-bilingual-chat)（MIT），
聊天环布局、行定位、发送配方和降级策略都来自它，这个仓库是在它的 1.4.0 上改的。
加载器是 [`CowboyBingus/BingusSharedLoader`](https://github.com/CowboyBingus/BingusSharedLoader)（0BSD），
没改，只随安装包分发。方法上参考了 [`Puipipi/HD2-Agent-Skills`](https://github.com/Puipipi/HD2-Agent-Skills)（MIT）。

“HELLDIVERS”及相关名称、标志归其权利人所有。本项目非官方，与 Arrowhead、Sony、PlayStation 没有隶属关系。
