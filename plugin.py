"""QQ Bot 官方机器人适配器插件。

职责:
1. 作为客户端连接 QQ Bot WebSocket 网关。
2. 将入站事件 (C2C_MESSAGE_CREATE, GROUP_AT_MESSAGE_CREATE, GROUP_MESSAGE_CREATE)
   转换为 Host 侧 MessageDict。
3. 将 Host 出站消息转换为 QQ Bot REST API 调用并发送。
"""

from __future__ import annotations

import base64
from typing import Any, ClassVar, Dict, Optional, cast

from maibot_sdk import MaiBotPlugin, MessageGateway, PluginConfigBase

from .codecs.inbound import QQBotInboundCodec
from .codecs.outbound import QQBotOutboundCodec
from .config import QQBotPluginSettings
from .constants import QQBOT_GATEWAY_NAME
from .deduplicator import QQBotMessageDeduplicator
from .filters import QQBotChatFilter
from .runtime_state import QQBotRuntimeStateManager
from .transport import QQBotTransportClient


_SUPPORTED_INBOUND_MESSAGE_EVENTS = frozenset(
    {
        "C2C_MESSAGE_CREATE",
        "GROUP_AT_MESSAGE_CREATE",
        "GROUP_MESSAGE_CREATE",
    }
)


class QQBotAdapterPlugin(MaiBotPlugin):
    """QQ Bot 消息网关插件。"""

    config_model: ClassVar[type[PluginConfigBase] | None] = QQBotPluginSettings

    def __init__(self) -> None:
        """初始化 QQ Bot 适配器插件实例。"""
        super().__init__()
        self._transport: Optional[QQBotTransportClient] = None
        self._inbound_codec: Optional[QQBotInboundCodec] = None
        self._outbound_codec: Optional[QQBotOutboundCodec] = None
        self._deduplicator: Optional[QQBotMessageDeduplicator] = None
        self._chat_filter: Optional[QQBotChatFilter] = None
        self._runtime_state: Optional[QQBotRuntimeStateManager] = None

    # -- 生命周期 --

    async def on_load(self) -> None:
        """在插件加载时根据配置决定是否启动连接。"""
        await self._restart_connection_if_needed()

    async def on_unload(self) -> None:
        """在插件卸载时关闭连接。"""
        await self._stop_connection()
        self.ctx.logger.info("QQ Bot 适配器已卸载")

    async def on_config_update(self, scope: str, config_data: Dict[str, Any], version: str) -> None:
        """在配置更新后重载连接状态。

        Args:
            scope: 配置变更范围。
            config_data: 最新的配置数据。
            version: 配置版本号。
        """
        if scope != "self":
            return

        self.set_plugin_config(config_data)
        if version:
            self.ctx.logger.debug("QQ Bot 适配器收到配置更新通知: %s", version)
        await self._restart_connection_if_needed()

    # -- MessageGateway --

    @MessageGateway(
        name=QQBOT_GATEWAY_NAME,
        route_type="duplex",
        platform="qq_bot",
        protocol="qq_official",
        description="QQ 官方 Bot WebSocket 双工消息网关",
    )
    async def handle_qqbot_gateway(
        self,
        message: Dict[str, Any],
        route: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """处理 Host 出站消息并调用 QQ Bot REST API 发送。

        Args:
            message: Host 侧标准 MessageDict。
            route: Platform IO 生成的路由信息。
            metadata: Platform IO 附带的投递元数据。
            **kwargs: 预留扩展参数。

        Returns:
            Dict[str, Any]: 标准化后的发送结果。
        """
        del metadata
        del kwargs

        transport = self._transport
        outbound_codec = self._outbound_codec
        if transport is None or outbound_codec is None:
            return {"success": False, "error": "QQ Bot 传输层未初始化"}

        try:
            action_name, params = outbound_codec.build_outbound_action(message, route or {})
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        try:
            if action_name == QQBotOutboundCodec.ACTION_POST_C2C:
                response = await transport.post_c2c_message(
                    openid=params["openid"],
                    content=params.get("content", ""),
                    msg_type=params.get("msg_type", 0),
                    msg_id=params.get("msg_id", ""),
                )
            elif action_name == QQBotOutboundCodec.ACTION_POST_GROUP:
                response = await transport.post_group_message(
                    group_openid=params["group_openid"],
                    content=params.get("content", ""),
                    msg_type=params.get("msg_type", 0),
                    msg_id=params.get("msg_id", ""),
                )
            elif action_name == QQBotOutboundCodec.ACTION_UPLOAD_AND_SEND_C2C:
                response = await self._upload_and_send(
                    transport=transport,
                    params=params,
                    is_group=False,
                    target_openid=params["openid"],
                )
            elif action_name == QQBotOutboundCodec.ACTION_UPLOAD_AND_SEND_GROUP:
                response = await self._upload_and_send(
                    transport=transport,
                    params=params,
                    is_group=True,
                    target_openid=params["group_openid"],
                )
            else:
                return {"success": False, "error": f"未知动作: {action_name}"}
        except Exception as exc:
            self.ctx.logger.error("QQ Bot 发送消息失败: %s", exc)
            return {"success": False, "error": str(exc)}

        # 检查响应
        if isinstance(response, dict) and response.get("success") is False:
            return response

        external_message_id = str(response.get("id") or response.get("message_id") or "").strip()
        return {
            "success": True,
            "external_message_id": external_message_id or None,
        }

    async def _upload_and_send(
        self,
        transport: QQBotTransportClient,
        params: Dict[str, Any],
        is_group: bool,
        target_openid: str,
    ) -> Dict[str, Any]:
        """上传媒体文件并发送媒体消息。

        流程:
        1. 解码 base64 → bytes
        2. upload_media → file_info
        3. post_message (msg_type=7, media={file_info})

        Args:
            transport: 传输客户端。
            params: 编解码器返回的参数。
            is_group: 是否群聊。
            target_openid: 目标 openid。

        Returns:
            Dict[str, Any]: API 响应。
        """
        media = params.get("media", {})
        if not isinstance(media, dict):
            return {"success": False, "error": "媒体参数格式错误"}

        data_b64 = str(media.get("data_base64") or "").strip()
        if not data_b64:
            return {"success": False, "error": "媒体数据为空（缺少 base64）"}

        try:
            file_data = base64.b64decode(data_b64)
        except Exception as exc:
            return {"success": False, "error": f"Base64 解码失败: {exc}"}

        file_type = int(media.get("file_type", 1))

        upload_resp = await transport.upload_media(
            file_type=file_type,
            file_data=file_data,
            is_group=is_group,
            target_openid=target_openid,
        )

        if isinstance(upload_resp, dict) and upload_resp.get("success") is False:
            return upload_resp

        file_info = upload_resp.get("file_info")
        if not file_info:
            self.ctx.logger.warning("QQ Bot 文件上传响应中缺少 file_info: %s", upload_resp)
            return {"success": False, "error": "上传响应中缺少 file_info"}

        content = str(params.get("content") or "").strip()
        msg_id = str(params.get("msg_id") or "").strip()

        if is_group:
            return await transport.post_group_message(
                group_openid=target_openid,
                content=content,
                msg_type=7,
                media={"file_info": file_info},
                msg_id=msg_id,
            )
        return await transport.post_c2c_message(
            openid=target_openid,
            content=content,
            msg_type=7,
            media={"file_info": file_info},
            msg_id=msg_id,
        )

    # -- 入站 Dispatch 回调 --

    async def _on_dispatch(self, event_data: Dict[str, Any], event_type: str) -> None:
        """处理 QQ Bot WSS Dispatch 事件。

        处理链: 去重 → 过滤 → 编解码 → route_message

        Args:
            event_data: 事件的 ``d`` 字段。
            event_type: 事件类型字符串 (t 字段)。
        """
        settings = self._load_settings()
        codec = self._inbound_codec
        dedupe = self._deduplicator
        chat_filter = self._chat_filter

        if event_type not in _SUPPORTED_INBOUND_MESSAGE_EVENTS:
            self.ctx.logger.debug("QQ Bot 收到未处理的 Dispatch 事件: %s", event_type)
            return

        if codec is None or dedupe is None or chat_filter is None:
            return

        # 1. 提取去重所需字段
        msg_id = str(event_data.get("id") or "").strip()
        author = event_data.get("author", {})
        if not isinstance(author, dict):
            author = {}
        user_openid = str(author.get("user_openid") or "").strip()
        group_openid = (
            str(event_data.get("group_openid") or "").strip()
            if event_type.startswith("GROUP")
            else ""
        )
        msg_seq = event_data.get("msg_seq")
        if msg_seq is not None:
            msg_seq = int(msg_seq)

        # 2. 去重
        session_key = QQBotInboundCodec.build_session_key(user_openid, group_openid)
        if dedupe.is_duplicate(msg_id, session_key, msg_seq):
            self.ctx.logger.debug("QQ Bot 重复消息已丢弃: msg_id=%s, seq=%s", msg_id, msg_seq)
            return

        # 3. 聊天名单过滤
        sender_id = str(author.get("member_openid") or user_openid).strip()
        if not chat_filter.is_inbound_chat_allowed(sender_id, group_openid, settings.chat):
            return

        # 4. 构造 MessageDict
        try:
            message_dict = await codec.build_message_dict(
                event_type, event_data, settings.qqbot.app_id,
            )
        except Exception as exc:
            self.ctx.logger.error("QQ Bot 入站消息编解码失败 (%s): %s", event_type, exc)
            return

        # 5. 路由到 Host
        accepted = await self.ctx.gateway.route_message(
            gateway_name=QQBOT_GATEWAY_NAME,
            message=message_dict,
            external_message_id=msg_id,
            dedupe_key=msg_id,
        )
        if not accepted:
            self.ctx.logger.debug("QQ Bot 消息被 Host 丢弃: msg_id=%s", msg_id)

    # -- 连接状态回调 --

    async def _on_connection_opened(self) -> None:
        """WSS Ready 后激活网关路由。"""
        settings = self._load_settings()
        runtime_state = self._runtime_state
        if runtime_state is not None:
            await runtime_state.report_connected(settings.qqbot.app_id, settings.qqbot)

    async def _on_connection_closed(self) -> None:
        """WSS 断开后撤销网关路由。"""
        runtime_state = self._runtime_state
        if runtime_state is not None:
            await runtime_state.report_disconnected()

        deduplicator = self._deduplicator
        if deduplicator is not None:
            deduplicator.clear()

    # -- 连接管理 --

    def _load_settings(self) -> QQBotPluginSettings:
        """返回当前生效的插件配置。"""
        return cast(QQBotPluginSettings, self.config)

    async def _restart_connection_if_needed(self) -> None:
        """根据当前配置重启连接循环。"""
        settings = self._load_settings()

        await self._stop_connection()

        if not settings.should_connect():
            self.ctx.logger.info("QQ Bot 适配器保持空闲状态（插件未启用）")
            return
        if not settings.validate_runtime_config(self.ctx.logger):
            return
        if not QQBotTransportClient.is_available():
            self.ctx.logger.error("QQ Bot 适配器依赖 aiohttp，当前环境未安装")
            return

        if not settings.chat.enable_chat_list_filter:
            self.ctx.logger.info(
                "QQ Bot 聊天名单过滤已关闭：将忽略 group_list 与 private_list，仅保留 ban_user_id"
            )

        # 延迟初始化运行时组件
        self._inbound_codec = QQBotInboundCodec(self.ctx.logger)
        self._outbound_codec = QQBotOutboundCodec()
        self._deduplicator = QQBotMessageDeduplicator()
        self._chat_filter = QQBotChatFilter(self.ctx.logger)
        self._runtime_state = QQBotRuntimeStateManager(
            self.ctx.gateway, self.ctx.logger, QQBOT_GATEWAY_NAME,
        )

        self._transport = QQBotTransportClient(
            logger=self.ctx.logger,
            on_connection_opened=self._on_connection_opened,
            on_connection_closed=self._on_connection_closed,
            on_dispatch=self._on_dispatch,
        )
        self._transport.configure(settings.qqbot)
        await self._transport.start()

    async def _stop_connection(self) -> None:
        """停止当前连接并清理运行时状态。"""
        transport = self._transport
        if transport is not None:
            await transport.stop()
            self._transport = None


def create_plugin() -> QQBotAdapterPlugin:
    """创建 QQ Bot 适配器插件实例。

    Returns:
        QQBotAdapterPlugin: 插件实例。
    """
    return QQBotAdapterPlugin()
