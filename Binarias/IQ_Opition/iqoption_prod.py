#!/usr/bin/env python3
"""
iqoption_prod.py — Produção (DEMO por padrão)
- Carrega modelo: modelo_v6.keras
- Usa scaler: scaler_v6.pkl (ou constroi a partir de candles.csv)
- Gera sinais e executa ordens (IQ Option) em modo DEMO/REAL
- Logging robusto em operacoes_log.csv (inclui model_prob, stake, balance_before/after)
- Flags: --dry-run (não envia ordens), --mode (demo/real)
"""

import os
import time
import csv
import argparse
from datetime import datetime, date
import threading
import pickle
import traceback

import numpy as np
import pandas as pd
import ta
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
from iqoptionapi.stable_api import IQ_Option

# ---------------------------
# Config padrão (pode sobrescrever via args)
# ---------------------------
MODEL_FILE = "modelo_v6.keras"
SCALER_FILE = "scaler_v6.pkl"
CANDLES_CSV = "candles.csv"
LOG_CSV = "operacoes_log.csv"

ASSET_DEFAULT = "EURUSD"
ASSET_BACKUP = "EURUSD-OTC"
PERIOD = 60               # segundos por candle (1m)
WINDOW = 50               # janelas LSTM (deve bater com treino)
TH_UP = 0.55
TH_DOWN = 0.45
EXPIRATION_MIN = 1        # expiração em minutos
DEFAULT_STAKE_PCT = 0.01  # 1% do saldo por operação
MIN_STAKE = 1.0           # stake mínimo na moeda da conta
MAX_DAILY_LOSS_PCT = 0.05 # stop loss diário (5% saldo)
DAILY_TAKE_PCT = 0.10     # take profit diário (10% saldo)
MAX_CONSEC_LOSSES = 5
PAYOUT_ESTIMATE = 0.7     # usado só para simulações/backtest

# ---------------------------
# Utilitários: logging
# ---------------------------
def ensure_log_header(path=LOG_CSV):
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp","asset","direction","result","profit",
                "model_prob","stake","balance_before","balance_after"
            ])

