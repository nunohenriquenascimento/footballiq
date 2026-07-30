import sys
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import engine  # noqa: E402


TABLE_NAME = "competitions"


def main() -> int:
    try:
        inspector = inspect(engine)
        if not inspector.has_table(TABLE_NAME):
            print(
                f"Erro: a tabela {TABLE_NAME!r} não existe.",
                file=sys.stderr,
            )
            return 1

        columns = inspector.get_columns(TABLE_NAME)
    except (SQLAlchemyError, RuntimeError) as exc:
        print(
            f"Erro ao verificar a base de dados: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"Tabela encontrada: {TABLE_NAME}")
    print("Colunas:")
    for column in columns:
        nullable = "NULL" if column["nullable"] else "NOT NULL"
        print(f"- {column['name']}: {column['type']} ({nullable})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
