"""
services/kie_gateway.py
========================
KIE.AI Unified API Gateway — 统一 API 网关

All AI model API calls go through KIE.AI platform:
    - Video generation (Seedance, Veo, Sora, Runway, Kling)
    - Image generation (Seedream, Nano Banana, FLUX)
    - TTS (ElevenLabs multilingual)
    - Lip-sync (Kling AI Avatar, InfiniteTalk)
    - Chat/LLM (GPT-5.2, Gemini 3 Flash/Pro)

API Architecture:
    POST /api/v1/jobs/createTask  → submit async task (Sora, Seedance, Kling, etc.)
    GET  /api/v1/jobs/recordInfo  → poll task status (Sora, Seedance, Kling, etc.)
    POST /api/v1/veo/generate    → Veo 3.1 video generation (dedicated endpoint)
    GET  /api/v1/veo/record-info → Veo 3.1 task status (dedicated endpoint)
    POST /api/v1/runway/generate → Runway video generation (dedicated endpoint)
    GET  /api/v1/runway/record-detail → Runway task status (dedicated endpoint)
    POST /{model}/v1/chat/completions → OpenAI-compatible chat

File Upload (for image-to-video):
    POST https://kieai.redpandaai.co/api/file-base64-upload  → upload via base64
    POST https://api.kie.ai/api/file-url-upload               → upload via URL
    Files are temporary (auto-deleted after 3 days)
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import aiohttp

from utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

KIE_BASE_URL = "https://api.kie.ai"

# File upload uses a different base URL (confirmed working March 2026)
KIE_UPLOAD_BASE_URL = "https://kieai.redpandaai.co"

# Generic endpoints (Sora, Seedance, Kling, Hailuo, etc.)
KIE_CREATE_TASK = f"{KIE_BASE_URL}/api/v1/jobs/createTask"
KIE_QUERY_TASK = f"{KIE_BASE_URL}/api/v1/jobs/recordInfo"

# Veo 3.1 dedicated endpoints
KIE_VEO_GENERATE = f"{KIE_BASE_URL}/api/v1/veo/generate"
KIE_VEO_QUERY = f"{KIE_BASE_URL}/api/v1/veo/record-info"

# Runway dedicated endpoints
KIE_RUNWAY_GENERATE = f"{KIE_BASE_URL}/api/v1/runway/generate"
KIE_RUNWAY_QUERY = f"{KIE_BASE_URL}/api/v1/runway/record-detail"

KIE_CHAT_BASE = KIE_BASE_URL  # e.g. /gemini-2.5-flash/v1/chat/completions

DEFAULT_TIMEOUT = 60
DOWNLOAD_TIMEOUT = 300
POLL_INTERVAL = 15  # seconds between polls
MAX_POLL_RETRIES = 120  # 30 min max wait


class TaskState(str, Enum):
    """KIE.AI task states."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Provider routing: determines which endpoint set to use
class KieProvider(str, Enum):
    """API provider routing for different model families."""
    GENERIC = "generic"   # /api/v1/jobs/createTask + recordInfo
    VEO = "veo"           # /api/v1/veo/generate + record-info
    RUNWAY = "runway"     # /api/v1/runway/generate + record-detail


@dataclass
class KieTask:
    """Represents a KIE.AI async task."""
    task_id: str
    model: str
    provider: KieProvider = KieProvider.GENERIC
    state: TaskState = TaskState.PENDING
    result_urls: list[str] = field(default_factory=list)
    result_json: Optional[str] = None
    cost_time: int = 0  # ms
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


# ──────────────────────────────────────────────────────────────
# KIE Gateway
# ──────────────────────────────────────────────────────────────

