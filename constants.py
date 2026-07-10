"""QQ Bot 适配器共享常量。"""

QQBOT_GATEWAY_NAME = "qqbot_gateway"
SUPPORTED_CONFIG_VERSION = "0.1.0"

# -- API 端点 --
QQBOT_API_BASE = "https://api.sgroup.qq.com"
QQBOT_SANDBOX_API_BASE = "https://sandbox.api.sgroup.qq.com"
QQBOT_TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
QQBOT_WSS_GATEWAY = "wss://api.sgroup.qq.com/websocket"
QQBOT_SANDBOX_WSS_GATEWAY = "wss://sandbox.api.sgroup.qq.com/websocket"

# -- 默认值 --
DEFAULT_RECONNECT_DELAY_SEC = 5.0
DEFAULT_HEARTBEAT_INTERVAL_SEC = 30.0
DEFAULT_ACTION_TIMEOUT_SEC = 15.0
DEFAULT_TOKEN_REFRESH_BEFORE_SEC = 300  # 过期前 5 分钟预刷新
DEFAULT_CHAT_LIST_TYPE = "whitelist"

# -- Intent 位域 --
INTENT_GUILDS = 1 << 0             # 1
INTENT_GUILD_MEMBERS = 1 << 1      # 2
INTENT_GUILD_MESSAGES = 1 << 9     # 512（私域频道 MESSAGE_CREATE、MESSAGE_DELETE）
INTENT_GUILD_MESSAGE_REACTIONS = 1 << 10  # 1024
INTENT_DIRECT_MESSAGE = 1 << 12    # 4096（DIRECT_MESSAGE_CREATE、DIRECT_MESSAGE_DELETE）
INTENT_GROUP_AND_C2C = 1 << 25     # 33554432（C2C、群 @ 与群全量消息等事件）
INTENT_INTERACTION = 1 << 26       # 67108864
INTENT_MESSAGE_AUDIT = 1 << 27     # 134217728
INTENT_FORUM_EVENT = 1 << 28       # 268435456
INTENT_AUDIO_ACTION = 1 << 29      # 536870912 (AUDIO_START, AUDIO_FINISH, AUDIO_ON_MIC, AUDIO_OFF_MIC)
INTENT_PUBLIC_GUILD_MESSAGES = 1 << 30  # 1073741824（公域频道 AT_MESSAGE_CREATE）

# 默认订阅：C2C、群 @ 与群全量消息事件所在的 Intent。
# 群全量消息没有单独的 Intent；仅当群主开启允许机器人接收全部消息时，平台才会推送该事件。
DEFAULT_INTENTS = INTENT_GROUP_AND_C2C  # 33554432

# -- OpCode --
OP_DISPATCH = 0             # 服务端推送事件
OP_HEARTBEAT = 1            # 心跳 (双向)
OP_IDENTIFY = 2             # 客户端鉴权
OP_RESUME = 6               # 客户端恢复连接
OP_RECONNECT = 7            # 服务端要求重连
OP_INVALID_SESSION = 9      # 鉴权/恢复失败 (d 字段含 code 说明原因)
OP_HELLO = 10               # 建连后首条消息 (心跳周期, ms)
OP_HEARTBEAT_ACK = 11       # 心跳回复

# OP_HTTP_CALLBACK_ACK = 12   # [仅 webhook] HTTP 回调回包
# OP_CALLBACK_VALIDATION = 13 # [仅 webhook] 回调地址验证

# -- WSS 错误码 (op=9 时 d.code) --
# 官方参考: https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/error-trace/websocket.html
WSS_ERR_INVALID_OPCODE  = 4001  # 无效 opcode        → 退出，不可 Identify
WSS_ERR_INVALID_PAYLOAD = 4002  # 无效 payload       → 退出，不可 Identify
WSS_ERR_INVALID_SESSION = 4006  # 无效 session_id    → 重新 Identify
WSS_ERR_SEQ_MISMATCH     = 4007  # seq 错误           → 重新 Identify
WSS_ERR_RATE_LIMITED     = 4008  # 发送过快           → 可 Resume
WSS_ERR_SESSION_EXPIRED  = 4009  # 连接过期           → 可 Resume
WSS_ERR_INVALID_SHARD    = 4010  # 无效 shard         → 退出，不可 Identify
WSS_ERR_SHARD_OVERLOAD   = 4011  # guild 过多需分片   → 退出，不可 Identify
WSS_ERR_INVALID_VERSION  = 4012  # 无效 version       → 退出，不可 Identify
WSS_ERR_INVALID_INTENT   = 4013  # 无效 intent        → 退出，不可 Identify
WSS_ERR_INTENT_NO_PERM   = 4014  # intent 无权限      → 退出，不可 Identify
WSS_ERR_INTERNAL_START   = 4900  # 内部错误 (到 4913) → 重新 Identify
WSS_ERR_INTERNAL_END     = 4913
WSS_ERR_BOT_DISABLED     = 4914  # 机器人已下架       → 退出，仅连沙箱
WSS_ERR_BOT_BANNED       = 4915  # 机器人已封禁       → 退出，联系官方

# -- 出站消息类型 --
MSG_TYPE_TEXT = 0

# -- 媒体文件类型 --
FILE_TYPE_IMAGE = 1
