"""
QQ Bot 被动回复上下文缓存

QQ 官方 Bot 出站消息必须携带最近收到的用户消息 msg_id 才算「被动回复」；
否则被服务端判定为「主动消息」，普通机器人无权限（错误码 40034105）。

自发消息（如表情包、无引用的回复）不带 reply 段，出站时需回落到本缓存记录的
最近 msg_id，才能成功发送。

QQ 规则补充：同一个 msg_id 最多可回复 5 次，且每次 msg_seq 必须递增，否则会被
判定为重复消息。本缓存按会话追踪 msg_id 与已用 seq。

Made BY Galeros

"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple


class QQBotPassiveContext:
    """维护每个会话最近一条用户消息的 msg_id，用于被动回复回落。"""

    # QQ 被动回复窗口（秒）：私聊 60 分钟、群聊 5 分钟。留少量余量。
    _C2C_WINDOW_SEC = 3500.0
    _GROUP_WINDOW_SEC = 290.0
    # 单条 msg_id 最多回复次数（msg_seq 取值 1..5）。
    _MAX_REPLIES = 5

    def __init__(self) -> None:
        # conversation_key → [msg_id, 到期时间戳, 已用 seq]
        self._store: Dict[str, List] = {}

    def record(self, conversation_key: str, msg_id: str, is_group: bool) -> None:
        """记录会话最近一条用户消息 msg_id（覆盖旧值并重置 seq）。

        Args:
            conversation_key: 会话键（群聊用 group_openid，私聊用 user_openid）。
            msg_id: 用户消息 ID。
            is_group: 是否群聊，决定被动窗口时长。
        """
        if not conversation_key or not msg_id:
            return
        window = self._GROUP_WINDOW_SEC if is_group else self._C2C_WINDOW_SEC
        self._store[conversation_key] = [msg_id, time.time() + window, 0]

    def acquire(
        self, conversation_key: str, prefer_msg_id: str = "", is_group: bool = False,
    ) -> Tuple[Optional[str], int]:
        """取出一个可用的被动回复 (msg_id, msg_seq)。

        优先使用显式引用的 prefer_msg_id；否则回落到会话缓存的最近 msg_id。
        每次调用递增 msg_seq，超过上限或过期则失效。

        Args:
            conversation_key: 会话键。
            prefer_msg_id: 出站消息显式引用的 msg_id（reply 段），可为空。
            is_group: 是否群聊。

        Returns:
            Tuple[Optional[str], int]: (msg_id, msg_seq)。无可用被动目标时返回 (None, 0)。
        """
        now = time.time()
        entry = self._store.get(conversation_key)

        # 显式引用优先：与缓存不同则以引用目标重建计数窗口。
        if prefer_msg_id and (entry is None or entry[0] != prefer_msg_id):
            window = self._GROUP_WINDOW_SEC if is_group else self._C2C_WINDOW_SEC
            entry = [prefer_msg_id, now + window, 0]
            self._store[conversation_key] = entry

        if entry is None:
            return None, 0

        msg_id, expire_at, used = entry
        if now >= expire_at or used >= self._MAX_REPLIES:
            self._store.pop(conversation_key, None)
            # 显式引用即便过期也交给服务端判定，回落场景则放弃。
            return (prefer_msg_id, 1) if prefer_msg_id else (None, 0)

        used += 1
        entry[2] = used
        return msg_id, used

    def clear(self) -> None:
        """清空缓存（WSS 断开时调用）。"""
        self._store.clear()
