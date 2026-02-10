# AgentOS 文档导航

欢迎来到 AgentOS 文档中心！

## 📖 快速导航

### 🚀 新手入门
- [主项目 README](../README.md) - 项目概述和快速开始
- [快速开始指南](../QUICKSTART.md) - 5分钟上手
- [部署指南](guides/deployment.md) - Docker 部署详细步骤
- [测试指南](../TESTING_GUIDE.md) - 如何运行测试

### 🏗️ 架构与设计
- [系统架构](../ARCHITECTURE.md) - 核心架构设计
- [API 参考](03-toolkit/api-reference.md) - API 接口文档

### 📋 产品需求
- [PRD0 - 产品概述](01-prd/PRD0.md) - 产品需求概述
- [PRD1 - 架构规范](01-prd/PRD1.md) - 详细需求文档
- [PRD2 - Toolkit系统](01-prd/PRD2.md) - Toolkit 系统需求

### 📊 进度与报告

#### 性能报告
- [性能基线报告](reports/performance/PERFORMANCE_BASELINE_REPORT.md) - PRD4 性能测试结果

#### PRD 合规性
- [PRD 合规性矩阵](reports/prd/PRD_COMPLIANCE_MATRIX.md) - 完整的 PRD 合规性检查
- [PRD 审计摘要](reports/prd/PRD_AUDIT_SUMMARY.md) - 审计总结

#### 测试报告
- [测试完成报告](reports/testing/FINAL_TEST_COMPLETION_REPORT.md) - 测试改进完成报告
- [服务测试报告](reports/testing/SERVICES_TEST_IMPROVEMENT_REPORT.md) - 服务模块测试详情

#### 微信集成
- [微信集成报告](reports/wechat/WECHAT_INTEGRATION_COMPLETION_REPORT.md) - 微信集成实现文档

#### 归档文档
查看 [归档目录](archive/) 获取历史报告和旧版本文档。

---

## 📂 目录结构

```
docs/
├── README.md                   # 本文件 - 文档导航
├── 01-prd/                     # 产品需求文档
├── 02-progress/                # 进度报告
├── 03-toolkit/                 # 技术文档和 API
├── 04-guides/                  # 用户指南
├── 05-testing/                 # 测试文档
├── guides/                     # 指南文档
│   └── deployment.md           # Docker 部署
├── reports/                    # 各类报告
│   ├── performance/            # 性能报告
│   ├── prd/                    # PRD 合规性
│   ├── testing/                # 测试报告
│   └── wechat/                 # 微信集成
└── archive/                    # 归档文档
```

---

## 🔍 查找文档

### 按目的查找

| 我想... | 查看文档 |
|---------|----------|
| 快速上手 | [QUICKSTART.md](../QUICKSTART.md) |
| 部署到服务器 | [guides/deployment.md](guides/deployment.md) |
| 运行测试 | [TESTING_GUIDE.md](../TESTING_GUIDE.md) |
| 了解架构 | [ARCHITECTURE.md](../ARCHITECTURE.md) |
| 调用 API | [03-toolkit/api-reference.md](03-toolkit/api-reference.md) |
| 查看性能 | [reports/performance/](reports/performance/) |
| 检查 PRD 合规性 | [reports/prd/PRD_COMPLIANCE_MATRIX.md](reports/prd/PRD_COMPLIANCE_MATRIX.md) |

### 按角色查找

| 角色 | 推荐文档 |
|------|----------|
| **新用户** | README.md → QUICKSTART.md → guides/deployment.md |
| **开发者** | ARCHITECTURE.md → 03-toolkit/api-reference.md → TESTING_GUIDE.md |
| **测试员** | TESTING_GUIDE.md → reports/testing/ |
| **产品经理** | 01-prd/ → reports/prd/ → reports/performance/ |
| **运维** | guides/deployment.md → ARCHITECTURE.md |

---

## 📝 文档维护

### 文档规范

1. **所有文档使用 Markdown 格式**
2. **文件名使用小写和下划线**（除根目录保留的文档）
3. **更新文档时同步更新本导航页**
4. **过时文档移至 archive/ 目录**

### 新增文档

如需新增文档，请：

1. 确定文档类别（guides, reports, 或其他）
2. 在对应目录创建文档
3. 更新本导航页
4. 在根目录 README.md 中添加链接（如果是核心文档）

---

**最后更新:** 2026-02-10
**维护者:** AgentOS Team
