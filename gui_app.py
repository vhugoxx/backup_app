from __future__ import annotations
import sys, json
from pathlib import Path

from PySide6.QtCore    import QObject, QThread, Signal, Qt, QEvent
from PySide6.QtWidgets import (
    QApplication, QWidget, QFormLayout, QPushButton, QLineEdit, QCheckBox,
    QGroupBox, QHBoxLayout, QVBoxLayout, QProgressBar, QPlainTextEdit,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QMessageBox
)

# ---------------------------------------------------------------------
# caminhos persistentes (ficheiro gravado na pasta da aplicação)
_SESSION_FILE = Path(__file__).with_name("last_session.json")

# utilitário para ler / gravar
def _load_session() -> dict:
    try:
        return json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        print("Aviso: não foi possível ler sessão anterior:", exc)
        return {}

def _save_session(data: dict) -> None:
    try:
        _SESSION_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as exc:
        print("Aviso: não foi possível gravar sessão:", exc)
# ---------------------------------------------------------------------


# ------------------------- BackupWorker ------------------------------
from core.runner       import cli_run
from core.sleep_guard  import SleepGuard           # mantém o PC acordado

class BackupWorker(QObject):
    progress = Signal(int, int)      # ficheiro_actual, total
    log      = Signal(str)
    finished = Signal(bool, str)     # ok, caminho_log

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg   = cfg
        self._stop = False

    def cancel(self):
        self._stop = True

    def run(self):
        guard = SleepGuard()
        guard.start()

        def _emit_progress(cur, tot):
            if self._stop:
                raise KeyboardInterrupt
            self.progress.emit(cur, tot)

        def _emit_log(msg: str):
            self.log.emit(msg)

        try:
            ok, logp = cli_run(
                self.cfg["src"], self.cfg["dst"], self.cfg["types"],
                self.cfg["recursive"], self.cfg["preserve"],
                callbacks={"progress": _emit_progress, "log": _emit_log}
            )
        except KeyboardInterrupt:
            ok, logp = False, None
            self.log.emit("[yellow]Cancelamento pedido…[/yellow]")
        finally:
            guard.stop()
            self.finished.emit(ok, str(logp) if logp else "")
