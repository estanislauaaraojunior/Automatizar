"""
executor.py — cliente WebSocket da Deriv e execução de ordens.

Responsabilidades:
  - Gerenciar ciclo de vida da conexão WebSocket
  - Autorizar token e subscrever fluxo de ticks
  - Chamar strategy.get_signal() a cada tick
  - Enviar proposals de compra/venda via API Deriv
  - Rastrear contratos abertos e registrar resultado via RiskManager

Fluxo de uma operação:
  tick → get_signal() → send_proposal → handle_proposal (buy) → handle_contract (result)
"""

import json
from collections import deque
from typing import Optional

import websocket

from config import (
    APP_ID, TOKEN, SYMBOL,
    DURATION, DURATION_UNIT, BASIS, CURRENCY,
    MIN_TICKS,
)
from risk_manager import RiskManager
from strategy import get_signal


class DerivBot:
    """
    Bot de trading para a plataforma Deriv via WebSocket API.

    Args:
        risk_manager: instância de RiskManager já inicializada
        demo:         True  → exibe avisos de modo demo
                      False → opera em conta real (requer TOKEN de conta real)
    """

    def __init__(self, risk_manager: RiskManager, demo: bool = True) -> None:
        self.risk_manager = risk_manager
        self.demo = demo
        self._ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"

        # Histórico de preços (janela deslizante de 200 ticks)
        self._prices: deque = deque(maxlen=200)

        # Estado da operação em andamento
        self._in_trade: bool = False
        self._pending_direction: str = ""
        self._pending_stake: float = 0.0
        self._pending_indicators: dict = {}
        self._open_contract_id: Optional[str] = None

        self._ws: Optional[websocket.WebSocketApp] = None

    # ─────────────────────────────────────────────────────────
    #  API pública
    # ─────────────────────────────────────────────────────────

    def run(self) -> None:
        """Inicia o bot. Bloqueia até encerramento."""
        mode = "DEMO" if self.demo else "REAL 💸"
        print(f"\n{'=' * 55}")
        print(f"  Deriv Trading Bot — Modo: {mode}")
        print(f"  Símbolo : {SYMBOL}")
        print(f"  Duração : {DURATION} {DURATION_UNIT}")
        print(f"  Saldo   : {self.risk_manager.balance:.2f} USD")
        print(f"  Stake   : {self.risk_manager.get_stake():.2f} USD (1% do saldo)")
        print(f"{'=' * 55}\n")

        ws = websocket.WebSocketApp(
            self._ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._ws = ws
        ws.run_forever(reconnect=5)

    # ─────────────────────────────────────────────────────────
    #  Handlers WebSocket
    # ─────────────────────────────────────────────────────────

    def _on_open(self, ws) -> None:
        print("[BOT] Conectado à Deriv WebSocket API")
        ws.send(json.dumps({"authorize": TOKEN}))

    def _on_message(self, ws, message: str) -> None:
        data = json.loads(message)

        if "error" in data:
            print(f"[BOT] Erro API: {data['error']['message']}")
            return

        msg_type = data.get("msg_type", "")

        if msg_type == "authorize":
            self._handle_authorize(ws, data["authorize"])
        elif msg_type == "tick":
            self._handle_tick(ws, data["tick"])
        elif msg_type == "proposal":
            self._handle_proposal(ws, data["proposal"])
        elif msg_type == "buy":
            self._handle_buy(ws, data["buy"])
        elif msg_type == "proposal_open_contract":
            self._handle_contract_update(data["proposal_open_contract"])

    def _on_error(self, ws, error) -> None:
        print(f"[BOT] Erro WebSocket: {error}")

    def _on_close(self, ws, code, msg) -> None:
        print(f"[BOT] Conexão encerrada (código: {code}) — tentando reconectar...")

    # ─────────────────────────────────────────────────────────
    #  Lógica de negócio
    # ─────────────────────────────────────────────────────────

    def _handle_authorize(self, ws, auth: dict) -> None:
        balance = float(auth.get("balance", self.risk_manager.balance))
        self.risk_manager.balance = balance
        print(f"[BOT] Autorizado | Saldo real: {balance:.2f} USD")
        ws.send(json.dumps({"ticks": SYMBOL, "subscribe": 1}))

    def _handle_tick(self, ws, tick: dict) -> None:
        price = float(tick["quote"])
        self._prices.append(price)

        # Aguardar acúmulo de ticks para indicadores estáveis
        n = len(self._prices)
        if n < MIN_TICKS:
            print(f"\r[BOT] Aquecendo... {n}/{MIN_TICKS} ticks", end="", flush=True)
            return

        # Não abrir nova ordem se já há contrato ativo
        if self._in_trade:
            return

        if not self.risk_manager.can_trade():
            return

        prices_list = list(self._prices)
        signal, indicators = get_signal(prices_list)
        self._print_status(price, indicators, signal)

        if signal in ("BUY", "SELL"):
            self._send_proposal(ws, signal, indicators)

    def _send_proposal(self, ws, direction: str, indicators: dict) -> None:
        contract_type = "CALL" if direction == "BUY" else "PUT"
        stake = self.risk_manager.get_stake()

        # Salva estado da operação pendente
        self._pending_direction   = direction
        self._pending_stake       = stake
        self._pending_indicators  = indicators

        proposal = {
            "proposal":       1,
            "amount":         stake,
            "basis":          BASIS,
            "contract_type":  contract_type,
            "currency":       CURRENCY,
            "duration":       DURATION,
            "duration_unit":  DURATION_UNIT,
            "symbol":         SYMBOL,
        }
        ws.send(json.dumps(proposal))
        print(
            f"\n[BOT] → {direction} | Stake: {stake:.2f} USD | "
            f"ADX:{indicators.get('adx', '?'):.1f} RSI:{indicators.get('rsi', '?'):.1f}"
        )

    def _handle_proposal(self, ws, proposal: dict) -> None:
        proposal_id = proposal["id"]
        self._in_trade = True
        ws.send(json.dumps({"buy": proposal_id, "price": self._pending_stake}))

    def _handle_buy(self, ws, buy: dict) -> None:
        contract_id = str(buy.get("contract_id", ""))
        self._open_contract_id = contract_id
        print(f"[BOT] Contrato aberto | ID: {contract_id}")

        # Subscrever atualizações do contrato para capturar o resultado
        if contract_id:
            ws.send(json.dumps({
                "proposal_open_contract": 1,
                "contract_id":           int(contract_id),
                "subscribe":             1,
            }))

    def _handle_contract_update(self, contract: dict) -> None:
        if not contract.get("is_sold"):
            return  # contrato ainda aberto

        profit = float(contract.get("profit", 0.0))

        self.risk_manager.record_result(
            symbol     = SYMBOL,
            direction  = self._pending_direction,
            stake      = self._pending_stake,
            duration   = DURATION,
            profit     = profit,
            indicators = self._pending_indicators,
        )

        self._in_trade         = False
        self._open_contract_id = None

    # ─────────────────────────────────────────────────────────
    #  Display
    # ─────────────────────────────────────────────────────────

    def _print_status(self, price: float, indicators: dict, signal: Optional[str]) -> None:
        if not indicators:
            return

        adx_v   = indicators.get("adx", 0.0)
        rsi_v   = indicators.get("rsi", 0.0)
        ema9_v  = indicators.get("ema9", 0.0)
        ema21_v = indicators.get("ema21", 0.0)
        mach_v  = indicators.get("macd_hist", 0.0)

        tag = ""
        if adx_v < 20:
            tag = "[LATERAL]"
        elif signal:
            tag = f"[→ {signal}]"

        print(
            f"\r[TICK] {price:.4f} | "
            f"EMA9:{ema9_v:.4f} EMA21:{ema21_v:.4f} | "
            f"RSI:{rsi_v:.1f} ADX:{adx_v:.1f} MACD_H:{mach_v:+.5f} "
            f"{tag}          ",
            end="",
            flush=True,
        )
