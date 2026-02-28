# OpenTypeless

一个将豆包 ASR 能力封装为 OpenAI 兼容接口的小项目，支持 Docker 启动，并提供一份可配合 Spokenly 使用的参考修正提示词，实现和 Typeless 类似的语音修正效果。

当前支持两种 ASR 后端：

1. **IME 协议模式（原有方式）**：通过 `doubaoime-asr` 连接豆包输入法 ASR 协议。
2. **官方 API 模式**：支持官方录音文件识别 **标准版** 与 **极速版**（App Key + Access Key）。

## 项目目的

1. 提供豆包 ASR to API 功能（OpenAI 兼容），可通过 Docker 一键启动。
2. 提供一份参考修正提示词（见 `推荐提示词.md`），可配合 Spokenly 对语音转写结果做稳定整理与纠错。

## API 服务说明

- 服务根地址（Docker 映射后）：`http://127.0.0.1:8836`
- OpenAI 兼容前缀：`/v1`
- 主要接口：`POST /v1/audio/transcriptions`
- 模型列表：`GET /v1/models`
- 健康检查：`GET /health`

## 后端选择（重点）

你可以通过 `model` 参数在一次请求内选择后端：

- `doubao-asr`：IME 协议模式（原有）
- `doubao-asr-official`：官方 API 模式（具体标准/极速由 `DOUBAO_ASR_OFFICIAL_MODE` 决定）
- `doubao-asr-official-standard`：官方标准版
- `doubao-asr-official-flash`：官方极速版

也可以通过环境变量设置默认后端：

- `DOUBAO_ASR_DEFAULT_BACKEND=ime`
- `DOUBAO_ASR_DEFAULT_BACKEND=official`

说明：如果传入了上述两个模型之一，会优先按模型选择；否则回落到 `DOUBAO_ASR_DEFAULT_BACKEND`。

## 官方 API 模式配置

配置文件名：项目根目录下的 `.env`（可先从 `.env.example` 复制）。

启用官方 API 模式时至少需要配置：

- `DOUBAO_ASR_OFFICIAL_APP_KEY`
- `DOUBAO_ASR_OFFICIAL_ACCESS_KEY`

官方模式选择：

- `DOUBAO_ASR_OFFICIAL_MODE=standard`（标准版，submit/query 轮询）
- `DOUBAO_ASR_OFFICIAL_MODE=flash`（极速版，单次请求返回，默认）

可选配置：

- `DOUBAO_ASR_OFFICIAL_STANDARD_SUBMIT_ENDPOINT`（默认 `https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit`）
- `DOUBAO_ASR_OFFICIAL_STANDARD_QUERY_ENDPOINT`（默认 `https://openspeech.bytedance.com/api/v3/auc/bigmodel/query`）
- `DOUBAO_ASR_OFFICIAL_FLASH_ENDPOINT`（默认 `https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash`）
- `DOUBAO_ASR_OFFICIAL_STANDARD_RESOURCE_ID`（默认 `volc.seedasr.auc`）
- `DOUBAO_ASR_OFFICIAL_FLASH_RESOURCE_ID`（默认 `volc.bigasr.auc_turbo`）
- `DOUBAO_ASR_OFFICIAL_MODEL_NAME`（默认 `bigmodel`）
- `DOUBAO_ASR_OFFICIAL_UID`（默认 `opentypeless`）
- `DOUBAO_ASR_OFFICIAL_TIMEOUT_SEC`（默认 `120`）
- `DOUBAO_ASR_OFFICIAL_QUERY_INTERVAL_SEC`（标准版 query 轮询间隔，默认 `1.0`）
- `DOUBAO_ASR_OFFICIAL_QUERY_TIMEOUT_SEC`（标准版 query 总超时，默认 `300`）

## Docker 启动

在项目根目录执行：

```bash
docker compose up -d --build
```

常用命令：

```bash
# 查看状态
docker compose ps

# 查看日志
docker compose logs -f doubao-asr-api

# 停止
docker compose down
```

## Spokenly 配置参考

- URL：`http://127.0.0.1:8836`（不要手动加 `/v1`）
- 模型：
  - `doubao-asr`（IME）
  - `doubao-asr-official`（官方，按 `DOUBAO_ASR_OFFICIAL_MODE` 选择标准/极速）
  - `doubao-asr-official-standard`（官方标准版）
  - `doubao-asr-official-flash`（官方极速版）
