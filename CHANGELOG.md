# Changelog

All notable changes to AgentOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Multi-tenancy support enhancements
- Advanced context strategies optimization
- Performance improvements for vector search

## [0.1.0] - 2026-02-08

### Added
- Initial release of AgentOS Core
- Modular microkernel + plugin architecture
- Provider pattern for memory, context, and LLM components
- WebSocket-based real-time communication
- FastAPI server with REST API
- Docker containerization support
- Comprehensive test suite (unit, integration, e2e)
- Authentication and authorization system (JWT)
- SQLite database with SQLAlchemy ORM
- Aider integration for coding capabilities
- Coze-style skill system
- Vector memory support (Mem0)
- Advanced context management strategies
- Observability middleware
- Knowledge management with RAG
- Search engine with embeddings
- Multi-provider support (LiteLLM)
- Configuration management (YAML + .env)

### Security
- JWT-based authentication
- Password hashing with bcrypt
- SQL injection prevention with SQLAlchemy
- Input validation with Pydantic

### Documentation
- Product Requirements Documentation (PRD)
- Architecture documentation
- API reference
- User guides
- Testing documentation
- Progress tracking

## [0.0.1] - 2026-01-XX

### Added
- Initial project setup
- Basic agent framework
- Core component architecture

---

## Version Format

The version format follows [Semantic Versioning 2.0.0](https://semver.org/):
- **MAJOR**: Incompatible API changes
- **MINOR**: Backwards-compatible functionality additions
- **PATCH**: Backwards-compatible bug fixes

## Categories

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security vulnerability fixes

---

**Note**: This changelog follows the [Keep a Changelog](https://keepachangelog.com/) format.
