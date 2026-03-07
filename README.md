# UGC Video Pro

AI-powered UGC product video generator with multi-model support, frame chaining for long videos, and a modern web interface.

## Features

- **Three generation modes**: Image-to-Video, Text-to-Video, URL-to-Video
- **Six AI models**: Sora 2, Sora 2 Pro, Seedance 2.0, Veo 3.0, Veo 3.0 Pro, Veo 3.1 Pro
- **Frame chaining**: Generate videos longer than a single model's max clip by seamlessly chaining segments
- **Multi-language**: Chinese, English, Italian script generation
- **Web interface**: Modern dark-theme dashboard with real-time progress via WebSocket
- **Multi-user**: Invite-only registration with JWT authentication
- **Admin panel**: User management and invite code generation
- **Google Drive**: Optional cloud storage for generated videos
- **Docker deployment**: One-command deploy with PostgreSQL, Nginx, and Let's Encrypt SSL

## Architecture

```
FastAPI (web/app.py)
├── /api/auth/*     → JWT authentication (login, register, invite codes)
├── /api/video/*    → Video generation (upload, generate, download)
├── /api/admin/*    → Admin management (users, invite codes)
├── /api/ws/*       → WebSocket real-time progress
└── /static/*       → HTML/JS/CSS frontend

Core Pipeline (unchanged):
    VideoOrchestrator
    ├── ImageAnalyzer (Gemini Vision)
    ├── ScriptGenerator (Gemini)
    ├── FrameChainer (model adapters + ffmpeg)
    │   ├── SoraAdapter
    │   ├── VeoAdapter
    │   └── SeedanceAdapter
    ├── VideoStitcher (ffmpeg)
    └── GoogleDriveUploader
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Domain name (for HTTPS)
- API keys: OpenAI, Google AI, Seedance (at least one)

### 1. Clone and configure

```bash
git clone https://github.com/fede0429/ugc-video-pro.git
cd ugc-video-pro

# Create configuration files
cp .env.example .env
cp config.example.yaml config.yaml

# Edit .env — fill in all required values:
nano .env
```

Required environment variables:
```
SECRET_KEY=<random-string>
JWT_SECRET=<random-string>
DATABASE_URL=postgresql+asyncpg://ugcvideo:yourpassword@db:5432/ugcvideo
POSTGRES_USER=ugcvideo
POSTGRES_PASSWORD=yourpassword
POSTGRES_DB=ugcvideo
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=<strong-password>
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
SEEDANCE_API_KEY=...
```

### 2. Initialize SSL (first time only)

```bash
chmod +x scripts/init-ssl.sh
./scripts/init-ssl.sh yourdomain.com your@email.com
```

### 3. Start all services

```bash
docker compose up -d
```

### 4. Access the dashboard

Open `https://yourdomain.com` in your browser. Log in with the admin credentials you set in `.env`.

## Development (local)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start PostgreSQL (or use a local instance)
docker run -d --name ugc-pg -e POSTGRES_USER=ugcvideo -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=ugcvideo -p 5432:5432 postgres:16-alpine

# Set environment variables
export DATABASE_URL=postgresql+asyncpg://ugcvideo:dev@localhost:5432/ugcvideo
export JWT_SECRET=dev-secret-key
export ADMIN_EMAIL=admin@dev.local
export ADMIN_PASSWORD=admin123
export STATIC_DIR=./static
export DATA_ROOT=./data

# Run the application
python main.py --debug
```

Open `http://localhost:8000` in your browser.

## Project Structure

```
ugc-video-pro/
├── main.py                 # FastAPI entry point (uvicorn)
├── config.example.yaml     # Configuration template
├── .env.example            # Environment variables template
├── requirements.txt        # Python dependencies
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Full stack: app + PostgreSQL + Nginx + Certbot
├── nginx.conf              # Nginx reverse proxy configuration
├── scripts/
│   └── init-ssl.sh         # SSL certificate initialization script
├── web/                    # FastAPI backend
│   ├── app.py              # Application factory
│   ├── auth.py             # JWT authentication
│   ├── database.py         # SQLAlchemy async engine
│   ├── models_db.py        # ORM models (User, InviteCode, VideoTask)
│   ├── schemas.py          # Pydantic request/response schemas
│   ├── routes_auth.py      # Auth API endpoints
│   ├── routes_video.py     # Video generation endpoints
│   ├── routes_admin.py     # Admin management endpoints
│   ├── websocket.py        # WebSocket progress manager
│   └── tasks.py            # Background video generation runner
├── static/                 # Pure HTML/JS/CSS frontend
│   ├── index.html          # Dashboard (main SPA)
│   ├── login.html          # Login page
│   ├── register.html       # Registration page
│   ├── css/style.css       # Styles
│   ├── js/
│   │   ├── api.js          # API client with JWT
│   │   ├── auth.js         # Login/register logic
│   │   ├── dashboard.js    # Video wizard + list + WebSocket
│   │   └── admin.js        # Admin panel logic
│   └── assets/logo.svg     # App logo
├── core/                   # Video generation pipeline
│   ├── orchestrator.py     # Main pipeline controller
│   ├── script_generator.py # AI script generation (Gemini)
│   ├── frame_chainer.py    # Frame chain generation
│   └── video_stitcher.py   # FFmpeg video stitching
├── models/                 # AI model adapters
│   ├── base.py             # Base adapter + duration helpers
│   ├── sora.py             # OpenAI Sora adapter
│   ├── veo.py              # Google Veo adapter
│   └── seedance.py         # Seedance adapter
├── services/               # External services
│   ├── image_analyzer.py   # Gemini Vision image analysis
│   ├── google_drive.py     # Google Drive uploader
│   └── url_extractor.py    # URL content extraction
├── utils/                  # Utilities
│   ├── ffmpeg_tools.py     # FFmpeg wrapper
│   └── logger.py           # Logging setup
└── bot/                    # Legacy Telegram bot (not used by web)
    ├── telegram_handler.py
    └── messages.py         # i18n message catalog (shared by web)
```

## API Documentation

After starting the application, visit:
- Swagger UI: `https://yourdomain.com/api/docs`
- ReDoc: `https://yourdomain.com/api/redoc`

## Server Recommendations

### Hetzner Cloud (recommended)

For a single-user or small-team deployment:

| Component | Recommendation |
|-----------|---------------|
| **Server** | Hetzner CPX21 (3 vCPU / 4 GB RAM / 80 GB NVMe) |
| **Location** | Nuremberg (nbg1) or Falkenstein (fsn1) |
| **OS** | Ubuntu 24.04 LTS |
| **Cost** | ~€6.49/month |

The application is lightweight — most heavy work (AI model inference) happens on external APIs. The server mainly handles:
- FastAPI + Nginx (web serving)
- PostgreSQL (metadata)
- FFmpeg (video stitching — CPU-intensive but brief)
- Temporary file storage

For heavier usage (multiple concurrent users with frequent FFmpeg stitching), consider CPX31 (4 vCPU / 8 GB RAM) at ~€10.49/month.

### Initial server setup

```bash
# SSH into your new server
ssh root@your-server-ip

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
apt install docker-compose-plugin -y

# Create deploy user
adduser deploy
usermod -aG docker deploy
su - deploy

# Clone and deploy
git clone https://github.com/fede0429/ugc-video-pro.git
cd ugc-video-pro
# Follow Quick Start steps above
```

## License

Private — all rights reserved.
