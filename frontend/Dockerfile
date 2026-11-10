# ============================================================
#  Frontend + Nginx Gateway
#  前端构建 + Nginx 网关（同源 /api 反向代理）
# ============================================================
FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com && npm ci --no-audit --no-fund

COPY frontend/ ./

# 同源部署：浏览器请求 /api，由 Nginx 转发到后端
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
