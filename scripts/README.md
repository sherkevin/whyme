# Scripts 目录

本目录包含各种实用脚本，用于项目设置、部署和维护。

## 目录结构

### setup/
初始化和设置脚本

- `install_deps.sh` - 安装依赖
- `init_db.sh` - 初始化数据库
- `setup_env.sh` - 设置环境

### deploy/
部署相关脚本

- `deploy.sh` - 部署到生产环境
- `rollback.sh` - 回滚部署
- `health_check.sh` - 健康检查

### migration/
数据迁移脚本

- `migrate.sh` - 运行数据库迁移
- `rollback_migration.sh` - 回滚迁移
- `seed_data.sh` - 种子数据

### dev/
开发辅助脚本

- `format.sh` - 代码格式化
- `lint.sh` - 代码检查
- `test.sh` - 运行测试
- `serve.sh` - 启动开发服务器

## 使用方法

```bash
# 运行设置脚本
./scripts/setup/install_deps.sh

# 运行测试
./scripts/dev/test.sh

# 部署到生产
./scripts/deploy/deploy.sh production
```

## 添加新脚本

1. 将脚本放入相应的子目录
2. 添加执行权限: `chmod +x script_name.sh`
3. 在本文件中添加说明
4. 确保脚本有适当的错误处理

## 注意事项

- 所有脚本应该以 `set -e` 开始，以便在错误时退出
- 使用相对路径，以便从项目根目录运行
- 添加适当的日志记录
- 测试脚本后再提交

---
**维护者**: AgentOS Team
**最后更新**: 2026-02-09
