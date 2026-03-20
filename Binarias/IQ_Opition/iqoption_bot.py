# trader_monitor.py
from iqoptionapi.stable_api import IQ_Option
import pandas as pd
import numpy as np
import time
import datetime
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
import os
import warnings
warnings.filterwarnings("ignore")

# -----------------------------
# Indicadores técnicos
# -----------------------------
def EMA(series, span):
    return series.ewm(span=span, adjust=False).mean()

def SMA(series, window):
    return series.rolling(window=window).mean()

def MACD(series, fast=12, slow=26, signal=9):
    ema_fast = EMA(series, fast)
    ema_slow = EMA(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = EMA(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def RSI(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/period, adjust=False).mean()
    ma_down = down.ewm(alpha=1/period, adjust=False).mean()
    rs = ma_up / (ma_down + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def bollinger_bands(series, window=20, num_std=2):
    ma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = ma + (std * num_std)
    lower = ma - (std * num_std)
    return ma, upper, lower

def OBV(df):
    obv = [0]
    for i in range(1, len(df)):
        if df['close'].iat[i] > df['close'].iat[i-1]:
            obv.append(obv[-1] + df['volume'].iat[i])
        elif df['close'].iat[i] < df['close'].iat[i-1]:
            obv.append(obv[-1] - df['volume'].iat[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=df.index)

# ADX implementation (Average Directional Index)
def ADX(df, n=14):
    # True Range
    high = df['max']
    low = df['min']
    close = df['close']
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr_smooth = tr.rolling(window=n).sum()
    plus_dm_smooth = pd.Series(plus_dm).rolling(window=n).sum()
    minus_dm_smooth = pd.Series(minus_dm).rolling(window=n).sum()

    plus_di = 100 * (plus_dm_smooth / (tr_smooth + 1e-10))
    minus_di = 100 * (minus_dm_smooth / (tr_smooth + 1e-10))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
    adx = dx.rolling(window=n).mean()
    return adx, plus_di, minus_di

# -----------------------------
# Funções principais
# -----------------------------
def baixar_candles_IQ(Iq, par="EURUSD", periodo=60, quantidade=200):
    """
    Usa Iq.get_candles(par, periodo, quantidade, agora)
    Retorna DataFrame com colunas: at, open, max, min, close, volume
    """
    agora = time.time()
    candles = Iq.get_candles(par, periodo, quantidade, agora)
    df = pd.DataFrame(candles)
    df["at"] = pd.to_datetime(df["from"], unit="s")
    df = df[["at", "open", "max", "min", "close", "volume"]]
    return df

def adicionar_indicadores(df):
    df = df.copy().reset_index(drop=True)
    # EMAs
    df['ema_fast'] = EMA(df['close'], span=9)
    df['ema_slow'] = EMA(df['close'], span=21)
    # MACD
    macd_line, macd_signal, macd_hist = MACD(df['close'])
    df['macd'] = macd_line
    df['macd_signal'] = macd_signal
    df['macd_hist'] = macd_hist
    # RSI
    df['rsi'] = RSI(df['close'], period=14)
    # Bollinger
    df['bb_mid'], df['bb_upper'], df['bb_lower'] = bollinger_bands(df['close'], window=20, num_std=2)
    # OBV
    df['obv'] = OBV(df)
    # ADX
    adx, pdi, mdi = ADX(df, n=14)
    df['adx'] = adx
    df['pdi'] = pdi
    df['mdi'] = mdi
    # preencher NaNs
    df = df.fillna(method='bfill').fillna(method='ffill')
    return df

# Rule-based immediate signal generator (uses indicators)
def gerar_sinal_imediato(df):
    ultimo = df.iloc[-1]
    anterior = df.iloc[-2]

    # CALL conditions
    cond_ema = ultimo['ema_fast'] > ultimo['ema_slow']
    cond_macd = (anterior['macd_hist'] < 0) and (ultimo['macd_hist'] > 0)
    cond_rsi = (ultimo['rsi'] > 50) and (ultimo['rsi'] < 80)
    cond_bb = ultimo['close'] > ultimo['bb_mid']
    cond_adx = ultimo['adx'] > 20 and ultimo['pdi'] > ultimo['mdi']
    cond_obv = ultimo['obv'] > df['obv'].iloc[-10]

    # PUT conditions (inverse)
    cond_ema_put = ultimo['ema_fast'] < ultimo['ema_slow']
    cond_macd_put = (anterior['macd_hist'] > 0) and (ultimo['macd_hist'] < 0)
    cond_rsi_put = (ultimo['rsi'] < 50) and (ultimo['rsi'] > 20)
    cond_bb_put = ultimo['close'] < ultimo['bb_mid']
    cond_adx_put = ultimo['adx'] > 20 and ultimo['mdi'] > ultimo['pdi']
    cond_obv_put = ultimo['obv'] < df['obv'].iloc[-10]

    ts = pd.to_datetime(ultimo['at'])
    reason = []
    if cond_ema and cond_macd and cond_rsi and cond_bb and cond_adx and cond_obv:
        reason = ['EMA+', 'MACD+', f'RSI {ultimo["rsi"]:.1f}', 'BB+', 'ADX+','OBV+']
        return ("CALL", ts, reason)
    elif cond_ema_put and cond_macd_put and cond_rsi_put and cond_bb_put and cond_adx_put and cond_obv_put:
        reason = ['EMA-', 'MACD-', f'RSI {ultimo["rsi"]:.1f}', 'BB-', 'ADX-','OBV-']
        return ("PUT", ts, reason)
    else:
        return (None, ts, [])

# Preparar dados multifeature para LSTM
def preparar_dados_multifeature(df, janela=50, features=None):
    if features is None:
        features = ['close', 'ema_fast', 'ema_slow', 'macd_hist', 'rsi', 'bb_mid', 'obv', 'adx']
    dados = df[features].values.astype(float)
    scaler = MinMaxScaler(feature_range=(0,1))
    dados_scaled = scaler.fit_transform(dados)

    X, y = [], []
    for i in range(janela, len(dados_scaled)):
        X.append(dados_scaled[i-janela:i, :])
        y.append(dados_scaled[i, 0])  # prever close
    X = np.array(X)
    y = np.array(y)
    return X, y, scaler

# Treina um modelo LSTM simples (apenas uma vez ou sob demanda)
def treinar_modelo_multifeature(X, y, epocas=10, batch_size=32):
    modelo = tf.keras.models.Sequential([
        tf.keras.layers.LSTM(64, return_sequences=True, input_shape=(X.shape[1], X.shape[2])),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.LSTM(32, return_sequences=False),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(16, activation='relu'),
        tf.keras.layers.Dense(1)
    ])
    modelo.compile(optimizer='adam', loss='mean_squared_error')
    modelo.fit(X, y, epochs=epocas, batch_size=batch_size, verbose=0)
    return modelo

# Usar modelo para prever próximo preço (retorna valor previsto em escala original)
def prever_proximo_preco(modelo, df, scaler, janela=50, features=None):
    if features is None:
        features = ['close', 'ema_fast', 'ema_slow', 'macd_hist', 'rsi', 'bb_mid', 'obv', 'adx']
    last_block = df[features].values[-janela:]
    scaled = scaler.transform(last_block)
    X = scaled.reshape(1, scaled.shape[0], scaled.shape[1])
    pred_scaled = modelo.predict(X)
    # reconstruir array dummy para inverter escala
    dummy = np.zeros((1, scaler.scale_.shape[0]))
    dummy[0,0] = pred_scaled[0,0]
    inv = scaler.inverse_transform(dummy)[0,0]
    return inv

# Score para escolher ativo com tendência
def calcular_forca_tendencia(df):
    # diferença relativa entre EMAs
    ema_diff = (df['ema_fast'].iloc[-1] - df['ema_slow'].iloc[-1]) / (df['close'].iloc[-1] + 1e-10)
    rsi = df['rsi'].iloc[-1]
    adx = df['adx'].iloc[-1] if not np.isnan(df['adx'].iloc[-1]) else 0
    vol = df['close'].pct_change().rolling(5).std().iloc[-1]
    vol = 0 if np.isnan(vol) else vol
    score = abs(ema_diff) * (rsi/50) * (1 + adx/50) * (1 + vol*10)
    return score

# Utility: assegura que arquivos de log existam
def garantir_logs():
    if not os.path.exists("sinais_detectados.csv"):
        with open("sinais_detectados.csv", "w") as f:
            f.write("timestamp,ativo,sinal,horario_candle,motivo,confiabilidade\n")
    if not os.path.exists("log_checagem.csv"):
        with open("log_checagem.csv", "w") as f:
            f.write("timestamp,ativo,score,adx,rsi,ema_diff\n")

# -----------------------------
# Execução principal (loop 24h)
# -----------------------------
def main():
    print("=== Robô Monitor - Iniciando ===")
    email = input("Digite seu e-mail IQ Option: ")
    senha = input("Digite sua senha: ")

    periodo = 60        # timeframe em segundos (1 min)
    qtd_candles = 200   # histórico por ativo para análise
    tempo_max_analisar = 10 * 60  # 10 minutos em segundos
    janela_lstm = 50

    garantir_logs()

    print("🔗 Conectando à IQ Option...")
    Iq = IQ_Option(email, senha)
    Iq.connect()
    if not Iq.check_connect():
        raise Exception("❌ Falha na conexão. Verifique login/senha.")
    print("✅ Conectado à IQ Option!")

    # construir lista de pares padrão + tentar adicionar ativos abertos da API (digital e forex)
    pares_base = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "EURGBP", "EURJPY",
        "GBPJPY", "NZDUSD"
    ]
    # adicionar OTC variantes comum (se desejar)
    pares_otc_guess = [p + "-OTC" for p in pares_base]
    pares = pares_base + pares_otc_guess

    # tentar pegar pares abertos via API e mesclar
    try:
        all_open = Iq.get_all_open_time()
        # all_open pode ter chaves 'forex', 'digital', 'turbo' dependendo da versão da API
        for k in ['forex', 'digital', 'turbo', 'binary']:
            if k in all_open:
                try:
                    keys = list(all_open[k].keys())
                    for key in keys:
                        if key not in pares:
                            pares.append(key)
                except Exception:
                    pass
    except Exception:
        # se falhar, seguimos com pares locais
        pass

    print(f"Ativos considerados: {len(pares)} pares (lista inicial).")

    # opcional: treinar modelo LSTM inicial usando último ativo disponível (treinamento leve)
    modelo = None
    scaler = None
    modelo_treinado_para = None

    while True:
        try:
            # 1) varrer pares e calcular score de tendência
            melhor_par = None
            melhor_score = 0
            detalhes_melhor = None

            for par in pares:
                try:
                    df = baixar_candles_IQ(Iq, par=par, periodo=periodo, quantidade=qtd_candles)
                    df = adicionar_indicadores(df)
                    score = calcular_forca_tendencia(df)

                    # salvar log de checagem
                    with open("log_checagem.csv", "a") as f:
                        f.write(f"{datetime.datetime.now()},{par},{score:.6f},{df['adx'].iloc[-1]:.3f},{df['rsi'].iloc[-1]:.2f},{(df['ema_fast'].iloc[-1]-df['ema_slow'].iloc[-1]):.6f}\n")

                    if score > melhor_score:
                        melhor_score = score
                        melhor_par = par
                        detalhes_melhor = df
                except Exception as e:
                    # problemas com par: ignora e continua
                    # print(f"Erro lendo {par}: {e}")
                    continue

            if not melhor_par:
                print("❌ Nenhum par analisável no momento. Aguardando 1 minuto...")
                time.sleep(60)
                continue

            print(f"\n🔥 Ativo escolhido para monitoramento: {melhor_par} (score {melhor_score:.6f})\n")

            # 2) Treinar (ou reciclar) modelo LSTM para este ativo, se não estiver treinado para ele
            try:
                if modelo is None or modelo_treinado_para != melhor_par:
                    X, y, scaler_local = preparar_dados_multifeature(detalhes_melhor, janela=janela_lstm)
                    if len(X) > 10:  # número mínimo de janelas para treinar
                        print(f"🔁 Treinando LSTM leve para {melhor_par} (pode demorar alguns segundos)...")
                        modelo = treinar_modelo_multifeature(X, y, epocas=6, batch_size=32)
                        scaler = scaler_local
                        modelo_treinado_para = melhor_par
                        print("✅ Modelo treinado (versão leve).")
                    else:
                        modelo = None
                        scaler = None
                else:
                    pass
            except Exception as e:
                modelo = None
                scaler = None

            # 3) monitorar ativo por até 10 minutos (10 candles)
            inicio = time.time()
            encontrou_sinal = False
            while (time.time() - inicio) < tempo_max_analisar:
                try:
                    df_mon = baixar_candles_IQ(Iq, par=melhor_par, periodo=periodo, quantidade=qtd_candles)
                    df_mon = adicionar_indicadores(df_mon)

                    sinal, horario_candle, motivos = gerar_sinal_imediato(df_mon)
                    confianca = 0.0

                    # se houver modelo treinado, prever próximo preço e usar como força extra
                    if modelo is not None and scaler is not None:
                        try:
                            pred = prever_proximo_preco(modelo, df_mon, scaler, janela=janela_lstm)
                            ultimo_preco = df_mon['close'].iloc[-1]
                            delta_pct = (pred - ultimo_preco) / (ultimo_preco + 1e-10)
                            # baseado no delta, mapear para confiança 0-100
                            confianca_modelo = min(100, max(0, abs(delta_pct) * 1000))  # heurística
                        except Exception:
                            confianca_modelo = 0.0
                    else:
                        confianca_modelo = 0.0

                    # se sinal rule-based existe, combinar com confiança do modelo
                    if sinal:
                        # base confidence from indicators: count how many motivos existem (max 6)
                        base_conf = min(100, len(motivos) / 6 * 80)  # até 80 vindo das regras
                        confianca = round(min(100, base_conf + confianca_modelo * 0.2), 1)
                        ts_str = pd.to_datetime(horario_candle).strftime("%Y-%m-%d %H:%M:%S")
                        print("\n✅ Oportunidade detectada!")
                        print(f"Ativo: {melhor_par}")
                        print(f"Horário do candle: {ts_str}")
                        print(f"Sinal: {sinal}")
                        print(f"Motivos: {', '.join(motivos)}")
                        print(f"Confiabilidade estimada: {confianca}%\n")

                        # salvar sinal no CSV
                        with open("sinais_detectados.csv", "a") as f:
                            motivos_texto = "|".join(motivos) if motivos else ""
                            f.write(f"{datetime.datetime.now()},{melhor_par},{sinal},{ts_str},{motivos_texto},{confianca}\n")

                        encontrou_sinal = True
                        # esperar próximo candle para evitar spam e então voltar a varrer ativos
                        time.sleep(periodo)
                        break
                    else:
                        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sem sinal em {melhor_par} — último candle {df_mon['at'].iloc[-1]} — aguardando próximo candle...")
                        time.sleep(periodo)
                except Exception as e:
                    print(f"⚠️ Erro durante monitoramento de {melhor_par}: {e}")
                    time.sleep(5)

            if not encontrou_sinal:
                print(f"⏰ Nenhuma oportunidade em {melhor_par} nos últimos 10 minutos. Irei escolher outro ativo.\n")
                time.sleep(2)

        except KeyboardInterrupt:
            print("\n🛑 Execução interrompida pelo usuário. Encerrando.")
            break
        except Exception as e:
            print(f"⚠️ Erro principal do loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
