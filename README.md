# HD2 Chat Translator · 绝地潜兵 2 聊天翻译

给《HELLDIVERS™ 2》用的聊天翻译 mod + 本地操作台。

> 下载：[最新 Release](https://github.com/XD2233XD/HD2-ChatTranslator/releases/latest) · 作者 **XD2233XD**

- **入站**：队友的非中文聊天自动译成中文，紧跟原话显示（默认是仅本机可见的独立一行），并标注源语言，例如
  `[EN] 前方有敌人，需要支援`
- **出站**：自己发的中文约 1 秒后自动补发一条 `[EN] ...` 真实聊天消息，队友也看得见（原文不动）
- **控制台发言**：游戏内中文输入法有 bug（会卡控制/掉焦点），所以可以直接在控制台输入框里用中文输入法打字，
  点发送 → 控制台翻译 → 游戏内 mod 写进聊天框 → 游戏自己发出去，全程不碰游戏内 IME
- **游戏黑话/缩写**：`sr` `lol` `gg` `ez` `wtf` `666` 这类按字面翻一定错的词有内置词典（精确命中 0 延迟），
  组合句与未收录缩写交给模型按游戏语境推断；另附 HD2 缩写（RR/EAT/AC/AMR/HMG/SC/FRV/EXO…）
- **系统消息**：按发送者名单/前缀过滤，不送翻译、不占行
- **操作台**：本机网页控制台，管语言对、开关、术语表、历史、日志、API Key、一键部署/卸载

> 当前适配：Steam build **25480438** / EXE **1.8.46015.0**。游戏大版本更新后内存偏移可能变化，
> mod 会退化为「译文留在输入框，按回车即发」，不会崩溃。重新适配方法见 `docs/参考-上游工作原理.md`。

## 它是怎么工作的

```
游戏内 Lua mod (Bingus 加载器)
  ├─ 读聊天环 64 条记录：发送者 + 正文 + 类型
  ├─ 入站：把正文发给本机控制台 → 控制台调模型翻译 → 写回该行的正文属性（仅本机）
  ├─ 出站：把自己的话发给控制台 → 译文写进聊天输入框 + 置两个状态字节 → 游戏自己发送
  └─ 传输：内嵌 node 助手（HTTP keep-alive）↔ http://127.0.0.1:8731/v1

控制台 (Python, 无第三方依赖)
  ├─ OpenAI 兼容端点 /v1/chat/completions（mod 只发 {kind,text,target,name}）
  ├─ DeepSeek / 任意 OpenAI 兼容 API（API Key 只在本机）
  ├─ 语言识别、术语表、缓存、历史（SQLite）
  └─ 网页 UI：设置 / 术语表 / 记录 / 日志 / 安装诊断
```

设计上**不在游戏进程里跑网络请求**：翻译在控制台进程完成，游戏线程只做几微秒的内存读写，
和上游 `hd2-bilingual-chat` 的取舍一致（实测掉帧来自游戏自己的聊天行重排，不是 mod）。

## 目录

```
HD2-ChatTranslator/
├─ mod/
│  ├─ src/chat_translator.lua      # 游戏内全部逻辑（Lua）
│  ├─ tools/                       # 打包、Lua 编译检查、偏移核对
│  ├─ vendor/                      # Bingus Shared Loader v20（安装用，0BSD）
│  └─ dist/                        # 生成的 Arsenal 可导入 ZIP
├─ console/
│  ├─ app.py                       # 控制台入口
│  ├─ server.py                    # 本地 HTTP + OpenAI 兼容端点
│  ├─ translator.py                # 模型调用 / 语言识别 / 术语表 / 缓存
│  ├─ installer.py                 # 找游戏 / 装 Arsenal / 读日志
│  ├─ install_manual.py            # 手动部署 patch_1 / patch_2、精确卸载
│  ├─ web/                         # 单页控制台
│  └─ tests/                       # 离线自测（不需要游戏/不需要真 key）
├─ docs/
│  ├─ 参考-上游工作原理.md          # 内存布局、发送配方、更新后重定位
│  └─ 实机验证清单.md               # 每条要看的日志证据
└─ 调研/                            # 上游仓库、skills 等资料
```

## 发布包（给其他人用）

```
release/HD2ChatTranslator-1.0.0-win64.zip   (~12.5 MB)
release/SHA256SUMS.txt                      zip 的 SHA256
release/SHA256SUMS.txt.sig                  ed25519 签名
release/hd2ct_ed25519.pub                   公钥
```

解压后目录：

```
HD2ChatTranslator-1.0.0/
├─ HD2ChatTranslator.exe          控制台（免 Python，双击即用）
├─ _internal/                     运行库，必须和 exe 放一起
├─ mod/HD2ChatTranslator-1.0.0.zip    Arsenal 可导入的 mod 包
├─ loader/Bingus-Shared-Loader-v20.zip Lua 加载器（0BSD）
├─ WATERMARK.json                 作者 / 水印 ID / build ID / 每文件 SHA256
├─ SHA256SUMS.txt (+ .sig)        包内文件校验与签名
├─ hd2ct_ed25519.pub              验签公钥
├─ README-SIGNATURE.txt           验签说明
├─ 使用说明.txt
├─ LICENSE / NOTICE.md / README.md
```

作者署名 **XD2233XD**，水印 ID `HD2CT-XD2233XD-9c04daa02b4d4d67`；每次构建生成独立 build ID，
并写进 PNG 元数据、ZIP 归档注释、manifest、Lua 源码注释和控制台页脚。

验签：

```cmd
ssh-keygen -Y check-novalidate -n hd2ct -s SHA256SUMS.txt.sig - < SHA256SUMS.txt
```

应输出 `Good "hd2ct" signature with ED25519 key SHA256:8yTBFgrqbd19eOFZ2qwVUuvcP7BcQJqH4zIKy39Erhc`。

对方只需要：解压 → 双击 exe → 填 API Key → 退出游戏 → 点「一键部署」。
不需要装 Python 或编译工具；Node 是**可选**的（没有会自动退回系统 `curl`，每条消息慢约 0.2 秒，功能不变）。

## 安装

### 1. 控制台

**发布版**：双击 `HD2ChatTranslator.exe`，浏览器自动打开 `http://127.0.0.1:8731/`。

**开发版**（本机调试）：

需要 Python 3.12（本机 `E:\Python312\python.exe`）。无第三方依赖。

```powershell
cd E:\Projects\HD2-ChatTranslator\console
E:\Python312\python.exe app.py
```

浏览器打开 `http://127.0.0.1:8731/`，在 **设置 → 翻译服务** 填 API Key 和模型，保存即可。
游戏内 2 秒内热加载，不用重启游戏。

### 2. 游戏内 mod（二选一）

**A. 一键部署（推荐，本机已用）**

控制台 → **安装 / 诊断** → **一键部署到游戏**。要求先完全退出游戏。

它只写两个文件，不碰语言包：

| 文件 | 内容 |
|---|---|
| `data\9ba626afa44a3aa3.patch_1` | 本 mod |
| `data\9ba626afa44a3aa3.patch_2` | Bingus Shared Loader v20 |

**B. Arsenal 导入**

把 `mod/dist/HD2ChatTranslator-1.0.0.zip` 和 `mod/vendor/Bingus-Shared-Loader-v20.zip`
导入 [HD2 Arsenal](https://github.com/Orbit-Studios/hd2arsenal-release/releases)，
加载器放列表最后，Deploy。

> 两种方式任选其一，不要同时用。卸载：控制台 → **卸载**，只删除标记匹配的 patch_1/2。

### 3. 验证加载

启动游戏后看：

```
%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\HD2ChatTranslator.log
```

应出现：

```
START version=1.0.0 (HD2 Chat Translator)
CONFIG read=zh-CN send=en inbound=on outbound=on tag=code system=5/0
ARMED mode=mem ...
```

没有 `START` → 加载器没加载；有 `START` 没有 `ARMED` → 游戏场景/偏移问题。
控制台 **日志** 页可以直接看这个文件。

## 使用

1. 控制台保持运行（关掉它，翻译会失败并回滚，聊天本身不受影响）。
2. 游戏里正常用聊天键打字、回车发送。
3. 自己发中文 → 约 1 秒后出现 `[EN] ...`。
4. 队友说英文 → 那一行下面出现 `[EN] 中文译文`。

### 输入法 / 窗口

HD2 对中文 IME 的处理有 bug：组字时可能卡住移动/控制，甚至把焦点弹出游戏。三层处理：

1. **控制台发言**（最稳）：中文输入法在浏览器里用，游戏内完全不碰 IME。
2. **输入法守护**（默认开启）：游戏窗口在前台时，控制台把该窗口线程的键盘布局切到
   `00000409`（英文 US）；离开游戏自动切回。这样游戏里按中文输入法也只会出字母，不会弹候选窗。
   设置里可关；状态见「安装 / 诊断」。
3. **无边框窗口**（可选）：安装页 →「改无边框窗口（需退出游戏）」。会把
   `user_settings.config` 改成 `fullscreen=false` / `borderless_fullscreen=true` 并备份。
   IME 候选窗弹出时不容易把游戏切出去；**必须重启游戏生效**。

### 控制台发言（推荐）

操作步骤：

1. 控制台 → 概览 → **控制台发言**
2. 在浏览器输入框里用中文输入法正常打字（这里不受游戏影响）
3. 选发送语言，点「翻译并发送到游戏」
4. 控制台翻译 → 写 `%LOCALAPPDATA%\HD2ChatTranslator\send.txt` → 游戏内 mod 取走 →
   写进聊天框并置状态字节 → 游戏自己发出

日志会依次出现 `OUTBOX send` → `SEND wrote` → `MSEND armed` → `MSEND ok`。
**需要已经在飞船/任务里**；标题界面聊天面板没运行，会卡在 `MSEND failed`（文字留在输入框）。

### 标注语义（重要）

游戏聊天里同时有两种 `[XX]`：

| 出现位置 | 含义 | 例子 |
|---|---|---|
| 队友消息下面的译文 | **源语言**（默认） | `[EN] 前方有敌人` |
| 你自己发出的译文 | 这条消息**是什么语言** | `[EN] Enemies ahead!` |

在设置里「入站标注方式」可改：

- `source`（默认）：`[EN]`，只标源语言（你要求的“标注源语言”）
- `arrow`：`[EN→CN]`，源和目标都写清楚，适合想区分两种 `[EN]` 的场景
- `target`：`[CN]`，只标目标语言
- `off`：不标

> 说明：控制台发出的英文消息带 `[EN]`，表示“这条是英文”；入站译文的 `[EN]` 表示“原文是英文”。
> 默认只标源语言；如果觉得两种 `[EN]` 容易混，切到 `arrow` 即可。
>
> 默认 `line`：译文作为一条**仅本机可见的独立聊天消息**（`↳ [EN] ...`）由游戏自己排版，
> 不改原行、布局最稳。代价是它显示成你自己的消息，`↳` 前缀用来区分“这是译文，不是我说的”。
> 想要“贴在原行下面”的紧凑效果可切 `row`；代价是第二行会从发送者名字下面开始，看着略偏左。

### 黑话与缩写

| 输入 | 输出 | 说明 |
|---|---|---|
| `sr` / `sry` | 抱歉 | 精确命中，0ms |
| `LOL` | 哈哈 | 大小写/标点不敏感 |
| `gg wp` | 打得好，辛苦了 | 组合词交给模型 |
| `666` / `牛批` | awesome / Awesome, that was a carry | 中文→英文 |
| `rr` `eat` `ac` `amr` | 无后座力炮（RR） / 一次性反坦克（EAT） / 自动加农炮（AC） / 反器材步枪（AMR） | 缩写保留在括号里，便于对照 |

词典在 `console/slang.py`，可直接加词；改完重启控制台。用户术语表优先于模型提示，但内置精确命中在术语表之前
（要覆盖 `sr` 这类词，改 `slang.py` 或把它从 `EN` 字典删掉）。

### 设置项

| 项 | 说明 |
|---|---|
| 阅读语言 | 别人的话翻成什么（默认简体中文） |
| 发送语言 | 自己的话翻成什么（默认英语） |
| 入站标注方式 | `[EN]` 只标源语言（默认）/ `[EN→CN]` 源→目标 / `[CN]` 只标目标 / 关闭 |
| 入站显示方式 | `line` 单独一条本地消息（默认，布局最稳）/ `row` 写回原行下面（译文第二行从名字下面开始） |
| 翻译入站 / 出站 | 两个方向独立开关 |
| 出站前缀 | `auto` = `[EN]`/`[CN]`；也可固定字面量；`0` = 不加 |
| 系统消息名单 / 前缀 | 命中就不翻译（默认 SYSTEM/系统/服务器…） |
| 调试聊天日志 | 把每条原始聊天行写进日志，用于核对系统消息特征 |
| 术语表 | 源术语 → 译名，写进提示词 |

### 日志关键字

| 关键字 | 含义 |
|---|---|
| `OWN message` | 认出了自己的发言 |
| `TRANSLATE ok` | 译文回来了 |
| `MSEND ok` | 游戏真的取走输入框并发出 |
| `INBOUND translated` | 入站译文已写入该行 |
| `INBOUND skipped` | 同语言或系统消息，未翻译 |
| `TRANSLATE skipped by service` | 控制台判定跳过 |
| `HELPER ...` | node 助手状态 |
| `PERF ours=` | mod 自己在该帧的开销 |

## 已实现 / 已验证

**离线已验证**（`console/tests/`，18 项 + node 传输 1 项全过）

- Lua 在游戏自带 `lua51.dll` 上编译通过
- 协议：mod JSON → OpenAI 形状响应，`[EN]` 标注、同语言跳过、系统标记跳过、缓存命中
- 黑话精确命中：`sr`/`LOL`/`RR` 0ms、大小写标点不敏感、中英双向
- HD2 缩写带原名：`RR` → `无后座力炮（RR）`，组合句由模型补全
- node 助手能走 **http**（上游只支持 https，已改）并正确回传 `out.txt/raw.txt`
- 打包：ZIP 内含 manifest / Addon / 空 companions，TOC 长度自洽

**实机已验证（2026-10-18，Steam build 25480438）**

- Bingus v20 从 `data\...patch_2` 加载本 mod：`mods/hd2ct/chat_translator: loaded`
- 本 mod：`START version=1.0.0` → `ARMED mode=mem` → `HELPER ready 0.10s`
- 控制台发言出站（中文输入法问题绕行）：

  ```
  OUTBOX send "[EN] Enemies ahead, need support"
  SEND wrote → MSEND armed state=0x139b8 flag=0x1e0f
  CHAT name="蓝牙一号" body="[EN] Enemies ahead, need support"
  SEND verified ... after 16 ms → MSEND ok sent=1
  ```

- 中文进聊天环（字体/编码路径）：`[CN] 需要支援，在我的位置` → `MSEND ok sent=2`
- **入站写入链路（self-test，真实聊天行）**：`need help` → `INBOUND set idx=2 slot=2 off=+0x240 len=22` →
  `INBOUND height 17.0 -> 34.0` → 游戏里正常显示中文「需要支援」（玩家目视确认）
- **入站 line 模式（最终默认）**：`INBOUND line ok=true` → 聊天栏新增
  `蓝牙一号: ↳ [EN] 前方接敌，现在需要支援`，玩家目视确认「正常，就用这个」
- 黑话实测：`sr`→`[EN] 抱歉`（0ms）、`sr my bad, need backup at my position`→`[EN] 抱歉我的错，需要支援，来我位置`（887ms）
- HD2 缩写实测：`RR is down, need someone with EAT` → `[EN] 无后座力炮（RR）倒了，需要有人带一次性反坦克（EAT）`（968ms）
- 标注方式实测：`[EN]`（默认 source）、`[EN→CN]`（arrow）、`[CN]`（target）三种都按设置输出
- 输入法守护实测：游戏前台时线程键盘布局 `0x8040804 → 0x4090409`，离开后恢复 `0x8040804`

**已知视觉问题**

- 把译文写进**控制台发出的消息行**时，游戏会在该行显示一个 “ok” 投递状态，译文第二行会和它叠在一起。
  这是测试用 `@peer` 打到 console 行造成的；**普通聊天行（手打消息/队友消息）布局正常**（self-test 已目视确认）。
  真实入站只写队友的普通行，不会碰 console 行。

**实机待验证**

- 真实队友英文 → 原行下面中文（`consider_inbound` 的队伍分支；self-test 不经过它）
- 系统消息的真实发送者名/前缀（需要实机样本）

验证步骤与判据见 `docs/实机验证清单.md`。

## 风险与边界

- 不注入 DLL、不改游戏 EXE、不读写网络协议；只读写游戏自己的聊天 UI 内存，并调用游戏自己的发送流程。
- 与所有 mod 一样，**风险自负**；上游在官方反作弊环境下测试过，但没有任何“绝对安全”的保证。
- 需要联网与模型额度；每条消息一次请求，正常 0.3–0.8 秒。
- 游戏更新后偏移变化 → 降级而不是崩溃（译文留在输入框）。
- 只在本机 Windows 10/11 x64 验证。

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

## 许可与致谢

- 本项目：MIT。
- 底座：[`Alkaid4521/hd2-bilingual-chat`](https://github.com/Alkaid4521/hd2-bilingual-chat)（MIT）——
  聊天环布局、行定位、发送配方与降级策略来自它，本仓库在其 1.4.0 上改造。
- 加载器：[`CowboyBingus/BingusSharedLoader`](https://github.com/CowboyBingus/BingusSharedLoader)（0BSD），
  不修改、只随安装包分发。
- 方法参考：[`Puipipi/HD2-Agent-Skills`](https://github.com/Puipipi/HD2-Agent-Skills)（MIT）。
- “HELLDIVERS”及相关名称、标志归其权利人所有；本项目非官方、无隶属关系。


