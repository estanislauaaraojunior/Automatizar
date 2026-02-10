#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Funções Utilitárias
Funções auxiliares reutilizáveis para automação
"""

import logging
import os
from datetime import datetime


def setup_logger(name):
    """
    Configura e retorna um logger com formatação personalizada.
    
    Args:
        name (str): Nome do logger (geralmente __name__)
        
    Returns:
        logging.Logger: Logger configurado
    """
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    # Cria logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Cria handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    
    # Formato do log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def get_timestamp():
    """
    Retorna timestamp atual formatado.
    
    Returns:
        str: Timestamp no formato YYYY-MM-DD_HH-MM-SS
    """
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')


def validate_env_vars(required_vars):
    """
    Valida se as variáveis de ambiente necessárias estão definidas.
    
    Args:
        required_vars (list): Lista de nomes de variáveis obrigatórias
        
    Raises:
        ValueError: Se alguma variável obrigatória não estiver definida
    """
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(
            f"Variáveis de ambiente faltando: {', '.join(missing_vars)}"
        )


# Adicione mais funções utilitárias conforme necessário
