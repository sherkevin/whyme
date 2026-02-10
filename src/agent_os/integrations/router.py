"""Integrations API Router - WeChat Webhook and Crawler Endpoints."""

import uuid
import logging
import os
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from agent_os.integrations.wechat import WeChatWebhookReceiver, process_wechat_message, WeChatService
from agent_os.integrations.crawler import WebCrawler, crawl_url, LinkExtractor
from agent_os.integrations.schema import (
    WebhookVerifyRequest,
    ProcessWeChatMessageRequest,
    ProcessWeChatMessageResponse,
    WebhookHealthResponse,
    CrawlURLRequest,
    CrawlURLResponse,
    ExtractLinksRequest,
    ExtractLinksResponse,
    CreateResourceFromURL,
    SendTextMessageRequest,
    SendNewsMessageRequest,
    SendCardMessageRequest,
    SendMessageResponse
)
from agent_os.items.crud import create_item, create_workspace
from agent_os.items.schema import ItemCreate, WorkspaceCreate
from agent_os.db.base import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ============================================================================
# WeChat Webhook Endpoints
# ============================================================================

@router.get("/wechat/webhook", response_class=PlainTextResponse)
async def wechat_webhook_verify(request: Request):
    """
    微信 Webhook 验证端点 (GET)

    用于微信服务器验证 Webhook URL

    Args:
        request: FastAPI Request

    Returns:
        PlainTextResponse: 验证返回的 echostr
    """
    try:
        # 获取验证参数
        signature = request.query_params.get("signature", "")
        timestamp = request.query_params.get("timestamp", "")
        nonce = request.query_params.get("nonce", "")
        echostr = request.query_params.get("echostr", "")

        logger.info(f"WeChat webhook verification request: signature={signature}, timestamp={timestamp}")

        # 验证签名
        # TODO: 从环境变量或配置文件读取 token
        token = "your_token_here"  # 替换为实际 token

        receiver = WeChatWebhookReceiver(token=token)

        if receiver.verify_signature(signature, timestamp, nonce):
            logger.info("WeChat webhook verification successful")
            return PlainTextResponse(content=echostr)
        else:
            logger.warning("WeChat webhook verification failed")
            raise HTTPException(status_code=403, detail="Invalid signature")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in WeChat webhook verification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wechat/webhook", response_model=ProcessWeChatMessageResponse)
