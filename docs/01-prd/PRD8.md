# 模块二：核心业务逻辑与服务 (Services & Workers)
1. 配置管理服务 (Config Service) [对应 B-62]
要求: 将强边阈值抽离为全局配置。
实现: 读取环境变量 GARDEN_STRONG_EDGE_THRESHOLD，若未设置则默认返回 0.65。代码中所有判断强边的地方必须调用此配置。

2. 统计聚合服务 (Profile Stats Service) [对应 B-60, B-05]
要求: 提供内部方法 get_user_garden_stats(user_id, workspace_id)。

计算口径:
- total_notes: 该用户/工作区下状态为活跃的笔记/卡片总数。
- neural_connections: relation_strength >= config.strong_threshold 且去重（A-B 和 B-A 视为同一条连接）的强边总数。
- generated_insights: 该用户下 status='stable' 且 level >= 2 的去重总数（按 canonical_hash 去重）。

3. Cluster 强度计算服务 & Insight Worker [对应 B-63, B-53]
3.1 Cluster Strength 公式: cluster_strength = (strong_edges_count) + (avg_relation_strength * 2.0) + (1.0 / (avg_days_between_nodes + 1))

3.2 Insight 聚合 Worker 规则: 
触发条件: 某 canonical_hash 关联的证据来源数 sources >= 3 且跨度 timespan >= 3 天，且所属 cluster_strength >= 2.5（暂定阈值）。
行为: 满足条件时，更新该 Insight 的 status = 'stable'。
去重逻辑: 遇到重复的 canonical_hash 时，不要新建 DB 记录，而是累加 evidence_count += 1 并更新关联 Sources。
