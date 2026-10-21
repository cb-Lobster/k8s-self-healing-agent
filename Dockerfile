# syntax=docker/dockerfile:1

# ============================================================
# Stage 1: builder —— 从国内镜像源下载 k8s 官方 deb 包，解出 kubectl
#          该阶段的 apt 缓存、curl、deb 包都不会进入最终镜像
# ============================================================
FROM debian:bullseye-slim AS builder

# 阿里云 Kubernetes 镜像仓库同步的最后一个 1.28.x 版本（官方 legacy apt repo 已停更）
# deb 包文件名内嵌 sha256，可做完整性校验；如需其他版本，覆盖下面 3 个 ARG 即可
ARG KUBECTL_VERSION=1.28.2-00
ARG KUBECTL_DEB_SHA256=81d72df9025b03499811e33522b4be3d44e75506a3bf122e51e55d29aa73303d
ARG KUBECTL_MIRROR=https://mirrors.aliyun.com/kubernetes/apt/pool
# buildx 构建多架构时会自动注入 TARGETARCH；普通 docker build 用默认值
ARG TARGETARCH=amd64

RUN set -eux; \
    # bullseye 已进入归档阶段，官方源已清空 oldstable 包，改用阿里云 debian-archive 镜像
    printf '%s\n' \
      'deb http://mirrors.aliyun.com/debian-archive/debian bullseye main' \
      'deb http://mirrors.aliyun.com/debian-archive/debian-security bullseye-security main' \
      > /etc/apt/sources.list; \
    echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid-until; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl ca-certificates; \
    rm -rf /var/lib/apt/lists/*; \
    deb="kubectl_${KUBECTL_VERSION}_${TARGETARCH}_${KUBECTL_DEB_SHA256}.deb"; \
    curl -fsSL --retry 3 --connect-timeout 10 -o "/tmp/${deb}" "${KUBECTL_MIRROR}/${deb}"; \
    echo "${KUBECTL_DEB_SHA256}  /tmp/${deb}" | sha256sum -c -; \
    dpkg-deb -x "/tmp/${deb}" /kubectl-root; \
    install -m 0755 /kubectl-root/usr/bin/kubectl /kubectl; \
    rm -rf "/tmp/${deb}" /kubectl-root; \
    /kubectl version --client

# ============================================================
# Stage 2: runtime —— 最终运行镜像，只含 kubectl + Python 应用
# ============================================================
FROM python:3.10-slim

# 保留 HuggingFace 镜像配置（当前轻量关键词检索不依赖外部模型）
ENV HF_ENDPOINT=https://hf-mirror.com \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 从 builder 阶段复制 kubectl：不依赖本地二进制，最终镜像也不含 curl
COPY --from=builder /kubectl /usr/local/bin/kubectl

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
      -i https://mirrors.cloud.tencent.com/pypi/simple

COPY . .

CMD ["python", "-m", "agent.main"]
