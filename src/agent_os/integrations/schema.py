"""Integration Schemas - Request/Response Models for Webhooks."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


# ============================================================================
# WeChat Webhook Schemas
# ============================================================================

class WeChatTextMessage(BaseModel):
    """微信文本消息"""
    content: str = Field(..., description="消息内容")


class WeChatLinkMessage(BaseModel):
    """微信链接消息"""
    title: str = Field(..., description="链接标题")
    description: str = Field("", description="链接描述")
    url: str = Field(..., description="链接URL")


class WeChatImageMessage(BaseModel):
    """微信图片消息"""
    pic_url: str = Field(..., description="图片URL")
    media_id: str = Field(..., description="媒体ID")


class WebhookVerifyRequest(BaseModel):
    """微信 Webhook 验证请求"""
    signature: str = Field(..., description="微信签名")
    timestamp: str = Field(..., description="时间戳")
    nonce: str = Field(..., description="随机数")
    echostr: Optional[str] = Field(None, description="验证返回字符串")


class ProcessWeChatMessageRequest(BaseModel):
    """处理微信消息请求"""
    workspace_id: str = Field(..., description="工作空间ID")
    creator_id: str = Field(..., description="创建者ID")
    default_area_id: Optional[str] = Field(None, description="默认区域ID")
    xml_data: str = Field(..., description="微信XML数据")


class ProcessWeChatMessageResponse(BaseModel):
    """处理微信消息响应"""
    status: str = Field(..., description="处理状态: success, error")
    result: Optional[Dict[str, Any]] = Field(None, description="处理结果")
    error: Optional[str] = Field(None, description="错误信息")


class WebhookHealthResponse(BaseModel):
    """Webhook 健康检查响应"""
    status: str = Field(..., description="服务状态")
    service: str = Field(..., description="服务名称")


# ============================================================================
# Crawler Schemas
# ============================================================================

class CrawlURLRequest(BaseModel):
    """爬取URL请求"""
    url: str = Field(..., description="目标URL")
    timeout: int = Field(10, description="超时时间(秒)")


class CrawlURLResponse(BaseModel):
    """爬取URL响应"""
    url: str = Field(..., description="URL")
    title: Optional[str] = Field(None, description="页面标题")
    description: Optional[str] = Field(None, description="页面描述")
    content: str = Field("", description="页面内容")
    links: list = Field([], description="页面链接")
    content_type: str = Field(..., description="内容类型")
    status: str = Field(..., description="爬取状态")


class ExtractLinksRequest(BaseModel):
    """提取链接请求"""
    text: str = Field(..., description="输入文本")


class ExtractLinksResponse(BaseModel):
    """提取链接响应"""
    urls: list = Field([], description="提取的URL列表")
    count: int = Field(..., description="URL数量")


# ============================================================================
# Resource Item Creation Schemas
# ============================================================================

class CreateResourceFromURL(BaseModel):
    """从URL创建Resource Item"""
    workspace_id: str = Field(..., description="工作空间ID")
    creator_id: str = Field(..., description="创建者ID")
    url: str = Field(..., description="URL")
    default_area_id: Optional[str] = Field(None, description="默认区域ID")
    title: Optional[str] = Field(None, description="标题(可选)")
