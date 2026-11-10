# AI反诈骗检测系统 v2.0

> 基于 Spring Boot + Vue + Python 的多模态AI反诈骗检测平台
> **团队**：后端开发 | 前端开发 | AI算法

---

## 项目简介

AI反诈骗检测系统是一个毕业设计项目，支持文本、语音、图像三种诈骗检测方式，并提供区块链存证、数字水印、模型训练等辅助功能。

### 核心功能
- **文本诈骗检测** - 基于规则 + 机器学习的文本风险评估
- **语音诈骗检测** - 语音转文字后进行诈骗内容识别
- **图像诈骗检测** - 图片OCR + 诈骗内容检测
- **风险评估** - 多维度综合风险评分
- **区块链存证** - 检测结果上链存证，防篡改
- **数字水印** - 文件水印嵌入与提取
- **Agent 线索研判** - 状态机双暂停（信息补充 / 人工审核）、带出处的研判草稿、失败即关闭（fail-closed）
- **仪表盘** - 数据统计可视化

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Spring Boot 2.5.x + MyBatis Plus + JWT + Redis + AOP |
| 数据库 | MySQL 8.0 |
| 缓存 | Redis 7.x |
| AI服务 | Python 3.x + Flask（HTTP微服务） |
| Agent服务 | Python + FastAPI + LangGraph + MCP（只读工具白名单） |
| 前端 | Vue 3 + Element Plus + ECharts |
| 接口文档 | Swagger 3.0 |
| 部署 | Docker + Docker Compose（Nginx 单入口） |

---

## 交付物与验收材料

| 材料 | 链接 | 说明 |
| --- | --- | --- |
| 演示录屏 | [demo.mp4](docs/assets/demo.mp4) | 46 秒，登录 → 建案 → 补充 → 待审核（5 条引用）→ 管理员复核 → 已完成 |
| 可用性测试 | [可用性测试报告](docs/可用性测试报告.md) | 任务卡、SUS 量表、自动化预演数据；3 人真人测试待执行 |
| 系统测试 | [系统测试报告](docs/系统测试报告.md) | 接口与链路测试记录 |
| 部署说明 | [部署文档](docs/部署文档.md) | 本机开发与 Docker Compose 两种方式 |
| 论文初稿 | [论文初稿](docs/论文初稿.md) | 设计、实现与评测 |
| 需求与设计 | [需求](docs/agent-thesis-requirements.md) · [技术设计](docs/agent-thesis-technical-design.md) · [论文素材](docs/agent-thesis-paper-materials.md) | 可追溯的过程文档 |

录屏时间点：0:00 登录 → 0:07 建案录入 → 0:13 提交 → 0:16 等待补充 → 0:24 待审核（5 条引用）→ 0:32 管理员登录 → 0:40 人工复核 → 0:46 已完成。

---

## 项目结构

```
AI反诈骗/
├── backend/               # Java后端
│   ├── src/main/java/com/cucn/springboot/
│   │   ├── controller/    # 控制层（API接口）
│   │   ├── service/       # 业务层
│   │   ├── mapper/        # 数据访问层
│   │   ├── entity/        # 实体类
│   │   ├── config/        # 配置类
│   │   ├── aspect/        # AOP切面（限流、操作日志）
│   │   ├── annotation/    # 自定义注解
│   │   ├── utils/         # 工具类
│   │   ├── common/        # 公共模块
│   │   └── exception/     # 全局异常处理
│   ├── src/test/          # 单元测试 & 集成测试
│   ├── Dockerfile         # 后端Docker镜像
│   └── pom.xml            # Maven配置
│
├── ai-service/            # Python AI微服务
│   ├── flask_app/         # Flask HTTP服务入口
│   │   ├── app.py         # API路由
│   │   └── requirements.txt
│   ├── anti_fraud_text.py # 文本检测算法
│   ├── anti_fraud_voice.py# 语音检测算法
│   ├── anti_fraud_image.py# 图像检测算法
│   ├── risk_assessment.py # 风险评估
│   ├── blockchain_cert.py # 区块链存证
│   ├── multimodal_features.py  # 多模态特征提取
│   ├── data/              # 数据集
│   ├── models/            # 训练好的模型文件
│   ├── scripts/           # 数据采集/预处理/训练脚本
│   ├── archive/           # 旧版脚本归档
│   └── blockchain_data/   # 区块链数据
│
├── frontend/              # 前端（Vue 3 + Element Plus）
│
├── sql/                   # 数据库脚本
│   ├── anti_fraud.sql     # 初始化脚本（全新安装）
│   └── upgrade_v2.sql     # v2升级脚本（已有库升级用）
│
├── docs/                  # 技术文档
│   ├── 数据库设计文档.md
│   ├── 系统测试报告.md
│   ├── 部署文档.md
│   └── fraud_detection_results/  # 模型训练结果
│
├── 任务书/                # 分工任务文档
│   ├── 后端开发任务书.md
│   ├── 前端开发任务书.md
│   ├── AI算法开发任务书.md
│   └── 团队协作规范.md
│
├── Dockerfile.ai          # AI服务Docker镜像
├── docker-compose.yml     # 一键部署编排
├── nginx.conf             # Nginx反向代理配置
├── .env.template          # 环境变量模板
└── README.md              # 本文件
```

