"""
QQ Bot 入站消息过滤器

Made BY Galeros

"""

from __future__ import annotations

from typing import Any, Collection

from .config import QQBotChatConfig


class QQBotChatFilter:
    """QQ Bot 聊天名单过滤器。

    过滤器逻辑:
    - 全局屏蔽用户 (ban_user_id)
    - 群聊白名单/黑名单
    - 私聊白名单/黑名单
    - 可选的过滤开关

    """

    def __init__(self, logger: Any) -> None:
        """初始化过滤器。

        Args:
            logger: 插件日志对象。
        """
        self._logger = logger

    def is_inbound_chat_allowed(
        self, sender_user_id: str, group_id: str, chat_config: QQBotChatConfig,
    ) -> bool:
        """检查入站消息是否通过聊天名单过滤。

        Args:
            sender_user_id: 发送者标识 (openid)。
            group_id: 群组标识，私聊时为空字符串。
            chat_config: 聊天过滤配置。

        Returns:
            bool: 若允许接收则返回 ``True``。
        """
        # 全局屏蔽
        if sender_user_id in chat_config.ban_user_id:
            self._logger.debug("消息被全局屏蔽: sender=%s", sender_user_id)
            return False

        # 过滤开关关闭
        if not chat_config.enable_chat_list_filter:
            return True

        # 群聊过滤
        if group_id:
            allowed = self._is_allowed(group_id, chat_config.group_list_type, chat_config.group_list)
            if not allowed:
                if chat_config.show_dropped_chat_list_messages:
                    self._logger.debug("群聊消息未通过过滤: group=%s", group_id)
                return False
            return True

        # 私聊过滤
        allowed = self._is_allowed(sender_user_id, chat_config.private_list_type, chat_config.private_list)
        if not allowed:
            if chat_config.show_dropped_chat_list_messages:
                self._logger.debug("私聊消息未通过过滤: user=%s", sender_user_id)
            return False
        return True

    @staticmethod
    def _is_allowed(target: str, list_type: str, items: Collection[str]) -> bool:
        """检查目标是否被允许。

        Args:
            target: 目标 ID。
            list_type: ``"whitelist"`` 或 ``"blacklist"``。
            items: 配置的 ID 列表。

        Returns:
            bool: 若允许则返回 ``True``。
        """
        if list_type == "whitelist":
            return target in items
        return target not in items
