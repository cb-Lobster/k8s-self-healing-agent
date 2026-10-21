# Kubernetes 故障排查标准操作手册 (SOP)

## 1. 故障现象：CrashLoopBackOff (容器反复崩溃)
- **可能原因**：应用程序代码报错、启动命令配置错误、缺少环境变量、依赖服务（如数据库）未就绪。
- **排查步骤**：
  1. 执行 `kubectl logs <pod-name> --tail=100` 查看最新日志，寻找 Error、Exception 或 Exit Code。
  2. 执行 `kubectl describe pod <pod-name>` 查看 Events 和 Last State，确认退出码（如 Exit Code 1 通常为应用自身错误，137 为被 OOMKilled）。
- **修复建议**：若因为配置更改导致应用启动失败，优先使用 `rollback_deployment` 工具进行回滚。

## 2. 故障现象：ImagePullBackOff (镜像拉取失败)
- **可能原因**：镜像名称拼写错误、镜像仓库网络不可达（国内常见）、私有仓库鉴权失败（缺少 ImagePullSecret）。
- **排查步骤**：
  1. 执行 `kubectl describe pod <pod-name>` 查看 Events 中的具体报错（如 `i/o timeout` 或 `Unauthorized`）。
- **修复建议**：不建议直接重启。需人工确认镜像是否正确，或检查集群的 `registries.yaml` 镜像加速配置。

## 3. 故障现象：OOMKilled (内存溢出被杀)
- **可能原因**：容器运行内存超过了 YAML 中定义的 limits 限制。
- **排查步骤**：
  1. 执行 `kubectl describe pod <pod-name>`，查看 Last State 的 Reason 是否为 `OOMKilled`。
- **修复建议**：使用 `scale_deployment` 扩容副本分担压力，或者通知人工调大 Deployment 的 resources.limits.memory。

## 4. 故障现象：Pod Pending (调度失败)
- **可能原因**：节点资源不足（CPU/内存不够）、没有满足亲和性规则、PVC 存储卷挂载失败。
- **排查步骤**：
  1. 执行 `kubectl describe pod <pod-name>`，查看 Events 中是否有 `Insufficient cpu/memory`。
- **修复建议**：属于集群资源问题，需人工介入扩容节点或清理无用资源。Agent 不应自动处理。

## 5. 故障现象：Readiness probe failed (就绪探针失败)
- **可能原因**：应用启动较慢，在规定时间内未完成健康检查；或者健康检查接口路径配置错误。
- **排查步骤**：
  1. 执行 `kubectl describe pod <pod-name>` 查看探针失败的具体信息。
- **修复建议**：使用 `restart_deployment` 尝试滚动重启。
