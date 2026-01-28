# 高优先级功能使用示例

本文档演示如何使用新实现的用户确认和 Diff 功能。

## 场景 1: 基本的用户确认

### 后端代码

```python
import asyncio
from agent_os.server.websocket_io import WebSocketIO

async def example_confirm_ask():
    """演示 confirm_ask 的使用"""

    # 创建输出队列和事件循环
    output_queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    # 创建 WebSocketIO 实例
    ws_io = WebSocketIO(output_queue, loop, pretty=True)

    # 在后台线程启动确认请求
    task = asyncio.create_task(
        asyncio.to_thread(
            ws_io.confirm_ask,
            question="是否继续执行此操作？",
            default="y",
            subject="这将修改 3 个文件"
        )
    )

    # 模拟前端接收事件并发送响应
    event = await output_queue.get()
    print(f"发送到前端的事件: {event}")

    # 模拟用户点击 "Yes"
    confirm_id = event["payload"]["data"]["confirm_id"]
    ws_io.receive_confirm_response(confirm_id, True)

    # 等待确认完成
    result = await task
    print(f"用户的选择: {result}")  # True

# 运行示例
# asyncio.run(example_confirm_ask())
```

### 前端处理

```javascript
// 接收 confirm_ask 事件
function handleWebSocketMessage(msg) {
    if (msg.type === 'event' && msg.payload.action === 'confirm_ask') {
        const data = msg.payload.data;
        showConfirmDialog(data);
    }
}

// 显示确认对话框
function showConfirmDialog(data) {
    const questionEl = document.getElementById('confirm-question');
    const subjectEl = document.getElementById('confirm-subject');

    questionEl.textContent = data.question;
    subjectEl.textContent = data.subject;

    // 存储确认 ID
    state.pendingConfirm = data.confirm_id;

    // 显示对话框
    document.getElementById('confirm-dialog-overlay').style.display = 'flex';
}

// 发送响应
function sendConfirmResponse(approved) {
    state.ws.send(JSON.stringify({
        type: 'input',
        payload: {
            confirm_id: state.pendingConfirm,
            response: approved ? 'yes' : 'no'
        }
    }));

    hideConfirmDialog();
}
```

---

## 场景 2: Diff 确认流程

### 后端代码

```python
import asyncio
from agent_os.server.diff_service import DiffService

async def example_diff_confirmation():
    """演示 diff 确认流程"""

    output_queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    diff_service = DiffService("session_123", output_queue, loop)

    # 原始文件内容
    original_content = """def hello():
    print("Hello, World!")
    return 0
"""

    # 新的文件内容
    new_content = """def hello():
    print("Hello, AgentOS!")
    return 0

def goodbye():
    print("Goodbye!")
    return 0
"""

    # 提议更改（后台任务）
    task = asyncio.create_task(
        diff_service.propose_change(
            file_path="hello.py",
            original_content=original_content,
            new_content=new_content,
            description="添加 goodbye 函数"
        )
    )

    # 接收 diff 事件
    event = await output_queue.get()
    print(f"Diff 事件: {event['payload']['action']}")
    print(f"Diff 内容:\n{event['payload']['data']['diff_content']}")

    # 用户批准更改
    diff_service.handle_user_response("approve", None)

    # 等待确认完成
    approved = await task
    print(f"更改是否被批准: {approved}")  # True

    # 获取新内容以应用
    if approved:
        new_content = await diff_service.approve_diff(
            f"session_123:hello.py"
        )
        # 应用到文件...
        print(f"应用新内容到文件")

# asyncio.run(example_diff_confirmation())
```

### Diff 输出示例

```
--- a/hello.py
+++ b/hello.py
@@ -1,4 +1,9 @@
 def hello():
-    print("Hello, World!")
+    print("Hello, AgentOS!")
     return 0
+
+def goodbye():
+    print("Goodbye!")
+    return 0
```

---

## 场景 3: Aider Coder 集成

### 初始化 AiderAgent

```python
from agent_os.agent_aider import AiderAgent
from agent_os.core.config import load_config
import asyncio

async def example_aider_with_confirmations():
    """演示 AiderAgent 使用确认对话框"""

    # 加载配置
    config = load_config("config.yaml")

    # 创建 agent
    agent = AiderAgent(
        session_id="test_session",
        workspace_root="./workspace",
        config=config
    )

    # 设置 WebSocket 通信
    output_queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    agent._output_queue = output_queue
    agent._event_loop = loop

    # 发送消息
    response = await agent.chat(
        message="创建一个计算器程序",
        user_id="user_123",
        callbacks=[]
    )

    print(f"Agent 响应: {response['content']}")

    # 处理确认事件
    while not output_queue.empty():
        event = await output_queue.get()
        if event["payload"]["action"] == "confirm_ask":
            # 发送到前端显示
            print(f"需要确认: {event['payload']['data']['question']}")

# asyncio.run(example_aider_with_confirmations())
```