class KieGateway:
    """
    Unified API gateway for all KIE.AI model calls.

    Handles provider-specific endpoint routing:
    - Veo 3.1: dedicated /api/v1/veo/* endpoints
    - Runway: dedicated /api/v1/runway/* endpoints
    - Others (Sora, Seedance, Kling, etc.): generic /api/v1/jobs/* endpoints

    Usage:
        gw = KieGateway(config)
        task = await gw.create_task("bytedance/seedance-1.5-pro", {
            "prompt": "A cat playing piano",
            "duration": 10,
            "aspect_ratio": "9:16"
        })
        result = await gw.wait_for_task(task.task_id)
        local_path = await gw.download(result.result_urls[0], "/tmp/video.mp4")
    """

    def __init__(self, config: dict):
        self.config = config
        kie_config = config.get("kie", {})
        self._api_key = kie_config.get("api_key", "")
        self._callback_url = kie_config.get("callback_url", "")
        self._poll_interval = kie_config.get("poll_interval", POLL_INTERVAL)
        self._max_retries = kie_config.get("max_poll_retries", MAX_POLL_RETRIES)

        if not self._api_key:
            logger.warning("KIE.AI API key not configured — model calls will fail")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    # ── Task Creation ───────────────────────────────────────

    async def create_task(
        self,
        model: str,
        input_params: dict,
        callback_url: Optional[str] = None,
        provider: KieProvider = KieProvider.GENERIC,
    ) -> KieTask:
        """
        Submit an async generation task to KIE.AI.

        Routes to the appropriate endpoint based on provider:
        - GENERIC: /api/v1/jobs/createTask (body: {model, input, callBackUrl})
        - VEO: /api/v1/veo/generate (body: {model, prompt, imageUrls, ...})
        - RUNWAY: /api/v1/runway/generate (body: {model, prompt, imageUrl, ...})

        Args:
            model: Model identifier
            input_params: Model-specific input parameters
            callback_url: Optional webhook URL for completion notification
            provider: Which KIE.AI endpoint family to use

        Returns:
            KieTask with task_id for polling
        """
        cb_url = callback_url or self._callback_url

        if provider == KieProvider.VEO:
            url = KIE_VEO_GENERATE
            # Veo uses flat body structure (not nested under "input")
            body: dict[str, Any] = {
                "model": model,
                **input_params,
            }
            if cb_url:
                body["callBackUrl"] = cb_url

        elif provider == KieProvider.RUNWAY:
            url = KIE_RUNWAY_GENERATE
            # Runway also uses flat body structure
            body = {
                "model": model,
                **input_params,
            }
            if cb_url:
                body["callBackUrl"] = cb_url

        else:
            # Generic: Sora, Seedance, Kling, Hailuo, etc.
            url = KIE_CREATE_TASK
            body = {
                "model": model,
                "input": input_params,
            }
            if cb_url:
                body["callBackUrl"] = cb_url

        logger.info(
            f"KIE createTask: provider={provider.value}, model={model}, "
            f"url={url}, input_keys={list(input_params.keys())}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=body,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as resp:
                resp_text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(
                        f"KIE createTask error {resp.status}: {resp_text[:500]}"
                    )
                data = await resp.json(content_type=None)

        code = data.get("code", 0)
        if code != 200:
            msg = data.get("msg", "Unknown error")
            raise RuntimeError(f"KIE createTask failed (code={code}): {msg}")

        task_id = data.get("data", {}).get("taskId", "")
        if not task_id:
            raise RuntimeError(f"No taskId in KIE response: {data}")

        logger.info(f"KIE task created: {task_id} (provider={provider.value}, model={model})")
        return KieTask(task_id=task_id, model=model, provider=provider)

    # ── Task Polling ────────────────────────────────────────

    async def query_task(
        self,
        task_id: str,
        provider: KieProvider = KieProvider.GENERIC,
    ) -> KieTask:
        """
        Query the status of a task.
        Routes to the correct query endpoint based on provider.

        Returns:
            KieTask with current state and results if completed
        """
        if provider == KieProvider.VEO:
            return await self._query_veo_task(task_id)
        elif provider == KieProvider.RUNWAY:
            return await self._query_runway_task(task_id)
        else:
            return await self._query_generic_task(task_id)

    async def _query_generic_task(self, task_id: str) -> KieTask:
        """Query task via generic /api/v1/jobs/recordInfo endpoint."""
        url = f"{KIE_QUERY_TASK}?taskId={task_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    resp_text = await resp.text()
                    raise RuntimeError(
                        f"KIE recordInfo error {resp.status}: {resp_text[:300]}"
                    )
                data = await resp.json(content_type=None)

        code = data.get("code", 0)
        if code != 200:
            msg = data.get("msg", "Unknown error")
            raise RuntimeError(f"KIE recordInfo failed (code={code}): {msg}")

        task_data = data.get("data", {})
        raw_state = (task_data.get("state") or "pending").lower()

        # Map KIE states to our enum
        state_map = {
            "pending": TaskState.PENDING,
            "queued": TaskState.PENDING,
            "waiting": TaskState.PENDING,
            "running": TaskState.PROCESSING,
            "processing": TaskState.PROCESSING,
            "in_progress": TaskState.PROCESSING,
            "generating": TaskState.PROCESSING,
            "success": TaskState.SUCCESS,
            "completed": TaskState.SUCCESS,
            "done": TaskState.SUCCESS,
            "failed": TaskState.FAILED,
            "fail": TaskState.FAILED,
            "error": TaskState.FAILED,
            "cancelled": TaskState.CANCELLED,
        }
        state = state_map.get(raw_state, TaskState.PENDING)

        # Parse result URLs
        result_urls = []
        result_json_str = task_data.get("resultJson", "")
        if result_json_str and state == TaskState.SUCCESS:
            try:
                result_obj = json.loads(result_json_str)
                result_urls = result_obj.get("resultUrls", [])
                if not result_urls:
                    # Try other formats
                    if "url" in result_obj:
                        result_urls = [result_obj["url"]]
                    elif "video_url" in result_obj:
                        result_urls = [result_obj["video_url"]]
                    elif "audio_url" in result_obj:
                        result_urls = [result_obj["audio_url"]]
            except json.JSONDecodeError:
                logger.warning(f"Could not parse resultJson: {result_json_str[:200]}")

        error = None
        if state == TaskState.FAILED:
            error = (
                task_data.get("errorMsg")
                or task_data.get("error")
                or task_data.get("failMsg")
                or "Task failed without error message"
            )

        return KieTask(
            task_id=task_id,
            model=task_data.get("model", ""),
            provider=KieProvider.GENERIC,
            state=state,
            result_urls=result_urls,
            result_json=result_json_str,
            cost_time=task_data.get("costTime", 0),
            error=error,
        )

    async def _query_veo_task(self, task_id: str) -> KieTask:
        """Query task via Veo-specific /api/v1/veo/record-info endpoint."""
        url = f"{KIE_VEO_QUERY}?taskId={task_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    resp_text = await resp.text()
                    raise RuntimeError(
                        f"KIE veo record-info error {resp.status}: {resp_text[:300]}"
                    )
                data = await resp.json(content_type=None)

        code = data.get("code", 0)
        if code != 200:
            msg = data.get("msg", "Unknown error")
            raise RuntimeError(f"KIE veo record-info failed (code={code}): {msg}")

        task_data = data.get("data", {})

        # Veo uses successFlag: 0=generating, 1=success, 2=failed, 3=gen_failed
        success_flag = task_data.get("successFlag", 0)
        if success_flag == 1:
            state = TaskState.SUCCESS
        elif success_flag in (2, 3):
            state = TaskState.FAILED
        else:
            state = TaskState.PROCESSING

        # Parse result URLs from response.resultUrls
        result_urls = []
        response_obj = task_data.get("response", {})
        if response_obj and state == TaskState.SUCCESS:
            result_urls = response_obj.get("resultUrls", [])
            if not result_urls:
                origin_urls = response_obj.get("originUrls", [])
                if origin_urls:
                    result_urls = origin_urls

        error = None
        if state == TaskState.FAILED:
            error = (
                task_data.get("errorMessage")
                or task_data.get("errorCode")
                or "Veo task failed"
            )

        return KieTask(
            task_id=task_id,
            model="veo3",
            provider=KieProvider.VEO,
            state=state,
            result_urls=result_urls,
            cost_time=0,
            error=error,
        )

    async def _query_runway_task(self, task_id: str) -> KieTask:
        """Query task via Runway-specific /api/v1/runway/record-detail endpoint."""
        url = f"{KIE_RUNWAY_QUERY}?taskId={task_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    resp_text = await resp.text()
                    raise RuntimeError(
                        f"KIE runway record-detail error {resp.status}: {resp_text[:300]}"
                    )
                data = await resp.json(content_type=None)

        code = data.get("code", 0)
        if code != 200:
            msg = data.get("msg", "Unknown error")
            raise RuntimeError(f"KIE runway record-detail failed (code={code}): {msg}")

        task_data = data.get("data", {})

        # Runway uses state: wait, queueing, generating, success, fail
        raw_state = (task_data.get("state") or "wait").lower()
        state_map = {
            "wait": TaskState.PENDING,
            "queueing": TaskState.PROCESSING,
            "generating": TaskState.PROCESSING,
            "success": TaskState.SUCCESS,
            "fail": TaskState.FAILED,
        }
        state = state_map.get(raw_state, TaskState.PENDING)

        # Parse video URL from videoInfo.videoUrl
        result_urls = []
        video_info = task_data.get("videoInfo", {})
        if video_info and state == TaskState.SUCCESS:
            video_url = video_info.get("videoUrl", "")
            if video_url:
                result_urls = [video_url]

        error = None
        if state == TaskState.FAILED:
            error = (
                task_data.get("failMsg")
                or f"Runway task failed (code={task_data.get('failCode', 'unknown')})"
            )

        return KieTask(
            task_id=task_id,
            model="runway",
            provider=KieProvider.RUNWAY,
            state=state,
            result_urls=result_urls,
            cost_time=0,
            error=error,
        )

    async def wait_for_task(
        self,
        task_id: str,
        provider: KieProvider = KieProvider.GENERIC,
        poll_interval: Optional[float] = None,
        max_retries: Optional[int] = None,
        on_poll: Optional[callable] = None,
    ) -> KieTask:
        """
        Poll a task until it completes or fails.

        Args:
            task_id: The task ID to poll
            provider: Which endpoint family to poll
            poll_interval: Seconds between polls (default from config)
            max_retries: Max poll attempts (default from config)
            on_poll: Optional callback(attempt, max_retries, state)

        Returns:
            Completed KieTask

        Raises:
            RuntimeError: If task failed
            TimeoutError: If max retries exceeded
        """
        interval = poll_interval or self._poll_interval
        retries = max_retries or self._max_retries

        for attempt in range(1, retries + 1):
            task = await self.query_task(task_id, provider=provider)

            if on_poll:
                await on_poll(attempt, retries, task.state.value)

            if task.state == TaskState.SUCCESS:
                logger.info(
                    f"KIE task {task_id} succeeded after {attempt} polls "
                    f"({task.cost_time}ms generation time)"
                )
                return task

            if task.state == TaskState.FAILED:
                raise RuntimeError(
                    f"KIE task {task_id} failed: {task.error}"
                )

            if task.state == TaskState.CANCELLED:
                raise RuntimeError(f"KIE task {task_id} was cancelled")

            logger.debug(
                f"KIE task {task_id}: state={task.state.value}, "
                f"attempt={attempt}/{retries}, next poll in {interval}s"
            )
            await asyncio.sleep(interval)

        raise TimeoutError(
            f"KIE task {task_id} timed out after {retries} polls "
            f"({retries * interval / 60:.1f} min)"
        )

    # ── File Download ───────────────────────────────────────

    async def download(
        self,
        url: str,
        output_path: str,
        timeout: int = DOWNLOAD_TIMEOUT,
    ) -> str:
        """
        Download a generated file from KIE.AI result URL.

        Returns:
            Local file path
        """
        logger.info(f"Downloading from KIE: {url[:80]}...")

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    resp_text = await resp.text()
                    raise RuntimeError(
                        f"KIE download error {resp.status}: {resp_text[:300]}"
                    )

                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)

        file_size = Path(output_path).stat().st_size
        logger.info(
            f"Downloaded: {output_path} ({file_size / 1024 / 1024:.1f} MB)"
        )
        return output_path

    # ── File Upload ───────────────────────────────────────
    # KIE.AI cannot reach our server (46.225.212.66:8001)
    # so we MUST upload images to KIE CDN first, then use
    # the CDN URL for image-to-video generation.
    #
    # Upload base URL: https://kieai.redpandaai.co
    # Files auto-delete after 3 days (free).

    async def upload_image(
        self,
        file_path: str,
    ) -> str:
        """
        Upload a local image to KIE.AI CDN and get an HTTPS URL back.

        Uses the base64 upload API at kieai.redpandaai.co (free,
        files auto-delete after 3 days). This is REQUIRED because
        KIE.AI's video generation servers cannot reach our Hetzner
        server directly — they time out trying to download images.

        Args:
            file_path: Local path to image file (jpeg, jpg, png, webp)

        Returns:
            HTTPS URL of the uploaded image (downloadUrl on KIE CDN)

        Raises:
            RuntimeError: If upload fails
        """
        import base64 as b64_mod

        path = Path(file_path)
        if not path.exists():
            raise RuntimeError(f"Image file not found: {file_path}")

        # Read and encode
        with open(file_path, "rb") as f:
            img_bytes = f.read()
        img_b64 = b64_mod.b64encode(img_bytes).decode()

        # Determine MIME type
        suffix = path.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        mime = mime_map.get(suffix, "image/jpeg")
        base64_data = f"data:{mime};base64,{img_b64}"

        # Upload via KIE.AI base64 endpoint (correct URL: kieai.redpandaai.co)
        url = f"{KIE_UPLOAD_BASE_URL}/api/file-base64-upload"
        body = {
            "base64Data": base64_data,
            "uploadPath": "ugc-uploads",
            "fileName": path.name,
        }

        logger.info(f"KIE upload_image: {path.name} ({len(img_bytes) / 1024:.1f} KB)")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=body,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                resp_text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(
                        f"KIE file upload error {resp.status}: {resp_text[:500]}"
                    )
                data = await resp.json(content_type=None)

        if not data.get("success"):
            raise RuntimeError(
                f"KIE file upload failed: {data.get('msg', 'Unknown error')}"
            )

        download_url = data.get("data", {}).get("downloadUrl", "")
        if not download_url:
            raise RuntimeError(f"No downloadUrl in KIE upload response: {data}")

        logger.info(f"KIE upload_image success: {download_url[:80]}...")
        return download_url

    # ── Chat API (OpenAI-compatible) ────────────────────────

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[str] = None,
    ) -> str:
        """
        Call KIE.AI chat API (OpenAI-compatible).

        Args:
            model: Chat model path, e.g. "gemini-2.5-flash"
            messages: OpenAI-format messages list
            temperature: Sampling temperature
            max_tokens: Max output tokens
            response_format: Optional, e.g. "json_object"

        Returns:
            Response text content
        """
        url = f"{KIE_CHAT_BASE}/{model}/v1/chat/completions"

        body: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            body["response_format"] = {"type": response_format}

        logger.info(f"KIE chat: model={model}, messages={len(messages)}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=body,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp_text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(
                        f"KIE chat error {resp.status}: {resp_text[:500]}"
                    )
                data = await resp.json(content_type=None)

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"No choices in KIE chat response: {data}")

        content = choices[0].get("message", {}).get("content", "")
        logger.info(f"KIE chat response: {len(content)} chars")
        return content

    # ── Credit Check ────────────────────────────────────────

    async def check_credits(self) -> dict:
        """Check remaining credits on KIE.AI account."""
        url = f"{KIE_BASE_URL}/api/v1/chat/credit"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}"}
                data = await resp.json(content_type=None)

        return data.get("data", data)
