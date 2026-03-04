"""
web/database.py
===============
SQLAlchemy async database engine, session factory, and initialization.

Expects DATABASE_URL environment variable in the form:
    postgresql+asyncpg://user:password@host:port/dbname

Provides:
    - engine: AsyncEngine (singleton)
    - AsyncSessionLocal: async sessionmaker
    - Base: declarative base for all ORM models
    - get_db(): FastAPI dependency that yields a session
    - init_db(): creates tables and seeds the admin user
"""

import os
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# ── Database URL ─────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://ugc:ugc@localhost:5432/ugcvideo",
)

# Ensure the driver prefix is correct for asyncpg
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# ── Engine ───────────────────────────────────────────────────────────────────
engine = create_async_engine(
    DATABASE_URL,
    echo=os.environ.get("DB_ECHO", "false").lower() == "true",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# ── Session factory ──────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Declarative base ─────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ── FastAPI dependency ───────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session as a FastAPI dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Database initialisation ──────────────────────────────────────────────────
async def init_db() -> None:
    """
    Create all tables (if they don't exist) and seed the initial admin user.

    The admin credentials are read from environment variables:
        ADMIN_EMAIL    (default: admin@ugcvideo.pro)
        ADMIN_PASSWORD (default: ChangeMe123!)
    """
    # Import here to avoid circular imports
    from web.models_db import User, UserRole  # noqa: F401  (ensures table metadata is registered)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created (or already exist).")

    # Seed admin user
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@ugcvideo.pro")
    admin_password = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")

    from sqlalchemy import select
    from web.auth import hash_password

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == admin_email)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            admin = User(
                email=admin_email,
                password_hash=hash_password(admin_password),
                display_name="Admin",
                role=UserRole.admin,
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            logger.info(f"Seeded admin user: {admin_email}")
        else:
            logger.info(f"Admin user already exists: {admin_email}")