async def wechat_webhook_receive(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    微信 Webhook 消息接收端点 (POST)

    接收来自微信服务器的消息推送

    Args:
        request: FastAPI Request
        db: 数据库会话

    Returns:
        ProcessWeChatMessageResponse: 处理结果
    """
    try:
        # 读取 XML 数据
        xml_data = await request.body()

        if not xml_data:
            raise HTTPException(status_code=400, detail="Empty XML data")

        xml_str = xml_data.decode('utf-8')
        logger.info(f"Received WeChat message: {len(xml_str)} bytes")

        # TODO: 从请求头或配置获取 workspace_id 和 creator_id
        # 这里使用临时值，生产环境应该从认证信息中获取
        workspace_id = "default-workspace-id"
        creator_id = "system-user-id"

        # 检查 workspace 是否存在，不存在则创建
        try:
            workspace_uuid = uuid.UUID(workspace_id)
        except ValueError:
            # 创建临时 workspace
            workspace = await create_workspace(db, WorkspaceCreate(
                name="WeChat Integration Workspace",
                owner_id=uuid.uuid4()
            ))
            workspace_uuid = workspace.id

        # 处理消息
        result = await process_wechat_message(
            xml_data=xml_str,
            db=db,
            workspace_id=str(workspace_uuid),
            creator_id=creator_id,
            webhook_token=None,  # 验证已经在GET端点完成
            default_area_id=None
        )

        return ProcessWeChatMessageResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing WeChat webhook: {e}")
        return ProcessWeChatMessageResponse(
            status="error",
            error=str(e)
        )


@router.post("/wechat/process", response_model=ProcessWeChatMessageResponse)
async def process_wechat_message_endpoint(
    request_data: ProcessWeChatMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    手动处理微信消息端点

    用于测试或手动触发消息处理

    Args:
        request_data: 处理请求
        db: 数据库会话

    Returns:
        ProcessWeChatMessageResponse: 处理结果
    """
    try:
        # 验证 workspace_id 和 creator_id 格式
        try:
            workspace_uuid = uuid.UUID(request_data.workspace_id)
            creator_uuid = uuid.UUID(request_data.creator_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid UUID format: {e}")

        # 处理消息
        result = await process_wechat_message(
            xml_data=request_data.xml_data,
            db=db,
            workspace_id=request_data.workspace_id,
            creator_id=request_data.creator_id,
            webhook_token=None,
            default_area_id=request_data.default_area_id
        )

        return ProcessWeChatMessageResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing WeChat message: {e}")
        return ProcessWeChatMessageResponse(
            status="error",
            error=str(e)
        )


@router.get("/wechat/health", response_model=WebhookHealthResponse)
async def wechat_webhook_health():
    """
    微信 Webhook 健康检查

    Returns:
        WebhookHealthResponse: 健康状态
    """
    return WebhookHealthResponse(
        status="healthy",
        service="wechat-webhook"
    )


# ============================================================================
# WeChat Send Message Endpoints
# ============================================================================

# Global WeChat service instance for sending messages
_wechat_service: Optional[WeChatService] = None


def get_wechat_service() -> WeChatService:
    """获取或创建 WeChatService 实例"""
    global _wechat_service
    if _wechat_service is None:
        # 从环境变量获取微信应用凭证
        app_id = os.getenv("WECHAT_APP_ID")
        app_secret = os.getenv("WECHAT_APP_SECRET")
        webhook_token = os.getenv("WECHAT_WEBHOOK_TOKEN")

        _wechat_service = WeChatService(
            webhook_token=webhook_token,
            app_id=app_id,
            app_secret=app_secret
        )
    return _wechat_service


@router.post("/wechat/send/text", response_model=SendMessageResponse)
async def send_text_message(request_data: SendTextMessageRequest):
    """
    发送文本消息到微信

    Args:
        request_data: 发送请求

    Returns:
        SendMessageResponse: 发送结果
    """
    try:
        service = get_wechat_service()

        result = await service.send_message_to_user(
            openid=request_data.openid,
            message_type="text",
            content=request_data.content
        )

        if result.get("errcode") == 0:
            return SendMessageResponse(
                status="success",
                errcode=0,
                errmsg="ok",
                msgid=result.get("msgid")
            )
        else:
            return SendMessageResponse(
                status="error",
                errcode=result.get("errcode"),
                errmsg=result.get("errmsg", "Unknown error")
            )

    except Exception as e:
        logger.error(f"Error sending text message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wechat/send/news", response_model=SendMessageResponse)
async def send_news_message(request_data: SendNewsMessageRequest):
    """
    发送图文消息到微信

    Args:
        request_data: 发送请求

    Returns:
        SendMessageResponse: 发送结果
    """
    try:
        service = get_wechat_service()

        result = await service.send_message_to_user(
            openid=request_data.openid,
            message_type="news",
            articles=request_data.articles
        )

        if result.get("errcode") == 0:
            return SendMessageResponse(
                status="success",
                errcode=0,
                errmsg="ok",
                msgid=result.get("msgid")
            )
        else:
            return SendMessageResponse(
                status="error",
                errcode=result.get("errcode"),
                errmsg=result.get("errmsg", "Unknown error")
            )

    except Exception as e:
        logger.error(f"Error sending news message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wechat/send/card", response_model=SendMessageResponse)
async def send_card_message(request_data: SendCardMessageRequest):
    """
    发送卡片消息到微信 (使用图文消息格式)

    Args:
        request_data: 发送请求

    Returns:
        SendMessageResponse: 发送结果
    """
    try:
        service = get_wechat_service()

        result = await service.send_message_to_user(
            openid=request_data.openid,
            message_type="card",
            title=request_data.title,
            description=request_data.description,
            url=request_data.url,
            image_url=request_data.image_url
        )

        if result.get("errcode") == 0:
            return SendMessageResponse(
                status="success",
                errcode=0,
                errmsg="ok",
                msgid=result.get("msgid")
            )
        else:
            return SendMessageResponse(
                status="error",
                errcode=result.get("errcode"),
                errmsg=result.get("errmsg", "Unknown error")
            )

    except Exception as e:
        logger.error(f"Error sending card message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Crawler Endpoints
# ============================================================================

@router.post("/crawler/crawl", response_model=CrawlURLResponse)
async def crawl_url_endpoint(request_data: CrawlURLRequest):
    """
    爬取URL内容

    Args:
        request_data: 爬取请求

    Returns:
        CrawlURLResponse: 爬取结果
    """
    try:
        crawler = WebCrawler(timeout=request_data.timeout)

        result = await crawler.fetch_page(request_data.url)

        if result is None:
            return CrawlURLResponse(
                url=request_data.url,
                title=None,
                description=None,
                content="",
                links=[],
                content_type="unknown",
                status="error"
            )

        return CrawlURLResponse(
            url=result.get("url", request_data.url),
            title=result.get("title"),
            description=result.get("description"),
            content=result.get("content", "")[:1000],  # 限制响应内容长度
            links=result.get("links", []),
            content_type=result.get("content_type", "unknown"),
            status="success"
        )

    except Exception as e:
        logger.error(f"Error crawling URL {request_data.url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/extract-links", response_model=ExtractLinksResponse)
async def extract_links_endpoint(request_data: ExtractLinksRequest):
    """
    从文本中提取链接

    Args:
        request_data: 提取请求

    Returns:
        ExtractLinksResponse: 提取结果
    """
    try:
        extractor = LinkExtractor()
        urls = extractor.extract_urls(request_data.text)

        return ExtractLinksResponse(
            urls=urls,
            count=len(urls)
        )

    except Exception as e:
        logger.error(f"Error extracting links: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawler/create-resource", response_model=ProcessWeChatMessageResponse)
async def create_resource_from_url(
    request_data: CreateResourceFromURL,
    db: AsyncSession = Depends(get_db)
):
    """
    从URL创建Resource Item

    Args:
        request_data: 创建请求
        db: 数据库会话

    Returns:
        ProcessWeChatMessageResponse: 创建结果
    """
    try:
        # 验证UUID格式
        try:
            workspace_uuid = uuid.UUID(request_data.workspace_id)
            creator_uuid = uuid.UUID(request_data.creator_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid UUID format: {e}")

        # 爬取URL
        crawler = WebCrawler(timeout=10)
        crawl_result = await crawler.fetch_page(request_data.url)

        if crawl_result is None:
            return ProcessWeChatMessageResponse(
                status="error",
                error=f"Failed to crawl URL: {request_data.url}"
            )

        # 创建Resource Item
        title = request_data.title or crawl_result.get("title") or request_data.url
        description = crawl_result.get("description", "")
        content = crawl_result.get("content", "")

        # 组合内容
        full_content = f"URL: {request_data.url}\n\n"
        if description:
            full_content += f"Description: {description}\n\n"
        full_content += f"Content:\n{content}"

        item_data = ItemCreate(
            workspace_id=workspace_uuid,
            creator_id=creator_uuid,
            type="resource",
            title=title,
            content=full_content,
            source_type="web_crawler",
            source_meta={
                "url": request_data.url,
                "content_type": crawl_result.get("content_type"),
                "crawl_date": None  # TODO: 添加时间戳
            }
        )

        if request_data.default_area_id:
            item_data.area_id = uuid.UUID(request_data.default_area_id)

        item = await create_item(db, item_data)

        return ProcessWeChatMessageResponse(
            status="success",
            result={
                "item_id": str(item.id),
                "type": "resource",
                "url": request_data.url,
                "title": title
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating resource from URL: {e}")
        return ProcessWeChatMessageResponse(
            status="error",
            error=str(e)
        )


# ============================================================================
# Health Endpoints
# ============================================================================

@router.get("/health", response_model=WebhookHealthResponse)
async def integrations_health():
    """
    集成服务健康检查

    Returns:
        WebhookHealthResponse: 健康状态
    """
    return WebhookHealthResponse(
        status="healthy",
        service="integrations"
    )
