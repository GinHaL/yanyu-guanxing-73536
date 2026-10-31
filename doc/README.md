# 73536+ HAR 存档逆向解析与实现说明

本文说明《烟雨江湖》`download3` 存档下载响应的**协议恢复、会话解包、内层解密与完整性验证**，对应本仓库当前的 Python 实现。重点是从合法获取的 HAR 中恢复个人存档，而不是读取游戏进程内存或提取本机原始数据库。

- 最低允许尝试的存档版本：**73536**。
- 已有真实下载响应验证的版本：**73536、73570**（具体渠道与未来版本不能据此推定全部兼容）。
- 仅将 `command=download3` 作为存档解密入口；`upload3` 上传请求不作为完整存档来源。
- 不读取 `keys.json`／`keys.local.json`；已知渠道后缀内置于源码，密钥恢复和验证发生在运行期间。

> 本文描述的是程序当前支持的数据格式，不提供未来版本通用的解密保证，也不涵盖未经授权的账号、网络流量或数据。

## 1. 入口数据与有效性前提

HAR 文件通常具有 `log.entries[]` 结构，每条记录包含 `request`、`response` 和 `startedDateTime` 等字段。程序只选择 `request.headers` 中 `command=download3` 的请求，按 HAR 采集时间逆序尝试有效记录。

| 字段 | 位置 | 用途 |
| --- | --- | --- |
| `acc` | 下载请求头及相关会话请求头 | 定位账号、派生网络密钥、核对存档身份 |
| `k` | 同账号关联响应头 | 服务端密钥种子密文 |
| `plat` | 请求头 | 判定 `android` 或 `ios` |
| `session` | `download3` 请求头 | 会话 Token 派生参数 |
| `ver` | `download3` 请求头 | 请求版本的初步校验 |
| `startedDateTime` | HAR 条目 | 估算生成 Token 所用的 Unix 秒时间 |
| `data` | 下载响应体 JSON | 会话层封装的存档密文 |
| `extra` | 下载响应体 JSON | 用 `realKey` 恢复版本密码段 `psw` |
| `code` | 下载响应体 JSON | 响应结果校验 |

要求下载 HTTP 状态为 `200`，响应 JSON 的 `code` 为 `0` 或 `"0"`。若响应文本不是直接的 JSON，当前实现还会尝试用 `realKey` 解开兼容的 Base64/XXTEA 包装。

**缺少 `k`、`session`、`extra`、`data` 或有效的下载响应时，均不能假定可恢复完整存档。** HAR 中的真实账号、会话与响应内容不应公开。

## 2. 协议密钥：由 acc 与响应头 k 推导 realKey

源码入口：`yyjh/game/protocol.py` 的 `derive()`，以及 `yyjh/capture/decode.py` 的 `_session_keys()`。

基于已分析的 `ProtocolEnvelope` 密钥结构，先构造 16 字节的 `key0`：

```text
key0 = acc[:5] + "eakec" + "000000"
seed = XXTEA_DECRYPT(Base64Decode(k), key0)
realKey = acc[:5] + "eakec" + seed[:6]
```

上述表达式是算法形状的简化写法：代码实际按固定长度的 16 字节缓冲区写入前缀及前 6 字节种子，并校验解出的种子长度。`realKey` 并非用户在命令行输入的密码，也不是存档文件在设备上的本地外层密钥。

程序优先尝试 HAR 中可与目标账号关联的 `k` 响应头，优先选择下载时间前较近的候选；成功并不只依靠字符串形状，还需继续通过后续完整解密校验。

## 3. extra：恢复 8 位 psw

`download3` 成功响应含有 `extra`，它提供内层存档密钥的动态版本密码段：

```text
psw = XXTEA_DECRYPT(Base64Decode(extra), realKey)
```

解出后必须是 **8 位字母或数字**；不满足该条件的候选直接丢弃。

存档完整内层密钥由两部分组成：

```text
innerKey = psw(8) + channel_suffix(8)
```

