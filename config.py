"""QQ Bot 适配器配置模型。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, Dict, List, Literal, Optional

from maibot_sdk import Field, PluginConfigBase
from pydantic import ValidationInfo, field_validator

from .constants import (
    DEFAULT_ACTION_TIMEOUT_SEC,
    DEFAULT_CHAT_LIST_TYPE,
    DEFAULT_HEARTBEAT_INTERVAL_SEC,
    DEFAULT_INTENTS,
    DEFAULT_RECONNECT_DELAY_SEC,
    DEFAULT_TOKEN_REFRESH_BEFORE_SEC,
    QQBOT_API_BASE,
    QQBOT_SANDBOX_API_BASE,
    QQBOT_SANDBOX_WSS_GATEWAY,
    QQBOT_WSS_GATEWAY,
    SUPPORTED_CONFIG_VERSION,
)

def _schema_i18n(
    *,
    label_en: str,
    label_ja: str,
    hint_en: Optional[str] = None,
    hint_ja: Optional[str] = None,
    placeholder_en: Optional[str] = None,
    placeholder_ja: Optional[str] = None,
) -> Dict[str, Dict[str, str]]:
    """构造 WebUI 配置项多语言说明，保留外层中文字段兼容旧格式。"""

    i18n: Dict[str, Dict[str, str]] = {
        "en_US": {"label": label_en},
        "ja_JP": {"label": label_ja},
    }
    if hint_en is not None:
        i18n["en_US"]["hint"] = hint_en
    if hint_ja is not None:
        i18n["ja_JP"]["hint"] = hint_ja
    if placeholder_en is not None:
        i18n["en_US"]["placeholder"] = placeholder_en
    if placeholder_ja is not None:
        i18n["ja_JP"]["placeholder"] = placeholder_ja
    return i18n


# -- 插件设置 --


class QQBotPluginOptions(PluginConfigBase):
    """插件级配置。"""

    __ui_label__: ClassVar[str] = "插件设置"
    __ui_order__: ClassVar[int] = 0

    enabled: bool = Field(
        default=False,
        description="是否启用 QQ Bot 适配器。",
        json_schema_extra={
            "hint": "关闭后插件会保持空闲，不会建立 QQ Bot WebSocket 连接。",
            "i18n": _schema_i18n(
                label_en="Enable adapter",
                label_ja="アダプターを有効化",
                hint_en="When disabled, the plugin stays idle and will not open a QQ Bot WebSocket connection.",
                hint_ja="無効にすると、プラグインは待機状態のままになり、QQ Bot WebSocket 接続を開始しません。",
            ),
            "label": "启用适配器",
            "order": 0,
        },
    )
    config_version: str = Field(
        default=SUPPORTED_CONFIG_VERSION,
        description="当前配置结构版本。",
        json_schema_extra={
            "disabled": True,
            "hidden": True,
            "i18n": _schema_i18n(label_en="Config version", label_ja="設定バージョン"),
            "label": "配置版本",
            "order": 99,
        },
    )

    def should_connect(self) -> bool:
        """判断当前配置下是否应当启动连接。

        Returns:
            bool: 若插件连接已启用，则返回 ``True``。
        """
        return self.enabled

    @field_validator("config_version", mode="before")
    @classmethod
    def _normalize_config_version(cls, value: Any) -> str:
        """规范化配置版本字段。"""
        normalized_value = _normalize_string(value)
        return normalized_value or SUPPORTED_CONFIG_VERSION


# -- QQ Bot 连接配置 --


class QQBotConnectionConfig(PluginConfigBase):
    """QQ Bot WebSocket 与 REST API 连接配置。"""

    __ui_label__: ClassVar[str] = "QQ Bot 连接"
    __ui_order__: ClassVar[int] = 1

    app_id: str = Field(
        default="",
        description="QQ Bot AppID，从 QQ 开放平台获取。",
        json_schema_extra={
            "hint": "在 q.qq.com 创建机器人应用后获取。",
            "i18n": _schema_i18n(
                label_en="App ID",
                label_ja="App ID",
                hint_en="Obtained from the QQ Open Platform after creating a bot application.",
                hint_ja="QQ オープンプラットフォームで Bot アプリを作成した後に取得します。",
                placeholder_en="Your App ID",
                placeholder_ja="あなたの App ID",
            ),
            "label": "App ID",
            "order": 0,
            "placeholder": "请输入 App ID",
        },
    )
    app_secret: str = Field(
        default="",
        description="QQ Bot AppSecret，从 QQ 开放平台获取。",
        json_schema_extra={
            "hint": "与 AppID 对应的密钥，请妥善保管。",
            "i18n": _schema_i18n(
                label_en="App Secret",
                label_ja="App Secret",
                hint_en="The secret key corresponding to your App ID. Keep it safe.",
                hint_ja="App ID に対応する秘密鍵です。安全に保管してください。",
                placeholder_en="Your App Secret",
                placeholder_ja="あなたの App Secret",
            ),
            "input_type": "password",
            "label": "App Secret",
            "order": 1,
            "placeholder": "请输入 App Secret",
        },
    )
    use_sandbox: bool = Field(
        default=False,
        description="是否使用 QQ Bot 沙箱环境。",
        json_schema_extra={
            "hint": "沙箱环境用于开发测试，上线前请关闭。",
            "i18n": _schema_i18n(
                label_en="Use sandbox",
                label_ja="サンドボックスを使用",
                hint_en="Sandbox environment for development and testing. Disable before going live.",
                hint_ja="開発・テスト用のサンドボックス環境です。本番前に無効にしてください。",
            ),
            "label": "使用沙箱环境",
            "order": 2,
        },
    )
    intents: int = Field(
        default=DEFAULT_INTENTS,
        description="订阅的事件 Intents（位域）。",
        json_schema_extra={
            "hint": "默认 33554432 (" + str(DEFAULT_INTENTS) + ") 订阅了 C2C 私聊消息和群 @ 消息。群全量消息需 bot 在群内获得管理员或主动发言权限后由服务端自动推送。",
            "i18n": _schema_i18n(
                label_en="Intents",
                label_ja="Intents",
                hint_en="Default 33554432 = C2C messages + Group @ mentions. Full group messages require admin/active speaker permission.",
                hint_ja="購読するイベントインテントのビットフィールドです。",
            ),
            "label": "Intents",
            "order": 3,
        },
    )
    shard_count: int = Field(
        default=1,
        description="分片总数。",
        json_schema_extra={
            "hint": "多分片部署时的总分片数，单实例保持 1。",
            "i18n": _schema_i18n(
                label_en="Shard count",
                label_ja="シャード数",
                hint_en="Total shard count for multi-instance deployment. Keep 1 for single instance.",
                hint_ja="複数インスタンス展開時の総シャード数です。単一インスタンスでは 1 のままにします。",
            ),
            "label": "分片总数",
            "order": 4,
        },
    )
    shard_index: int = Field(
        default=0,
        description="当前分片序号 (0-based)。",
        json_schema_extra={
            "hint": "多分片部署时的当前分片编号，单实例保持 0。",
            "i18n": _schema_i18n(
                label_en="Shard index",
                label_ja="シャードインデックス",
                hint_en="Current shard index for multi-instance deployment. Keep 0 for single instance.",
                hint_ja="複数インスタンス展開時の現在のシャード番号です。単一インスタンスでは 0 のままにします。",
            ),
            "label": "分片序号",
            "order": 5,
        },
    )
    heartbeat_interval: float = Field(
        default=DEFAULT_HEARTBEAT_INTERVAL_SEC,
        description="心跳超时判定间隔，单位为秒。",
        json_schema_extra={
            "hint": "用于判断 QQ Bot WSS 连接是否失活，必须大于 0。",
            "i18n": _schema_i18n(
                label_en="Heartbeat interval (sec)",
                label_ja="ハートビート間隔（秒）",
                hint_en="Used to detect whether the QQ Bot WSS connection is stale. Must be greater than 0.",
                hint_ja="QQ Bot WSS 接続が失活していないかを判定する間隔です。0 より大きい値にしてください。",
            ),
            "label": "心跳间隔（秒）",
            "order": 6,
            "step": 1,
        },
    )
    reconnect_delay_sec: float = Field(
        default=DEFAULT_RECONNECT_DELAY_SEC,
        description="连接断开后的重连等待时间，单位为秒。",
        json_schema_extra={
            "hint": "连接断开后会等待该时长再尝试重新连接。",
            "i18n": _schema_i18n(
                label_en="Reconnect delay (sec)",
                label_ja="再接続待機（秒）",
                hint_en="After a disconnect, wait this long before trying to reconnect.",
                hint_ja="接続が切断された後、再接続を試すまでこの時間待機します。",
            ),
            "label": "重连等待（秒）",
            "order": 7,
            "step": 1,
        },
    )
    action_timeout_sec: float = Field(
        default=DEFAULT_ACTION_TIMEOUT_SEC,
        description="调用 REST API 的超时时间，单位为秒。",
        json_schema_extra={
            "hint": "发送消息、上传文件等操作会在超时后报错。",
            "i18n": _schema_i18n(
                label_en="Action timeout (sec)",
                label_ja="アクションタイムアウト（秒）",
                hint_en="Actions such as sending messages or uploading files fail after this timeout.",
                hint_ja="メッセージ送信やファイルアップロードなどのアクションは、この時間を超えるとエラーになります。",
            ),
            "label": "动作超时（秒）",
            "order": 8,
            "step": 1,
        },
    )
    token_refresh_before_sec: float = Field(
        default=DEFAULT_TOKEN_REFRESH_BEFORE_SEC,
        description="在 access_token 过期前多少秒提前刷新。",
        json_schema_extra={
            "hint": "access_token 有效期 7200 秒，默认提前 5 分钟刷新。",
            "i18n": _schema_i18n(
                label_en="Token refresh before expiry (sec)",
                label_ja="トークン期限前リフレッシュ（秒）",
                hint_en="access_token expires in 7200s. Default refreshes 5 min before expiry.",
                hint_ja="access_token の有効期限は 7200 秒です。デフォルトで期限の 5 分前にリフレッシュします。",
            ),
            "label": "Token 提前刷新（秒）",
            "order": 9,
            "step": 10,
        },
    )
    connection_id: str = Field(
        default="",
        description="可选连接标识，用于区分多条 QQ Bot 链路。",
        json_schema_extra={
            "hint": "当存在多条 QQ Bot 连接时，可用它作为路由作用域标识。",
            "i18n": _schema_i18n(
                label_en="Connection ID",
                label_ja="接続識別子",
                hint_en="When multiple QQ Bot connections exist, use this as the routing scope identifier.",
                hint_ja="複数の QQ Bot 接続がある場合、ルーティングスコープの識別子として使用できます。",
                placeholder_en="For example: primary",
                placeholder_ja="例：primary",
            ),
            "label": "连接标识",
            "order": 10,
            "placeholder": "例如：primary",
        },
    )

    def base_url(self) -> str:
        """根据沙箱开关返回 REST API 基地址。"""
        return QQBOT_SANDBOX_API_BASE if self.use_sandbox else QQBOT_API_BASE

    def ws_url(self) -> str:
        """根据沙箱开关返回 WSS 网关地址。"""
        return QQBOT_SANDBOX_WSS_GATEWAY if self.use_sandbox else QQBOT_WSS_GATEWAY

    @field_validator("app_id", "app_secret", "connection_id", mode="before")
    @classmethod
    def _normalize_text_fields(cls, value: Any) -> str:
        """规范化文本字段。"""
        return _normalize_string(value)

    @field_validator("intents", "shard_count", "shard_index", mode="before")
    @classmethod
    def _normalize_int_fields(cls, value: Any, info: ValidationInfo) -> int:
        """规范化整数字段。"""
        defaults: Dict[str, int] = {
            "intents": DEFAULT_INTENTS,
            "shard_count": 1,
            "shard_index": 0,
        }
        return _normalize_int(value, defaults[str(info.field_name)])

    @field_validator(
        "heartbeat_interval",
        "reconnect_delay_sec",
        "action_timeout_sec",
        "token_refresh_before_sec",
        mode="before",
    )
    @classmethod
    def _normalize_float_fields(cls, value: Any, info: ValidationInfo) -> float:
        """规范化正浮点数字段。"""
        defaults: Dict[str, float] = {
            "heartbeat_interval": DEFAULT_HEARTBEAT_INTERVAL_SEC,
            "reconnect_delay_sec": DEFAULT_RECONNECT_DELAY_SEC,
            "action_timeout_sec": DEFAULT_ACTION_TIMEOUT_SEC,
            "token_refresh_before_sec": DEFAULT_TOKEN_REFRESH_BEFORE_SEC,
        }
        return _normalize_positive_float(value, defaults[str(info.field_name)])


# -- 聊天过滤配置 --


class QQBotChatConfig(PluginConfigBase):
    """聊天名单配置。"""

    __ui_label__: ClassVar[str] = "聊天过滤"
    __ui_order__: ClassVar[int] = 2

    enable_chat_list_filter: bool = Field(
        default=True,
        description="是否启用群聊与私聊名单过滤。",
        json_schema_extra={
            "hint": "关闭后将忽略群聊名单和私聊名单，仅保留全局屏蔽用户。",
            "i18n": _schema_i18n(
                label_en="Enable chat list filter",
                label_ja="チャットリストフィルターを有効化",
                hint_en="When disabled, group and private lists are ignored; only globally banned users remain.",
                hint_ja="無効にすると、グループ/個人チャットのリストを無視し、全体のブロックユーザーのみを適用します。",
            ),
            "label": "启用聊天名单过滤",
            "order": 0,
        },
    )
    show_dropped_chat_list_messages: bool = Field(
        default=False,
        description="是否显示未通过聊天名单过滤而被丢弃的消息日志。",
        json_schema_extra={
            "hint": "关闭后不会记录群聊/私聊因未通过聊天名单过滤而被丢弃的日志，默认关闭以减少刷屏。",
            "i18n": _schema_i18n(
                label_en="Show dropped chat-list logs",
                label_ja="チャットリストで破棄されたログを表示",
                hint_en="When disabled, dropped group/private chat-list logs are not recorded. Default off to reduce log noise.",
                hint_ja="無効にすると、チャットリストで破棄されたグループ/個人チャットのログを記録しません。ログの増加を抑えるため既定ではオフです。",
            ),
            "label": "显示聊天名单丢弃日志",
            "order": 1,
        },
    )
    group_list_type: Literal["whitelist", "blacklist"] = Field(
        default=DEFAULT_CHAT_LIST_TYPE,
        description="群聊名单模式。",
        json_schema_extra={
            "hint": "白名单模式只接收列表内群聊，黑名单模式则忽略列表内群聊。",
            "i18n": _schema_i18n(
                label_en="Group list mode",
                label_ja="グループリストモード",
                hint_en="Whitelist mode only accepts listed groups; blacklist mode ignores listed groups.",
                hint_ja="ホワイトリストではリスト内のグループのみ受信し、ブラックリストではリスト内のグループを無視します。",
            ),
            "label": "群聊名单模式",
            "order": 2,
        },
    )
    group_list: List[str] = Field(
        default_factory=list,
        description="群聊名单中的群 openid 列表。",
        json_schema_extra={
            "hint": "群 openid 会被统一转换为字符串并自动去重。",
            "i18n": _schema_i18n(
                label_en="Group list",
                label_ja="グループリスト",
                hint_en="Group openids are normalized to strings and deduplicated automatically.",
                hint_ja="グループ openid は文字列に正規化され、自動的に重複排除されます。",
                placeholder_en="Enter group_openid",
                placeholder_ja="group_openid を入力",
            ),
            "label": "群聊名单",
            "order": 3,
            "placeholder": "请输入群 openid",
        },
    )
    private_list_type: Literal["whitelist", "blacklist"] = Field(
        default=DEFAULT_CHAT_LIST_TYPE,
        description="私聊名单模式。",
        json_schema_extra={
            "hint": "白名单模式只接收列表内私聊，黑名单模式则忽略列表内私聊。",
            "i18n": _schema_i18n(
                label_en="Private list mode",
                label_ja="個人チャットリストモード",
                hint_en="Whitelist mode only accepts listed private chats; blacklist mode ignores listed private chats.",
                hint_ja="ホワイトリストではリスト内の個人チャットのみ受信し、ブラックリストではリスト内の個人チャットを無視します。",
            ),
            "label": "私聊名单模式",
            "order": 4,
        },
    )
    private_list: List[str] = Field(
        default_factory=list,
        description="私聊名单中的用户 openid 列表。",
        json_schema_extra={
            "hint": "用户 openid 会被统一转换为字符串并自动去重。",
            "i18n": _schema_i18n(
                label_en="Private list",
                label_ja="個人チャットリスト",
                hint_en="User openids are normalized to strings and deduplicated automatically.",
                hint_ja="ユーザー openid は文字列に正規化され、自動的に重複排除されます。",
                placeholder_en="Enter user_openid",
                placeholder_ja="user_openid を入力",
            ),
            "label": "私聊名单",
            "order": 5,
            "placeholder": "请输入用户 openid",
        },
    )
    ban_user_id: List[str] = Field(
        default_factory=list,
        description="全局屏蔽的用户 openid 列表。",
        json_schema_extra={
            "hint": "这些用户的消息会在进入 Host 之前被直接丢弃。",
            "i18n": _schema_i18n(
                label_en="Globally blocked users",
                label_ja="全体ブロックユーザー",
                hint_en="Messages from these users are dropped before entering the Host.",
                hint_ja="これらのユーザーからのメッセージは Host に入る前に破棄されます。",
            ),
            "label": "全局屏蔽用户",
            "order": 6,
            "placeholder": "请输入用户 openid",
        },
    )
    ban_qq_bot: bool = Field(
        default=False,
        description="是否屏蔽 QQ 官方机器人消息。",
        json_schema_extra={
            "hint": "开启后会忽略来自 QQ 官方机器人或频道机器人的消息。",
            "i18n": _schema_i18n(
                label_en="Block official bots",
                label_ja="公式 Bot をブロック",
                hint_en="When enabled, messages from QQ official bots or channel bots are ignored.",
                hint_ja="有効にすると、QQ 公式 Bot またはチャンネル Bot からのメッセージを無視します。",
            ),
            "label": "屏蔽官方机器人",
            "order": 7,
        },
    )

    @field_validator("group_list_type", "private_list_type", mode="before")
    @classmethod
    def _normalize_list_types(cls, value: Any) -> Literal["whitelist", "blacklist"]:
        """规范化名单模式字段。"""
        normalized_value = _normalize_string(value)
        if normalized_value == "whitelist":
            return "whitelist"
        if normalized_value == "blacklist":
            return "blacklist"
        return DEFAULT_CHAT_LIST_TYPE

    @field_validator("group_list", "private_list", "ban_user_id", mode="before")
    @classmethod
    def _normalize_id_lists(cls, value: Any) -> List[str]:
        """规范化 ID 列表字段。"""
        return _normalize_string_list(value)


# -- 根配置 --


class QQBotPluginSettings(PluginConfigBase):
    """QQ Bot 插件完整配置。"""

    plugin: QQBotPluginOptions = Field(default_factory=QQBotPluginOptions)
    qqbot: QQBotConnectionConfig = Field(default_factory=QQBotConnectionConfig)
    chat: QQBotChatConfig = Field(default_factory=QQBotChatConfig)

    @classmethod
    def from_mapping(cls, raw_config: Mapping[str, Any], logger: Any) -> "QQBotPluginSettings":
        """从 Runner 注入的原始配置字典解析插件配置。

        Args:
            raw_config: Runner 注入的原始配置内容。
            logger: 兼容旧调用签名保留的日志对象。

        Returns:
            QQBotPluginSettings: 规范化后的插件配置模型。
        """
        del logger
        return cls.model_validate(dict(raw_config))

    def should_connect(self) -> bool:
        """判断当前配置下是否应当启动连接。"""
        return self.plugin.should_connect()

    def validate_runtime_config(self, logger: Any) -> bool:
        """校验当前配置是否满足启动连接的前提条件。

        Args:
            logger: 插件日志对象。

        Returns:
            bool: 若配置满足启动条件则返回 ``True``。
        """
        config_version = self.plugin.config_version
        if not config_version:
            logger.error("QQ Bot 适配器配置缺少 plugin.config_version，当前插件要求版本 %s", SUPPORTED_CONFIG_VERSION)
            return False
        if config_version != SUPPORTED_CONFIG_VERSION:
            logger.error(
                "QQ Bot 适配器配置版本不兼容: 当前为 %s，插件要求 %s",
                config_version,
                SUPPORTED_CONFIG_VERSION,
            )
            return False
        if not self.qqbot.app_id:
            logger.warning("QQ Bot 适配器已启用，但 qqbot.app_id 为空")
            return False
        if not self.qqbot.app_secret:
            logger.warning("QQ Bot 适配器已启用，但 qqbot.app_secret 为空")
            return False
        return True


# -- 工具函数 --


def _normalize_float(value: Any, default: float) -> float:
    """规范化浮点数配置值。"""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _normalize_int(value: Any, default: int) -> int:
    """规范化整数配置值。"""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def _normalize_positive_float(value: Any, default: float) -> float:
    """规范化正浮点数配置值。"""
    if isinstance(value, (int, float)) and float(value) > 0:
        return float(value)
    if isinstance(value, str):
        try:
            parsed_value = float(value.strip())
        except ValueError:
            return default
        if parsed_value > 0:
            return parsed_value
    return default


def _normalize_string(value: Any) -> str:
    """规范化字符串配置值。"""
    return "" if value is None else str(value).strip()


def _normalize_string_list(value: Any) -> List[str]:
    """规范化字符串列表配置值。"""
    if not isinstance(value, list):
        return []
    normalized_values: List[str] = []
    seen_values = set()
    for item in value:
        item_text = _normalize_string(item)
        if not item_text or item_text in seen_values:
            continue
        seen_values.add(item_text)
        normalized_values.append(item_text)
    return normalized_values
