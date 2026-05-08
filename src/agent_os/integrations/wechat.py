"""WeChat Integration Module - Stage 4 Implementation.

Receives and processes WeChat messages, creates Resource items.
Also provides functionality to send messages back to WeChat users.
"""

import hashlib
import logging
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.items.crud import create_item
from agent_os.items.schema import ItemCreate

logger = logging.getLogger(__name__)


# ============================================================================
# WeChat Webhook Receiver
# ============================================================================

class WeChatWebhookReceiver:
    """
    微信 Webhook 接收器

    处理来自微信服务器的消息推送
    """

    def __init__(self, token: str | None = None):
        """
        初始化 Webhook 接收器

        Args:
            token: 微信公众平台配置的Token (用于签名验证)
        """
        self.token = token

    def verify_signature(
        self,
        signature: str,
        timestamp: str,
        nonce: str
    ) -> bool:
        """
        验证微信签名

        Args:
            signature: 微信签名
            timestamp: 时间戳
            nonce: 随机数

        Returns:
            验证是否成功
        """
        if not self.token:
            # 开发环境可能不需要验证
            logger.warning("No token configured, skipping signature verification")
            return True

        # 按微信文档排序: token, timestamp, nonce
        tmp_list = [self.token, timestamp, nonce]
        tmp_list.sort()

        # 拼接字符串
        tmp_str = "".join(tmp_list)

        # SHA1 加密
        hash_str = hashlib.sha1(tmp_str.encode('utf-8')).hexdigest()

        # 对比签名
        return hash_str == signature

    def parse_xml_message(self, xml_data: str) -> dict[str, Any]:
        """
        解析微信 XML 消息

        Args:
            xml_data: XML 字符串

        Returns:
            解析后的消息字典
        """
        try:
            root = ET.fromstring(xml_data)

            # 提取消息类型
            msg_type = root.find('MsgType')
            if msg_type is None:
                raise ValueError("MsgType not found in XML")

            # 根据消息类型解析
            if msg_type.text == 'text':
                return self._parse_text_message(root)
            elif msg_type.text == 'image':
                return self._parse_image_message(root)
            elif msg_type.text == 'link':
                return self._parse_link_message(root)
            else:
                return {
                    'type': msg_type.text,
                    'raw': xml_data
                }

        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing WeChat message: {e}")
            raise

    def _parse_text_message(self, root: ET.Element) -> dict[str, Any]:
        """解析文本消息"""
        to_user = root.find('ToUserName').text
        from_user = root.find('FromUserName').text
        create_time = root.find('CreateTime').text
        msg_id = root.find('MsgId').text
        content = root.find('Content').text

        return {
            'type': 'text',
            'to_user': to_user,
            'from_user': from_user,
            'create_time': create_time,
            'msg_id': msg_id,
            'content': content,
            'raw': None
        }

    def _parse_image_message(self, root: ET.Element) -> dict[str, Any]:
        """解析图片消息"""
        to_user = root.find('ToUserName').text
        from_user = root.find('FromUserName').text
        create_time = root.find('CreateTime').text
        msg_id = root.find('MsgId').text
        pic_url = root.find('PicUrl').text
        media_id = root.find('MediaId').text

        return {
            'type': 'image',
            'to_user': to_user,
            'from_user': from_user,
            'create_time': create_time,
            'msg_id': msg_id,
            'pic_url': pic_url,
            'media_id': media_id,
            'raw': None
        }

    def _parse_link_message(self, root: ET.Element) -> dict[str, Any]:
        """解析链接消息"""
        to_user = root.find('ToUserName').text
        from_user = root.find('FromUserName').text
        create_time = root.find('CreateTime').text
        msg_id = root.find('MsgId').text
        title = root.find('Title').text
        description = root.find('Description').text
        url = root.find('Url').text

        return {
            'type': 'link',
            'to_user': to_user,
            'from_user': from_user,
            'create_time': create_time,
            'msg_id': msg_id,
            'title': title,
            'description': description,
            'url': url,
            'raw': None
        }

    async def process_message(
        self,
        db: AsyncSession,
        message: dict[str, Any],
        workspace_id: str,
        creator_id: str,
        default_area_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        处理微信消息，创建 Resource Item

        Args:
            db: 数据库会话
            message: 解析后的消息字典
            workspace_id: 工作空间ID
            creator_id: 创建者ID
            default_area_id: 默认区域ID

        Returns:
            创建的Item信息
        """
        try:
            msg_type = message.get('type')

            if msg_type == 'text':
                return await self._process_text_message(
                    db, message, workspace_id, creator_id, default_area_id
                )
            elif msg_type == 'link':
                return await self._process_link_message(
                    db, message, workspace_id, creator_id, default_area_id
                )
            elif msg_type == 'image':
                return await self._process_image_message(
                    db, message, workspace_id, creator_id, default_area_id
                )
            else:
                logger.warning(f"Unsupported message type: {msg_type}")
                return None

        except Exception as e:
            logger.error(f"Error processing WeChat message: {e}")
            return None

    async def _process_text_message(
        self,
        db: AsyncSession,
        message: dict[str, Any],
        workspace_id: str,
        creator_id: str,
        default_area_id: str | None
    ) -> dict[str, Any]:
        """处理文本消息"""
        content = message.get('content', '').strip()

        if not content:
            return None

        # 创建 Item
        item_data = ItemCreate(
            workspace_id=uuid.UUID(workspace_id),
            creator_id=uuid.UUID(creator_id),
            type="resource",
            title=content[:100],  # 标题取前100字符
            content=content,
            source_type="wechat",
            source_meta={
                "msg_type": "text",
                "from_user": message.get('from_user'),
                "msg_id": message.get('msg_id'),
                "create_time": message.get('create_time')
            }
        )

        if default_area_id:
            item_data.area_id = uuid.UUID(default_area_id)

        item = await create_item(db, item_data)

        return {
            "item_id": str(item.id),
            "type": "text",
            "status": "created"
        }

    async def _process_link_message(
        self,
        db: AsyncSession,
        message: dict[str, Any],
        workspace_id: str,
        creator_id: str,
        default_area_id: str | None
    ) -> dict[str, Any]:
        """处理链接消息"""
        url = message.get('url', '').strip()
        title = message.get('title', '').strip()
        description = message.get('description', '').strip()

        if not url:
            return None

        # 组合内容
        content = f"Title: {title}\n\nDescription: {description}\n\nURL: {url}"

        # 创建 Item
        item_data = ItemCreate(
            workspace_id=uuid.UUID(workspace_id),
            creator_id=uuid.UUID(creator_id),
            type="resource",
            title=title or url[:100],
            content=content,
            source_type="wechat",
            source_meta={
                "msg_type": "link",
                "from_user": message.get('from_user'),
                "msg_id": message.get('msg_id'),
                "url": url,
                "create_time": message.get('create_time')
            }
        )

        if default_area_id:
            item_data.area_id = uuid.UUID(default_area_id)

        item = await create_item(db, item_data)

        return {
            "item_id": str(item.id),
            "type": "link",
            "url": url,
            "status": "created"
        }

    async def _process_image_message(
        self,
        db: AsyncSession,
        message: dict[str, Any],
        workspace_id: str,
        creator_id: str,
        default_area_id: str | None
    ) -> dict[str, Any]:
        """处理图片消息"""
        pic_url = message.get('pic_url', '').strip()
        media_id = message.get('media_id', '').strip()

        content = f"[图片] Media ID: {media_id}"
        if pic_url:
            content += f"\n图片URL: {pic_url}"

        # 创建 Item
        item_data = ItemCreate(
            workspace_id=uuid.UUID(workspace_id),
            creator_id=uuid.UUID(creator_id),
            type="resource",
            title=f"[图片] {media_id}",
            content=content,
            source_type="wechat",
            source_meta={
                "msg_type": "image",
                "from_user": message.get('from_user'),
                "msg_id": message.get('msg_id'),
                "pic_url": pic_url,
                "media_id": media_id,
                "create_time": message.get('create_time')
            }
        )

        if default_area_id:
            item_data.area_id = uuid.UUID(default_area_id)

        item = await create_item(db, item_data)

        return {
            "item_id": str(item.id),
            "type": "image",
            "media_id": media_id,
            "status": "created"
        }


# ============================================================================
# Link Extractor
# ============================================================================

class LinkExtractor:
    """
    链接提取器 - 从文本中提取URL

    支持多种URL格式:
    - HTTP/HTTPS URLs
    - 带查询参数的URLs
    - 带锚点的URLs
    - 纯文本URLs
    """

    # URL 正则表达式
    URL_PATTERN = r'https?://\S+'

    def extract_urls(self, text: str) -> list[str]:
        """
        从文本中提取所有URL

        Args:
            text: 输入文本

        Returns:
            URL列表
        """
        import re

        if not text:
            return []

        # 查找所有URL
        urls = re.findall(self.URL_PATTERN, text, re.IGNORECASE)

        # 清理URL - 移除末尾的标点符号
        cleaned_urls = []
        for url in urls:
            # 移除末尾的标点符号
            while url and url[-1] in '.,，。！!??:;；：':
                url = url[:-1]
            if url:
                cleaned_urls.append(url)

        # 去重
        unique_urls = list(set(cleaned_urls))

        logger.info(f"Extracted {len(unique_urls)} URLs from text")

        return unique_urls

    def extract_first_url(self, text: str) -> str | None:
        """
        从文本中提取第一个URL

        Args:
            text: 输入文本

        Returns:
            第一个URL，如果没有则返回None
        """
        urls = self.extract_urls(text)
        return urls[0] if urls else None


# ============================================================================
# 便捷函数
# ============================================================================

async def process_wechat_message(
    xml_data: str,
    db: AsyncSession,
    *,
    workspace_id: str,
    creator_id: str,
    webhook_token: str | None = None,
    default_area_id: str | None = None
) -> dict[str, Any] | None:
    """
    处理微信消息的完整流程

    Args:
        xml_data: 微信XML数据
        db: 数据库会话
        workspace_id: 工作空间ID
        creator_id: 创建者ID
        webhook_token: Webhook Token (用于验证)
        default_area_id: 默认区域ID

    Returns:
        处理结果
    """
    receiver = WeChatWebhookReceiver(token=webhook_token)

    # 解析消息
    try:
        message = receiver.parse_xml_message(xml_data)
    except Exception as e:
        logger.error(f"Failed to parse WeChat XML: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

    # 处理消息
    try:
        result = await receiver.process_message(
            db, message, workspace_id, creator_id, default_area_id
        )
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Failed to process WeChat message: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# WeChat Message Sender
# ============================================================================

class WeChatMessageSender:
    """
    微信消息发送器

    发送文本、图片等消息给微信用户
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        access_token: str | None = None
    ):
        """
        初始化消息发送器

        Args:
            app_id: 微信公众平台 AppID
            app_secret: 微信公众平台 AppSecret
            access_token: 访问令牌 (可选，如果不提供会自动获取)
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = access_token
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def get_access_token(self) -> str:
        """
        获取访问令牌

        Returns:
            access_token 字符串
        """
        if self.access_token:
            return self.access_token

        # 从微信服务器获取 access_token
        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret
        }

        response = await self._http_client.get(url, params=params)
        data = await response.json()

        if data.get('errcode', 0) != 0:
            raise Exception(f"Failed to get access_token: {data.get('errmsg')}")

        access_token = data.get('access_token')
        self.access_token = access_token

        logger.info("Successfully obtained WeChat access token")
        return access_token

    async def send_text_message(
        self,
        openid: str,
        content: str
    ) -> dict[str, Any]:
        """
        发送文本消息

        Args:
            openid: 用户OpenID
            content: 文本内容

        Returns:
            发送结果
        """
        token = await self.get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"

        data = {
            "touser": openid,
            "msgtype": "text",
            "text": {
                "content": content
            }
        }

        response = await self._http_client.post(url, json=data)
        result = await response.json()

        if result.get('errcode') == 0:
            logger.info(f"Text message sent successfully to {openid}")
            return {"status": "success", "msgid": result.get('msgid')}
        else:
            logger.error(f"Failed to send text message: {result.get('errmsg')}")
            return {"status": "error", "error": result.get('errmsg')}

    async def send_news_message(
        self,
        openid: str,
        articles: list[dict[str, str]]
    ) -> dict[str, Any]:
        """
        发送图文消息

        Args:
            openid: 用户OpenID
            articles: 图文文章列表，每篇包含 title, description, url, picurl

        Returns:
            发送结果
        """
        token = await self.get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"

        # 确保不超过8篇文章
        articles = articles[:8]

        data = {
            "touser": openid,
            "msgtype": "news",
            "news": {
                "articles": articles
            }
        }

        response = await self._http_client.post(url, json=data)
        result = await response.json()

        if result.get('errcode') == 0:
            logger.info(f"News message sent successfully to {openid}")
            return {"status": "success"}
        else:
            logger.error(f"Failed to send news message: {result.get('errmsg')}")
            return {"status": "error", "error": result.get('errmsg')}

    async def send_card_message(
        self,
        openid: str,
        title: str,
        description: str,
        url: str,
        image_url: str | None = None
    ) -> dict[str, Any]:
        """
        发送卡片消息（单图文）

        Args:
            openid: 用户OpenID
            title: 标题
            description: 描述
            url: 点击跳转URL
            image_url: 图片URL（可选）

        Returns:
            发送结果
        """
        article = {
            "title": title,
            "description": description,
            "url": url,
        }

        if image_url:
            article["picurl"] = image_url

        return await self.send_news_message(openid, [article])

    async def close(self):
        """关闭HTTP客户端"""
        await self._http_client.aclose()


# ============================================================================
# WeChat Service - 高层服务类
# ============================================================================

class WeChatService:
    """
    微信集成服务 - 高层接口

    集成接收和发送功能，提供完整的微信集成
    """

    def __init__(
        self,
        webhook_token: str | None = None,
        app_id: str | None = None,
        app_secret: str | None = None
    ):
        """
        初始化微信服务

        Args:
            webhook_token: Webhook验证Token (接收消息)
            app_id: 微信公众号AppID (发送消息)
            app_secret: 微信公众号AppSecret (发送消息)
        """
        self.webhook_token = webhook_token
        self.app_id = app_id
        self.app_secret = app_secret

        self.receiver = WeChatWebhookReceiver(token=webhook_token)
        self.sender = None

    async def get_sender(self) -> WeChatMessageSender:
        """
        获取消息发送器实例（延迟初始化）

        Returns:
            WeChatMessageSender实例
        """
        if self.sender is None:
            if not self.app_id or not self.app_secret:
                raise ValueError("app_id and app_secret are required for sending messages")

            self.sender = WeChatMessageSender(
                app_id=self.app_id,
                app_secret=self.app_secret
            )

        return self.sender

    async def handle_webhook(
        self,
        xml_data: str,
        signature: str | None = None,
        timestamp: str | None = None,
        nonce: str | None = None,
        db: AsyncSession | None = None,
        workspace_id: str | None = None,
        creator_id: str | None = None,
        default_area_id: str | None = None
    ) -> dict[str, Any]:
        """
        处理Webhook请求

        Args:
            xml_data: 微信XML数据
            signature: 签名
            timestamp: 时间戳
            nonce: 随机数
            db: 数据库会话
            workspace_id: 工作空间ID
            creator_id: 创建者ID
            default_area_id: 默认区域ID

        Returns:
            处理结果
        """
        # 验证签名
        if signature and timestamp and nonce:
            if not self.receiver.verify_signature(signature, timestamp, nonce):
                return {
                    "status": "error",
                    "error": "Invalid signature"
                }

        # 解析消息
        try:
            message = self.receiver.parse_xml_message(xml_data)
        except Exception as e:
            logger.error(f"Failed to parse WeChat XML: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

        # 如果提供了数据库，处理消息
        if db and workspace_id and creator_id:
            try:
                result = await self.receiver.process_message(
                    db, message, workspace_id, creator_id, default_area_id
                )
                return {
                    "status": "success",
                    "message": "WeChat message processed successfully",
                    "result": result
                }
            except Exception as e:
                logger.error(f"Failed to process WeChat message: {e}")
                return {
                    "status": "error",
                    "error": str(e)
                }
        else:
            return {
                "status": "success",
                "message": "WeChat message parsed (no database processing)",
                "parsed_message": message
            }

    async def send_message_to_user(
        self,
        openid: str,
        message_type: str,
        **kwargs
    ) -> dict[str, Any]:
        """
        发送消息给微信用户

        Args:
            openid: 用户OpenID
            message_type: 消息类型 ('text', 'news', 'card')
            **kwargs: 消息类型特定的参数

        Returns:
            发送结果
        """
        sender = await self.get_sender()

        if message_type == 'text':
            content = kwargs.get('content', '')
            return await sender.send_text_message(openid, content)

        elif message_type == 'card':
            title = kwargs.get('title', '')
            description = kwargs.get('description', '')
            url = kwargs.get('url', '')
            image_url = kwargs.get('image_url')
            return await sender.send_card_message(openid, title, description, url, image_url)

        elif message_type == 'news':
            articles = kwargs.get('articles', [])
            return await sender.send_news_message(openid, articles)

        else:
            return {
                "status": "error",
                "error": f"Unsupported message type: {message_type}"
            }

    async def close(self):
        """关闭服务"""
        if self.sender:
            await self.sender.close()