- API 密钥：按你的服务配置（未开启可留空）

说明：Spokenly 的 OpenAI 兼容模式会自动拼接 API 路径；若手动填写 `/v1`，可能变成重复路径（如 `/v1/v1/...`）并返回 `Not Found`。

### Spokenly 快速配置（推荐）

1. 在项目根目录复制配置文件：

```bash
cp .env.example .env
```

2. 编辑 `.env`，至少填写以下字段：

```env
DOUBAO_ASR_API_KEY=sk-your-gateway-key
DOUBAO_ASR_DEFAULT_BACKEND=official
DOUBAO_ASR_OFFICIAL_MODE=flash
DOUBAO_ASR_OFFICIAL_APP_KEY=your-app-key
DOUBAO_ASR_OFFICIAL_ACCESS_KEY=your-access-key
```

3. 重启服务：

```bash
docker compose up -d --build
```

4. 在 Spokenly 中填写：

- URL：`http://127.0.0.1:8836`
- API Key：填写 `.env` 里的 `DOUBAO_ASR_API_KEY`
- 模型：`doubao-asr-official-flash`（推荐）

如果你想切到官方标准版：

- 模型改为 `doubao-asr-official-standard`
- 或保留模型 `doubao-asr-official`，把 `.env` 中 `DOUBAO_ASR_OFFICIAL_MODE` 改为 `standard`

## Docker 环境变量示例

在 `docker-compose.yml` 的 `environment` 下添加：

```yaml
# 默认后端（ime 或 official）
DOUBAO_ASR_DEFAULT_BACKEND: ime

# 仅官方 API 模式需要
# DOUBAO_ASR_OFFICIAL_APP_KEY: your-app-key
# DOUBAO_ASR_OFFICIAL_ACCESS_KEY: your-access-key
# DOUBAO_ASR_OFFICIAL_MODE: flash
# DOUBAO_ASR_OFFICIAL_STANDARD_RESOURCE_ID: volc.seedasr.auc
# DOUBAO_ASR_OFFICIAL_FLASH_RESOURCE_ID: volc.bigasr.auc_turbo
# DOUBAO_ASR_OFFICIAL_MODEL_NAME: bigmodel
# DOUBAO_ASR_OFFICIAL_UID: your-uid
```

## 参考提示词与关键应用场景

参考提示词文件：`推荐提示词.md`

该提示词重点覆盖以下场景：

1. **局部自我修正，不丢上下文**  
   只修正当前片段，同时保留前后无关内容。  
   预期输入：
   ```text
   我明天上午十点开会，下午去银行，不对，下午去医院拿报告，晚上回家写周报
   ```
   预期输出：
   ```text
   我明天上午十点开会，下午去医院拿报告，晚上回家写周报
   ```

2. **多事项结构化输出**  
   识别“第一/第二/第三”等并列项时，转换为阿拉伯数字列表，且每项换行，输出更清晰。  
   预期输入：
   ```text
   我一会儿出门要做三件事，第一去超市买牛奶和鸡蛋，第二去取快递，第三给妈妈打电话，完事回家
   ```
   预期输出：
   ```text
   我一会儿出门要做三件事
   1. 去超市买牛奶和鸡蛋
   2. 去取快递
   3. 给妈妈打电话
   完事回家
   ```

3. **热词驱动纠错**  
   对专有名词（如 `DeepSeek`）进行发音近似纠错，减少 ASR 误识别。  
   预期输入：
   ```text
   转写文本：我把模型切到 Deep Sick R1，再比较下 Qwen 和 Deep Seat
   热词表：DeepSeek, DeepSeek-R1, Qwen
   ```
   预期输出：
   ```text
   我把模型切到 DeepSeek-R1，再比较下 Qwen 和 DeepSeek
   ```

4. **保留口语风格、删除无效语气词**  
   尽量保留用户说话习惯，同时清理“嗯/啊”等无实义语气词，提升可读性。  
   预期输入：
   ```text
   嗯 这个方案啊 我觉得吧 先小范围试一下 然后再全量 这样更稳
   ```
   预期输出：
   ```text
   这个方案我觉得先小范围试一下，然后再全量，这样更稳
   ```

## License

MIT
