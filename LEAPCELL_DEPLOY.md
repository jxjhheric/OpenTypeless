# Leapcell 部署指南

本文档详细介绍如何在 Leapcell 平台上部署 OpenTypeless 服务。

## 目录

- [前提条件](#前提条件)
- [部署步骤](#部署步骤)
- [环境变量配置](#环境变量配置)
- [验证部署](#验证部署)
- [常见问题](#常见问题)

## 前提条件

1. **Leapcell 账户**: 拥有 Leapcell 账号并完成实名认证
2. **GitHub 仓库**: 代码已推送到 GitHub 仓库
3. **字节跳动 ASR 凭证**: 需要从字节跳动开放平台获取以下凭据：
   - App Key
   - Access Key

## 部署步骤

### 1. Fork 或克隆仓库

首先 Fork 本仓库，或者确保你的仓库包含以下文件：

```
.
├── Dockerfile              # Docker 构建文件
├── doubao_asr_api.py       # 主应用程序
├── leapcell.yaml          # Leapcell 部署配置
└── .env.example           # 环境变量示例
```

### 2. 在 Leapcell 创建新项目

1. 登录 [Leapcell 控制台](https://leapcell.io)
2. 点击「新建项目」
3. 选择「从 GitHub 导入」
4. 选择你的仓库和分支

### 3. 配置部署设置

项目导入后，Leapcell 会自动识别 `leapcell.yaml` 配置文件。你可以：

- 确认服务端口为 `8000`
- 确认构建方式为 Docker
- 根据需要调整副本数（默认 1-3）

### 4. 配置环境变量（关键步骤）

在 Leapcell 控制台的「环境变量」或「Secrets」中配置以下敏感信息：

#### 必须配置

| 变量名 | 说明 | 获取方式 |
|--------|------|----------|
| `DOUBAO_ASR_OFFICIAL_APP_KEY` | 官方鉴权 App Key | 字节跳动开放平台 |
| `DOUBAO_ASR_OFFICIAL_ACCESS_KEY` | 官方鉴权 Access Key | 字节跳动开放平台 |

#### 可选配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DOUBAO_ASR_API_KEY` | - | 网关鉴权密钥 |
| `DOUBAO_ASR_DEFAULT_BACKEND` | `official` | 默认后端: `ime` / `official` |
| `DOUBAO_ASR_OFFICIAL_MODE` | `flash` | 官方模式: `standard` / `flash` |

> **注意**: `DOUBAO_ASR_OFFICIAL_APP_KEY` 和 `DOUBAO_ASR_OFFICIAL_ACCESS_KEY` 是必填项，否则 ASR 服务将无法正常工作。

### 5. 部署服务

1. 点击「部署」按钮
2. 等待 Docker 镜像构建完成
3. 部署成功后，系统会分配一个公开访问 URL

## 环境变量详情

### 官方 ASR 模式区别

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `flash` | 极速版，单次请求 | 短音频（< 1分钟），响应更快 |
| `standard` | 标准版，轮询查询 | 长音频，需要等待处理完成 |

### 资源 ID

| 模式 | 资源 ID |
|------|---------|
| standard | `volc.seedasr.auc` |
| flash | `volc.bigasr.auc_turbo` |

## 验证部署

部署完成后，可以通过以下方式验证：

### 1. 健康检查

```bash
curl https://your-app.leapcell.io/health
```

预期响应：
```json
{"status":"ok"}
```

### 2. 模型列表

```bash
curl https://your-app.leapcell.io/v1/models
```

### 3. 语音转文字测试

使用 OpenAI 兼容的音频转录接口：

```bash
curl -X POST https://your-app.leapcell.io/v1/audio/transcriptions \
  -H "Authorization: Bearer $DOUBAO_ASR_API_KEY" \
  -F "file=@your-audio-file.mp3" \
  -F "model=doubao-asr-official-flash"
```

> **注意**: 如果未设置 `DOUBAO_ASR_API_KEY`，可以省略 Authorization 头。

## 常见问题

### Q1: 部署失败，提示端口未监听

确保：
1. `Dockerfile` 中 `EXPOSE 8000` 与 `leapcell.yaml` 中 `service.port: 8000` 一致
2. 应用正确监听了 `0.0.0.0:8000`（而非 `localhost:8000`）

### Q2: ASR 调用返回 401 错误

检查环境变量是否正确配置：
- `DOUBAO_ASR_OFFICIAL_APP_KEY`
- `DOUBAO_ASR_OFFICIAL_ACCESS_KEY`

这些值需要从字节跳动开放平台获取。

### Q3: 音频转录超时

- `flash` 模式适合短音频（< 1分钟）
- 长音频建议使用 `standard` 模式，并调整 `DOUBAO_ASR_OFFICIAL_QUERY_TIMEOUT_SEC`

### Q4: 如何修改后端模式？

修改环境变量 `DOUBAO_ASR_DEFAULT_BACKEND`：
- `ime`: 使用 Doubao IME ASR
- `official`: 使用官方 ASR API

或者在请求中通过 model 参数指定：
- `doubao-asr` (IME)
- `doubao-asr-official`
- `doubao-asr-official-standard`
- `doubao-asr-official-flash`

## 相关链接

- [Leapcell 官方文档](https://leapcell.io/docs)
- [字节跳动开放平台](https://www.volcengine.com/docs/4640)
- [OpenTypeless GitHub 仓库](https://github.com/jxjhheric/OpenTypeless)

## 更新日志

- **2024**: 初始版本，支持 Leapcell 部署
