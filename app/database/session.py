from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.database.connection import engine

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessão de base de dados e fecha-a no final."""

    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()