# 文档整理计划

**创建时间:** 2026-02-09
**状态:** 执行中

---

## 问题诊断

### 1. 重复目录 ⚠️

#### docs/02-progress/ vs docs/progress/
- **问题**: 两个目录包含重复的 PRD4 stage 报告
- **原因**: 历史遗留，未统一命名规范
- **决策**: 保留 `docs/02-progress/`，删除 `docs/progress/`

### 2. 根目录冗余文档 ⚠️

| 文件 | 问题 | 操作 |
|------|------|------|
| `ACCEPTANCE_VERIFICATION_REPORT.md` | 与 `FINAL_ACCEPTANCE_CHECK.md` 重复 | 归档 |
| `FINAL_ACCEPTANCE_CHECK.md` | 最新验收文档，保留 | 保留 |
| `FINAL_WORK_SUMMARY.md` | 与 `docs/06-status/prd9-final-summary.md` 重复 | 归档 |
| `PROJECT_IMPROVEMENTS_SUMMARY.md` | 过时 | 归档 |
| `QUICKSTART.md` vs `README_QUICKSTART.md` | 内容重复 | 合并 |
| `DOCKER.md` vs `DOCKER_QUICKSTART.md` | 重复 | 合并 |

### 3. docs/ 根目录冗余文档 ⚠️

| 文件 | 问题 | 操作 |
|------|------|------|
| `PRD7-diff.md`, `PRD8-diff.md` | 应在 `docs/01-prd/` | 移动 |
| `backend-developer-completion-report.md` | 过时 | 归档 |
| `development-progress-summary.md` | 过时 | 归档 |
| `phase2-week3-module-analysis.md` | 过时 | 归档 |
| `phase3-test-reorganization-plan.md` | 过时 | 归档 |
| `refactoring-*.md` (3个) | 重构完成，归档 | 归档 |

---

## 整理目标

1. **统一目录结构** - 遵循现有编号规范
2. **消除重复** - 每个主题只保留一个权威文档
3. **归档过时内容** - 保留历史但不干扰当前文档
4. **改进可导航性** - 清晰的索引和分类

---

## 新的文档结构

```
docs/
├── 00-start.md                    # 快速开始
├── 01-prd/                        # PRD 文档
│   ├── PRD0.md ~ PRD6.md
│   ├── PRD4-diff.md
│   ├── PRD9-diff.md
│   └── PRD_COMPLIANCE_REPORT.md
├── 02-progress/                   # 开发进度 (保留)
│   ├── PRD4-stage1~7-completion-report.md
│   └── skills-implementation-report.md
├── 03-toolkit/                    # Toolkit 指南
├── 04-guides/                     # 用户指南
├── 05-testing/                    # 测试文档
├── 06-status/                     # 当前状态
│   ├── connection-engine-verification.md
│   ├── hybrid-search-verification.md
│   ├── insight-deduplication-verification.md
│   ├── performance-tests-implementation.md
│   ├── prd9-final-summary.md
│   └── FINAL_TEST_REPORT.md
├── 07-archives/                   # 历史归档 (保留)
├── 08-acceptance/                 # 验收文档 (重命名)
├── 09-api/                        # API 文档 (重命名)
├── 10-architecture/               # 架构文档 (重命名)
├── 11-deployment/                 # 部署文档 (重命名)
└── INDEX.md                       # 文档索引
```

---

## 执行步骤

### Step 1: 归档根目录文档
- [ ] 归档 `ACCEPTANCE_VERIFICATION_REPORT.md`
- [ ] 归档 `FINAL_WORK_SUMMARY.md`
- [ ] 归档 `PROJECT_IMPROVEMENTS_SUMMARY.md`
- [ ] 合并 QUICKSTART 文档
- [ ] 合并 DOCKER 文档

### Step 2: 清理 docs/ 根目录
- [ ] 移动 PRD7/PRD8-diff.md 到 01-prd/
- [ ] 归档过时报告到 07-archives/
- [ ] 归档重构文档

### Step 3: 删除重复目录
- [ ] 删除 `docs/progress/` (保留 02-progress)
- [ ] 移动 stage2-4 报告到 02-progress

### Step 4: 重命名目录统一命名
- [ ] `acceptance/` → `08-acceptance/`
- [ ] `api/` → `09-api/`
- [ ] `architecture/` → `10-architecture/`
- [ ] `deployment/` → `11-deployment/`
- [ ] `development/` → `12-development/`

### Step 5: 更新文档索引
- [ ] 更新 `docs/INDEX.md`
- [ ] 更新 `docs/README.md`
- [ ] 更新主 README.md 链接

---

## 执行时间估算

| 步骤 | 时间 | 状态 |
|------|------|------|
| Step 1: 根目录 | 30 min | ⏳ |
| Step 2: docs/ 根目录 | 30 min | |
| Step 3: 删除重复 | 15 min | |
| Step 4: 重命名 | 20 min | |
| Step 5: 更新索引 | 30 min | |
| **总计** | **~2小时** | |

---

## 验收标准

- [ ] 无重复文档
- [ ] 目录命名统一 (编号前缀)
- [ ] 所有链接正确
- [ ] INDEX.md 完整
- [ ] Git 提交清晰

---

**创建者:** Claude (AI Assistant)
**状态:** 执行中
**预计完成:** 2026-02-09
