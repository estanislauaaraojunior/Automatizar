# ============================================================
#  config.py — configurações centralizadas do bot Deriv
#  Edite APENAS este arquivo para ajustar o comportamento.
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()  # carrega variáveis de .env (ignorado se não existir)

# ----- Conta -----
# True  → opera na conta DEMO (seguro — dinheiro virtual)
# False → opera na conta REAL (requer TOKEN de conta real + confirmação no terminal)
DEMO_MODE = True

# ----- Conexão -----
APP_ID = os.environ.get("DERIV_APP_ID", "1089")
TOKEN  = os.environ["DERIV_TOKEN"]    # defina em .env — crie em: developers.deriv.com

# ----- Instrumento -----
SYMBOL        = "R_100"  # índice sintético 24/7 (sem impacto de notícias)
DURATION      = 5        # duração do contrato
DURATION_UNIT = "t"      # "t" = ticks | "s" = segundos | "m" = minutos
BASIS         = "stake"  # base do contrato
CURRENCY      = "USD"

# ----- Parâmetros dos indicadores -----
EMA_FAST     = 9
EMA_SLOW     = 21
RSI_PERIOD   = 14
MACD_FAST    = 12
MACD_SLOW    = 26
MACD_SIGNAL  = 9
ADX_PERIOD   = 14
BB_PERIOD    = 20
BB_STD       = 2.0

# ----- Filtros de entrada -----
RSI_OVERSOLD    = 35   # abaixo → sobrevendido (não abre SELL aqui)
RSI_OVERBOUGHT  = 65   # acima → sobrecomprado (não abre BUY aqui)
ADX_MIN         = 20   # abaixo → mercado lateral → sem entrada

# ----- Gestão de risco -----
STAKE_PCT         = 0.01   # 1% do saldo por operação
STOP_LOSS_PCT     = 0.05   # -5% do saldo diário → para o dia
TAKE_PROFIT_PCT   = 0.10   # +10% do saldo diário → para o dia
MAX_CONSEC_LOSSES = 3      # losses consecutivos antes de pausar
PAUSE_DURATION_SEC = 1800  # 30 min de pausa

# ----- Aquecimento -----
MIN_TICKS = 50  # ticks mínimos antes de operar (garante indicadores estáveis)

# ----- Arquivos de log -----
TICKS_CSV        = "ticks.csv"
OPERATIONS_LOG   = "operacoes_log.csv"
