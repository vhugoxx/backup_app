"""
SleepGuard – impede que o Windows entre em suspensão, desligue o ecrã ou
hiberne enquanto o backup estiver a correr.

API simples:

    guard = SleepGuard()
    guard.start()   # ativa
    ...
    guard.stop()    # liberta

Também pode ser usado como context-manager::

    with SleepGuard():
        executar_tarefa_longa()
"""

from __future__ import annotations
import ctypes
import platform
import atexit


class SleepGuard:
    # Constantes WinAPI
    _ES_CONTINUOUS         = 0x80000000
    _ES_SYSTEM_REQUIRED    = 0x00000001
    _ES_AWAYMODE_REQUIRED  = 0x00000040  # mantém ligado mesmo quando tampa fechada

    def __init__(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError("SleepGuard só está disponível em Windows.")
        self._active = False

    # -------------------------------------------------------------

    def start(self) -> None:
        """Ativa o bloqueio de suspensão."""
        if not self._active:
            ctypes.windll.kernel32.SetThreadExecutionState(
                self._ES_CONTINUOUS
                | self._ES_SYSTEM_REQUIRED
                | self._ES_AWAYMODE_REQUIRED
            )
            self._active = True
            # garante liberação caso o programa feche abruptamente
            atexit.register(self.stop)

    def stop(self) -> None:
        """Liberta o bloqueio (permite suspensão novamente)."""
        if self._active:
            ctypes.windll.kernel32.SetThreadExecutionState(self._ES_CONTINUOUS)
            self._active = False

    # --------- suporte a "with" ---------------------------------

    def __enter__(self) -> "SleepGuard":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop()
        # não suprime exceções
        return False
