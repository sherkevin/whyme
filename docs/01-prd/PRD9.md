## 模块三：API 接口层开发 (API Layer) [对应 B-64 规范要求]

**通用要求**：所有接口需返回标准 JSON，并在 OpenAPI/Swagger 中明确声明 Schema（类型、是否 nullable）。

### 1. 更新获取当前用户 API [对应 B-05]

* **Endpoint**: `GET /user/me`
* **修改**: 在返回体中增加 `stats` 对象，调用上述“统计聚合服务”填充 `total_notes`, `neural_connections`, `generated_insights`。向下兼容原有字段。

### 2. 新增 Garden 节点列表 API [对应 B-56]

* **Endpoint**: `GET /garden/nodes`
* **Query Params**:
* `date_range` (String, e.g., "last_90_days", "all")
* `types` (Array of Strings)
* `limit` (Int, default 300), `offset` (Int, default 0)


* **Response Schema**:
```json
{
  "data": [
    {
      "id": "string",
      "object_type": "string",
      "title": "string",
      "created_at": "datetime",
      "strong_connection_count": "integer",
      "snippet": "string (nullable)"
    }
  ]
}

```



### 3. 新增 Garden 边查询 API [对应 B-57]

* **Endpoint**: `POST /garden/edges/batch` (使用 POST 以便传递大数组，或者 GET 传逗号分隔参数)
* **Request Body**:
* `node_ids`: Array of Strings (从 /garden/nodes 获取的节点 ID 列表)


* **Response**:
* **逻辑**: 仅返回起点 `from_id` 和终点 `to_id` **均在入参 `node_ids` 列表中**，且 `relation_strength >= config.strong_threshold` 的强边。
* 返回格式包含 `connections_count`（强边数量）元数据。



### 4. 新增 Garden 节点详情 API [对应 B-59]

* **Endpoint**: `GET /garden/nodes/:id`
* **Response**:
* 返回节点详细信息：`title`, `type`, `time`, `summary`, `jump_url`。
* `connected_nodes`: 数组，包含最多 5 个相关联的节点（按 `relation_strength` 降序排列）。



### 5. 更新今日 Insight API [对应 B-54]

* **Endpoint**: `GET /today/insight`
* **Query Params**: `day` (String, YYYY-MM-DD), `theme` (String, optional).
* **Response Modifications**: 确保返回字段结构必须包含 `claim`, `rationale`, `implications`, `sources`。前端可直接遍历渲染。
