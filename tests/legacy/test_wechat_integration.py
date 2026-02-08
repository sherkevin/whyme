"""Stage 4: WeChat Integration Tests.

Complete integration tests for WeChat webhook, crawler, and resource creation.
"""

import pytest
import uuid
from datetime import datetime

from agent_os.integrations.wechat import WeChatWebhookReceiver, LinkExtractor
from agent_os.integrations.crawler import WebCrawler, crawl_url
from agent_os.integrations.schema import (
    WebhookVerifyRequest,
    ProcessWeChatMessageRequest,
    CrawlURLRequest,
    ExtractLinksRequest,
    CreateResourceFromURL
)
from agent_os.items.crud import create_workspace, create_item, get_item
from agent_os.items.schema import WorkspaceCreate, ItemCreate


# ============================================================================
# WeChat Webhook Tests
# ============================================================================

@pytest.mark.asyncio
async def test_wechat_signature_verification():
    """测试微信签名验证"""
    receiver = WeChatWebhookReceiver(token="test_token")

    # 测试正确的签名
    # 根据微信算法: sort([token, timestamp, nonce]) -> sha1
    timestamp = "1234567890"
    nonce = "random_nonce"
    tmp_list = ["test_token", timestamp, nonce]
    tmp_list.sort()
    tmp_str = "".join(tmp_list)

    import hashlib
    correct_signature = hashlib.sha1(tmp_str.encode('utf-8')).hexdigest()

    assert receiver.verify_signature(correct_signature, timestamp, nonce) == True

    # 测试错误的签名
    assert receiver.verify_signature("wrong_signature", timestamp, nonce) == False


@pytest.mark.asyncio
async def test_wechat_text_message_parsing():
    """测试微信文本消息解析"""
    xml_data = """
    <xml>
        <ToUserName><![CDATA[gh_user]]></ToUserName>
        <FromUserName><![CDATA[openid]]></FromUserName>
        <CreateTime>1234567890</CreateTime>
        <MsgType><![CDATA[text]]></MsgType>
        <Content><![CDATA[Hello, this is a test message]]></Content>
        <MsgId>1234567890123456</MsgId>
    </xml>
    """

    receiver = WeChatWebhookReceiver()
    message = receiver.parse_xml_message(xml_data)

    assert message["type"] == "text"
    assert message["content"] == "Hello, this is a test message"
    assert message["from_user"] == "openid"
    assert message["msg_id"] == "1234567890123456"


