"""Testes unitários para a configuração da base de dados."""

from footballiq.db.config import DatabaseSettings


def test_database_settings_from_env(monkeypatch) -> None:
    """As variáveis de ambiente devem sobrepor os valores por defeito."""
    monkeypatch.setenv("FOOTBALLIQ_DB_HOST", "localhost")
    monkeypatch.setenv("FOOTBALLIQ_DB_PORT", "5433")
    monkeypatch.setenv("FOOTBALLIQ_DB_NAME", "footballiq_dev")
    monkeypatch.setenv("FOOTBALLIQ_DB_USER", "footballiq")
    monkeypatch.setenv("FOOTBALLIQ_DB_PASSWORD", "secret")
    monkeypatch.setenv("FOOTBALLIQ_DB_SSLMODE", "require")

    settings = DatabaseSettings.from_env()

    assert settings.host == "localhost"
    assert settings.port == 5433
    assert settings.dbname == "footballiq_dev"
    assert settings.user == "footballiq"
    assert settings.password == "secret"
    assert settings.sslmode == "require"


def test_database_settings_default_values() -> None:
    """Os valores por defeito devem manter o desenvolvimento local previsível."""
    settings = DatabaseSettings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 5432
    assert settings.dbname == "footballiq_dev"
    assert settings.user == ""
    assert settings.password == ""
    assert settings.sslmode == "prefer"


def test_dsn_omits_password_when_empty() -> None:
    """A string de conexão não deve expor password vazia em logs ou output."""
    settings = DatabaseSettings(password="")

    assert "password=" not in settings.dsn
    assert "dbname=footballiq_dev" in settings.dsn
    assert "user=" not in settings.dsn


def test_as_connect_kwargs_requires_explicit_user() -> None:
    """Uma ligação não deve abrir sem uma role explícita e segura."""
    settings = DatabaseSettings()

    try:
        settings.as_connect_kwargs()
    except ValueError as exc:
        assert "FOOTBALLIQ_DB_USER" in str(exc)
    else:
        raise AssertionError("Expected ValueError when FOOTBALLIQ_DB_USER is unset.")
