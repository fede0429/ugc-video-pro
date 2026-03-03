#!/usr/bin/env python3
"""
UGC Video Pro - AI-Powered UGC Product Video Generator
=======================================================
Standalone application for generating UGC product videos via Telegram Bot.
Supports multiple AI models (Sora 2, Veo 3.x, Seedance 2.0), frame chaining
for long videos, multi-language output (Chinese / English / Italian).

Usage:
    python main.py                          # Uses config.yaml or config.example.yaml
    python main.py --config myconfig.yaml   # Custom config path
    python main.py --debug                  # Enable debug logging

Architecture:
    main.py → UGCVideoBot → VideoOrchestrator
                               ├── ImageAnalyzer (Gemini)
                               ├── ScriptGenerator (Gemini)
                               ├── FrameChainer (model adapters + ffmpeg)
                               │   ├── SoraAdapter
                               │   ├── VeoAdapter
                               │   └── SeedanceAdapter
                               ├── VideoStitcher (ffmpeg)
                               └── GoogleDriveUploader
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

import yaml

from bot.telegram_handler import UGCVideoBot
from utils.logger import setup_logger


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file.
    
    Priority: explicit path > config.yaml > config.example.yaml
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

    # Resolve environment variables in config values
    import os
    def resolve_env(obj):
        if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_key = obj[2:-1]
            return os.environ.get(env_key, obj)
        elif isinstance(obj, dict):
            return {k: resolve_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_env(i) for i in obj]
        return obj

    return resolve_env(config)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="UGC Video Pro - AI-Powered UGC Product Video Generator",
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
        "--version", "-v",
        action="version",
        version="UGC Video Pro 1.0.0",
    )
    return parser.parse_args()


async def main() -> None:
    """Main entry point for UGC Video Pro."""
    args = parse_args()

    # Load config first to get log level
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Setup logging
    log_level = "DEBUG" if args.debug else config.get("log_level", "INFO")
    logger = setup_logger(log_level)
    logger.info("UGC Video Pro starting up...")
    logger.info(f"Config loaded from: {args.config or 'config.yaml'}")

    # Validate required config keys
    required_keys = [
        ("telegram", "bot_token"),
    ]
    for section, key in required_keys:
        if not config.get(section, {}).get(key):
            logger.error(f"Missing required config: {section}.{key}")
            sys.exit(1)

    # Ensure output directory exists
    output_dir = config.get("video", {}).get("output_dir", "/tmp/ugc_videos")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f"Video output directory: {output_dir}")

    # Start the Telegram bot
    try:
        bot = UGCVideoBot(config)
        logger.info("Starting Telegram bot...")
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Load .env file if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # python-dotenv not installed, that's fine

    asyncio.run(main())
