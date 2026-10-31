# 烟雨观星 73536+ · HAR 存档解析与本地观星

面向《烟雨江湖》的**个人存档解析及观星工具**。从获取的 HAR 抓包中识别 `download3` 存档响应，在本机派生协议、会话和存档解密密钥，恢复完整 JSON，并生成可供内置网页版使用的存档文件。

**支持范围：存档版本 ≥ 73536，且采用当前已适配的 `download3` 协议。** 已有真实响应验证涉及 **73536、73570**；更高版本只表示允许尝试解析，不代表对未来加密变化作出保证。73492 及以下的 HAR 不受支持。

- 无需 ADB、Root、模拟器内存扫描或密钥爆破。
- 不依赖 `keys.json` 或 `keys.local.json`，不将临时解密密钥持久化。
- 支持多角色列表、网页自动载入；新解析的同一角色只保存一份当前存档。
- 核心解析采用 Python 标准库；网页在本地浏览器中打开。

> 本项目是相关开源发布项目的衍生与适配作品，**并非对原项目、网页版或游戏资源的原创权利主张**。项目来源和权利说明见 [NOTICE.md](NOTICE.md)。

## 快速开始

需要 **Python 3.8 或更高版本**，建议 Python 3.11。Windows PowerShell、CMD 和 Git Bash 均可运行；其他系统需要有可用的 Python 和浏览器。

发布后的仓库地址：

```bash
git clone https://github.com/GinHaL/yanyu-guanxing-73536.git
cd yanyu-guanxing-73536
python run.py
```

核心功能无需额外安装依赖。`requirements.txt` 只作说明，直接运行即可。

启动后显示本机已解析的角色，例如：

```text
烟雨观星 · HAR 存档工具 v1.1.0

已解析角色（默认最新）：
  [1] 示例角色甲  android·s53  2026-10-31 15:00  217 字段
  [2] 示例角色乙  ios·s26      2026-10-30 19:20  221 字段

  [n] 解析 HAR
  [q] 退出
请选择（直接回车默认第一个角色）：
```

- 输入角色编号：使用默认浏览器打开网页版，并自动载入该角色的 `dat.json`。
- 输入 `n`：粘贴或拖入 `.har` 文件路径；成功解密、保存后自动打开网页版。
- 输入 `q`：退出；直接回车选第一个角色（如果已有角色）。

也可以不经过菜单直接解密：

```powershell
python .\run.py capture ".\example.har"
```

该命令**只解析和保存**，不自动打开浏览器；交互菜单的 `n` 才会在解析成功后打开网页。

## 如何取得可解析的 HAR

常用抓包工具包括 [ProxyPin](https://github.com/wanghongenpin/proxypin) 和 mitmproxy。仅抓取自己有权访问的账号及流量。

1. 在游戏中退出登录，打开抓包工具并开始录制。
2. 重新登录并进入角色，确保 HAR 捕获了包含 `k` 响应头的登录/会话请求。
3. 使用游戏提供的**下载存档**操作，确保抓到 `command=download3` 的响应。
4. 停止抓包并导出完整的 `.har` 文件，复制到运行本工具的电脑。
5. 输入 `n` 或执行 `python run.py capture "路径.har"`。

仅有 `upload3` 上传请求、没有 `download3` 下载响应时，无法使用此工具恢复存档。具体排查见 [使用说明](doc/使用说明.md)。

## 输出及角色管理

每个账号、平台、区服在当前存档目录中对应一个角色记录，位于：

```text
output/
  _har_only/
    android-s53-<账号摘要>/
      dat.json
      dat.db
      dat.meta.json
```

- `dat.json`：完整解密后的存档数据，供网页自动载入。
- `dat.db`：使用**网页/第三方工具兼容的 v1.8 封装**重新生成的 SQLite 存档文件，**不能等同于游戏客户端原始 dat.db**。
- `dat.meta.json`：角色、平台、区服、版本及时间等信息；**仍包含账号标识，属于敏感数据**。

同一角色重新导入后，只保留一份当前导出文件；新数据解密和写盘成功后才替换，若可比较的 HAR 下载时间比当前记录更早则拒绝覆盖。兼容读取的历史快照可能仍存在于旧目录，程序不会为此主动删除原文件。

**请勿向公开仓库上传个人 HAR、`output/`、自动载入网页或账号存档。**

## 技术概要

对于已适配的 `download3` 会话格式，主要流程是：

```text
HAR acc + k                  → realKey
HAR extra + realKey          → 8 位 psw
platform + session + 时间戳  → 16 位会话 Token
download3.data + Token      → 版本号 + 内层密文
psw + 内置渠道后缀           → innerKey
内层密文 + innerKey          → zlib → JSON → 校验 → 存档输出
```

临时 `realKey`、Token 和 `innerKey` 均在运行时获得。渠道后缀来自源码内置已知常量，逐候选验证，并非从 HAR 凭空推导；未知渠道或变化后的封装可能无法解密。

技术细节见 [解密原理与实现](doc/README.md)、[73536+ 适配说明](本次更新内容.md)。

## 文档

| 文档 | 内容 |
| --- | --- |
| [使用说明](doc/使用说明.md) | 抓包、角色选择、输出目录与常见报错 |
| [解密原理与实现](doc/README.md) | 协议密钥、会话层、内层 XXTEA、校验和模块结构 |
| [73536+ 适配说明](本次更新内容.md) | `download3` 格式与版本支持边界 |
| [相关项目与实现来源](原版使用说明.md) | 参考仓库及功能关系 |
| [版权与归属声明](NOTICE.md) | 第三方来源、权利边界与使用说明 |

## 参考项目

感谢以下公开项目与相关作者的探索、代码和文档：

- [yanyu-amateur/yanyu-guanxing](https://github.com/yanyu-amateur/yanyu-guanxing)：存档工具及原始实现来源。
- [leonas30200/yanyu-guanxing](https://github.com/leonas30200/yanyu-guanxing)：相关 Python 存档解析与 HAR 适配版本参考。
- [dte2mdj/yanyu-guanxing-web](https://github.com/dte2mdj/yanyu-guanxing-web)：观星网页版及功能实现参考。

项目与游戏运营方无官方关联。仅用于本人授权的数据查看、备份及技术学习。公开仓库可见不等于具备再分发授权，具体权利与使用限制见 [NOTICE.md](NOTICE.md)。
