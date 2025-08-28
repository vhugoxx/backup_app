# -*- coding: utf-8 -*-
"""Bootstrap da aplicação com verificação de privilégios de Administrador (Windows).

O programa termina imediatamente se não estiver a correr como Administrador,
antes de carregar a UI ou inicializar qualquer módulo com side-effects.
"""
from pathlib import Path
import sys

def _assert_admin_or_exit() -> None:
    """Termina imediatamente se o processo não estiver com privilégios de Administrador (Windows)."""
    try:
        import ctypes  # só disponível no Windows
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        # Se não conseguir verificar (ex.: não-Windows), assume que NÃO é admin
        is_admin = False

    if not is_admin:
        msg = (
            "Este programa requer privilégios de Administrador.\n"
            "Por favor, abre o 'Prompt de Comando' ou 'PowerShell' como Administrador e volta a executar."
        )
        # Mensagem no terminal
        print(msg, file=sys.stderr)

        # (Opcional) Mostrar um pop-up se Qt estiver disponível sem inicializar toda a app
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "Permissão necessária", msg)
        except Exception:
            pass  # Se não houver Qt disponível aqui, ignora

        sys.exit(1)


if __name__ == "__main__":
    # Bloqueia execução sem privilégios
    _assert_admin_or_exit()

    # --- Só a partir daqui importamos módulos que podem ter side-effects ---
    PROJECT_ROOT = Path(__file__).parent
    log_path = PROJECT_ROOT / "backup_crash.log"

    import faulthandler, os
    faulthandler.enable(open(log_path, "w"))  # mantém registo de crash
    os.environ["QT_DEBUG_PLUGINS"] = "1"

    # Import tardio para evitar carregar a UI antes do check de admin
    from src.gui_app import iniciar_app
    iniciar_app()
