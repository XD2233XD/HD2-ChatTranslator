# HD2 Chat Translator 1.0.0

《绝地潜兵 2》聊天翻译 mod + 本地操作台。适配 Steam build **25480438** / EXE **1.8.46015.0**。

## 功能

- **入站**：队友的非中文聊天自动译成中文，紧跟原话显示（默认仅本机可见的独立一行），带源语言标注
  （默认 `[EN] 中文…`）；系统消息按名单/前缀过滤。
- **出站**：自己发的中文约 1 秒后自动补发一条 `[EN] ...` 真实聊天消息，队友也能看到。
- **控制台发言**：绕开 HD2 中文输入法 bug（会卡控制/弹焦点），在浏览器里用中文输入法打字，
  控制台翻译后由 mod 写进游戏聊天框，游戏自己发送。
- **游戏黑话/缩写**：`sr` `lol` `gg` `ez` `wtf` `666` 等内置词典（0ms），HD2 缩写
  `RR/EAT/AC/AMR/HMG/SC/FRV/EXO` 给出中文名并保留缩写；组合句交给模型。
- **本地操作台**：设置、术语表、历史、日志、API Key、一键部署/卸载、输入法守护、无边框窗口按钮。
- **发布包**：免 Python 的 `HD2ChatTranslator.exe`；Arsenal 可导入的 mod ZIP；Bingus 加载器。
- **水印/签名**：作者 XD2233XD，稳定水印 ID + build ID + ed25519 签名。

## 安装

1. 下载 `HD2ChatTranslator-1.0.0-win64.zip` 并解压。
2. 双击 `HD2ChatTranslator.exe`，填 API Key（DeepSeek 或任意 OpenAI 兼容接口）。
3. 完全退出游戏 → 控制台「安装 / 诊断」→「一键部署到游戏」→ 启动游戏。

不装 Python；Node 可选（没有会自动退回系统 `curl`）。

## 验证签名

下载 `SHA256SUMS.txt` + `.sig` + `hd2ct_ed25519.pub`，在下载目录：

```cmd
ssh-keygen -Y check-novalidate -n hd2ct -s SHA256SUMS.txt.sig - < SHA256SUMS.txt
```

应输出：

```
Good "hd2ct" signature with ED25519 key SHA256:8yTBFgrqbd19eOFZ2qwVUuvcP7BcQJqH4zIKy39Erhc
```

## 已知限制

- 真实队友网络消息尚未在本机实机采样；入站完整队列用 `@peer` 调试注入验证过。
- 游戏大版本更新可能移动内存偏移；mod 会降级为「译文留在输入框」，不会崩溃。
- `row` 模式下译文第二行会从发送者名字下面开始；默认 `line` 模式布局最稳。

## 许可

MIT。上游 `Alkaid4521/hd2-bilingual-chat`（MIT）、`CowboyBingus/BingusSharedLoader`（0BSD）。
