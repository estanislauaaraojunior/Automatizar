"""
risk_manager.py — controle de risco profissional.

Responsabilidades:
  - Sizing pelo %risco fixo do saldo (sem martingale)
  - Stop diário e take profit diário
  - Pausa automática após N losses consecutivos
  - Log completo de cada operação em CSV
"""

import csv
import time
from datetime import datetime, date
from config import (
    STAKE_PCT, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
    MAX_CONSEC_LOSSES, PAUSE_DURATION_SEC, OPERATIONS_LOG,
)


class RiskManager:
    """
    Controla se o bot pode operar e com qual stake.

    Uso:
        rm = RiskManager(initial_balance=1000.0)
        if rm.can_trade():
            stake = rm.get_stake()
            # ... executa operação ...
            rm.record_result(symbol, direction, stake, duration, profit, indicators)
    """

    def __init__(self, initial_balance: float):
        self.balance: float = initial_balance
        self._initial_balance: float = initial_balance

        # Controle diário
        self._today: date = date.today()
        self._daily_start_balance: float = initial_balance
        self._daily_profit: float = 0.0

        # Controle de sequência de perdas
        self._consec_losses: int = 0
        self._pause_until: float = 0.0  # epoch timestamp

        # Inicializa arquivo de log com cabeçalho
        with open(OPERATIONS_LOG, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "symbol", "direction", "stake", "duration",
                "result", "profit",
                "balance_before", "balance_after",
                "ema9", "ema21", "rsi", "adx", "macd_hist",
                "consec_losses",
            ])

    # ──────────────────────────────────────────────
    #  Verificações
    # ──────────────────────────────────────────────

    def is_paused(self) -> bool:
        """True se estiver em período de pausa por losses consecutivos."""
        if time.time() < self._pause_until:
            remaining = int(self._pause_until - time.time())
            print(f"[RISCO] Bot pausado — retorna em {remaining // 60}m {remaining % 60}s")
            return True
        return False

    def can_trade(self) -> bool:
        """True se todas as condições de risco permitirem nova entrada."""
        self._reset_daily_if_needed()

        if self.is_paused():
            return False

        daily_pnl_pct = (
            self._daily_profit / self._daily_start_balance
            if self._daily_start_balance > 0 else 0.0
        )

        if daily_pnl_pct <= -STOP_LOSS_PCT:
            print(
                f"[RISCO] Stop diário atingido: {daily_pnl_pct * 100:.2f}% "
                f"(limite: -{STOP_LOSS_PCT * 100:.0f}%)"
            )
            return False

        if daily_pnl_pct >= TAKE_PROFIT_PCT:
            print(
                f"[RISCO] Take profit diário atingido: {daily_pnl_pct * 100:.2f}% "
                f"(meta: +{TAKE_PROFIT_PCT * 100:.0f}%)"
            )
            return False

        return True

    # ──────────────────────────────────────────────
    #  Sizing
    # ──────────────────────────────────────────────

    def get_stake(self) -> float:
        """Retorna o stake da próxima operação (STAKE_PCT % do saldo atual)."""
        stake = round(self.balance * STAKE_PCT, 2)
        return max(stake, 0.35)  # mínimo aceitável pela Deriv (~$0.35)

    # ──────────────────────────────────────────────
    #  Registro de resultado
    # ──────────────────────────────────────────────

    def record_result(
        self,
        symbol: str,
        direction: str,
        stake: float,
        duration: int,
        profit: float,
        indicators: dict,
    ) -> None:
        """
        Atualiza saldo, controles de risco e salva log.

        Args:
            profit: variação no saldo (positivo = lucro, negativo = prejuízo)
        """
        self._reset_daily_if_needed()

        balance_before = self.balance
        self.balance = round(self.balance + profit, 2)
        self._daily_profit = round(self._daily_profit + profit, 2)

        if profit < 0.0:
            self._consec_losses += 1
        else:
            self._consec_losses = 0

        if self._consec_losses >= MAX_CONSEC_LOSSES:
            self._pause_until = time.time() + PAUSE_DURATION_SEC
            print(
                f"[RISCO] {MAX_CONSEC_LOSSES} losses consecutivos — "
                f"pausando por {PAUSE_DURATION_SEC // 60} minutos"
            )

        result_str = "WIN" if profit >= 0.0 else "LOSS"
        print(
            f"[TRADE] {result_str:4s} | Profit: {profit:+.2f} USD | "
            f"Saldo: {self.balance:.2f} | PnL hoje: {self._daily_profit:+.2f}"
        )

        with open(OPERATIONS_LOG, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                symbol, direction, stake, duration,
                result_str, profit,
                balance_before, self.balance,
                indicators.get("ema9",      ""),
                indicators.get("ema21",     ""),
                indicators.get("rsi",       ""),
                indicators.get("adx",       ""),
                indicators.get("macd_hist", ""),
                self._consec_losses,
            ])

    # ──────────────────────────────────────────────
    #  Interno
    # ──────────────────────────────────────────────

    def _reset_daily_if_needed(self) -> None:
        today = date.today()
        if today != self._today:
            print(f"[RISCO] Novo dia — resetando contadores diários")
            self._today = today
            self._daily_start_balance = self.balance
            self._daily_profit = 0.0
            self._consec_losses = 0