# ---------------------------------------------------------------------


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Backup Seletivo")
        self._session = _load_session()
        self._build_ui()

    # ---------------- UI --------------------------------------------------
    def _build_ui(self):
        form = QFormLayout(self)

        # origem / destino
        self.src_edit = QLineEdit(self._session.get("src",""), self)
        self.dst_edit = QLineEdit(self._session.get("dst",""), self)

        src_btn = QPushButton("…")
        dst_btn = QPushButton("…")
        src_btn.clicked.connect(lambda: self._pick_dir(self.src_edit))
        dst_btn.clicked.connect(lambda: self._pick_dir(self.dst_edit))

        form.addRow("Origem:",  self._hlayout(self.src_edit, src_btn))
        form.addRow("Destino:", self._hlayout(self.dst_edit, dst_btn))

        # opções
        self.recursive_chk = QCheckBox("Incluir subpastas", self)
        self.recursive_chk.setChecked(self._session.get("recursive", True))
        self.preserve_chk  = QCheckBox("Preservar estrutura relativa (DEST/<ext>/…)", self)
        self.preserve_chk.setChecked(self._session.get("preserve", True))
        form.addRow(self.recursive_chk)
        form.addRow(self.preserve_chk)

        # árvore de tipos
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True)
        self._populate_tree()
        form.addRow("Tipos:", self.tree)

        # custom ext
        self.custom_edit = QLineEdit(self._session.get("custom",""), self)
        self.custom_edit.setPlaceholderText("ex: svg heic md")
        form.addRow("Custom:", self.custom_edit)

        # progresso & botões
        self.progress = QProgressBar(); self.progress.setValue(0)
        form.addRow(self.progress)

        self.start_btn   = QPushButton("Iniciar");   self.start_btn.clicked.connect(self._start)
        self.cancel_btn  = QPushButton("Cancelar");  self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)

        form.addRow(self._hlayout(self.start_btn, self.cancel_btn))

        # log
        self.log_area = QPlainTextEdit(self); self.log_area.setReadOnly(True)
        form.addRow("Log:", self.log_area)
    # ----------------------------------------------------------------------

    @staticmethod
    def _hlayout(*widgets):
        box = QHBoxLayout(); box.setContentsMargins(0,0,0,0)
        for w in widgets: box.addWidget(w)
        return box

    # --------- popula árvore de extensões ---------------------------------
    def _populate_tree(self):
        cats_file = Path(__file__).with_name("core").joinpath("file_types.json")
        import json
        cats = json.loads(cats_file.read_text(encoding="utf-8"))["categories"]

        self.tree.clear()
        saved = set(self._session.get("types", []))

        def add_item(parent: QTreeWidgetItem, text: str, checked=False):
            item = QTreeWidgetItem(parent, [text])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            item.setCheckState(0, state)
            return item

        for cat, exts in cats.items():
            par = add_item(self.tree, cat)
            # não temos ItemIsTristate, mas quando o pai muda percorremos os filhos
            par.setData(0, Qt.UserRole, "category")
            for ext in exts:
                add_item(par, ext, ext in saved).setData(0, Qt.UserRole, "ext")

        self.tree.itemChanged.connect(self._sync_parent)

    # pai ⇄ filhos
    def _sync_parent(self, item: QTreeWidgetItem, _col: int):
        if item.data(0, Qt.UserRole) == "category":
            # alterar todos os filhos
            state = item.checkState(0)
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, state)
        else:
            parent = item.parent()
            if parent is None: return
            states = {parent.child(i).checkState(0) for i in range(parent.childCount())}
            parent.setCheckState(0, Qt.CheckState.Checked if states=={Qt.CheckState.Checked}
                                 else Qt.CheckState.Unchecked)

    # --------------------------- fluxo -------------------------------------
    def _selected_exts(self) -> list[str]:
        exts = []
        for i in range(self.tree.topLevelItemCount()):
            cat   = self.tree.topLevelItem(i)
            for j in range(cat.childCount()):
                leaf = cat.child(j)
                if leaf.checkState(0) == Qt.CheckState.Checked:
                    exts.append(leaf.text(0))
        extra = [e.strip().lstrip(".") for e in self.custom_edit.text().split() if e.strip()]
        return sorted(set(exts + extra))

    def _start(self):
        exts = self._selected_exts()
        if not self.src_edit.text() or not self.dst_edit.text() or not exts:
            QMessageBox.warning(self, "Faltam dados",
                                "Indique origem, destino e pelo menos uma extensão.")
            return

        # guardar sessão
        self._session.update({
            "src": self.src_edit.text(),
            "dst": self.dst_edit.text(),
            "recursive": self.recursive_chk.isChecked(),
            "preserve":  self.preserve_chk.isChecked(),
            "types": exts,
            "custom": self.custom_edit.text()
        })
        _save_session(self._session)

        cfg = dict(
            src=self._session["src"],
            dst=self._session["dst"],
            types=exts,
            recursive=self.recursive_chk.isChecked(),
            preserve=self.preserve_chk.isChecked()
        )

        # preparar thread
        self.worker = BackupWorker(cfg)
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)

        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._append_log)
        self.worker.finished.connect(self._on_finished)
        self.thread.started.connect(self.worker.run)

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.thread.start()

    def _cancel(self):
        if hasattr(self, "worker"):
            self.worker.cancel()

    # sinais -----------------
    def _on_progress(self, cur: int, tot: int):
        self.progress.setMaximum(tot)
        self.progress.setValue(cur)

    def _append_log(self, msg: str):
        self.log_area.appendPlainText(msg)

    def _on_finished(self, ok: bool, logp: str):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        txt = "Concluído com sucesso." if ok else "Interrompido."
        if logp:
            txt += f"\nLog: {logp}"
        QMessageBox.information(self, "Backup", txt)
        # encerra-se automaticamente
        self.close()

    # impedir fechar sem confirmar
    def closeEvent(self, ev: QEvent):
        if hasattr(self, "thread") and self.thread.isRunning():
            if QMessageBox.question(self, "Backup em curso",
                                    "Cancelar o backup e sair?") != QMessageBox.Yes:
                ev.ignore(); return
            self._cancel(); self.thread.wait()
        ev.accept()


# ------------------------ main ----------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(760, 560)
    win.show()
    sys.exit(app.exec())
