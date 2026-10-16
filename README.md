# K8s 故障自愈 Agent

基于 LangChain + DeepSeek 的 K8s 智能自愈助手。自动发现异常 Pod，诊断根因，按预设策略执行重启 / 扩容 / 回滚，形成"发现 → 诊断 → 修复 → 验证"闭环。

## 项目背景

K8s 环境里 Pod 异常是家常便饭：CrashLoopBackOff、ImagePullBackOff、OOMKilled、PodPending……传统做法是收到告警后登录服务器，逐条敲 `kubectl get/describe/logs` 排查，再手动修复。本项目利用 AI Agent 把这一整套流程自动化。

## 功能特性

- ReAct Agent 自动决定排查顺序
- 5 个查询工具：get_pods / describe_pod / get_pod_logs / get_events / get_deployments
- 4 个写操作工具：restart / scale / rollback / delete_pod
- 故障类型 → 修复动作对照表（Prompt 内置）
- 安全约束：ImagePullBackOff 不自动修复、每次只修一个问题、修复后必须验证

## 架构

```
用户输入
   ↓
ReAct Agent (LangChain + DeepSeek)
   ↓ 自动决策
   ├── 查询工具：get_pods / describe_pod / get_pod_logs / get_events
   └── 写操作工具：restart / scale / rollback / delete_pod
   ↓
自愈报告
```

## 技术栈

- **Agent 框架**：LangChain (`create_agent`)
- **大模型**：DeepSeek API
- **K8s 环境**：k3d (k3s in Docker)
- **云服务器**：腾讯云轻量应用服务器 (Ubuntu 22.04 LTS)

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/cb-Lobster/k8s-self-healing-agent.git
cd k8s-self-healing-agent
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 搭建 K8s 环境

```bash
# 装 k3d
sudo wget https://github.com/k3d-io/k3d/releases/download/v5.6.3/k3d-linux-amd64 -O /usr/local/bin/k3d
sudo chmod +x /usr/local/bin/k3d

# 起集群
k3d cluster create self-healing --agents 1

# 验证
kubectl get nodes
```

### 4. 配置环境变量

```bash
cp .env.example .env
vim .env  # 填入 DeepSeek API Key
```

### 5. 运行 Agent

```bash
python -m agent.main
```

输入：
```
巡检
```

## 项目结构

```
k8s-self-healing-agent/
├── agent/
│   ├── main.py              # Agent 入口
│   └── tools/
│       ├── k8s_query.py     # 查询类工具
│       └── k8s_action.py    # 写操作工具
├── requirements.txt
├── .env.example
└── README.md
```

## 故障类型 → 修复动作对照表

| 故障类型 | 典型特征 | 推荐动作 |
|---|---|---|
| CrashLoopBackOff（配置错误） | 容器主动 exit，日志显示命令错误 | rollback_deployment |
| CrashLoopBackOff（依赖缺失） | 连不上 DB/Redis 等外部服务 | 通知人工，不自动修复 |
| ImagePullBackOff | 镜像拉取失败 | 通知人工，不自动修复 |
| OOMKilled | 内存超限被杀 | scale_deployment 或通知 |
| PodPending | 资源不足/调度失败 | 通知人工 |
| 无就绪探针 | readiness probe 失败 | restart_deployment |

## 实战演示

**制造故障：**
```bash
kubectl create deployment broken-app --image=nginx:alpine
kubectl patch deployment broken-app -p '{"spec":{"template":{"spec":{"containers":[{"name":"nginx","command":["sh","-c","echo starting; sleep 5; exit 1"]}]}}}}'
```

**Agent 自愈：**
```
巡检需求 > default 命名空间有个 broken-app 一直崩溃，日志显示 exit code 1，这是新版本发布引入的故障，帮我回滚修复
```

**Agent 输出：**
- 发现异常：broken-app CrashLoopBackOff
- 根因诊断：容器命令被覆盖，exit 1
- 修复动作：rollback_deployment
- 验证结果：新 Pod 1/1 Running，Deployment 1/1 可用

## 踩坑记录

- **k3s 镜像拉取超时**：k3s 内部 containerd 不读宿主机 Docker 的镜像源配置，需单独创建 `/etc/rancher/k3s/registries.yaml` 并注入到节点容器，再重启节点。
- **agent 节点没有 `/etc/rancher/k3s` 目录**：先 `docker exec <agent> mkdir -p /etc/rancher/k3s` 再拷贝配置。
- **svclb 镜像 ImagePullBackOff**：k3s 的 Service LB 辅助 Pod，等待镜像源生效后自动恢复，不影响集群使用。
- **ReAct 格式与新版 LangChain 不兼容**：LangChain v1.0+ 已弃用 `create_react_agent`，改用 `create_agent`，调用方式和输出格式都变了。

## 后续计划

- [ ] 接入 ChromaDB RAG 知识库，Agent 检索故障处理 SOP
- [ ] 接入飞书/钉钉 Webhook，实时推送自愈报告
- [ ] 打包 Docker 镜像，用 Deployment 部署到 K8s 集群
- [ ] 配置 RBAC 最小权限，Secret 管理 API Key
- [ ] 加审批机制，高风险操作需人工确认

## License

MIT
