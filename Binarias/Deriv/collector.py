"""
collector.py — coletor autônomo de ticks.

Roda INDEPENDENTE do bot de trading.
Salva cada tick em ticks.csv para uso futuro em:
  - Backtesting de estratégias
  - Treinamento de modelos LSTM / RandomForest
  - Análise de distribuição de preços

Uso:
    python collector.py

Pressione Ctrl+C para encerrar. A reconexão é automática (intervalo 5s).
"""

import csv
import json
import os
import signal
import sys
import websocket
from datetime import datetime

from config import APP_ID, TOKEN, SYMBOL, TICKS_CSV

WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"

_tick_count = 0
_ws_instance = None


# ─────────────────────────────────────────────────────────────
#  Utilitários
# ─────────────────────────────────────────────────────────────

def _ensure_header() -> None:
    """Cria o arquivo com cabeçalho se não existir ou estiver vazio."""
    if not os.path.exists(TICKS_CSV) or os.path.getsize(TICKS_CSV) == 0:
        with open(TICKS_CSV, "w", newline="") as f:
            csv.writer(f).writerow(["epoch", "datetime", "symbol", "price"])


# ─────────────────────────────────────────────────────────────
#  Handlers WebSocket
# ─────────────────────────────────────────────────────────────

def on_open(ws) -> None:
    print(f"[COLETOR] Conectado | Símbolo: {SYMBOL}")
    ws.send(json.dumps({"authorize": TOKEN}))
    ws.send(json.dumps({"ticks": SYMBOL, "subscribe": 1}))


def on_message(ws, message: str) -> None:
    global _tick_count

    data = json.loads(message)

    if "error" in data:
        print(f"\n[COLETOR] Erro API: {data['error']['message']}")
        return

    if data.get("msg_type") == "authorize":
        print("[COLETOR] Autorizado. Iniciando coleta...")
        return

    if "tick" in data:
        tick      = data["tick"]
        epoch     = tick["epoch"]
        price     = tick["quote"]
        dt_str    = datetime.fromtimestamp(epoch).isoformat()
        _tick_count += 1

        with open(TICKS_CSV, "a", newline="") as f:
            csv.writer(f).writerow([epoch, dt_str, SYMBOL, price])

        # Exibe contador na mesma linha para não poluir o terminal
        print(
            f"\r[COLETOR] Ticks coletados: {_tick_count:>7,} | "
            f"Último: {price} @ {dt_str}",
            end="",
            flush=True,
        )


def on_error(ws, error) -> None:
    print(f"\n[COLETOR] Erro WebSocket: {error}")


def on_close(ws, close_status_code, close_msg) -> None:
    print(f"\n[COLETOR] Conexão encerrada (código: {close_status_code}) — reconectando...")


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────

def _handle_interrupt(sig, frame) -> None:
    print(f"\n\n[COLETOR] Interrompido. {_tick_count:,} ticks salvos em '{TICKS_CSV}'.")
    if _ws_instance:
        _ws_instance.close()
    sys.exit(0)


def main() -> None:
    global _ws_instance

    _ensure_header()
    signal.signal(signal.SIGINT, _handle_interrupt)

    print("=" * 55)
    print("  Deriv Tick Collector")
    print(f"  Símbolo : {SYMBOL}")
    print(f"  Arquivo : {TICKS_CSV}")
    print("  Pressione Ctrl+C para encerrar")
    print("=" * 55)

    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    _ws_instance = ws
    ws.run_forever(reconnect=5)


if __name__ == "__main__":
    main()
