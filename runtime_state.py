"""QQ Bot 网关运行时状态管理。

通过 ``self.ctx.gateway.update_state`` 向 Host 上报连接状态，
使 PlatformIO 可以绑定发送路由和接收路由。
"""

from __future__ import annotations

from typing import Any, Optional

from .config import QQBotConnectionConfig


class QQBotRuntimeStateManager:
    """管理 QQ Bot 网关的运行时连接状态。

    在 WSS 连接建立后调用 ``report_connected`` 通告 Host 可以下发消息。
    在 WSS 断开后调用 ``report_disconnected`` 通告 Host 停止下发消息。
    包含幂等性保护：相同 account_id + scope 不重复上报。
    """

    def __init__(self, gateway_capability: Any, logger: Any, gateway_name: str) -> None:
        """初始化状态管理器。

        Args:
            gateway_capability: ``self.ctx.gateway`` 对象。
            logger: 插件日志对象。
            gateway_name: 网关名 (如 ``"qqbot_gateway"``)。
        """
        self._gateway = gateway_capability
        self._logger = logger
        self._name = gateway_name
        self._connected: bool = False
        self._account_id: Optional[str] = None
        self._scope: Optional[str] = None

    async def report_connected(self, account_id: str, config: QQBotConnectionConfig) -> bool:
        """报告网关已连接。

        Args:
            account_id: Bot App ID，用作路由 account。
            config: 连接配置。

        Returns:
            bool: 若 Host 接受了状态更新则返回 ``True``。
        """
        normalized = str(account_id).strip()
        if not normalized:
            self._logger.warning("report_connected 被调用但 account_id 为空")
            return False

        scope = config.connection_id or None

        # 幂等性保护
        if self._connected and self._account_id == normalized and self._scope == scope:
            return True

        try:
            await self._gateway.update_state(
                gateway_name=self._name,
                ready=True,
                platform="qq",
                account_id=normalized,
                scope=config.connection_id,
                metadata={"app_id": config.app_id, "sandbox": config.use_sandbox},
            )
        except Exception as exc:
            self._logger.error("上报网关已连接失败: %s", exc)
            return False

        self._connected = True
        self._account_id = normalized
        self._scope = scope
        self._logger.info("QQ Bot 网关已就绪: account_id=%s", normalized)
        return True

    async def report_disconnected(self) -> None:
        """报告网关已断开。"""
        if not self._connected:
            return

        try:
            await self._gateway.update_state(
                gateway_name=self._name,
                ready=False,
                platform="qq",
            )
        except Exception as exc:
            self._logger.error("上报网关已断开失败: %s", exc)

        self._connected = False
        self._account_id = None
        self._scope = None
        self._logger.info("QQ Bot 网关已断开")