`psw` 来自本次 HAR，`channel_suffix` 是源码内置的已知渠道后缀，不是每次都能从 HAR 推导的任意新值。`yyjh/config/keytables.py` 提供后缀候选和平台排序，当前包括：

| 后缀 | 已知用途 |
| --- | --- |
| `po06ewkx` | 安卓官服 |
| `cgkmi4cq` | 先行服 |
| `yoqkmrtj` | iOS |
| `meeo0wmk` | 新服 |
| `tekelad9` | 历史安卓渠道 |

程序逐个尝试候选，并通过完整的 XXTEA → zlib → JSON 校验判断哪一把可用。**不能只根据 `android/ios` 或后缀名称断言密钥正确。**

当前实现另有一个仅包含 `psw` 的候选，用于兼容 XXTEA 对短密钥的补零处理；不代表存在从 HAR 直接恢复未知渠道后缀的通用算法。

## 4. download3 会话层：动态 Token

源码：`yyjh/capture/session.py` 的 `unwrap_download3()` 和 `_candidate_seconds()`。

逆向得到的新版下载存档会话层符合如下形式：

```text
token = MD5(
    platform + "_" + session + "_" + str(unix_seconds)
).hexdigest()[:16]

session_plain = XXTEA_DECRYPT(
    Base64Decode(download3.data), token
)
```

其中 `platform` 为 `android` 或 `ios`；`session` 取自下载请求；`unix_seconds` 为服务端/客户端生成封装时使用的整数秒时间。

因为 HAR 记录的 `startedDateTime` 未必正好等于加密发生的秒数，程序使用该时间作为中心，尝试 **0、±1、±2……±60 秒**，并限制最大偏移为 60 秒。这是确定范围的候选验证，不是扫描游戏内存。

Token 成功命中后，`session_plain` 应当是可解码的 Base64 字符串，解码得到：

```text
8 位十进制版本头 + XXTEA(innerKey, zlib(JSON))
```

此处的函数参数顺序仅表达“用哪个密钥处理什么数据”，不是 Python 实际的形参顺序。

对于 `download3.data` 中本身已经出现合法 8 位明文版本头的已支持变体，程序可直接进入内层解析；这**不意味着支持 73536 以前的上传或下载协议**。

## 5. 内层解密与验证

源码：`yyjh/game/savefmt.py` 中的 `parse_old()`、`try_inner()`。

完整链路：

```text
download3.data
   │ Base64 解码
   ▼
会话层 XXTEA（Token）
   │ 成功后得到 Base64 文本
   ▼
Base64 解码
   │ 版本号(8) + 内层密文
   ▼
内层 XXTEA（psw + 已知后缀）
   ▼
zlib 解压
   ▼
UTF-8 JSON 解析
   ▼
版本与账号一致性核验
   ▼
保存角色
```

校验条件包括：

1. 存档结构、Base64 数据和内层密文长度有效。
2. JSON 必须为对象结构；仅有长度字段匹配不算解密成功。
3. 解密版本号必须不小于 `73536`；若 JSON 中存在 `DBVersion`，还要与解密版本头一致。
4. 若 JSON 中存在 `EncryptID`，必须与目标 HAR 账号一致。
5. 未知渠道、会话变更或真实加密格式变化会导致明确失败，不使用缓存密钥绕过检查。

对于 HAR 中存在多条 `download3` 的情况，按采集时间从近到远尝试，选择第一条通过全部检查的有效存档。因此请尽量将不同账号的 HAR 分开导出，避免混淆。

## 6. 从 JSON 到网页版兼容 dat.db

源码：`yyjh/report.py`、`yyjh/game/savefmt.py`、`yyjh/localdb/sqlitedb.py`。

成功解析后，写出：

```text
output/_har_only/
  android-s53-<账号摘要>/
    dat.json
    dat.db
    dat.meta.json
```

`dat.json` 是恢复后的完整存档；`dat.meta.json` 保存版本、账号、区服和采集时间等信息，但不保存临时 `realKey`、Token、`psw` 或 `innerKey`。