---

## 快速开始

### 极速启动（命令速查）

> 第一次部署按顺序执行；日常启动只需第 3~5 步。

```bash
# 1. 初始化数据库（第一次部署执行一次；在Navicat或mysql命令行运行sql文件夹下的脚本）
mysql -u root -p < sql/anti_fraud.sql

# 2. 启动 Redis 服务（保持窗口开着，或注册为Windows服务）
redis-server.exe

# 3. 启动 AI 服务（Python）
cd ai-service
pip install -r requirements.txt
cd flask_app
python app.py

# 4. 启动 Java 后端
cd backend
mvn spring-boot:run

# 5. 启动前端
cd frontend
npm install
npm run dev
```

启动后访问：前端 http://localhost:5173 ｜ 后端 http://localhost:9090/health ｜ AI服务 http://localhost:5000/api/health

各步骤的详细说明见下方。

### 环境要求

| 软件 | 版本要求 | 检查命令 |
|------|---------|---------|
| JDK | 17+ | `java -version` |
| Maven | 3.6+ | `mvn -v` |
| MySQL | 8.0+ | `mysql --version` |
| Redis | 6.0+ | `redis-cli ping` |
| Python | 3.8 ~ 3.11 | `python --version` |
| Node.js | 16 ~ 18（前端用） | `node -v` |

---

### 第一步：数据库初始化

#### 全新安装（第一次用）

1. 打开Navicat或MySQL命令行，创建数据库：
   ```sql
   CREATE DATABASE anti_fraud DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

2. 执行初始化脚本（一步到位，包含所有v2功能）：
   ```bash
   mysql -u root -p anti_fraud < sql/anti_fraud.sql
   ```

#### 已有数据库（从v1升级）

直接执行升级脚本即可：
```bash
mysql -u root -p anti_fraud < sql/upgrade_v2.sql
```

> 升级脚本是幂等的，重复执行不会报错。

---

### 第二步：启动 Redis

确保Redis在运行：

```bash
# Windows：找到Redis安装目录，运行
redis-server.exe

# 或者用Docker
docker run -d -p 6379:6379 redis:7-alpine
```

验证：
```bash
redis-cli ping
# 返回 PONG 表示正常
```

---

### 第三步：启动 Python AI 服务

```bash
cd ai-service/flask_app

# 安装依赖（第一次需要）
pip install -r requirements.txt