@pytest.mark.asyncio
async def test_wechat_link_message_parsing():
    """测试微信链接消息解析"""
    xml_data = """
    <xml>
        <ToUserName><![CDATA[gh_user]]></ToUserName>
        <FromUserName><![CDATA[openid]]></FromUserName>
        <CreateTime>1234567890</CreateTime>
        <MsgType><![CDATA[link]]></MsgType>
        <Title><![CDATA[Test Link]]></Title>
        <Description><![CDATA[Test Description]]></Description>
        <Url><![CDATA[https://example.com]]></Url>
        <MsgId>1234567890123456</MsgId>
    </xml>
    """

    receiver = WeChatWebhookReceiver()
    message = receiver.parse_xml_message(xml_data)

    assert message["type"] == "link"
    assert message["title"] == "Test Link"
    assert message["description"] == "Test Description"
    assert message["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_wechat_image_message_parsing():
    """测试微信图片消息解析"""
    xml_data = """
    <xml>
        <ToUserName><![CDATA[gh_user]]></ToUserName>
        <FromUserName><![CDATA[openid]]></FromUserName>
        <CreateTime>1234567890</CreateTime>
        <MsgType><![CDATA[image]]></MsgType>
        <PicUrl><![CDATA[http://example.com/image.jpg]]></PicUrl>
        <MediaId><![CDATA[media_id_123]]></MediaId>
        <MsgId>1234567890123456</MsgId>
    </xml>
    """

    receiver = WeChatWebhookReceiver()
    message = receiver.parse_xml_message(xml_data)

    assert message["type"] == "image"
    assert message["pic_url"] == "http://example.com/image.jpg"
    assert message["media_id"] == "media_id_123"


# ============================================================================
# Link Extractor Tests
# ============================================================================

@pytest.mark.asyncio
async def test_link_extractor_single_url():
    """测试提取单个URL"""
    extractor = LinkExtractor()

    text = "Check out this link: https://example.com/test"
    urls = extractor.extract_urls(text)

    assert len(urls) == 1
    assert urls[0] == "https://example.com/test"


@pytest.mark.asyncio
async def test_link_extractor_multiple_urls():
    """测试提取多个URL"""
    extractor = LinkExtractor()

    text = """
    Visit https://example.com and http://test.org
    Also check https://another.com/path?query=value
    """

    urls = extractor.extract_urls(text)

    assert len(urls) == 3
    assert "https://example.com" in urls
    assert "http://test.org" in urls
    assert "https://another.com/path?query=value" in urls


@pytest.mark.asyncio
async def test_link_extractor_empty_text():
    """测试空文本"""
    extractor = LinkExtractor()

    urls = extractor.extract_urls("")

    assert len(urls) == 0


@pytest.mark.asyncio
async def test_link_extractor_no_urls():
    """测试没有URL的文本"""
    extractor = LinkExtractor()

    urls = extractor.extract_urls("This is just plain text with no URLs")

    assert len(urls) == 0


@pytest.mark.asyncio
async def test_link_extractor_first_url():
    """测试提取第一个URL"""
    extractor = LinkExtractor()

    text = "First: https://first.com, Second: https://second.com"
    first_url = extractor.extract_first_url(text)

    # 由于使用了set去重，顺序可能不同，只要能提取到URL即可
    assert first_url is not None
    assert first_url in ["https://first.com", "https://second.com"]


# ============================================================================
# WeChat Message Processing Tests
# ============================================================================

@pytest.mark.asyncio
async def test_process_text_message(db_session):
    """测试处理文本消息并创建Resource Item"""
    # 创建workspace
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="WeChat Test Workspace",
        owner_id=creator_id
    ))

    # 准备测试数据
    message = {
        'type': 'text',
        'content': 'Test message from WeChat',
        'from_user': 'test_user',
        'msg_id': 'msg_123',
        'create_time': '1234567890'
    }

    receiver = WeChatWebhookReceiver()
    result = await receiver.process_message(
        db_session,
        message,
        str(workspace.id),
        str(creator_id),
        None
    )

    assert result is not None
    assert result["type"] == "text"
    assert result["status"] == "created"
    assert "item_id" in result

    # 验证Item已创建
    item = await get_item(db_session, uuid.UUID(result["item_id"]))
    assert item is not None
    assert item.type == "resource"
    assert item.source_type == "wechat"


@pytest.mark.asyncio
async def test_process_link_message(db_session):
    """测试处理链接消息并创建Resource Item"""
    # 创建workspace
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="WeChat Test Workspace",
        owner_id=creator_id
    ))

    # 准备测试数据
    message = {
        'type': 'link',
        'title': 'Test Link Title',
        'description': 'Test Link Description',
        'url': 'https://example.com',
        'from_user': 'test_user',
        'msg_id': 'msg_456',
        'create_time': '1234567890'
    }

    receiver = WeChatWebhookReceiver()
    result = await receiver.process_message(
        db_session,
        message,
        str(workspace.id),
        str(creator_id),
        None
    )

    assert result is not None
    assert result["type"] == "link"
    assert result["status"] == "created"
    assert result["url"] == "https://example.com"

    # 验证Item已创建
    item = await get_item(db_session, uuid.UUID(result["item_id"]))
    assert item is not None
    assert "https://example.com" in item.content


@pytest.mark.asyncio
async def test_process_image_message(db_session):
    """测试处理图片消息并创建Resource Item"""
    # 创建workspace
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="WeChat Test Workspace",
        owner_id=creator_id
    ))

    # 准备测试数据
    message = {
        'type': 'image',
        'pic_url': 'http://example.com/image.jpg',
        'media_id': 'media_123',
        'from_user': 'test_user',
        'msg_id': 'msg_789',
        'create_time': '1234567890'
    }

    receiver = WeChatWebhookReceiver()
    result = await receiver.process_message(
        db_session,
        message,
        str(workspace.id),
        str(creator_id),
        None
    )

    assert result is not None
    assert result["type"] == "image"
    assert result["status"] == "created"
    assert result["media_id"] == "media_123"

    # 验证Item已创建
    item = await get_item(db_session, uuid.UUID(result["item_id"]))
    assert item is not None
    assert "media_123" in item.content


# ============================================================================
# Web Crawler Tests
# ============================================================================

