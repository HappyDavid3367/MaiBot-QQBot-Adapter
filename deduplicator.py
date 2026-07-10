"""QQ Bot 消息去重器。

策略:
1. 以 ``msg_id`` 为主键。若 msg_id 已见过，直接丢弃。
2. ``msg_seq`` 用于辅助判断: 若 msg_seq <= 同会话已记录的最大 seq，判定为重放。
3. 使用 TTL 驱逐过期条目，防止内存泄漏。
"""

from __future__ import annotations

import time
from typing import Dict


class QQBotMessageDeduplicator:
    """QQ Bot 消息去重器。

    双层去重:
    - msg_id 主键去重 (TTL 300 秒)
    - msg_seq 序列号检查 (按会话追踪最大 seq)
    """

    def __init__(self, ttl_sec: float = 300, max_size: int = 10000) -> None:
        """初始化去重器。

        Args:
            ttl_sec: 去重窗口（秒），过期条目自动驱逐。
            max_size: 最大缓存条目数，超出时驱逐最旧条目。
        """
        self._ttl_sec = ttl_sec
        self._max_size = max_size
        self._seen: Dict[str, float] = {}       # msg_id → 过期时间戳
        self._seq_tracker: Dict[str, int] = {}  # session_key → 最大 msg_seq

    def is_duplicate(self, msg_id: str, session_key: str, msg_seq: int | None) -> bool:
        """检查消息是否重复。

        Args:
            msg_id: QQ Bot 消息 ID。
            session_key: 会话键 (如 ``"c2c_{openid}"`` 或 ``"group_{group_openid}"``)。
            msg_seq: 消息序号，可能为 ``None``（旧版事件或未知）。

        Returns:
            bool: 若为重复消息则返回 ``True``。
        """
        now = time.monotonic()
        self._evict_expired(now)

        # 主键去重
        if msg_id and msg_id in self._seen:
            return True

        # seq 去重: 若 seq 存在且 <= 历史最大 seq，判定为重放
        if msg_seq is not None and session_key:
            last_seq = self._seq_tracker.get(session_key, -1)
            if msg_seq <= last_seq:
                return True

        # 记录
        if msg_id:
            self._seen[msg_id] = now + self._ttl_sec
        if msg_seq is not None and session_key:
            if msg_seq > self._seq_tracker.get(session_key, -1):
                self._seq_tracker[session_key] = msg_seq

        return False

    def _evict_expired(self, now: float) -> None:
        """驱逐过期条目。"""
        expired = [k for k, v in self._seen.items() if v < now]
        for k in expired:
            del self._seen[k]

        # 若超出容量，清理最旧条目
        if len(self._seen) > self._max_size:
            sorted_entries = sorted(self._seen.items(), key=lambda x: x[1])
            for k, _ in sorted_entries[: len(sorted_entries) - self._max_size]:
                del self._seen[k]

    def clear(self) -> None:
        """清空所有去重缓存。WSS 断开时调用。"""
        self._seen.clear()
        self._seq_tracker.clear()
