"""Base declarativa partilhada pelos modelos relacionais do FootballIQ."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Agrega as tabelas em metadata, sem abrir ligações ou criar objetos na base.

    DeclarativeBase permite descrever tabelas através de classes Python.
    Base.metadata guarda essa descrição em memória, para inspeção e futuras
    migrações; importar a classe não executa SQL.
    """
