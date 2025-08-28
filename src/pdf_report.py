# src/pdf_report.py
from __future__ import annotations

from pathlib import Path
from typing import Dict

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def gerar_relatorio_pdf(stats: Dict, destino: str | Path) -> Path:
    """Gera um relatório PDF com as estatísticas do backup.

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
    pdf_path = destino / "backup_relatorio.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Relatório de Backup")
    y -= 40

    c.setFont("Helvetica", 12)
    linhas = [
        f"Ficheiros analisados : {stats.get('files_scanned', 0)}",
        f"Ficheiros encontrados: {stats.get('files_found', 0)}",
        f"Ficheiros copiados   : {stats.get('files_copied', 0)}",
        f"Sem acesso           : {stats.get('files_denied', 0)}",
        f"MB analisados        : {stats.get('mb_scanned', 0.0):.2f}",
        f"MB copiados          : {stats.get('mb_copied', 0.0):.2f}",
    ]
    for linha in linhas:
        c.drawString(50, y, linha)
        y -= 20

    c.save()
    return pdf_path
