#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109.0",
#     "uvicorn[standard]>=0.27.0",
#     "python-multipart>=0.0.6",
#     "pydantic>=2.5.0",
#     "pydantic-settings>=2.1.0",
#     "doubaoime-asr",
# ]
#
# [tool.uv.sources]
# doubaoime-asr = { git = "https://github.com/starccy/doubaoime-asr" }
# ///
"""
OpenTypeless - Standalone single-file edition.

OpenAI-compatible Speech-to-Text API powered by Doubao IME ASR.

Run:
    uv run doubao_asr_api.py

Environment:
    通过 .env 文件或者 环境变量配置参数：
    | 变量 | 默认值 | 说明 |
    |------|--------|------|
    | `DOUBAO_ASR_HOST` | `127.0.0.1` | 监听地址 |
    | `DOUBAO_ASR_PORT` | `8000` | 监听端口 |
    | `DOUBAO_ASR_DEBUG` | `false` | 调试模式（启用 API 文档） |
    | `DOUBAO_ASR_LOG_LEVEL` | `INFO` | 日志级别（DEBUG/INFO/WARNING/ERROR） |
    | `DOUBAO_ASR_CREDENTIAL_PATH` | `./credentials.json` | 凭据文件路径 |
    | `DOUBAO_ASR_API_KEY` | — | API 密钥（可选），不设置时允许所有请求 |
    | `DOUBAO_ASR_DEFAULT_BACKEND` | `ime` | 默认后端（ime/official） |
    | `DOUBAO_ASR_OFFICIAL_MODE` | `flash` | 官方模式（standard/flash） |
    | `DOUBAO_ASR_OFFICIAL_APP_KEY` | — | 官方 API App Key |
    | `DOUBAO_ASR_OFFICIAL_ACCESS_KEY` | — | 官方 Access Key |
    | `DOUBAO_ASR_OFFICIAL_STANDARD_RESOURCE_ID` | `volc.seedasr.auc` | 官方标准版资源 ID |
    | `DOUBAO_ASR_OFFICIAL_FLASH_RESOURCE_ID` | `volc.bigasr.auc_turbo` | 官方极速版资源 ID |
    | `DOUBAO_ASR_OFFICIAL_MODEL_NAME` | `bigmodel` | 官方极速版模型名 |
    | `DOUBAO_ASR_OFFICIAL_UID` | `opentypeless` | 官方请求中的 user.uid |
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import sys
import time
import urllib.error
import urllib.request
import uuid
from contextlib import asynccontextmanager
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from doubaoime_asr import ASRConfig, ResponseType, transcribe_stream
from fastapi import APIRouter, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

__version__ = "0.1.0"
IME_MODEL_ID = "doubao-asr"
OFFICIAL_MODEL_ID = "doubao-asr-official"
OFFICIAL_STANDARD_MODEL_ID = "doubao-asr-official-standard"
OFFICIAL_FLASH_MODEL_ID = "doubao-asr-official-flash"


# =============================================================================
# Config
# =============================================================================

class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"
    credential_path: str = "./credentials.json"
    device_id: Optional[str] = None
    token: Optional[str] = None
    sample_rate: int = 16000
    channels: int = 1
    frame_duration_ms: int = 20
    api_key: Optional[str] = None
    default_backend: str = "ime"

    # Official file ASR API
    official_mode: str = "flash"
    official_standard_submit_endpoint: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
    official_standard_query_endpoint: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
    official_flash_endpoint: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
    official_standard_resource_id: str = "volc.seedasr.auc"
    official_flash_resource_id: str = "volc.bigasr.auc_turbo"
    official_model_name: str = "bigmodel"
    official_uid: str = "opentypeless"
    official_app_key: Optional[str] = None
    official_access_key: Optional[str] = None
    official_timeout_sec: int = 120
    official_query_interval_sec: float = 1.0
    official_query_timeout_sec: int = 300

    model_config = {"env_prefix": "DOUBAO_ASR_", "env_file": ".env"}


settings = Settings()


# =============================================================================
# Logging
# =============================================================================

def setup_logging():
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    fmt = "[%(asctime)s] %(levelname)s %(name)s - %(message)s"
    if level == logging.DEBUG:
        fmt = "[%(asctime)s] %(levelname)s %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    logger = logging.getLogger("doubao_asr_api")
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


logger = setup_logging()


# =============================================================================
# Models
# =============================================================================

class ResponseFormat(str, Enum):
    JSON = "json"
    TEXT = "text"
    SRT = "srt"
    VERBOSE_JSON = "verbose_json"
    VTT = "vtt"


class TranscriptionResponse(BaseModel):
    text: str = Field(..., description="The transcribed text.")


class VerboseTranscriptionResponse(BaseModel):
    task: str = "transcribe"
    language: str = "zh"
    duration: float = 0.0
    text: str


class ErrorResponse(BaseModel):
    error: dict


class BackendMode(str, Enum):
    IME = "ime"
    OFFICIAL = "official"


class OfficialMode(str, Enum):
    STANDARD = "standard"
    FLASH = "flash"


# =============================================================================
# Service
# =============================================================================

class ASRService:
    def __init__(self):
        self._config: Optional[ASRConfig] = None

    @property
    def config(self) -> ASRConfig:
        if self._config is None:
            kwargs = {
                "credential_path": settings.credential_path,
                "sample_rate": settings.sample_rate,
                "channels": settings.channels,
                "frame_duration_ms": settings.frame_duration_ms,
            }
            if settings.device_id:
                kwargs["device_id"] = settings.device_id
            if settings.token:
                kwargs["token"] = settings.token
            self._config = ASRConfig(**kwargs)
        return self._config

    async def transcribe(self, audio_data: bytes) -> str:
        size = len(audio_data)
        logger.info("Starting transcription: audio_size=%.1f KB", size / 1024)

        final_texts: List[str] = []
        async for response in transcribe_stream(audio_data, config=self.config, realtime=False):
            logger.debug("ASR response: type=%s, text=%r", response.type, getattr(response, "text", None))
            if response.type == ResponseType.FINAL_RESULT:
                final_texts.append(response.text or "")
                logger.info("Final result: %r", response.text)
            elif response.type == ResponseType.ERROR:
                raise RuntimeError(f"ASR error: {response.error_msg}")

        result = "".join(final_texts)
        logger.info("Transcription complete: %d segment(s), total_length=%d", len(final_texts), len(result))
        return result


asr_service = ASRService()


class OfficialASRError(RuntimeError):
    pass


class OfficialASRService:
    def _resolve_credentials(self) -> tuple[str, str]:
        app_key = settings.official_app_key
        access_key = settings.official_access_key

        missing = []
        if not app_key:
            missing.append("DOUBAO_ASR_OFFICIAL_APP_KEY")
        if not access_key:
            missing.append("DOUBAO_ASR_OFFICIAL_ACCESS_KEY")
        if missing:
            raise OfficialASRError(
                f"Official ASR credentials missing: {', '.join(missing)}"
            )
        return app_key, access_key

    @staticmethod
    def _extract_text(payload: dict) -> str:
        result = payload.get("result")
        if isinstance(result, dict):
            text = result.get("text")
            if isinstance(text, str):
                return text
        if isinstance(result, list):
            parts: List[str] = []
            for item in result:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return "".join(parts)
        if isinstance(payload.get("text"), str):
            return payload["text"]
        return ""

    @staticmethod
    def _status_code(payload: dict, headers: dict[str, str]) -> Optional[str]:
        value = headers.get("x-api-status-code")
        if value is None:
            code = payload.get("code")
            return None if code is None else str(code)
        return str(value)

    @staticmethod
    def _status_message(payload: dict, headers: dict[str, str]) -> str:
        return str(payload.get("message") or payload.get("msg") or headers.get("x-api-message") or "unknown error")

    def _request_json(self, url: str, headers: dict[str, str], body: dict) -> tuple[dict, dict[str, str]]:
        request = urllib.request.Request(
            url=url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=settings.official_timeout_sec) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                response_headers = {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise OfficialASRError(f"Official ASR HTTP {exc.code}: {response_body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise OfficialASRError(f"Official ASR request failed: {exc.reason}") from exc

        if not response_body:
            return {}, response_headers

        try:
            payload = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise OfficialASRError("Official ASR returned non-JSON response") from exc

        return payload, response_headers

    def _build_headers(self, resource_id: str, request_id: str, app_key: str, access_key: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Api-App-Key": app_key,
            "X-Api-Access-Key": access_key,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": request_id,
            "X-Api-Sequence": "-1",
        }

    def _build_request_audio(self, audio_data: bytes, audio_url: Optional[str] = None) -> dict[str, str]:
        if audio_url:
            return {"url": audio_url}
        return {"data": base64.b64encode(audio_data).decode("utf-8")}

    def _sync_transcribe_flash(self, audio_data: bytes) -> str:
        app_key, access_key = self._resolve_credentials()
        request_id = str(uuid.uuid4())
        request_uid = settings.official_uid or app_key or "opentypeless"
        headers = self._build_headers(settings.official_flash_resource_id, request_id, app_key, access_key)
        body = {
            "user": {"uid": request_uid},
            "audio": self._build_request_audio(audio_data),
            "request": {"model_name": settings.official_model_name},
        }

        payload, response_headers = self._request_json(settings.official_flash_endpoint, headers, body)
        status_code = self._status_code(payload, response_headers)
        if status_code == "20000003":
            logger.warning("Official ASR (flash) got silence audio: status=20000003")
            return ""
        if status_code and status_code != "20000000":
            raise OfficialASRError(
                f"Official ASR (flash) failed: status={status_code}, message={self._status_message(payload, response_headers)}"
            )

        text = self._extract_text(payload)
        if not text:
            raise OfficialASRError(f"Official ASR (flash) returned empty text: {payload}")
        return text

    def _sync_transcribe_standard(self, audio_data: bytes, audio_url: Optional[str] = None) -> str:
        app_key, access_key = self._resolve_credentials()
        request_id = str(uuid.uuid4())
        request_uid = settings.official_uid or app_key or "opentypeless"
        submit_headers = self._build_headers(settings.official_standard_resource_id, request_id, app_key, access_key)
        submit_body = {
            "user": {"uid": request_uid},
            "audio": self._build_request_audio(audio_data, audio_url),
            "request": {"model_name": settings.official_model_name},
        }
        submit_payload, submit_response_headers = self._request_json(
            settings.official_standard_submit_endpoint,
            submit_headers,
            submit_body,
        )
        submit_status = self._status_code(submit_payload, submit_response_headers)
        if submit_status and submit_status != "20000000":
            raise OfficialASRError(
                f"Official ASR (standard submit) failed: status={submit_status}, message={self._status_message(submit_payload, submit_response_headers)}"
            )

        task_id = submit_response_headers.get("x-api-request-id") or request_id
        query_headers = self._build_headers(settings.official_standard_resource_id, task_id, app_key, access_key)
        query_deadline = time.monotonic() + settings.official_query_timeout_sec

        while True:
            if time.monotonic() >= query_deadline:
                raise OfficialASRError("Official ASR (standard query) timeout")

            query_payload, query_response_headers = self._request_json(
                settings.official_standard_query_endpoint,
                query_headers,
                {},
            )
            query_status = self._status_code(query_payload, query_response_headers)
            if query_status == "20000000":
                text = self._extract_text(query_payload)
                if not text:
                    raise OfficialASRError(f"Official ASR (standard) returned empty text: {query_payload}")
                return text

            if query_status == "20000003":
                logger.warning("Official ASR (standard) got silence audio: status=20000003")
                return ""

            if query_status in {"20000001", "20000002"}:
                time.sleep(settings.official_query_interval_sec)
                continue

            raise OfficialASRError(
                f"Official ASR (standard query) failed: status={query_status}, message={self._status_message(query_payload, query_response_headers)}"
            )

    async def transcribe(
        self,
        audio_data: bytes,
        mode: OfficialMode,
        audio_url: Optional[str] = None,
    ) -> str:
        size = len(audio_data)
        logger.info(
            "Starting official transcription: mode=%s, audio_size=%.1f KB",
            mode.value,
            size / 1024,
        )

        if mode == OfficialMode.STANDARD:
            text = await asyncio.to_thread(self._sync_transcribe_standard, audio_data, audio_url)
        else:
            text = await asyncio.to_thread(self._sync_transcribe_flash, audio_data)

        logger.info("Official transcription complete: mode=%s, total_length=%d", mode.value, len(text))
        return text


official_asr_service = OfficialASRService()


def resolve_backend(model: str) -> BackendMode:
    normalized = model.strip().lower()
    if normalized == OFFICIAL_MODEL_ID:
        return BackendMode.OFFICIAL
    if normalized == OFFICIAL_STANDARD_MODEL_ID:
        return BackendMode.OFFICIAL
    if normalized == OFFICIAL_FLASH_MODEL_ID:
        return BackendMode.OFFICIAL
    if normalized == IME_MODEL_ID:
        return BackendMode.IME
    if normalized == BackendMode.OFFICIAL.value:
        return BackendMode.OFFICIAL
    try:
        return BackendMode(settings.default_backend.lower())
    except ValueError:
        logger.warning(
            "Invalid DOUBAO_ASR_DEFAULT_BACKEND=%r, fallback to ime",
            settings.default_backend,
        )
        return BackendMode.IME


def resolve_official_mode(model: str) -> OfficialMode:
    normalized = model.strip().lower()
    if normalized in {OFFICIAL_STANDARD_MODEL_ID, "official-standard", "standard"}:
        return OfficialMode.STANDARD
    if normalized in {OFFICIAL_FLASH_MODEL_ID, "official-flash", "flash"}:
        return OfficialMode.FLASH
    try:
        return OfficialMode(settings.official_mode.lower())
    except ValueError:
        logger.warning(
            "Invalid DOUBAO_ASR_OFFICIAL_MODE=%r, fallback to flash",
            settings.official_mode,
        )
        return OfficialMode.FLASH


# =============================================================================
# Routes
# =============================================================================

def verify_api_key(authorization: Annotated[Optional[str], Header()] = None):
    if not settings.api_key:
        return True
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": {"message": "Missing Authorization header"}})
    key = authorization[7:] if authorization.startswith("Bearer ") else authorization
    if key != settings.api_key:
        raise HTTPException(status_code=401, detail={"error": {"message": "Invalid API key"}})
    return True


router = APIRouter(prefix="/v1/audio", dependencies=[Depends(verify_api_key)])


def format_srt(text: str) -> str:
    return f"1\n00:00:00,000 --> 00:00:00,000\n{text}\n"


def format_vtt(text: str) -> str:
    return f"WEBVTT\n\n1\n00:00:00.000 --> 00:00:00.000\n{text}\n"


@router.post("/transcriptions")
async def transcribe(
    file: Annotated[UploadFile, File()],
    model: Annotated[str, Form()] = "doubao-asr",
    response_format: Annotated[ResponseFormat, Form()] = ResponseFormat.JSON,
    language: Annotated[Optional[str], Form()] = None,
    prompt: Annotated[Optional[str], Form()] = None,
    temperature: Annotated[Optional[float], Form()] = None,
    audio_url: Annotated[Optional[str], Form()] = None,
):
    backend = resolve_backend(model)
    official_mode = resolve_official_mode(model) if backend == BackendMode.OFFICIAL else None
    logger.info(
        "Request: filename=%s, model=%s, backend=%s, official_mode=%s, format=%s",
        file.filename,
        model,
        backend.value,
        official_mode.value if official_mode else "-",
        response_format.value,
    )
    audio_data = await file.read()
    if not audio_data:
        raise HTTPException(status_code=400, detail={"error": {"message": "Empty audio file"}})

    try:
        if backend == BackendMode.OFFICIAL:
            text = await official_asr_service.transcribe(
                audio_data,
                mode=official_mode or OfficialMode.FLASH,
                audio_url=audio_url,
            )
        else:
            text = await asr_service.transcribe(audio_data)
    except OfficialASRError as exc:
        raise HTTPException(status_code=502, detail={"error": {"message": str(exc)}}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail={"error": {"message": str(exc)}}) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error": {"message": str(exc)}}) from exc

    logger.info("Result: length=%d", len(text))

    match response_format:
        case ResponseFormat.TEXT:
            return PlainTextResponse(content=text)
        case ResponseFormat.SRT:
            return PlainTextResponse(content=format_srt(text))
        case ResponseFormat.VTT:
            return PlainTextResponse(content=format_vtt(text), media_type="text/vtt")
        case ResponseFormat.VERBOSE_JSON:
            return VerboseTranscriptionResponse(text=text, language=language or "zh")
        case _:
            return TranscriptionResponse(text=text)


# =============================================================================
# App
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OpenTypeless v%s", __version__)
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="OpenTypeless",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.debug else None,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "healthy", "version": __version__}


@app.get("/v1/models")
async def models() -> Dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"id": IME_MODEL_ID, "object": "model", "owned_by": "doubao-ime"},
            {
                "id": OFFICIAL_MODEL_ID,
                "object": "model",
                "owned_by": "doubao-official",
                "description": "Official backend, mode from DOUBAO_ASR_OFFICIAL_MODE",
            },
            {
                "id": OFFICIAL_STANDARD_MODEL_ID,
                "object": "model",
                "owned_by": "doubao-official",
                "description": "Official standard mode (submit/query)",
            },
            {
                "id": OFFICIAL_FLASH_MODEL_ID,
                "object": "model",
                "owned_by": "doubao-official",
                "description": "Official flash mode (single request)",
            },
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
