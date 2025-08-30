# src/pdf_report.py
from __future__ import annotations

from pathlib import Path
from typing import Dict
import datetime


from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def gerar_relatorio_pdf(stats: Dict, destino: str | Path) -> Path:
    """Gera um relatório PDF com as estatísticas do backup.

    O ficheiro é guardado com o nome ``backup_relatorio_<data>_<hora>.pdf``.


    Parameters
    ----------
    stats: Dict
        Dicionário com as estatísticas do backup.
    destino: str | Path
        Pasta onde o relatório será guardado.

    Returns
    -------
    Path
        Caminho para o ficheiro PDF criado.


    """
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = destino / f"backup_relatorio_{timestamp}.pdf"




    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Relatório de Backup")
    y -= 40

    c.setFont("Helvetica", 12)

    def _format_size(mb: float) -> str:
        if mb >= 1024 ** 2:
            return f"{mb / (1024 ** 2):.2f} TB"
        if mb >= 1024:
            return f"{mb / 1024:.2f} GB"
        return f"{mb:.2f} MB"

    def _format_duration(seconds: float) -> str:
        return str(datetime.timedelta(seconds=int(seconds)))

    # Tempos
    inicio = stats.get("start_time")
    fim = stats.get("end_time")
    dur = stats.get("duration", 0)
    if inicio:
        try:
            inicio = datetime.datetime.fromisoformat(inicio).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    if fim:
        try:
            fim = datetime.datetime.fromisoformat(fim).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    vss = stats.get("vss", {})
    if vss.get("usado"):
        vss_line = "Acesso VSS        : Sucesso"
    else:
        motivo = vss.get("motivo", "")
        vss_line = f"Acesso VSS        : Falha - {motivo}"

    linhas = [
        f"Início              : {inicio}",
        f"Fim                 : {fim}",
        f"Duração             : {_format_duration(dur)}",
        f"Ficheiros analisados: {stats.get('files_scanned', 0)}",
        f"Ficheiros encontrados: {stats.get('files_found', 0)}",
        f"Ficheiros copiados  : {stats.get('files_copied', 0)}",
        f"Sem acesso          : {stats.get('files_denied', 0)}",
        f"Dados analisados    : {_format_size(stats.get('mb_scanned', 0.0))}",
        f"Dados copiados      : {_format_size(stats.get('mb_copied', 0.0))}",
        vss_line,
    ]
    for linha in linhas:
        if linha is not None:
            c.drawString(50, y, linha)
            y -= 20

    # Tipos de ficheiro
    ext_counts = stats.get("ext_counts", {})
    ext_sizes = stats.get("ext_sizes", {})
    ext_arch = stats.get("ext_from_archives", {})
    if ext_counts:
        y -= 10
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Tipos de ficheiro:")
        y -= 20
        c.setFont("Helvetica", 12)
        for ext in sorted(ext_counts):
            count = ext_counts[ext]
            size = _format_size(ext_sizes.get(ext, 0.0))
            from_arch = ext_arch.get(ext, 0)
            linha = f".{ext}: {count} ficheiros ({size})"
            if from_arch:
                linha += f" [{from_arch} de ficheiros compactados]"
            c.drawString(60, y, linha)
            y -= 20
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 12)

    c.save()
    return pdf_path

