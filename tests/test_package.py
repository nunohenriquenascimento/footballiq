"""Verificações mínimas da fundação do pacote FootballIQ."""

import footballiq


def test_package_can_be_imported() -> None:
    """Confirma que o pacote instalado está acessível pelo seu nome público."""
    # Sem ajustar sys.path, a importação também verifica a instalação do src-layout.
    assert footballiq.__name__ == "footballiq"
