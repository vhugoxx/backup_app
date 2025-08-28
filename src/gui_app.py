# src/gui_app.py
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Set

from PySide6.QtCore import QObject, QThread, Signal, Qt, QEvent, QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QProgressBar, QSizePolicy, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget
)

# --- caminho do projeto / settings -------------------------------------------
APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR
SESSION_FILE = DATA_DIR / ".session.json"

# --- worker -------------------------------------------------------------------
class Worker(QObject):
    progress = Signal(int)        # incremento (1 por ficheiro)
    log      = Signal(str)
    finished = Signal(dict)       # stats no fim

    def __init__(self, cfg: Dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._stop = False

    def cancel(self):
        self._stop = True

    def run(self):
        """Executa num QThread."""
        from src.core.copier import copy_selected  # import tardio para arrancar mais depressa

        stats = {}
        try:
            self.log.emit("Iniciar backup...")
            copy_selected(
                **self.cfg,
                progress_cb=self.progress.emit,
                log_cb=self.log.emit,
                stop_flag=lambda: self._stop,
                stats=stats
            )
        except Exception as e:
            self.log.emit(f"❌ Erro: {e}")
        finally:
            if self._stop:
                self.log.emit("⏹️  Cancelado pelo utilizador.")
            else:
                self.log.emit("✔ Backup concluído.")
            self.finished.emit(stats)


# --- UI principal -------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Backup seletivo por tipo de ficheiros")
        self.resize(900, 620)

        self._thread: QThread | None = None
        self._worker: Worker | None = None

        self._build_ui()
        self._restore_session()

    # ---------- construção UI ----------
    def _build_ui(self):
        central = QWidget(self)
        grid = QGridLayout(central)
        grid.setSpacing(8)
        self.setCentralWidget(central)

        # opções
        self.chk_vss         = QCheckBox("Usar VSS (Windows, requer Administrador)")
        self.chk_vss.setStyleSheet("font-weight: bold")
        self.chk_recursive   = QCheckBox("Incluir sub-pastas");   self.chk_recursive.setChecked(True)
        self.chk_preserve    = QCheckBox("Preservar estrutura");  self.chk_preserve.setChecked(True)
        self.chk_archives    = QCheckBox("Incluir ficheiros compactados"); self.chk_archives.setChecked(True)

        row = 0
        grid.addWidget(self.chk_vss, row, 0, 1, 3); row += 1
        grid.setRowMinimumHeight(row, 12); row += 1

        # Origem
        grid.addWidget(QLabel("Origem:"), row, 0)
        self.src_edit = QLineEdit(self)
        grid.addWidget(self.src_edit, row, 1)
        btn_src = QPushButton("…", self)
        btn_src.clicked.connect(self._pick_src)
        grid.addWidget(btn_src, row, 2)
        row += 1
        grid.addWidget(self.chk_recursive, row, 0, 1, 3); row += 1

        # Destino
        grid.addWidget(QLabel("Destino:"), row, 0)
        self.dst_edit = QLineEdit(self)
        grid.addWidget(self.dst_edit, row, 1)
        btn_dst = QPushButton("…", self)
        btn_dst.clicked.connect(self._pick_dst)
        grid.addWidget(btn_dst, row, 2)
        row += 1
        grid.addWidget(self.chk_preserve,  row, 0, 1, 3); row += 1

        grid.setRowMinimumHeight(row, 12); row += 1
        grid.addWidget(self.chk_archives,  row, 0, 1, 3); row += 1

        # tipos de arquivo suportados
        box_arch = QGroupBox("Tipos de arquivo a examinar")
        h_arch = QHBoxLayout(box_arch)
        self.chk_zip = QCheckBox("zip"); self.chk_zip.setChecked(True)
        self.chk_tar = QCheckBox("tar"); self.chk_tar.setChecked(True)
        self.chk_rar = QCheckBox("rar"); self.chk_rar.setChecked(True)
        self.chk_7z  = QCheckBox("7z");  self.chk_7z.setChecked(True)
        for w in (self.chk_zip, self.chk_tar, self.chk_rar, self.chk_7z):
            h_arch.addWidget(w)
        grid.addWidget(box_arch, row, 0, 1, 3); row += 1

        # custom extensions
        grid.addWidget(QLabel("Custom:"), row, 0)
        self.custom_edit = QLineEdit(self)
        self.custom_edit.setPlaceholderText("ex: svg heic md")
        grid.addWidget(self.custom_edit, row, 1, 1, 2); row += 1

        # árvore de tipos
        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        grid.addWidget(self.tree, row, 0, 1, 3); row += 1
        self._populate_tree()

        # barra progresso + log
        self.progress = QProgressBar(self); self.progress.setValue(0)
        grid.addWidget(self.progress, row, 0, 1, 3); row += 1

        self.log = QTextEdit(self); self.log.setReadOnly(True)
        self.log.setPlaceholderText("Pronto.")
        grid.addWidget(self.log, row, 0, 1, 3); row += 1

        # botões
        btns = QHBoxLayout()
        self.btn_start = QPushButton("Iniciar")
        self.btn_cancel = QPushButton("Cancelar"); self.btn_cancel.setEnabled(False)
        self.btn_pdf = QPushButton("Gerar PDF"); self.btn_pdf.setEnabled(False)

        self.btn_start.clicked.connect(self._on_start)
        self.btn_cancel.clicked.connect(self._on_cancel)
        self.btn_pdf.clicked.connect(self._on_pdf)

        btns.addStretch(1)
        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_pdf)
        grid.addLayout(btns, row, 0, 1, 3)

    def _populate_tree(self):
        self.tree.clear()
        # grupos
        g_docs = QTreeWidgetItem(self.tree, ["Documentos"])
        for ext in ("pdf", "docx", "xlsx", "pptx"):
            QTreeWidgetItem(g_docs, [ext])
        g_img = QTreeWidgetItem(self.tree, ["Imagens"])
        for ext in ("jpg", "jpeg", "png", "gif"):
            QTreeWidgetItem(g_img, [ext])
        g_3d  = QTreeWidgetItem(self.tree, ["3D"])
        for ext in ("obj", "stl", "step"):
            QTreeWidgetItem(g_3d, [ext])
        g_code = QTreeWidgetItem(self.tree, ["Código"])
        for ext in ("py", "cpp", "cs"):
            QTreeWidgetItem(g_code, [ext])

        # tornar “checkable”
        def recurse(item: QTreeWidgetItem):
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Unchecked)
            for i in range(item.childCount()):
                recurse(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            recurse(self.tree.topLevelItem(i))

    # ---------- interações ----------
    def _pick_src(self):
        p = QFileDialog.getExistingDirectory(self, "Escolher origem", str(Path.home()))
        if p:
            self.src_edit.setText(p)

    def _pick_dst(self):
        p = QFileDialog.getExistingDirectory(self, "Escolher destino", str(Path.home()))
        if p:
            self.dst_edit.setText(p)

    def _collect_extensions(self) -> Set[str]:
        exts: Set[str] = set()
        # árvore
        def recurse(item: QTreeWidgetItem):
            if item.childCount() == 0 and item.checkState(0) == Qt.Checked:
                exts.add(item.text(0).lower())
            for i in range(item.childCount()):
                recurse(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            recurse(self.tree.topLevelItem(i))
        # custom
        custom = self.custom_edit.text().strip()
        if custom:
            for tok in custom.replace(",", " ").split():
                exts.add(tok.lower().lstrip("."))
        return exts

    def _archive_types(self) -> Set[str]:
        s = set()
        if self.chk_zip.isChecked(): s.add("zip")
        if self.chk_tar.isChecked(): s.add("tar")
        if self.chk_rar.isChecked(): s.add("rar")
        if self.chk_7z.isChecked():  s.add("7z")
        return s

    def _on_start(self):
        src = self.src_edit.text().strip()
        dst = self.dst_edit.text().strip()
        if not src or not dst:
            QMessageBox.warning(self, "Erro", "Indica a pasta de origem e destino.")
            return
        exts = self._collect_extensions()
        if not exts:
            QMessageBox.information(self, "Info", "Seleciona pelo menos uma extensão.")
            return

        cfg = dict(
            src=src,
            dst=dst,
            extensions=exts,
            recursive=self.chk_recursive.isChecked(),
            preserve_structure=self.chk_preserve.isChecked(),
            include_archives=self.chk_archives.isChecked(),
            archive_types=self._archive_types(),
            use_vss=self.chk_vss.isChecked(),
        )

        self._save_session(cfg)
        self.progress.setValue(0)
        self.log.clear()
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_pdf.setEnabled(False)

        # arranque da thread
        self._thread = QThread(self)
        self._worker = Worker(cfg)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_cancel(self):
        if self._worker:
            self._append_log("🚫 A cancelar… aguarda o fecho seguro do processo atual.")
            self._worker.cancel()
            self.btn_cancel.setEnabled(False)  # evita cliques múltiplos

    def _on_progress(self, inc: int):
        self.progress.setValue(self.progress.value() + inc)

    def _append_log(self, line: str):
        self.log.append(line)

    def _on_finished(self, stats: dict):
        # mostrar resumo
        total = (
            f"Ficheiros analisados : {stats.get('files_scanned', 0)}\n"
            f"Ficheiros encontrados: {stats.get('files_found', 0)}\n"
            f"Ficheiros copiados   : {stats.get('files_copied', 0)}\n"
            f"Sem acesso           : {stats.get('files_denied', 0)}\n"
            f"MB analisados        : {stats.get('mb_scanned', 0.0):.2f}\n"
            f"MB copiados          : {stats.get('mb_copied', 0.0):.2f}\n"
        )
        QMessageBox.information(self, "Resumo do backup", "Backup concluído!\n\n" + total)
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_pdf.setEnabled(True)
        self._worker = None
        self._thread = None

    def _on_pdf(self):
        # delega para o gerador já existente, se tiveres um; por agora só mensagem
        QMessageBox.information(self, "PDF", "Gerador de PDF em desenvolvimento 🙂")

    # ---------- sessão (tamanho/posições/cfg) ----------
    def _save_session(self, cfg: Dict):
        data = dict(
            geometry=self.saveGeometry().toBase64().data().decode(),
            src=self.src_edit.text().strip(),
            dst=self.dst_edit.text().strip(),
            recursive=self.chk_recursive.isChecked(),
            preserve=self.chk_preserve.isChecked(),
            vss=self.chk_vss.isChecked(),
            archives=self.chk_archives.isChecked(),
            custom=self.custom_edit.text().strip(),
            arch_types=list(self._archive_types()),
            exts=sorted(self._collect_extensions()),
        )
        try:
            SESSION_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _restore_session(self):
        if not SESSION_FILE.exists():
            return
        try:
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            return

        geom = data.get("geometry")
        if geom:
            from PySide6.QtCore import QByteArray
            self.restoreGeometry(QByteArray.fromBase64(geom.encode()))

        self.src_edit.setText(data.get("src", ""))
        self.dst_edit.setText(data.get("dst", ""))
        self.chk_recursive.setChecked(bool(data.get("recursive", True)))
        self.chk_preserve.setChecked(bool(data.get("preserve", True)))
        self.chk_vss.setChecked(bool(data.get("vss", False)))
        self.chk_archives.setChecked(bool(data.get("archives", True)))
        self.custom_edit.setText(data.get("custom", ""))

        # restaurar extensões marcadas
        want = set(data.get("exts", []))
        def mark(item: QTreeWidgetItem):
            txt = item.text(0).lower()
            if item.childCount() == 0 and txt in want:
                item.setCheckState(0, Qt.Checked)
            for i in range(item.childCount()):
                mark(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            mark(self.tree.topLevelItem(i))


# ---------- bootstrap ----------
def iniciar_app():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    iniciar_app()