# 启动Flask服务
python app.py
```

验证：浏览器打开 http://localhost:5000/api/health
返回 `{"status": "ok"}` 表示正常。

---

### 第四步：启动 Java 后端

#### 方式一：IDEA（推荐开发用）

1. 用IDEA打开项目（File → Open → 选择 `backend/pom.xml` → Open as Project）
2. 等待Maven依赖下载完成
3. 找到 `src/main/java/com/cucn/springboot/SpringbootApplication.java`
4. 右键 → Run 'SpringbootApplication'
5. 看到 `Started SpringbootApplication` 表示启动成功

#### 方式二：命令行

```bash
cd backend
mvn spring-boot:run
```

#### 验证后端

| 地址 | 说明 |
|------|------|
| http://localhost:9090/health | 健康检查，看各组件状态 |
| http://localhost:9090/swagger-ui/index.html | 接口文档（Swagger） |

健康检查返回示例：
```json
{
  "code": "200",
  "data": {
    "status": "ok",
    "components": {
      "backend": "ok",
      "database": "ok",
      "redis": "ok",
      "aiService": "ok"
    }
  }
}
```

四个组件都是 `ok` 就是全正常了。

---

### 第五步：测试登录

打开 Swagger 文档：http://localhost:9090/swagger-ui/index.html

找到 **user-controller → POST /user/login**，点 **Try it out**，输入：

```json
{
  "username": "admin",
  "password": "AntiFraud@2026"
}
```

点 Execute，返回的 `data` 里有 `token`，复制它。

然后点页面右上角的 **Authorize** 按钮，输入：
```
Bearer 你的token值
```
（注意 Bearer 和 token 之间有空格）

之后调用其他接口就自动带上token了。

---

## 前端开发指南

### 接口调用规范

- **Base URL**: `http://localhost:9090`
- **认证方式**: 请求头加 `token: 你的token值`（注意是 `token`，不是 `Authorization`）
- **返回格式**: 统一使用 `Result` 包装
  ```json
  {
    "code": "200",    // "200"成功，"401"未认证，"600"业务错误
    "msg": "",        // 错误信息
    "data": {}        // 返回数据
  }
  ```

### 主要接口列表

| 模块 | 接口 | 说明 | 鉴权 |
|------|------|------|------|
| 用户 | POST /user/login | 登录 | ❌ |
| 用户 | POST /user/register | 注册 | ❌ |
| 用户 | POST /user/logout | 登出 | ❌ |
| 用户 | GET /user/username/{username} | 根据用户名查用户 | ✅ |
| 用户 | PUT /user/password | 修改密码 | ✅ |
| 检测 | POST /detect/text | 文本诈骗检测 | ✅ |
| 检测 | POST /detect/voice | 语音诈骗检测 | ✅ |
| 检测 | POST /detect/image | 图像诈骗检测 | ✅ |
| 检测 | GET /detect/records | 检测记录列表 | ✅ |
| 检测 | GET /detect/records/{id} | 检测记录详情 | ✅ |
| 仪表盘 | GET /dashboard/summary | 统计概览 | ✅ |
| 仪表盘 | GET /dashboard/trend | 趋势数据 | ✅ |
| 文件 | POST /file/upload | 文件上传 | ✅ |
| 文件 | GET /file/{id} | 文件下载 | ✅ |
| 区块链 | POST /blockchain/cert | 区块链存证 | ✅ |
| 水印 | POST /watermark/embed | 嵌入水印 | ✅ |
| 水印 | POST /watermark/extract | 提取水印 | ✅ |
| 健康检查 | GET /health | 系统健康状态 | ❌ |

> 完整接口列表请访问 Swagger 文档：http://localhost:9090/swagger-ui/index.html

### 跨域

后端已配置CORS，前端直接调用 `http://localhost:9090` 即可，无需额外配置。

### 前端开发建议

- 新前端使用 **Vue 3 + Element Plus + ECharts**，代码在 `frontend/` 目录
- 启动方式：`cd frontend && npm install && npm run dev`
- 接口联调有问题联系后端开发

---

## AI算法开发指南

### AI服务架构

Python代码不再是被Java命令行调用的脚本了，而是**独立的HTTP微服务**，通过REST API和Java后端通信。

### 核心文件

| 文件 | 说明 |
|------|------|
| `ai-service/flask_app/app.py` | Flask HTTP服务入口（API路由都在这里） |
| `ai-service/anti_fraud_text.py` | 文本检测算法 |
| `ai-service/anti_fraud_voice.py` | 语音检测算法 |
| `ai-service/anti_fraud_image.py` | 图像检测算法 |
| `ai-service/risk_assessment.py` | 风险评估模块 |
| `ai-service/blockchain_cert.py` | 区块链存证 |
| `ai-service/watermark.py` | 数字水印 |
| `ai-service/model.py` | 机器学习模型定义 |

