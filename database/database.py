# QuantumLeap - async database setup
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from .models import Base

# Default for dev; override via config
DATABASE_URL = "sqlite+aiosqlite:///./quantumleap.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(database_url: str | None = None):
    global engine, async_session
    if database_url:
        engine = create_async_engine(database_url, echo=False)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
