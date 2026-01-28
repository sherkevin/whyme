# 文档维护指南

**版本**: v1.0
**最后更新**: 2026-01-28

---

## 📁 文档结构

```
docs/
├── README.md                      # 主文档（项目概览）
├── INDEX.md                       # 文档索引（快速导航）
├── DATABASE_SETUP.md              # 数据库配置指南
├── HIGH_PRIORITY_USAGE_EXAMPLES.md # 使用示例
├── openapi.json                   # API 规范
│
├── IMPLEMENTATION_ROADMAP.md      # 开发路线图（每周更新）
│
├── 01-prd/                        # 产品需求文档
│   ├── PRD0-PRD3.md
│   └── PRD_COMPLIANCE_REPORT.md
│
├── 02-progress/                   # 开发进度记录
│   └── latest-status.md
│
├── 03-toolkit/                    # 工具包系统文档
│   ├── api-reference.md
│   ├── architecture.md
│   └── ...
│
├── 04-guides/                     # 用户指南
│   ├── quickstart.md
│   ├── docker-setup.md
│   └── ...
│
├── 05-testing/                    # 测试文档
│   ├── phase3-test-report.md
│   └── upload-test-report.md
│
├── 06-status/                     # 状态报告（最新）
│   ├── FINAL_TEST_REPORT.md       # 完整测试报告
│   ├── WEEK3_TASK_SUMMARY.md      # Week 3 总结
│   └── openapi_verification_report.md
│
└── 07-archives/                   # 归档文档（历史）
    ├── TEST_RESULTS_SUMMARY.md
    ├── INTEGRATION_TEST_REPORT.md
    ├── HIGH_PRIORITY_FIXES_SUMMARY.md
    ├── MEDIUM_PRIORITY_FIXES_SUMMARY.md
    └── PROJECT_STATUS_ANALYSIS.md
```

---

## 📝 文档分类规则

### 1. 主文档（根目录）

**位置**: `docs/*.md`

**文档**:
- `README.md` - 项目概览和主要功能
- `INDEX.md` - 完整的文档索引和导航
- `DATABASE_SETUP.md` - 数据库配置
- `IMPLEMENTATION_ROADMAP.md` - 开发路线图
- `HIGH_PRIORITY_USAGE_EXAMPLES.md` - 使用示例

**更新频率**:
- `README.md`: 每周或有重大更新时
- `INDEX.md`: 每周或有文档结构变更时
- `IMPLEMENTATION_ROADMAP.md`: 每周更新进度

### 2. 状态报告（06-status/）

**位置**: `docs/06-status/`

**用途**: 最新的测试报告和状态总结

**文档**:
- `FINAL_TEST_REPORT.md` - 完整测试报告（每次完整测试后更新）
- `WEEK<N>_TASK_SUMMARY.md` - 每周总结（Week 完成后创建）
- `openapi_verification_report.md` - API 验证报告

**更新频率**:
- 每次完整测试后更新
- 每周结束时创建新的 Week 总结

### 3. 归档文档（07-archives/）

**位置**: `docs/07-archives/`

**用途**: 历史文档，仅作参考，不再更新

**归档规则**:
- 旧版本的测试报告
- 已解决的问题修复记录
- 过时的项目状态分析

**何时归档**:
- 当有新的测试报告替代时
- 当问题已修复且不再需要跟踪时
- 当项目阶段完成且有新总结时

---

## 🔄 文档更新流程

### 每周更新（Week 结束时）

1. **更新 `IMPLEMENTATION_ROADMAP.md`**
   - 标记完成的任务 [x]
   - 更新进度百分比
   - 添加新完成的里程碑

2. **创建新的 Week 总结**
   - 文件名: `WEEK<N>_TASK_SUMMARY.md`
   - 位置: `docs/06-status/`
   - 内容: 完成的功能、测试结果、已知问题