### API 接口（AI服务）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/detect/text` | POST | 文本检测 |
| `/api/detect/voice` | POST | 语音检测 |
| `/api/detect/image` | POST | 图像检测 |
| `/api/risk/assess` | POST | 风险评估 |
| `/api/blockchain/cert` | POST | 区块链存证 |
| `/api/watermark/embed` | POST | 嵌入水印 |
| `/api/watermark/extract` | POST | 提取水印 |

### 添加新算法的步骤

1. 在 `ai-service/` 下写好你的算法模块
2. 在 `ai-service/flask_app/app.py` 里加一个API路由
3. 重启AI服务，用Postman或Swagger测试接口
4. 通知后端开发在Java后端加对应的Client调用

### 数据目录

- 训练数据放 `ai-service/data/` 目录
- 模型文件放 `ai-service/models/` 目录（已加入.gitignore，不会上传到git）

---

## 配置说明

主要配置都在 `backend/src/main/resources/application.yml`，通过环境变量可以覆盖：

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| 服务端口 | `SERVER_PORT` | 9090 | 后端HTTP端口 |
| 数据库地址 | `DB_HOST` | localhost | MySQL地址 |
| 数据库端口 | `DB_PORT` | 3306 | MySQL端口 |
| 数据库名 | `DB_NAME` | anti_fraud | 数据库名称 |
| 数据库用户 | `DB_USERNAME` | root | MySQL用户名 |
| 数据库密码 | `DB_PASSWORD` | root | MySQL密码 |
| Redis地址 | `REDIS_HOST` | localhost | Redis地址 |
| Redis端口 | `REDIS_PORT` | 6379 | Redis端口 |
| Redis密码 | `REDIS_PASSWORD` | （空） | Redis密码 |
| AI服务地址 | `AI_SERVICE_URL` | http://localhost:5000 | Python AI服务地址 |
| JWT密钥 | `JWT_SECRET` | （内置默认值） | 生产环境务必修改 |
| JWT过期时间 | `JWT_EXPIRE_HOURS` | 24 | Token有效期（小时） |

---

## Docker 一键部署

```bash
# 复制环境变量模板
cp .env.template .env

# 修改 .env 里的密码等配置

# 一键启动全部服务
docker compose up -d --build
```

启动完成后统一从 Nginx 进入：<http://localhost>（前端与 `/api` 同源，无需再单独起前端）。
默认管理员：`admin / AntiFraud@2026`，**首次登录后请立即修改密码**。

本机 3306/6379 被占用时，在 `.env` 里改宿主端口即可，例如：

```dotenv
MYSQL_PORT=3307
REDIS_PORT=6380
NGINX_HTTP_PORT=80
```

详细部署说明见 [docs/部署文档.md](docs/部署文档.md)

---

## 常见问题

### Q1: 启动后端报数据库连接失败

确保MySQL已启动，检查 `backend/src/main/resources/application.yml` 里的数据库地址、用户名、密码是否正确。

### Q2: Redis连接失败

启动Redis服务，或安装Redis：
- Windows：下载安装包 https://github.com/microsoftarchive/redis/releases
- Docker：`docker run -d -p 6379:6379 redis:7-alpine`

### Q3: AI服务检测失败

检查Python Flask服务是否启动，访问 http://localhost:5000/api/health 验证。
如果是语音检测报错，检查是否安装了ffmpeg。

### Q4: Swagger页面404

正确地址是 `http://localhost:9090/swagger-ui/index.html`（不是 `/swagger-ui.html`）。

### Q5: 接口返回401"无token"

需要先登录获取token，然后在请求头里加上 `token: 你的token值`。
Swagger里点右上角 Authorize 按钮输入token。

---

## 项目文档

详细文档在 `docs/` 目录：

| 文档 | 说明 |
|------|------|
| [数据库设计文档](docs/数据库设计文档.md) | 数据库表结构、ER图、设计规范 |
| [系统测试报告](docs/系统测试报告.md) | 测试用例、安全测试、性能测试计划 |
| [部署文档](docs/部署文档.md) | Docker部署、Nginx配置、运维指南 |

---

## 开发规范

### Git 提交规范

```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式调整
refactor: 重构
test: 测试相关
chore: 构建/工具配置
```

### 分支策略

- `master` — 主分支，稳定版本
- `dev` — 开发分支
- `feature/xxx` — 功能分支

---

**最后更新**：2026-09-17
**版本**：v2.0
