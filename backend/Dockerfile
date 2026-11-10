# ============================================================
#  Java Backend Dockerfile
#  AI反诈骗检测系统 - Java后端
# ============================================================

# Build stage: compile Java source
# 构建阶段：编译Java源码
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /app

# Copy pom.xml first (better layer caching)
# 先复制pom.xml（利用Docker层缓存）
COPY pom.xml .
COPY settings-docker.xml /root/.m2/settings.xml
RUN mvn dependency:go-offline -B

# Copy source code and build
# 复制源码并构建
COPY src ./src
RUN mvn package -DskipTests -B -q

# ============================================================
# Runtime stage: run the application
# 运行阶段：启动应用
# ============================================================
FROM eclipse-temurin:17-jre-jammy

WORKDIR /app

# Install necessary tools
# 安装必要工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy jar from build stage
# 从构建阶段复制jar包
COPY --from=builder /app/target/*.jar app.jar

# Create data directories
# 创建数据目录
RUN mkdir -p /app/files /app/data

# Environment variables (can be overridden at runtime)
# 环境变量（运行时可覆盖）
ENV SPRING_PROFILES_ACTIVE=prod
ENV JAVA_OPTS="-Xms256m -Xmx512m"

# Expose port
# 暴露端口
EXPOSE 9090

# Health check
# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:9090/health/liveness || exit 1

# Start command
# 启动命令
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