3. **更新 `INDEX.md` 和 `README.md`**
   - 更新项目进度统计
   - 更新测试覆盖率
   - 添加新的文档链接

### 测试后更新

1. **更新 `FINAL_TEST_REPORT.md`**
   - 更新总体测试统计
   - 更新各模块测试结果
   - 添加新的测试结果分析

2. **归档旧测试报告**（如果存在）
   - 将旧的 `TEST_RESULTS_SUMMARY.md` 移至 `07-archives/`
   - 更新 INDEX.md 中的链接

### 问题修复后

1. **修复完成后**
   - 更新相关的 Week 总结或状态报告
   - 如果修复有详细记录，保留在 `07-archives/` 供参考

---

## 📋 文档命名规范

### 文件命名

- **使用 `kebab-case`**: `my-document-name.md`
- **描述性名称**: 文件名应清楚表明内容
- **数字前缀**: 对于有顺序的文档，使用数字前缀（如 01-prd/, 02-progress/）

### 特殊前缀

- `WEEK<N>_` - 每周总结（如 `WEEK3_TASK_SUMMARY.md`）
- `FINAL_` - 最终版本（如 `FINAL_TEST_REPORT.md`）
- 数字 `-` - 分类目录（如 `01-prd/`, `06-status/`）

### 大写命名

仅用于特殊重要文档：
- `README.md`
- `INDEX.md`
- `DATABASE_SETUP.md`
- `IMPLEMENTATION_ROADMAP.md`
- `HIGH_PRIORITY_USAGE_EXAMPLES.md`

---

## ✍️ 文档内容规范

### Markdown 格式

1. **标题层级**
   ```markdown
   # 一级标题（文档标题）
   ## 二级标题（主要章节）
   ### 三级标题（子章节）
   ```

2. **列表**
   ```markdown
   - 无序列表项
   - 另一个列表项

   1. 有序列表项
   2. 另一个列表项
   ```

3. **代码块**
   ````markdown
   ```python
   def example():
       pass
   ```
   ````

4. **表格**
   ```markdown
   | 列1 | 列2 | 列3 |
   |-----|-----|-----|
   | 数据1 | 数据2 | 数据3 |
   ```

5. **链接**
   ```markdown
   [链接文本](./path/to/file.md)
   ```

### 日期格式

- 使用格式: `YYYY-MM-DD`（如 2026-01-28）
- 在文档顶部标注更新日期

### 状态标识

使用 emoji 清晰标识状态：
- ✅ 已完成
- ⏳ 进行中
- 📋 计划中
- ⚠️ 有问题
- ❌ 失败/未通过

---

## 🔍 文档审查检查清单

### 发布前检查

- [ ] 所有链接正确且有效
- [ ] 文档结构清晰，易于导航
- [ ] 日期信息最新
- [ ] 统计数据准确
- [ ] 代码示例可以运行
- [ ] 拼写和语法正确

### 定期审查

- [ ] 归档的旧文档是否仍需要保留
- [ ] 主文档是否反映最新状态
- [ ] 测试报告是否最新
- [ ] 文档分类是否合理

---

## 🛠️ 文档工具

### 推荐工具

1. **Markdown 编辑器**
   - VS Code + Markdown Preview Enhanced
   - Typora
   - Obsidian

2. **链接检查**
   - VS Code: Markdown Link Check 扩展
   - 命令行: `markdown-link-check`

3. **格式化**
   - Prettier (支持 Markdown)
   - markdownlint

### 自动化脚本

可以创建脚本自动化常见任务：

```bash
# 示例：创建新的 Week 总结
./scripts/new-week-summary.sh 4

# 示例：归档旧测试报告
./scripts/archive-test-report.sh
```

---

## 📞 联系方式

如有文档相关问题，请联系：
- **维护者**: AgentOS 开发团队
- **更新频率**: 每周或有重大变更时
- **最后更新**: 2026-01-28

---

**文档版本**: v1.0
**最后更新**: 2026-01-28
