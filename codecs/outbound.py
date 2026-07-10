"""QQ Bot 出站消息编解码。

将 Host 侧 ``MessageDict`` 转换为 QQ Bot REST API 动作参数。

当前消息段转换规则：
- ``text`` → msg_type=0, content=纯文本
- ``image`` → 先上传再 msg_type=7 (media)
- ``at`` → 转为 ``@名称`` 文本
- ``reply`` → 提取 msg_id，同时写入 ``[reply]`` 文本标记
- ``voice`` → 写入 ``[语音]`` 文本标记
- ``forward`` → 转为文本提示
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from ..constants import FILE_TYPE_IMAGE, MSG_TYPE_TEXT


class QQBotOutboundCodec:
    """QQ Bot 出站消息编解码器。

    从 MessageDict 提取出站参数，由 plugin.py 调用 transport REST 方法发送。
    """

    # action_name 常量
    ACTION_POST_C2C = "post_c2c_message"
    ACTION_POST_GROUP = "post_group_message"
    ACTION_UPLOAD_AND_SEND_C2C = "upload_media_and_send_c2c"
    ACTION_UPLOAD_AND_SEND_GROUP = "upload_media_and_send_group"

    def build_outbound_action(
        self, message: Mapping[str, Any], route: Mapping[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """从 MessageDict 构造 QQ Bot API 动作。

        Args:
            message: Host 侧标准 MessageDict。
            route: Platform IO 路由信息。

        Returns:
            Tuple[str, Dict[str, Any]]: (action_name, params) 动作名称与参数字典。

        Raises:
            ValueError: 当缺少目标 ID（群或用户）时抛出。
        """
        message_info = message.get("message_info", {})
        if not isinstance(message_info, dict):
            message_info = {}

        group_info = message_info.get("group_info", {})
        if not isinstance(group_info, dict):
            group_info = {}

        additional_config = message_info.get("additional_config", {})
        if not isinstance(additional_config, dict):
            additional_config = {}

        raw_message = message.get("raw_message", [])
        if not isinstance(raw_message, list):
            raw_message = []

        # 确定目标
        target_group_id = str(
            group_info.get("group_id")
            or additional_config.get("platform_io_target_group_id")
            or ""
        ).strip()

        target_user_id = str(
            additional_config.get("platform_io_target_user_id")
            or route.get("target_user_id")
            or ""
        ).strip()

        # 提取回复 msg_id
        reply_msg_id = self._extract_reply_msg_id(raw_message)

        # 分离文本和媒体
        text_content, media_segments = self._separate_segments(raw_message)

        # 构造参数
        if media_segments:
            # 含媒体 → 上传后发送
            media = media_segments[0]  # QQ Bot 单条仅支持一个媒体
            if target_group_id:
                return self.ACTION_UPLOAD_AND_SEND_GROUP, {
                    "group_openid": target_group_id,
                    "content": text_content,
                    "msg_id": reply_msg_id,
                    "media": media,
                }
            if target_user_id:
                return self.ACTION_UPLOAD_AND_SEND_C2C, {
                    "openid": target_user_id,
                    "content": text_content,
                    "msg_id": reply_msg_id,
                    "media": media,
                }
            raise ValueError("出站媒体消息缺少目标 ID")

        # 纯文本
        if target_group_id:
            return self.ACTION_POST_GROUP, {
                "group_openid": target_group_id,
                "content": text_content,
                "msg_type": MSG_TYPE_TEXT,
                "msg_id": reply_msg_id,
            }
        if target_user_id:
            return self.ACTION_POST_C2C, {
                "openid": target_user_id,
                "content": text_content,
                "msg_type": MSG_TYPE_TEXT,
                "msg_id": reply_msg_id,
            }
        raise ValueError("出站消息缺少目标 ID")

    # -- 段分离 --

    def _separate_segments(
        self, raw_message: List[Dict[str, Any]],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """分离文本内容和媒体段。

        规则:
        - ``text`` → 拼入 text_content
        - ``image`` → 加入 media list（base64 + content_type）
        - ``at`` → 转为 ``@名称`` 文本
        - ``reply``、``forward`` → 转为文本标记
        - ``voice``、``file`` → 转为文本标记

        Args:
            raw_message: Host 消息段列表。

        Returns:
            Tuple[str, List[Dict[str, Any]]]: (纯文本, 媒体参数列表)。
        """
        text_parts: List[str] = []
        media_list: List[Dict[str, Any]] = []

        for item in raw_message:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").strip()
            item_data = item.get("data", "")

            if item_type == "text":
                text_parts.append(str(item_data or ""))

            elif item_type == "image":
                binary_b64 = str(item.get("binary_data_base64") or "").strip()
                content_type = str(item.get("mime_type") or "image/png").strip()
                if binary_b64:
                    media_list.append(
                        {
                            "type": "image",
                            "data_base64": binary_b64,
                            "content_type": content_type,
                            "file_type": FILE_TYPE_IMAGE,
                        }
                    )

            elif item_type == "at":
                # 将 @ 段转换为普通文本。
                if isinstance(item_data, dict):
                    name = str(item_data.get("target_user_nickname") or item_data.get("target_user_id") or "")
                    if name:
                        text_parts.append(f"@{name}")

            elif item_type in ("reply", "forward"):
                # reply 的 msg_id 由 _extract_reply_msg_id 提取；两个段均保留文本标记。
                text_parts.append(f"[{item_type}]")

            elif item_type == "voice":
                # 当前实现将语音段转换为文本标记。
                text_parts.append("[语音]")

            elif item_type == "file":
                text_parts.append("[文件]")

        text_content = "".join(text_parts).strip()

        return text_content, media_list

    @staticmethod
    def _extract_reply_msg_id(raw_message: List[Dict[str, Any]]) -> str:
        """提取回复引用的目标消息 ID。

        QQ Bot API 通过 ``msg_id`` 参数实现引用回复，而不是独立的 reply 段。

        Args:
            raw_message: Host 消息段列表。

        Returns:
            str: 被回复消息的 ID，无回复时为空字符串。
        """
        for item in raw_message:
            if isinstance(item, dict) and item.get("type") == "reply":
                data = item.get("data", {})
                if isinstance(data, dict):
                    target_id = str(data.get("target_message_id") or "").strip()
                    if target_id:
                        return target_id
        return ""