def append_log(record, path=LOG_CSV):
    ensure_log_header(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(record)

# ---------------------------
# IQ Option helpers
# ---------------------------
def connect_iq(email, password, retries=5, wait=5):
    for attempt in range(retries):
        try:
            api = IQ_Option(email, password)
            api.connect()
            time.sleep(1)
            if api.check_connect():
                api.change_balance("PRACTICE")  # default demo
                print("[IQ] Conectado (DEMO) - saldo:", api.get_balance(), api.get_currency())
                return api
        except Exception as e:
            print("[IQ] erro conexão:", e)
        print(f"[IQ] tentativa {attempt+1}/{retries} falhou. Esperando {wait}s...")
        time.sleep(wait)
    raise ConnectionError("Não foi possível conectar ao IQ Option.")

def safe_get_all_open_time(api):
    try:
        return api.get_all_open_time()
    except Exception:
        return None

def choose_open_asset(api, primary, backup):
    ot = safe_get_all_open_time(api)
    if not ot:
        return backup
    for cat in ("binary","turbo","digital"):
        group = ot.get(cat, {})
        if isinstance(group, dict):
            if group.get(primary, {}).get("open", False):
                return primary
            if group.get(backup, {}).get("open", False):
                return backup
    return backup

def fetch_candles(api, asset, period, n):
    raw = api.get_candles(asset, period, n, time.time())
    df = pd.DataFrame(raw)
    df['at'] = pd.to_datetime(df['from'], unit='s')
    df = df[['at','open','max','min','close','volume']].sort_values('at').reset_index(drop=True)
    return df

def send_order(api, asset, amount, direction, expiration_min):
    try:
        status, order_id = api.buy(amount, asset, direction, expiration_min)
        return status, order_id
    except Exception as e:
        print("[IQ] send_order exception:", e)
        return False, None

def get_trade_result(api, order_id, timeout=100):
    waited = 0
    while waited < timeout:
        try:
            if hasattr(api, "check_win_v4"):
                res = api.check_win_v4(order_id)
                if res is not None:
                    return float(res)
            if hasattr(api, "check_win_v3"):
                res = api.check_win_v3(order_id)
                if res is not None:
                    return float(res)
        except Exception:
            pass
        time.sleep(2)
        waited += 2
    return None

# ---------------------------
# Features / model helpers
# ---------------------------
def add_indicators(df):
    df = df.copy()
    df['ema9'] = ta.trend.EMAIndicator(df['close'], window=9).ema_indicator()
    df['ema21'] = ta.trend.EMAIndicator(df['close'], window=21).ema_indicator()
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    macd = ta.trend.MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df.dropna(inplace=True)
    return df

def build_features(df):
    df = df.copy().reset_index(drop=True)
    df['ema_diff'] = df['ema9'] - df['ema21']
    X = df[['close','rsi','ema_diff','macd']].values
    return X

def make_last_sequence(X, scaler, window=WINDOW):
    scaled = scaler.transform(X)
    if len(scaled) < window:
        return None
    seq = scaled[-window:].reshape(1, window, scaled.shape[1])
    return seq

# ---------------------------
# Risk management helpers
# ---------------------------
class RiskManager:
    def __init__(self, stake_pct=DEFAULT_STAKE_PCT, min_stake=MIN_STAKE,
                 max_daily_loss_pct=MAX_DAILY_LOSS_PCT, daily_take_pct=DAILY_TAKE_PCT,
                 max_consec_losses=MAX_CONSEC_LOSSES):
        self.stake_pct = stake_pct
        self.min_stake = min_stake
        self.max_daily_loss_pct = max_daily_loss_pct
        self.daily_take_pct = daily_take_pct
        self.max_consec_losses = max_consec_losses
        self.daily_pnl = 0.0
        self.consec_losses = 0
        self.last_reset = date.today()

    def reset_daily_if_needed(self):
        if date.today() != self.last_reset:
            self.daily_pnl = 0.0
            self.consec_losses = 0
            self.last_reset = date.today()

    def stake_from_balance(self, balance):
        stake = max(self.min_stake, round(balance * self.stake_pct, 2))
        return stake

    def record_result(self, pnl):
        self.daily_pnl += pnl
        if pnl < 0:
            self.consec_losses += 1
        else:
            self.consec_losses = 0

    def check_limits(self, balance):
        # stop loss reached?
        if self.daily_pnl <= -abs(self.max_daily_loss_pct * balance):
            return False, "stop_loss_daily"
        if self.daily_pnl >= abs(self.daily_take_pct * balance):
            return False, "take_profit_daily"
        if self.consec_losses >= self.max_consec_losses:
            return False, "max_consec_losses"
        return True, None

# ---------------------------
# Main live worker
# ---------------------------
def live_worker(email, password, mode="demo", dry_run=True,
                asset_primary=ASSET_DEFAULT, asset_backup=ASSET_BACKUP,
                period=PERIOD, window=WINDOW, th_up=TH_UP, th_down=TH_DOWN,
                expiration_min=EXPIRATION_MIN, stake_pct=DEFAULT_STAKE_PCT):

    # load model
    if not os.path.exists(MODEL_FILE):
        raise FileNotFoundError(f"{MODEL_FILE} não encontrado. Rode treino antes.")
    model = tf.keras.models.load_model(MODEL_FILE)
    # load scaler
    if os.path.exists(SCALER_FILE):
        with open(SCALER_FILE, "rb") as f:
            scaler = pickle.load(f)
    else:
        if os.path.exists(CANDLES_CSV):
            df_hist = pd.read_csv(CANDLES_CSV, parse_dates=['at']).sort_values('at').reset_index(drop=True)
            df_hist = add_indicators(df_hist)
            Xhist = build_features(df_hist)
            scaler = MinMaxScaler()
            scaler.fit(Xhist)
            # save scaler for future
            with open(SCALER_FILE, "wb") as f:
                pickle.dump(scaler, f)
        else:
            raise FileNotFoundError("Scaler ausente e candles.csv não encontrado para construir scaler.")

    # connect
    api = connect_iq(email, password)
    if mode.lower() == "real":
        api.change_balance("REAL")
    else:
        api.change_balance("PRACTICE")

    rm = RiskManager(stake_pct=stake_pct)
    ensure_log_header()

    print("[LIVE] Iniciando ciclo. Press Ctrl+C para parar.")
    while True:
        try:
            rm.reset_daily_if_needed()

            # choose asset available
            asset = choose_open_asset(api, asset_primary, asset_backup)
            df = fetch_candles(api, asset, period, max(200, window+20))
            df = add_indicators(df)
            X = build_features(df)
            seq = make_last_sequence(X, scaler, window)
            if seq is None:
                print("[LIVE] dados insuficientes, pulando ciclo.")
                time.sleep(period)
                continue

            pred = float(model.predict(seq, verbose=0)[0][0])
            direction = None
            if pred > th_up:
                direction = "call"
            elif pred < th_down:
                direction = "put"

            # compute stake
            balance = api.get_balance()
            stake = rm.stake_from_balance(balance)

            print(f"[{datetime.utcnow().isoformat()}] Asset={asset} Pred={pred:.4f} Direction={direction} Stake={stake} Balance={balance:.2f}")

            if direction:
                if dry_run:
                    # simulate pnl using payout estimate
                    pnl = stake * PAYOUT_ESTIMATE if np.random.rand() > 0.5 else -stake
                    result_label = "win" if pnl > 0 else "loss"
                    print(f"[DRY] Simulated {result_label} pnl={pnl:.2f}")
                    rm.record_result(pnl)
                    append_log([
                        datetime.utcnow().isoformat(), asset, direction, result_label, round(pnl,2),
                        round(pred,6), stake, round(balance,2), round(balance + pnl,2)
                    ])
                else:
                    # check risk limits before sending
                    ok, reason = rm.check_limits(balance)
                    if not ok:
                        print(f"[RISK] trade blocked by {reason}. Pausing loop for 60s.")
                        time.sleep(60)
                        continue
                    status, order_id = send_order(api, asset, stake, direction, expiration_min)
                    if not status:
                        print("[LIVE] Falha ao enviar ordem. Tentando depois.")
                        time.sleep(30)
                        continue
                    print(f"[LIVE] Ordem enviada (id={order_id}). Aguardando resultado...")
                    result_profit = get_trade_result(api, order_id)
                    if result_profit is None:
                        print("[LIVE] Resultado não obtido (timeout). Registrando erro.")
                        append_log([datetime.utcnow().isoformat(), asset, direction, "error", 0.0, round(pred,6), stake, round(balance,2), round(api.get_balance(),2)])
                    else:
                        result_label = "win" if result_profit > 0 else ("loss" if result_profit < 0 else "draw")
                        print(f"[LIVE] Resultado: {result_label} profit={result_profit:.2f}")
                        rm.record_result(result_profit)
                        append_log([datetime.utcnow().isoformat(), asset, direction, result_label, round(result_profit,2), round(pred,6), stake, round(balance,2), round(api.get_balance(),2)])
            else:
                print("[LIVE] Nenhum sinal (skip).")

            # small sleep until next candle
            time.sleep(period)
        except KeyboardInterrupt:
            print("Interrompido pelo usuário.")
            break
        except Exception as e:
            print("Erro no loop:", e)
            traceback.print_exc()
            # tenta reconectar
            try:
                print("Tentando reconectar à IQ Option...")
                api.connect()
                time.sleep(5)
            except:
                time.sleep(5)
            time.sleep(5)

# ---------------------------
# CLI
# ---------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="Email IQ Option")
    parser.add_argument("--password", required=True, help="Senha IQ Option")
    parser.add_argument("--mode", default="demo", choices=["demo","real"], help="demo ou real")
    parser.add_argument("--dry-run", action="store_true", help="Se presente, não envia ordens (apenas simula)")
    parser.add_argument("--asset", default=ASSET_DEFAULT, help="Ativo principal")
    parser.add_argument("--asset-backup", default=ASSET_BACKUP, help="Ativo backup (OTC)")
    parser.add_argument("--stake-pct", type=float, default=DEFAULT_STAKE_PCT, help="Percentual do saldo por trade")
    parser.add_argument("--expiration", type=int, default=EXPIRATION_MIN, help="Expiração em minutos")
    parser.add_argument("--period", type=int, default=PERIOD, help="Periodo do candle em segundos")
    parser.add_argument("--th-up", type=float, default=TH_UP, help="Threshold up")
    parser.add_argument("--th-down", type=float, default=TH_DOWN, help="Threshold down")
    args = parser.parse_args()

    live_worker(
        args.email, args.password,
        mode=args.mode,
        dry_run=args.dry_run,
        asset_primary=args.asset,
        asset_backup=args.asset_backup,
        period=args.period,
        window=WINDOW,
        th_up=args.th_up,
        th_down=args.th_down,
        expiration_min=args.expiration,
        stake_pct=args.stake_pct
    )