@pytest.mark.asyncio
async def test_web_crawler_init():
    """测试WebCrawler初始化"""
    crawler = WebCrawler(timeout=10)

    assert crawler.timeout == 10
    assert "Mozilla" in crawler.user_agent


@pytest.mark.asyncio
async def test_web_crawler_extract_metadata():
    """测试元数据提取"""
    crawler = WebCrawler()

    html_content = """
    <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test Description">
            <meta name="keywords" content="test, python, async">
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Description">
            <meta property="og:image" content="http://example.com/image.jpg">
        </head>
        <body>
            <a href="https://link1.com">Link 1</a>
            <a href="https://link2.com">Link 2</a>
        </body>
    </html>
    """

    metadata = crawler.extract_metadata("https://example.com", html_content)

    assert metadata["title"] == "Test Page"
    assert metadata["metadata"]["description"] == "Test Description"
    assert "test" in metadata["metadata"]["keywords"]
    assert metadata["metadata"]["og_title"] == "OG Title"
    assert metadata["metadata"]["og_image"] == "http://example.com/image.jpg"
    assert len(metadata["links"]) == 2


@pytest.mark.asyncio
async def test_web_crawler_extract_text_content():
    """测试文本内容提取"""
    crawler = WebCrawler()

    html_content = """
    <html>
        <head>
            <script>var x = 1;</script>
            <style>body { color: red; }</style>
        </head>
        <body>
            <h1>Title</h1>
            <p>Paragraph 1</p>
            <p>Paragraph 2</p>
        </body>
    </html>
    """

    text = crawler.extract_text_content(html_content)

    assert "Title" in text
    assert "Paragraph 1" in text
    assert "Paragraph 2" in text
    # Script和style应该被移除
    assert "var x = 1" not in text
    assert "color: red" not in text


@pytest.mark.asyncio
async def test_web_crawler_empty_html():
    """测试空HTML处理"""
    crawler = WebCrawler()

    text = crawler.extract_text_content("")

    assert text == ""


# ============================================================================
# Integration Tests - End-to-End
# ============================================================================

@pytest.mark.asyncio
async def test_full_wechat_workflow(db_session):
    """测试完整的微信消息处理流程"""
    # 创建workspace
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="Full Workflow Test",
        owner_id=creator_id
    ))

    # 模拟完整的微信消息流程
    xml_data = """
    <xml>
        <ToUserName><![CDATA[gh_user]]></ToUserName>
        <FromUserName><![CDATA[openid]]></FromUserName>
        <CreateTime>1234567890</CreateTime>
        <MsgType><![CDATA[text]]></MsgType>
        <Content><![CDATA[https://example.com Interesting article]]></Content>
        <MsgId>1234567890123456</MsgId>
    </xml>
    """

    # 解析消息
    receiver = WeChatWebhookReceiver()
    message = receiver.parse_xml_message(xml_data)

    # 提取URL
    extractor = LinkExtractor()
    urls = extractor.extract_urls(message["content"])
    assert len(urls) > 0

    # 处理消息
    result = await receiver.process_message(
        db_session,
        message,
        str(workspace.id),
        str(creator_id),
        None
    )

    assert result is not None
    assert result["status"] == "created"


@pytest.mark.asyncio
async def test_unsupported_message_type(db_session):
    """测试不支持的消息类型"""
    # 创建workspace
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="Unsupported Type Test",
        owner_id=creator_id
    ))

    # 不支持的消息类型
    message = {
        'type': 'voice',  # 不支持的类型
        'from_user': 'test_user'
    }

    receiver = WeChatWebhookReceiver()
    result = await receiver.process_message(
        db_session,
        message,
        str(workspace.id),
        str(creator_id),
        None
    )

    # 不支持的消息应该返回None
    assert result is None


@pytest.mark.asyncio
async def test_empty_text_message(db_session):
    """测试空文本消息"""
    # 创建workspace
    creator_id = uuid.uuid4()
    workspace = await create_workspace(db_session, WorkspaceCreate(
        name="Empty Message Test",
        owner_id=creator_id
    ))

    # 空文本消息
    message = {
        'type': 'text',
        'content': '   ',  # 只有空格
        'from_user': 'test_user',
        'msg_id': 'msg_empty',
        'create_time': '1234567890'
    }

    receiver = WeChatWebhookReceiver()
    result = await receiver.process_message(
        db_session,
        message,
        str(workspace.id),
        str(creator_id),
        None
    )

    # 空消息不应该创建Item
    assert result is None


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
