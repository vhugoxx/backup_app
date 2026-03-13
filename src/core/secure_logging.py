# src/core/secure_logging.py
"""
Módulo de logging seguro para ofuscar informações sensíveis em logs.

SEGURANÇA: Este módulo fornece funções para sanitizar caminhos de arquivo
e outras informações sensíveis antes de gravar em logs.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, Callable


def _obfuscate_path(full_path: str | Path, base_path: Optional[str | Path] = None) -> str:
    """Ofusca um caminho de arquivo para logging seguro.
    
    Args:
        full_path: Caminho completo do arquivo
        base_path: Caminho base para calcular caminho relativo (opcional)
        
    Returns:
        Caminho ofuscado mostrando apenas informação não sensível
    """
    if not full_path:
        return "<caminho vazio>"
    
    path = Path(full_path) if isinstance(full_path, str) else full_path
    
    # Se temos um base_path, tentar mostrar caminho relativo
    if base_path:
        base = Path(base_path) if isinstance(base_path, str) else base_path
        try:
            rel_path = path.relative_to(base)
            # Mostrar apenas os últimos 2-3 componentes do caminho
            parts = rel_path.parts
            if len(parts) <= 3:
                return str(rel_path)
            else:
                return f".../{'/'.join(parts[-3:])}"
        except ValueError:
            pass  # Não é relativo ao base_path
    
    # Fallback: mostrar apenas nome do arquivo e pasta pai
    try:
        if path.parent.name:
            return f".../{path.parent.name}/{path.name}"
        return f".../{path.name}"
    except Exception:
        return "<caminho inválido>"


def _obfuscate_username_in_path(path_str: str) -> str:
    """Remove nomes de usuário de caminhos do sistema.
    
    Args:
        path_str: String contendo um caminho
        
    Returns:
        Caminho com nome de usuário substituído por <user>
    """
    # Padrões comuns de diretórios de usuário
    patterns = [
        # Windows: C:\Users\username\...
        (r'([A-Za-z]:\\Users\\)[^\\]+', r'\1<user>'),
        # Linux/Mac: /home/username/...
        (r'(/home/)[^/]+', r'\1<user>'),
        # Mac: /Users/username/...
        (r'(/Users/)[^/]+', r'\1<user>'),
    ]
    
    result = path_str
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)
    
    return result


def sanitize_log_message(message: str, base_src: Optional[Path] = None, base_dst: Optional[Path] = None) -> str:
    """Sanitiza uma mensagem de log removendo informações sensíveis.
    
    Args:
        message: Mensagem original do log
        base_src: Diretório base de origem (para cálculo de caminhos relativos)
        base_dst: Diretório base de destino (para cálculo de caminhos relativos)
        
    Returns:
        Mensagem sanitizada
    """
    if not message:
        return message
    
    # Primeiro, ofuscar nomes de usuário em caminhos
    sanitized = _obfuscate_username_in_path(message)
    
    # Padrões para detectar caminhos completos
    # Windows: C:\..., D:\...
    windows_path_pattern = r'[A-Za-z]:\\[^\s:*?"<>|]+'
    # Linux/Unix: /home/..., /var/..., etc.
    unix_path_pattern = r'(?<!\w)/(?:home|var|tmp|usr|etc|opt|Users)/[^\s:*?"<>|]+'
    
    def replace_path(match):
        path_str = match.group(0)
        # Tentar determinar se é origem ou destino
        if base_src and path_str.startswith(str(base_src)):
            return _obfuscate_path(path_str, base_src)
        elif base_dst and path_str.startswith(str(base_dst)):
            return _obfuscate_path(path_str, base_dst)
        else:
            return _obfuscate_path(path_str)
    
    # Aplicar substituições
    sanitized = re.sub(windows_path_pattern, replace_path, sanitized)
    sanitized = re.sub(unix_path_pattern, replace_path, sanitized)
    
    return sanitized


def create_secure_log_callback(
    original_callback: Optional[Callable[[str], None]],
    base_src: Optional[Path] = None,
    base_dst: Optional[Path] = None
) -> Callable[[str], None]:
    """Cria um callback de log que sanitiza mensagens automaticamente.
    
    Args:
        original_callback: Callback original para enviar logs
        base_src: Diretório base de origem
        base_dst: Diretório base de destino
        
    Returns:
        Callback wrapper que sanitiza antes de passar para o original
    """
    def secure_callback(message: str) -> None:
        sanitized = sanitize_log_message(message, base_src, base_dst)
        if original_callback:
            original_callback(sanitized)
    
    return secure_callback


# Exportar funções principais
__all__ = [
    'sanitize_log_message',
    'create_secure_log_callback',
    '_obfuscate_path',
    '_obfuscate_username_in_path',
]
