"""
QQ Bot 入站消息编解码

将 QQ Bot WebSocket Dispatch 事件转换为 Host 侧 MessageDict
支持的事件类型:
C2C_MESSAGE_CREATE — 私聊消息
GROUP_AT_MESSAGE_CREATE — 群聊 @ 消息
GROUP_MESSAGE_CREATE — 群聊全量消息

Made BY Galeros

"""

from __future__ import annotations

from datetime import datetime
import asyncio
import base64
import hashlib
import json
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    from aiohttp import ClientSession, ClientTimeout

    AIOHTTP_AVAILABLE = True
except ImportError:
    ClientSession = None
    ClientTimeout = None
    AIOHTTP_AVAILABLE = False


class QQBotInboundCodec:
    """QQ Bot 入站消息编解码器。

    将 QQ Bot 事件 payload 转换为 MaiBot 标准 MessageDict。
    """

    def __init__(self, logger: Any) -> None:
        """初始化编解码器。

        Args:
            logger: 插件日志对象。
        """
        self._logger = logger

    async def build_message_dict(
        self, event_type: str, event_data: Dict[str, Any], self_id: str,
    ) -> Dict[str, Any]:
        """从 QQ Bot 事件构造 MessageDict。

        Args:
            event_type: 事件类型（如 ``"C2C_MESSAGE_CREATE"``）。
            event_data: 事件 payload 的 ``d`` 字段。
            self_id: Bot App ID。

        Returns:
            Dict[str, Any]: 标准 MessageDict，供 ``route_message`` 使用。
        """
        if event_type == "C2C_MESSAGE_CREATE":
            return await self._build_c2c_message_dict(event_data, self_id)
        if event_type in ("GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"):
            is_at = event_type == "GROUP_AT_MESSAGE_CREATE"
            return await self._build_group_message_dict(event_data, is_at, self_id)

        self._logger.warning("未知事件类型 %s，用通用 MessageDict 包装", event_type)
        return self._build_generic_message_dict(event_data, self_id)

    # -- C2C 私聊 --

    async def _build_c2c_message_dict(self, data: Dict[str, Any], self_id: str) -> Dict[str, Any]:
        """C2C_MESSAGE_CREATE → MessageDict。

        关键映射:
        - author.user_openid → user_info.user_id
        - author.username → user_info.user_nickname
        - content → raw_message [text]
        - attachments → raw_message [image/...]
        """
        author = data.get("author", {})
        if not isinstance(author, dict):
            author = {}

        user_openid = str(author.get("user_openid") or "").strip()
        username = str(author.get("username") or "").strip() or user_openid

        raw_message = await self._parse_content_and_attachments(data)

        plain_text = self._build_plain_text(raw_message)
        timestamp = self._parse_timestamp(data.get("timestamp"))

        message_info: Dict[str, Any] = {
            "user_info": {
                "user_id": user_openid,
                "user_nickname": username,
                "user_cardname": None,
            },
            "additional_config": {
                "self_id": self_id,
                "qqbot_event_type": "C2C_MESSAGE_CREATE",
                "platform_io_target_user_id": user_openid,
            },
        }

        msg_id = str(data.get("id") or f"qqbot-c2c-{uuid4().hex}").strip()

        return {
            "message_id": msg_id,
            "timestamp": str(float(timestamp)),
            "platform": "qq_bot",
            "message_info": message_info,
            "raw_message": raw_message,
            "is_mentioned": False,
            "is_at": False,
            "is_emoji": False,
            "is_picture": False,
            "is_command": plain_text.startswith("/"),
            "is_notify": False,
            "session_id": "",
            "processed_plain_text": plain_text,
            "display_message": plain_text,
        }

    # -- 群聊 --

    async def _build_group_message_dict(
        self, data: Dict[str, Any], is_at: bool, self_id: str,
    ) -> Dict[str, Any]:
        """GROUP_AT_MESSAGE_CREATE / GROUP_MESSAGE_CREATE → MessageDict。

        关键映射:
        - author.member_openid (优先) / user_openid → user_info.user_id
        - group_openid → group_info.group_id
        - is_at → is_at / is_mentioned
        """
        author = data.get("author", {})
        if not isinstance(author, dict):
            author = {}

        user_openid = str(author.get("user_openid") or "").strip()
        member_openid = str(author.get("member_openid") or "").strip()
        sender_id = member_openid or user_openid
        username = str(author.get("username") or "").strip() or sender_id

        group_openid = str(data.get("group_openid") or data.get("group_id") or "").strip()

        raw_message = await self._parse_content_and_attachments(data)

        plain_text = self._build_plain_text(raw_message)
        timestamp = self._parse_timestamp(data.get("timestamp"))

        additional_config: Dict[str, Any] = {
            "self_id": self_id,
            "qqbot_event_type": "GROUP_AT_MESSAGE_CREATE" if is_at else "GROUP_MESSAGE_CREATE",
            "platform_io_target_group_id": group_openid,
        }
        if member_openid and user_openid and member_openid != user_openid:
            additional_config["platform_io_target_user_id"] = user_openid

        message_info: Dict[str, Any] = {
            "user_info": {
                "user_id": sender_id,
                "user_nickname": username,
                "user_cardname": None,
            },
            "group_info": {
                "group_id": group_openid,
                "group_name": f"group_{group_openid[:8]}" if group_openid else "",
            },
            "additional_config": additional_config,
        }

        msg_id = str(data.get("id") or f"qqbot-group-{uuid4().hex}").strip()

        return {
            "message_id": msg_id,
            "timestamp": str(float(timestamp)),
            "platform": "qq_bot",
            "message_info": message_info,
            "raw_message": raw_message,
            "is_mentioned": is_at,
            "is_at": is_at,
            "is_emoji": False,
            "is_picture": False,
            "is_command": plain_text.startswith("/"),
            "is_notify": False,
            "session_id": "",
            "processed_plain_text": plain_text,
            "display_message": plain_text,
        }

    # -- 通用回退（仅供直接调用编解码器时使用） --

    def _build_generic_message_dict(self, data: Dict[str, Any], self_id: str) -> Dict[str, Any]:
        """为无法识别的 WSS 事件构造通用 MessageDict（用于调试）。"""
        msg_id = str(data.get("id") or f"qqbot-unknown-{uuid4().hex}").strip()
        return {
            "message_id": msg_id,
            "timestamp": str(time.time()),
            "platform": "qq_bot",
            "message_info": {
                "user_info": {"user_id": "unknown", "user_nickname": "unknown"},
                "additional_config": {"self_id": self_id},
            },
            "raw_message": [{"type": "text", "data": f"[未知 QQ Bot 事件: {json.dumps(data)[:200]}]"}],
            "is_mentioned": False,
            "is_at": False,
            "is_emoji": False,
            "is_picture": False,
            "is_command": False,
            "is_notify": False,
            "session_id": "",
            "processed_plain_text": "",
            "display_message": "",
        }

    # -- 内容解析 --

    async def _parse_content_and_attachments(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析 QQ Bot 事件的 content 和 attachments 为 MaiBot 消息段。

        QQ Bot API 中:
        - ``content`` 字段为纯文本字符串
        - ``attachments`` 为附件数组，包含 content_type, url 等

        Args:
            data: 事件 payload。

        Returns:
            List[Dict[str, Any]]: MaiBot 消息段列表。
        """
        result: List[Dict[str, Any]] = []

        # 文本内容
        content = str(data.get("content") or "").strip()
        if content:
            result.append({"type": "text", "data": content})

        # 附件
        attachments = data.get("attachments")
        if isinstance(attachments, list):
            for att in attachments:
                if not isinstance(att, dict):
                    continue
                att_type = str(att.get("content_type") or "").lower()
                att_url = self._normalize_url(str(att.get("url") or "").strip())

                if att_type.startswith("image/"):
                    result.append(await self._build_image_segment(att_url))
                else:
                    # 未知附件类型 → 文本降级
                    filename = att.get("filename", "attachment")
                    result.append({"type": "text", "data": f"[附件: {filename}]"})

        return result

    async def _build_image_segment(self, url: str) -> Dict[str, Any]:
        """下载 QQ 图片附件并构造图片消息段。

        下载成功 → ``{type:image, data:"", hash:sha256, binary_data_base64:...}``
        下载失败 → 退化为 ``[图片]`` 文本段。

        Args:
            url: 图片附件 URL（已补全协议头）。

        Returns:
            Dict[str, Any]: 图片消息段或文本降级段。
        """
        binary_data = await self._download_binary(url)
        if not binary_data:
            self._logger.warning("QQ Bot 图片下载失败，退化为文本占位: %s", url)
            return {"type": "text", "data": "[图片]"}

        return {
            "type": "image",
            "data": "",
            "hash": hashlib.sha256(binary_data).hexdigest(),
            "binary_data_base64": base64.b64encode(binary_data).decode("utf-8"),
        }

    async def _download_binary(self, url: str) -> Optional[bytes]:
        """下载远程二进制资源（图片等）。

        Args:
            url: 资源 URL。

        Returns:
            Optional[bytes]: 下载到的二进制内容；失败时返回 ``None``。
        """
        if not url:
            return None
        if not AIOHTTP_AVAILABLE or ClientSession is None or ClientTimeout is None:
            self._logger.warning("QQ Bot 入站编解码缺少 aiohttp，无法下载图片")
            return None

        try:
            timeout = ClientTimeout(total=15)
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        self._logger.warning(
                            "QQ Bot 图片下载失败: status=%d url=%s", response.status, url,
                        )
                        return None
                    return await response.read()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._logger.warning("QQ Bot 图片下载异常: %s (url=%s)", exc, url)
            return None

    @staticmethod
    def _normalize_url(url: str) -> str:
        """补全缺失的协议头。

        以防万一呢 :3

        Args:
            url: 原始 URL。

        Returns:
            str: 补全协议头后的 URL。
        """
        if not url:
            return url
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return f"https://{url}"

    # -- 辅助函数 --

    @staticmethod
    def _parse_timestamp(value: Any) -> float:
        """将 QQ Bot 的 RFC3339 时间戳转换为 Unix 时间戳。"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized_value = value.strip()
            if normalized_value:
                try:
                    return datetime.fromisoformat(
                        normalized_value.replace("Z", "+00:00")
                    ).timestamp()
                except ValueError:
                    pass
        return time.time()

    @staticmethod
    def _build_plain_text(raw_message: List[Dict[str, Any]]) -> str:
        """从消息段列表提取可读纯文本。

        Args:
            raw_message: 消息段列表。

        Returns:
            str: 纯文本内容。
        """
        parts: List[str] = []
        for item in raw_message:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip()
            item_data = item.get("data", "")
            if item_type == "text":
                parts.append(str(item_data or ""))
            elif item_type == "at":
                if isinstance(item_data, dict):
                    name = str(item_data.get("target_user_nickname") or item_data.get("target_user_id") or "")
                    if name:
                        parts.append(f"@{name}")
            elif item_type == "image":
                parts.append("[图片]")
            elif item_type == "voice":
                parts.append("[语音]")
            elif item_type in ("reply", "forward"):
                parts.append(f"[{item_type}]")
        text = "".join(parts).strip()
        return text or "[unsupported]"

    @staticmethod
    def build_session_key(user_openid: str, group_openid: str = "") -> str:
        """构造去重用的 session_key。

        Args:
            user_openid: 用户 openid。
            group_openid: 群 openid（群事件时使用）。

        Returns:
            str: session_key（如 ``"c2c_{openid}"`` 或 ``"group_{openid}"``）。
        """
        if group_openid:
            return f"group_{group_openid}"
        return f"c2c_{user_openid}"