---

## 场景 4: 完整的编辑流程

### 1. 用户请求编辑

```python
# 前端发送
ws.send(JSON.stringify({
    type: 'input',
    payload: {
        text: '添加一个函数来计算阶乘'
    }
}))
```

### 2. Aider 生成 Diff

```python
# 后端处理
async def handle_edit_request(message):
    # Aider 分析代码并生成 diff
    aider = await agent._get_aider()

    # 运行 Aider（会调用 confirm_ask）
    response = await aider.coder.run(message)

    return response
```

### 3. 显示 Diff 并等待确认

```javascript
// 前端接收 confirm_diff 事件
function handleWebSocketMessage(msg) {
    if (msg.payload.action === 'confirm_diff') {
        const diffData = msg.payload.data;

        // 显示 diff
        showDiffPanel({
            file: diffData.file,
            diff_content: diffData.diff_content,
            description: diffData.description,
            diff_id: diffData.diff_id
        });
    }
}

// 用户批准
function approveDiff() {
    ws.send(JSON.stringify({
        type: 'input',
        payload: {
            command: 'yes',
            diff_id: state.pendingDiff.diff_id
        }
    }));
}
```

### 4. 应用更改

```python
# 后端接收批准并应用
diff_service.handle_user_response("approve", diff_id)
# Aider 继续执行并应用更改
```

---

## 实际使用案例

### 案例 1: 创建新文件

**用户输入**: "创建一个 hello.py 文件，打印 Hello World"

**流程**:
1. Aider 分析请求
2. 生成文件内容
3. **显示确认**（如果是修改现有文件）
4. 用户点击 "Apply"
5. 文件被创建

### 案例 2: 修改代码

**用户输入**: "把 hello.py 改成打印 Hello AgentOS"

**流程**:
1. Aider 读取现有文件
2. 生成 diff
3. **显示 diff 确认对话框**:
   ```
   --- a/hello.py
   +++ b/hello.py
   @@ -1 +1 @@
   -print("Hello World")
   +print("Hello AgentOS")
   ```
4. 用户查看 diff
5. 用户点击 "✓ Apply" 或 "✗ Reject"
6. 应用或拒绝更改

### 案例 3: 删除文件

**用户输入**: "删除 test.txt 文件"

**流程**:
1. Aider 识别删除请求
2. **显示确认**: "确认删除 test.txt？"
3. 用户确认
4. 文件被删除

---

## 调试技巧

### 1. 查看事件日志

```python
# 在后端添加日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 或使用 print
print(f"[DEBUG] Event sent: {event}")
```

### 2. 前端调试

```javascript
// 添加 console.log
state.ws.onmessage = (event) => {
    console.log('[DEBUG] Received:', event.data);
    const msg = JSON.parse(event.data);
    handleWebSocketMessage(msg);
};
```

### 3. 查看 WebSocket 消息

```bash
# 使用浏览器开发者工具
# 1. 打开 DevTools (F12)
# 2. 切换到 Network 标签
# 3. 筛选 WS (WebSocket)
# 4. 点击 WebSocket 连接
# 5. 查看 Messages 标签
```

---

## 常见问题

### Q1: 确认对话框不显示

**检查**:
1. 是否正确设置了 `agent._output_queue` 和 `agent._event_loop`
2. WebSocket 连接是否正常
3. 前端是否监听了 `confirm_ask` 事件

**解决**:
```python
# 在 app.py 的 websocket_endpoint 中
agent._output_queue = output_queue
agent._event_loop = loop
```

### Q2: 用户响应没有发送到后端

**检查**:
1. 前端是否正确发送了 `confirm_id`
2. 后端是否正确处理了响应
3. WebSocketIO 的 `receive_confirm_response()` 是否被调用

**解决**:
```javascript
// 确保发送正确的格式
ws.send(JSON.stringify({
    type: 'input',
    payload: {
        confirm_id: state.pendingConfirm,
        response: 'yes'  // 或 'no'
    }
}));
```

### Q3: Diff 不显示

**检查**:
1. `DiffService.propose_change()` 是否被调用
2. 事件是否正确发送到前端
3. 前端 `showDiffPanel()` 是否正常工作

**解决**:
```javascript
// 检查事件处理
if (payload.action === 'confirm_diff' && payload.data) {
    console.log('Diff data:', payload.data);
    showDiffPanel(payload.data);
}
```

---

## 总结

✅ **所有高优先级功能已就绪并可以使用**

- ✅ 用户确认对话框 (`confirm_ask`)
- ✅ Diff 确认流程 (`confirm_diff`)
- ✅ Aider Coder 集成

**下一步**: 测试实际使用场景并收集用户反馈！
