# 模块一：数据库模型与索引升级 (Database & Models Layer)
1. 关系模型扩展 (KnowledgeCardLink Migration)
不要创建新表，直接对现有的 KnowledgeCardLink（或你代码库中对应的边表）进行 Schema Migration。

新增字段:
- relation_strength (Float): 默认值 0.0，范围 [0.0, 1.0]。
- is_active (Boolean): 默认 true。软删除或失效标志。
- updated_at (Datetime): 自动更新时间戳。

字段修改/确认:
- type (String/Enum): 必须限制为 ['related', 'support', 'contradict', 'reference']。

约束与索引:
- 唯一约束 (Unique Constraint): (from_id, to_id, type)，确保无重复类型的多余边。

性能索引:
- 建立联合索引 (workspace_id, relation_strength)，以及单列索引 (from_id) 和 (to_id) 以防全表扫描。对节点表 (Nodes/Cards) 建立 (user_id, created_at) 索引。

2. Insight 模型扩展 (DailyInsight Migration) [对应 B-52]
新增/确认字段:
- status (String): 枚举值 ['draft', 'candidate', 'stable', 'rejected']。
- level (Integer): 默认 1。有效值为 1, 2, 3。
- canonical_hash (String): 核心发现的哈希值，用于聚合去重。
- stability_score (Float): 默认 0.0。
- evidence_count (Integer): 默认 1。
