"""
strategy.py — motor de decisão.

Recebe histórico de preços (ticks) e retorna o sinal de entrada
junto com os valores dos indicadores calculados.

Condições de entrada (todas devem ser satisfeitas):

  BUY  → EMA9 > EMA21  AND  preço > EMA9  AND  RSI [35–65]
          AND  ADX > 20  AND  MACD_hist > 0  AND  momentum > 0

  SELL → EMA9 < EMA21  AND  preço < EMA9  AND  RSI [35–65]
          AND  ADX > 20  AND  MACD_hist < 0  AND  momentum < 0

  None → qualquer filtro falhou (mercado lateral ou indefinido)
"""

from typing import Optional, Tuple
import indicators as ind
from config import (
    EMA_FAST, EMA_SLOW,
    RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    ADX_PERIOD, ADX_MIN,
    BB_PERIOD, BB_STD,
)

# Tipo de retorno: (sinal, dict com valores dos indicadores)
SignalResult = Tuple[Optional[str], dict]


def get_signal(prices: list) -> SignalResult:
    """
    Avalia o estado do mercado e retorna ("BUY" | "SELL" | None, indicadores).

    O dict `indicadores` está sempre populado quando há dados suficientes,
    mesmo quando o sinal é None — útil para exibição e logging.
    """
    # ── Calcular todos os indicadores ──────────────────────
    ema9      = ind.ema(prices, EMA_FAST)
    ema21     = ind.ema(prices, EMA_SLOW)
    rsi_val   = ind.rsi(prices, RSI_PERIOD)
    macd_res  = ind.macd(prices, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    adx_val   = ind.adx(prices, ADX_PERIOD)
    bb_res    = ind.bollinger(prices, BB_PERIOD, BB_STD)
    mom       = ind.momentum(prices, 3)

    # Dados insuficientes para qualquer cálculo
    if any(v is None for v in [ema9, ema21, rsi_val, macd_res, adx_val, mom]):
        return None, {}

    macd_line, macd_sig, macd_hist = macd_res
    last_price = prices[-1]

    indicators: dict = {
        "ema9":      round(ema9, 5),
        "ema21":     round(ema21, 5),
        "rsi":       round(rsi_val, 2),
        "adx":       round(adx_val, 2),
        "macd_line": round(macd_line, 6),
        "macd_hist": round(macd_hist, 6),
        "momentum":  round(mom, 6),
    }

    if bb_res is not None:
        bb_upper, bb_mid, bb_lower = bb_res
        indicators.update({
            "bb_upper":  round(bb_upper, 5),
            "bb_mid":    round(bb_mid, 5),
            "bb_lower":  round(bb_lower, 5),
        })

    # ── Filtro 1: ADX — bloquear mercado lateral ────────────
    if adx_val < ADX_MIN:
        return None, indicators

    # ── Filtro 2: RSI — evitar extremos ────────────────────
    if not (RSI_OVERSOLD <= rsi_val <= RSI_OVERBOUGHT):
        return None, indicators

    # ── Sinal de COMPRA ─────────────────────────────────────
    if (
        ema9 > ema21          # tendência de alta confirmada
        and last_price > ema9  # preço acima da média rápida
        and macd_hist > 0      # momentum positivo
        and mom > 0            # últimos ticks subindo
    ):
        return "BUY", indicators

    # ── Sinal de VENDA ──────────────────────────────────────
    if (
        ema9 < ema21           # tendência de baixa confirmada
        and last_price < ema9  # preço abaixo da média rápida
        and macd_hist < 0      # momentum negativo
        and mom < 0            # últimos ticks caindo
    ):
        return "SELL", indicators

    # Sem sinal válido (ex: cruzamento recente, aguardar confirmação)
    return None, indicators
