# MaiBot-QQBot-Adapter

**MaiBot 的 QQ 官方机器人平台适配器插件**

通过 QQ 开放平台官方 Bot API（WebSocket + REST）将 [MaiBot](https://github.com/Mai-with-u/MaiBot) 接入 QQ，实现私聊与群聊消息的双向收发。

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)
[![maibot-plugin-sdk](https://img.shields.io/badge/SDK-maibot--plugin--sdk-orange)](https://github.com/Mai-with-u/maibot-plugin-sdk)


📖 **完整详细教程请访问：**  
**[MaiBot-QQBot-Adapter 详细使用教程](https://www.galeros.xyz/2026/07/07/qqbot-adapter/)**

### 安装

将本仓库克隆到 MaiBot 的 `plugins/` 下即可。

```
cd /path/to/MaiBot/plugins
git clone https://github.com/mayan613/MaiBot-QQBot-Adapter.git
```

### 前置条件

| 依赖 | 最低版本 | 用途 |
|------|----------|------|
| aiohttp (PyPI) | ≥ 3.8 | WebSocket 与 REST 通信（MaiBot 环境通常已内置） |
| QQ 机器人应用 | — | 在 [q.qq.com](https://q.qq.com) 创建，获取 AppID / AppSecret |
| MaiBot | ≥ 1.0.0 | 插件宿主 |

与 NapCat等适配器不同，本插件走 **QQ 官方开放平台**，使用 **AppID + AppSecret** 鉴权、**openid** 身份体系。


## 架构

```
QQ 开放平台  ──WSS 事件推送──▶  QQBotTransportClient  ──▶  MaiBot (plugin.py)
（api.sgroup.qq.com）           (transport.py)
             ◀──REST 出站发送──  QQBotTransportClient  ◀──
```

- **WSS 通道**：接收事件推送（Dispatch）、维持心跳、鉴权（Identify）、断线重连（Resume）
- **REST 通道**：发送消息、上传媒体等出站操作
- **Token 管理**：自动获取 / 预刷新 `access_token`（有效期 7200 秒，默认提前 5 分钟刷新）



## 配置

插件配置可通过 MaiBot WebUI 的插件配置页面修改。

### 配置项说明

| 配置节 | 字段 | 类型 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `[plugin]` | `enabled` | bool | false | 是否启用适配器 |
| `[plugin]` | `config_version` | str | 0.1.0 | 配置版本（无需变更） |
| `[qqbot]` | `app_id` | str | "" | QQ Bot AppID，从 QQ 开放平台获取 |
| `[qqbot]` | `app_secret` | str | "" | QQ Bot AppSecret，与 AppID 对应的密钥 |
| `[qqbot]` | `use_sandbox` | bool | false | 是否使用沙箱环境（开发测试用，上线前关闭） |
| `[qqbot]` | `intents` | int | 33554432 | 订阅的事件 Intents（位域），默认订阅 C2C 私聊 + 群 @ 消息 |
| `[qqbot]` | `shard_count` | int | 1 | 分片总数（单实例保持 1） |
| `[qqbot]` | `shard_index` | int | 0 | 当前分片序号（单实例保持 0） |
| `[qqbot]` | `heartbeat_interval` | float | 30.0 | 心跳超时判定间隔（秒） |
| `[qqbot]` | `reconnect_delay_sec` | float | 5.0 | 断线后的重连等待时间（秒） |
| `[qqbot]` | `action_timeout_sec` | float | 15.0 | REST API 调用超时时间（秒） |
| `[qqbot]` | `token_refresh_before_sec` | float | 300.0 | access_token 过期前提前刷新的秒数 |
| `[qqbot]` | `connection_id` | str | "" | 可选连接标识，用于区分多条链路 |
| `[chat]` | `enable_chat_list_filter` | bool | true | 是否启用群聊与私聊名单过滤 |
| `[chat]` | `show_dropped_chat_list_messages` | bool | false | 是否记录被名单过滤丢弃的日志 |
| `[chat]` | `group_list_type` | str | whitelist | 群聊名单模式（whitelist / blacklist） |
| `[chat]` | `group_list` | list | [] | 群聊名单中的群 openid 列表 |
| `[chat]` | `private_list_type` | str | whitelist | 私聊名单模式（whitelist / blacklist） |
| `[chat]` | `private_list` | list | [] | 私聊名单中的用户 openid 列表 |
| `[chat]` | `ban_user_id` | list | [] | 全局屏蔽的用户 openid 列表 |

### 如何获取 AppID / AppSecret

1. 访问 [QQ 开放平台](https://q.qq.com) 并登录。
2. 创建机器人应用，在「开发设置」中获取 **AppID** 与 **AppSecret**。
3. 在「功能配置」中开启需要的事件订阅（如私信、群 @ 等），否则平台不会推送对应事件。

### 使用 (MaiBot配置)

MaiBot Core 仍会用主配置里的 bot 平台账号识别“机器人自己”。由于 QQ 官方机器人**没有 QQ 号**，其平台账号使用 **AppID**。因此在启用此插件后，必须在 MaiBot 配置文件夹下的 `bot_config.toml` 中的 `[bot]` 部分的 `platforms` 配置项加入以下信息：

```toml
[bot]
platform = "qq"                # 这里的平台是留给官方的适配器的(Napcat,snowluma等)
qq_account = "111111"          # 跟你原来配置保持一致
platforms = [
    "qq_bot:xxxxxxxxxx",       # 重要: 格式为 "qq_bot:AppID"，冒号后填你的 AppID (为了避免冲突,本插件的平台名为qq_bot)
]
nickname = "麦麦"              # 根据你的要求来改
alias_names = []
```

> **重要**：平台前缀必须是 `qq_bot`（区分于 NapCat 的 `qq`），冒号后填 **AppID** 。两处 AppID 必须完全一致：适配器配置文件 `config.toml` 里的 `app_id`和此处的 `qq_bot:AppID`。

当然，如果你不喜欢直接编辑配置文件，也可以在 WebUI 中设置，具体方法是：`麦麦设置-基础-平台账号右边的加号-平台 qq_bot，账号填你的 AppID`（请填写自己的项目信息）。不设置将无法正确识别机器人自身。

### 消息收发

- **收消息**：他人通过 QQ 私聊 bot 或群内 @ bot → 自动注入 MaiBot 消息管道 → LLM 回复
- **发消息**：MaiBot 生成的回复 → 通过 QQ Bot REST API 发送
- **图片**：入站图片会趁 URL 中的临时 rkey 有效时立即下载并回填二进制；出站图片走「上传媒体 → 发送 media」两步式

## 注意事项

### QQ 官方平台限制

| 限制 | 说明 |
|------|------|
| 无法获取用户昵称 | 官方 API 出于隐私保护不下发昵称，私聊显示的“名字”会退化为用户 openid（一长串十六进制），属正常现象 |
| 无 QQ 号 | 官方 bot 身份为 AppID + openid，没有传统 QQ 号 |
| 群全量消息需权限 | `GROUP_MESSAGE_CREATE`（非 @ 的群消息）仅在 bot 为群管理员或获得主动发言权限后由服务端推送；`GROUP_AT_MESSAGE_CREATE`（群 @）始终可用 |
| 被动回复窗口 | 收到用户消息后，C2C 私聊有 60 分钟、群聊有 5 分钟的被动回复窗口，且每条消息最多回复 5 次 |
| 主动消息受限 | 主动推送消息受平台严格限制，本插件以被动回复为主 |

### 不支持的消息类型

受限于 QQ 官方 Bot API 与 MaiBot 能力，以下出站消息段会被降级处理：

| 消息类型 | 处理方式 |
|----------|----------|
| 出站 @ (`at`) | 官方 API 不支持出站 @，转为 `@名称` 文本 |
| 语音 (`voice`) | 转为 `[语音]` 文本标记 |
| 合并转发 (`forward`) | 转为文本提示 |
| 引用回复 (`reply`) | 映射到 `msg_id` 参数实现引用 |

## 故障排查

| 症状 | 可能原因 | 解决 |
|------|----------|------|
| 日志出现 `op=9 Invalid Session` 且带 4013/4014 | intents 无效或无权限 | 在 QQ 开放平台开启对应事件订阅；核对 `intents` 值 |
| 连接建立后很快断开、无 READY | AppSecret 错误或 token 获取失败 | 核对 `app_id` / `app_secret`；查看日志中 token 获取是否成功 |
| 断开日志显示 `close_code=4914/4915` | 机器人被下架 / 封禁 | 前往 QQ 开放平台检查应用状态 |
| 断开日志前有“心跳超时” | 网络问题或服务端未回 ACK | 检查网络；插件会自动重连 |
| 收到图片报“加载图片二进制失败” | 图片 rkey 过期或下载失败 | 属偶发，会退化为 `[图片]` 文本；检查网络到 `multimedia.nt.qq.com.cn` 的连通性 |
| 私聊名字是一长串十六进制 | 官方 API 不下发昵称 | 正常现象，显示的是用户 openid |
| 麦麦把自己的消息当成别人 | `bot_config.toml` 未配置 `qq_bot:AppID` | 在 `platforms` 中加入 `qq_bot:你的AppID`，重启主程序 |

## 许可证

本项目基于 GPL-3.0 许可证开源。
