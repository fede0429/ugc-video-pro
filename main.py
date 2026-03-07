#!/usr/bin/env python3
"""
UGC Video Pro - Web Application Entry Point
=============================================
FastAPI web application for AI-powered UGC product video generation.
Supports multiple AI models (Sora 2, Veo 3.x, Seedance 2.0), frame chaining
for long videos, multi-language output (Chinese / English / Italian).

Usage:
    python main.py                          # Uses config.yaml or config.example.yaml
    python main.py --config myconfig.yaml   # Custom config path
    python main.py --debug                  # Enable debug logging
    python main.py --host 0.0.0.0 --port 8080  # Override host/port

Architecture:
    main.py → FastAPI app (web/app.py)
                ├── /api/auth/*     → JWT authentication
                ├── /api/video/*    → Video generation endpoints
                ├── /api/admin/*    → Admin management
                ├── /api/ws/*       → WebSocket progress streams
                └── /static/*       → HTML/JS/CSS frontend
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

import yaml


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file.

    Priority: explicit path > config.yaml > config.example.yaml
    Environment variables are resolved inside ${VAR} and ${VAR:-default} patterns.
    """
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
    else:
        path = Path("config.yaml")
        if not path.exists():
            path = Path("config.example.yaml")
            if not path.exists():
                raise FileNotFoundError(
                    "No config file found. Copy config.example.yaml to config.yaml "
                    "and fill in your API keys."
                )

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    def resolve_env(obj):
        """Recursively resolve ${VAR} and ${VAR:-default} placeholders."""
        if isinstance(obj, str) and "${" in obj:
            import re
            # Match ${VAR:-default} or ${VAR}
            def replacer(match):
                inner = match.group(1)
                if ":-" in inner:
                    var_name, default = inner.split(":-", 1)
                else:
                    var_name, default = inner, match.group(0)  # keep raw if missing
                return os.environ.get(var_name.strip(), default)

            resolved = re.sub(r"\$\{([^}]+)\}", replacer, obj)
            return resolved
        elif isinstance(obj, dict):
            return {k: resolve_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_env(i) for i in obj]
        return obj

    return resolve_env(config)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="UGC Video Pro - AI-Powered UGC Product Video Generator (Web)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to configuration YAML file (default: config.yaml)",
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind to (overrides config web.host)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to listen on (overrides config web.port)",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="UGC Video Pro 2.0.0",
    )
    return parser.parse_args()


async def main() -> None:
    """Main entry point for UGC Video Pro web application."""
    import uvicorn

    args = parse_args()

    # ── Load configuration ────────────────────────────────────────
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Setup logging ─────────────────────────────────────────────
    from utils.logger import setup_logger
    log_level = "DEBUG" if args.debug else config.get("log_level", "INFO")
    logger = setup_logger(log_level)
    logger.info("UGC Video Pro (web) starting up...")
    logger.info(f"Config loaded from: {args.config or 'config.yaml'}")

    # ── Validate required config sections ────────────────────────
    # Database and JWT secret are required for the web app
    db_url = config.get("database", {}).get("url", "")
    jwt_secret = config.get("auth", {}).get("jwt_secret", "")

    if not db_url or db_url.startswith("${"):
        logger.warning(
            "DATABASE_URL not set — database features will be unavailable. "
            "Set DATABASE_URL in your .env file."
        )
    if not jwt_secret or jwt_secret.startswith("${"):
        logger.warning(
            "JWT_SECRET not set — authentication will use an insecure default. "
            "Set JWT_SECRET in your .env file."
        )

    # ── Ensure data directories exist ────────────────────────────
    web_config = config.get("web", {})
    for dir_key in ("upload_dir", "video_dir"):
        dir_path = web_config.get(dir_key)
        if dir_path:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            logger.debug(f"Data directory ensured: {dir_path}")

    # Legacy video output dir (used by core orchestrator)
    output_dir = config.get("video", {}).get("output_dir", "/tmp/ugc_videos")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # ── Create FastAPI app ────────────────────────────────────────
    from web.app import create_app
    app = create_app(config)

    # ── Determine host / port (CLI args override config) ─────────
    host = args.host or web_config.get("host", "0.0.0.0")
    port = args.port or web_config.get("port", 8000)

    logger.info(f"Starting web server on http://{host}:{port}")

    # ── Run with uvicorn ──────────────────────────────────────────
    uvicorn_config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=log_level.lower(),
        # Forward headers when behind nginx reverse proxy
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    server = uvicorn.Server(uvicorn_config)

    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Load .env file if present (development convenience)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # python-dotenv not installed — rely on environment variables

    asyncio.run(main())