`dat.db` 不是原始客户端数据库的字节复制品。程序先用**网页版兼容的 v1.8 平台固定密钥**重新封装解密后的 JSON，再写成 SQLite `save` 表：

```text
content = Base64(
    version(8) + XXTEA(zlib(JSON), v18_platform_key)
)
save(id, content, player)
```

这个固定密钥只服务于**导出兼容格式**，与 `download3` 网络层的动态 Token、`psw` 不是一回事。**不要据此将生成的 `dat.db` 当作可直接替换游戏客户端原始存档的文件。**

使用相同的账号、平台和区服再次解析时，当前归档采用固定角色目录，完成全部输出后才替换旧记录；当双方采集时间均可信且新输入较旧时拒绝覆盖。兼容读取的历史记录可能位于其他目录，程序不会自动删除那些原始文件。

## 7. 网页载入与项目结构

角色菜单和浏览器入口位于 `yyjh/wizard.py`。

选择已有角色或通过交互菜单成功导入 HAR 后：

1. 读取对应 `dat.json`；
2. 将其转换为 `Base64(zlib(JSON))`；
3. 通过自动载入页写入网页使用的 `localStorage` 键；
4. 打开内置 `web/index.html` 的自动载入副本；
5. 保留原有网页版的角色、洗髓、装备及模拟功能。

这是一种方便的本地数据交换方式，**不是加密保护**。同一浏览器环境中的本地存储或生成的自动载入页仍可能包含可恢复的完整存档信息。

| 代码路径 | 用途 |
| --- | --- |
| `run.py`、`yyjh/__main__.py` | CLI 入口 |
| `yyjh/capture/har.py` | HAR 读取和下载命令识别 |
| `yyjh/capture/decode.py` | 响应选择、协议密钥、密码段、校验 |
| `yyjh/capture/session.py` | 动态会话 Token 与第一层 XXTEA |
| `yyjh/game/protocol.py` | `acc` / `k` 协议密钥推导 |
| `yyjh/config/keytables.py` | 内置渠道后缀顺序 |
| `yyjh/core/xxtea.py` | XXTEA 算法 |
| `yyjh/game/savefmt.py` | 内层解密、JSON 验证、兼容封装 |
| `yyjh/report.py` | 单角色最新记录与安全替换 |
| `yyjh/wizard.py`、`yyjh/webapp.py` | 交互、网页版自动载入及资源整合 |

## 8. 支持边界与测试

| 场景 | 当前行为 |
| --- | --- |
| `download3` + 73536 | 已有真实格式验证 |
| `download3` + 73570 | 已有真实格式验证 |
| 版本号 ≥73536、但使用未知封装 | 尝试解析；未通过校验即失败 |
| 73492 及以下 | 不支持 |
| 只有 `upload3` 而没有 `download3` | 不支持 |
| 本地 `dat.db` 原始加密、设备扫描 | 不在功能范围内 |
| 依赖外部密钥 JSON 或手动填密钥 | 不在功能范围内 |

测试文件位于 `tests/`。如已安装 pytest，可运行：

```powershell
python -m pytest -q tests/test_capture_download.py tests/test_capture_session.py tests/test_har_only.py
```

测试代码使用合成账号与存档结构，不应把真实 HAR 或 `output/` 结果提交到公开仓库。对于新增游戏版本，仍需独立验证它的 HAR 数据封装和网页使用效果。

## 9. 技术来源及归属

实现与技术分析参考：

- [yanyu-amateur/yanyu-guanxing](https://github.com/yanyu-amateur/yanyu-guanxing)：原始存档提取及基础工具结构。
- [leonas30200/yanyu-guanxing](https://github.com/leonas30200/yanyu-guanxing)：相关 HAR 解析与 Python 适配实现。
- [dte2mdj/yanyu-guanxing-web](https://github.com/dte2mdj/yanyu-guanxing-web)：网页版功能和本地存档适配相关实现。

以上项目不因被引用而自动授权再分发。版权与第三方来源见 [NOTICE](../NOTICE.md)，操作步骤见 [使用说明](使用说明.md)。
