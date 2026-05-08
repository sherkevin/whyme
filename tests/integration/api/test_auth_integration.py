"""Stage 7: Authentication and Authorization Integration Tests.

Comprehensive tests for:
- Password hashing and verification
- JWT token generation and validation
- API key management
- User CRUD operations
- Authentication middleware
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from agent_os.auth.security import (
    DEFAULT_PERMISSIONS,
    check_permission,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    get_api_key_prefix,
    get_password_hash,
    hash_api_key,
    hash_token,
    verify_password,
)

# ============================================================================
# Password Hashing Tests
# ============================================================================

def test_password_hashing():
    """测试密码哈希生成"""
    password = "test_pass_123"

    # 生成哈希
    hashed = get_password_hash(password)

    # 哈希应该包含 salt 和 hash，用 $ 分隔
    assert '$' in hashed
    parts = hashed.split('$')
    assert len(parts) == 2
    # 哈希应该与原密码不同
    assert hashed != password
    # 哈希应该足够长（32 字符 hex salt + 64 字符 hex hash + $）
    assert len(hashed) == 97  # 32 + 1 + 64


def test_password_verification():
    """测试密码验证"""
    password = "correct_pass"

    # 生成哈希
    hashed = get_password_hash(password)

    # 正确密码应该验证通过
    assert verify_password(password, hashed) is True

    # 错误密码应该验证失败
    assert verify_password( "wrong_pass", hashed) is False


def test_password_hash_uniqueness():
    """测试相同密码生成不同哈希（由于 salt）"""
    password = "same_password"

    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)

    # 两次哈希应该不同（因为 argon2 使用随机 salt）
    assert hash1 != hash2

    # 但都应该能验证原密码
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_password_hash_empty():
    """测试空密码处理"""
    password = ""

    # 应该能哈希空密码
    hashed = get_password_hash(password)
    assert hashed is not None

    # 验证应该正确
    assert verify_password(password, hashed) is True
    assert verify_password(" ", hashed) is False


# ============================================================================
# JWT Token Tests
# ============================================================================

def test_create_access_token():
    """测试访问令牌创建"""
    data = {
        "sub": str(uuid.uuid4()),
        "username": "testuser"
    }

    token = create_access_token(data)

    # Token 应该是非空字符串
    assert token is not None
    assert len(token) > 0
    # Token 应该包含三个部分（header.payload.signature）
    parts = token.split(".")
    assert len(parts) == 3


def test_create_access_token_with_custom_expiration():
    """测试带自定义过期时间的访问令牌"""
    data = {"sub": str(uuid.uuid4())}

    # 创建 1 小时后过期的 token
    token = create_access_token(data, expires_delta=timedelta(hours=1))

    assert token is not None
    assert len(token) > 0

    # 解码并检查过期时间
    payload = decode_token(token)
    assert payload is not None
    assert "exp" in payload

    # 验证过期时间在未来
    exp_dt = datetime.fromtimestamp(payload["exp"], tz=UTC)
    now_dt = datetime.now(tz=UTC)
    assert exp_dt > now_dt

    # 验证过期时间大约在 1 小时后（允许 10 分钟误差）
    time_diff = exp_dt - now_dt
    assert timedelta(minutes=50) <= time_diff <= timedelta(minutes=70)


def test_create_refresh_token():
    """测试刷新令牌创建"""
    data = {"sub": str(uuid.uuid4())}

    token = create_refresh_token(data)

    assert token is not None
    assert len(token) > 0

    # 解码并验证类型
    payload = decode_token(token)
    assert payload is not None
    assert payload["type"] == "refresh"


def test_decode_valid_token():
    """测试解码有效令牌"""
    data = {
        "sub": str(uuid.uuid4()),
        "username": "testuser"
    }

    token = create_access_token(data)
    payload = decode_token(token)

    # 应该能成功解码
    assert payload is not None
    assert payload["sub"] == data["sub"]
    assert payload["username"] == data["username"]
    assert "exp" in payload
    assert "iat" in payload
    assert payload["type"] == "access"


def test_decode_invalid_token():
    """测试解码无效令牌"""
    # 完全无效的 token
    invalid_tokens = [
        "",
        "invalid.token.here",
        "Bearer token",
        "abc.def.ghi"
    ]

    for token in invalid_tokens:
        payload = decode_token(token)
        assert payload is None


def test_token_expiration():
    """测试令牌过期"""
    data = {"sub": str(uuid.uuid4())}

    # 创建已过期的 token（-1 分钟）
    expired_token = create_access_token(
        data,
        expires_delta=timedelta(minutes=-1)
    )

    # 过期的 token 应该无法解码
    payload = decode_token(expired_token)
    assert payload is None


def test_hash_token():
    """测试令牌哈希"""
    token = "test_token_123"

    hashed = hash_token(token)

    # 哈希应该是 SHA-256（64 字符的 hex 字符串）
    assert len(hashed) == 64
    assert all(c in '0123456789abcdef' for c in hashed)

    # 相同的 token 应该产生相同的哈希
    hashed2 = hash_token(token)
    assert hashed == hashed2

    # 不同的 token 应该产生不同的哈希
    hashed3 = hash_token("different_token")
    assert hashed != hashed3


# ============================================================================
# API Key Tests
# ============================================================================

def test_generate_api_key():
    """测试 API 密钥生成"""
    api_key = generate_api_key()

    # API 密钥应该以 mydow_ 开头
    assert api_key.startswith("mydow_")
    # API 密钥应该足够长
    assert len(api_key) > 40
    # API 密钥应该只包含安全的字符
    assert all(c.isalnum() or c in '-_' for c in api_key)


def test_api_key_uniqueness():
    """测试 API 密钥唯一性"""
    key1 = generate_api_key()
    key2 = generate_api_key()

    # 两个密钥应该不同
    assert key1 != key2


def test_get_api_key_prefix():
    """测试获取 API 密钥前缀"""
    api_key = "mydow_abc123def456"

    prefix = get_api_key_prefix(api_key)

    # 前缀应该是前 10 个字符
    assert prefix == "mydow_abc1"
    assert len(prefix) == 10


def test_hash_api_key():
    """测试 API 密钥哈希"""
    api_key = "mydow_test_api_key_123"

    hashed = hash_api_key(api_key)

    # 哈希应该是 SHA-256（64 字符）
    assert len(hashed) == 64
    assert all(c in '0123456789abcdef' for c in hashed)

    # 相同的密钥应该产生相同的哈希
    hashed2 = hash_api_key(api_key)
    assert hashed == hashed2


# ============================================================================
# Permission Tests
# ============================================================================

def test_check_permission_exact_match():
    """测试权限精确匹配"""
    user_permissions = ["items:read", "items:write"]

    # 精确匹配应该成功
    assert check_permission(user_permissions, "items:read") is True
    assert check_permission(user_permissions, "items:write") is True

    # 不存在的权限应该失败
    assert check_permission(user_permissions, "items:delete") is False


def test_check_permission_wildcard():
    """测试通配符权限"""
    user_permissions = ["items:*", "workspaces:read"]

    # 通配符应该匹配所有子权限
    assert check_permission(user_permissions, "items:read") is True
    assert check_permission(user_permissions, "items:write") is True
    assert check_permission(user_permissions, "items:delete") is True

    # 但不应该匹配其他资源
    assert check_permission(user_permissions, "workspaces:write") is False


def test_check_permission_global_wildcard():
    """测试全局通配符权限"""
    user_permissions = ["*"]

    # 全局通配符应该匹配所有权限
    assert check_permission(user_permissions, "items:read") is True
    assert check_permission(user_permissions, "users:delete") is True
    assert check_permission(user_permissions, "anything:anything") is True


def test_default_permissions():
    """测试默认权限定义"""
    # Admin 应该有所有权限
    admin_perms = DEFAULT_PERMISSIONS["admin"]
    assert "items:*" in admin_perms
    assert "users:*" in admin_perms
    assert "auth:*" in admin_perms

    # User 应该有基本权限
    user_perms = DEFAULT_PERMISSIONS["user"]
    assert "items:read" in user_perms
    assert "items:write" in user_perms
    assert "items:delete" in user_perms
    # 但不应该有用户管理权限
    assert not any("users:" in perm for perm in user_perms)

    # Viewer 应该只有只读权限
    viewer_perms = DEFAULT_PERMISSIONS["viewer"]
    assert "items:read" in viewer_perms
    assert "workspaces:read" in viewer_perms
    # 但不应该有写权限
    assert "items:write" not in viewer_perms
    assert "items:delete" not in viewer_perms


# ============================================================================
# Integration Tests
# ============================================================================

def test_complete_authentication_flow():
    """测试完整认证流程"""
    # 1. 用户注册（密码哈希）
    password = "user_pass_123"
    password_hash = get_password_hash(password)

    # 2. 用户登录（验证密码）
    assert verify_password(password, password_hash) is True
    assert verify_password( "wrong_pass", password_hash) is False

    # 3. 生成访问令牌
    user_id = str(uuid.uuid4())
    token_data = {
        "sub": user_id,
        "username": "testuser"
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": user_id})

    # 4. 验证令牌
    payload = decode_token(access_token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "access"

    refresh_payload = decode_token(refresh_token)
    assert refresh_payload is not None
    assert refresh_payload["type"] == "refresh"

    # 5. 令牌哈希（用于存储）
    token_hash = hash_token(access_token)
    assert len(token_hash) == 64


def test_complete_api_key_flow():
    """测试完整 API 密钥流程"""
    # 1. 生成 API 密钥
    api_key = generate_api_key()
    prefix = get_api_key_prefix(api_key)

    # 2. 哈希存储
    api_key_hash = hash_api_key(api_key)

    # 3. 验证前缀
    assert api_key.startswith(prefix)

    # 4. 验证哈希
    assert hash_api_key(api_key) == api_key_hash

    # 5. 验证权限
    user_permissions = ["items:read", "items:write"]
    assert check_permission(user_permissions, "items:read") is True
    assert check_permission(user_permissions, "items:delete") is False


def test_token_refresh_flow():
    """测试令牌刷新流程"""
    user_id = str(uuid.uuid4())

    # 1. 创建访问令牌和刷新令牌
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})

    # 2. 验证访问令牌
    access_payload = decode_token(access_token)
    assert access_payload["type"] == "access"

    # 3. 验证刷新令牌
    refresh_payload = decode_token(refresh_token)
    assert refresh_payload["type"] == "refresh"
    assert refresh_payload["sub"] == user_id

    # 4. 使用刷新令牌创建新的访问令牌
    new_access_token = create_access_token({"sub": user_id})
    new_payload = decode_token(new_access_token)
    assert new_payload is not None
    assert new_payload["type"] == "access"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
