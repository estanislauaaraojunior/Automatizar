from iqoptionapi.stable_api import IQ_Option
import pandas as pd
import numpy as np
import time
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt

# -------------------------
# Indicadores técnicos
# -------------------------
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
    up = delta.fillna(0).clip(lower=0)
    down = -1 * delta.fillna(0).clip(upper=0)
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

# =====================================
# 1. Baixar candles da IQ Option
# =====================================
def baixar_candles(email, senha, par="EURUSD", periodo=60, quantidade=1000):
    print("🔗 Conectando à IQ Option...")
    Iq = IQ_Option(email, senha)
    Iq.connect()
    if not Iq.check_connect():
        raise Exception("❌ Falha na conexão. Verifique login/senha.")

    print(f"✅ Conectado! Baixando {quantidade} candles de {par}...")
    agora = time.time()
    candles = Iq.get_candles(par, periodo, quantidade, agora)

    df = pd.DataFrame(candles)
    df["at"] = pd.to_datetime(df["from"], unit="s")
    df = df[["at", "open", "max", "min", "close", "volume"]]
    df.to_csv("candles.csv", index=False)
    print("💾 Candles salvos em candles.csv")
    return df

# =====================================
# 2. Adicionar indicadores ao DataFrame
# =====================================
def adicionar_indicadores(df):
    df = df.copy().reset_index(drop=True)
    df['ema_fast'] = EMA(df['close'], span=9)      # EMA curta
    df['ema_slow'] = EMA(df['close'], span=21)     # EMA longa
    macd_line, macd_signal, macd_hist = MACD(df['close'])
    df['macd'] = macd_line
    df['macd_signal'] = macd_signal
    df['macd_hist'] = macd_hist
    df['rsi'] = RSI(df['close'], period=14)
    df['bb_mid'], df['bb_upper'], df['bb_lower'] = bollinger_bands(df['close'], window=20, num_std=2)
    df['obv'] = OBV(df)
    # pequenas limpezas
    df = df.fillna(method='bfill').fillna(method='ffill')
    return df

# =====================================
# 3. Gerador de sinais rule-based (imediato)
#    - imprime exatamente quando entrar (timestamp do último candle)
# =====================================
def gerar_sinal_imediato(df):
    """
    Regras combinadas (exemplo razoável, não garante sucesso):
      - CALL (compra) quando:
          * ema_fast > ema_slow (tendência de alta)
          * macd_hist cruzou para positivo (momentum)
          * rsi > 50 e < 75 (momentum positivo, sem estar extremo)
          * fechamento acima da bb_mid (confirmação)
          * obv em alta (volume confirma)
      - PUT (venda) quando condições invertidas.
    """
    ultimo = df.iloc[-1]
    anterior = df.iloc[-2]

    # condições CALL
    cond_ema = ultimo['ema_fast'] > ultimo['ema_slow']
    cond_macd = (anterior['macd_hist'] < 0) and (ultimo['macd_hist'] > 0)  # cruzou para cima
    cond_rsi = (ultimo['rsi'] > 50) and (ultimo['rsi'] < 75)
    cond_bb = ultimo['close'] > ultimo['bb_mid']
    cond_obv = ultimo['obv'] > df['obv'].iloc[-10]  # obv maior que 10 candles atrás

    # condições PUT
    cond_ema_put = ultimo['ema_fast'] < ultimo['ema_slow']
    cond_macd_put = (anterior['macd_hist'] > 0) and (ultimo['macd_hist'] < 0)  # cruzou para baixo
    cond_rsi_put = (ultimo['rsi'] < 50) and (ultimo['rsi'] > 25)
    cond_bb_put = ultimo['close'] < ultimo['bb_mid']
    cond_obv_put = ultimo['obv'] < df['obv'].iloc[-10]

    agora_ts = pd.to_datetime(ultimo['at'])

    # decisão
    if cond_ema and cond_macd and cond_rsi and cond_bb and cond_obv:
        print(f"🟢 ENTRE COM CALL na hora {agora_ts} — condições: EMA+, MACD+, RSI {ultimo['rsi']:.1f}, OBV+, BB.")
        return ("CALL", agora_ts)
    elif cond_ema_put and cond_macd_put and cond_rsi_put and cond_bb_put and cond_obv_put:
        print(f"🔴 ENTRE COM PUT na hora {agora_ts} — condições: EMA-, MACD-, RSI {ultimo['rsi']:.1f}, OBV-, BB.")
        return ("PUT", agora_ts)
    else:
        print(f"⚪ Sem sinal claro para entrada no candle {agora_ts}.")
        return (None, agora_ts)

# =====================================
# 4. Preparar dados (agora com múltiplas features)
# =====================================
def preparar_dados_multifeature(df, janela=50, features=None):
    if features is None:
        features = ['close', 'ema_fast', 'ema_slow', 'macd_hist', 'rsi', 'bb_mid', 'obv']
    dados = df[features].values.astype(float)
    scaler = MinMaxScaler(feature_range=(0,1))
    dados_scaled = scaler.fit_transform(dados)

    X, y = [], []
    for i in range(janela, len(dados_scaled)):
        X.append(dados_scaled[i-janela:i, :])
        y.append(dados_scaled[i, 0])  # prever close (índice 0)
    X = np.array(X)
    y = np.array(y)
    return X, y, scaler

# =====================================
# 5. Treinar modelo (mesmo LSTM mas entrada shape ajustada)
# =====================================
def treinar_modelo_multifeature(X, y, epocas=20, batch_size=32):
    modelo = tf.keras.models.Sequential([
        tf.keras.layers.LSTM(64, return_sequences=True, input_shape=(X.shape[1], X.shape[2])),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.LSTM(32, return_sequences=False),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(16, activation='relu'),
        tf.keras.layers.Dense(1)
    ])
    modelo.compile(optimizer='adam', loss='mean_squared_error')
    modelo.fit(X, y, epochs=epocas, batch_size=batch_size, verbose=1)
    print("✅ Treinamento concluído.")
    return modelo

# =====================================
# 6. Testar e plotar previsões
# =====================================
def testar_modelo(modelo, X, y, scaler):
    previsoes = modelo.predict(X)
    # apenas reverter escala do alvo (close) — precisamos reconstruir vetores com formato das features
    # montar array com zeros e colocar a previsão na posição da feature 'close' (índice 0)
    dummy = np.zeros((previsoes.shape[0], scaler.scale_.shape[0]))
    dummy[:,0] = previsoes[:,0]
    inv = scaler.inverse_transform(dummy)[:,0]

    dummy_y = np.zeros((y.shape[0], scaler.scale_.shape[0]))
    dummy_y[:,0] = y
    inv_y = scaler.inverse_transform(dummy_y)[:,0]

    plt.figure(figsize=(10,6))
    plt.plot(inv_y, color='red', label='Preço Real')
    plt.plot(inv, color='blue', label='Previsão')
    plt.title('Previsão de Preço com TensorFlow (multifeature)')
    plt.xlabel('Tempo')
    plt.ylabel('Preço')
    plt.legend()
    plt.show()

# =====================================
# 7. Execução principal
# =====================================
if __name__ == "__main__":
    email = input("Digite seu e-mail IQ Option: ")
    senha = input("Digite sua senha: ")

    # Conecta e baixa primeiros candles
    par = "EURUSD-OTC"
    periodo = 60  # timeframe de 1 minuto
    quantidade = 200
    print(f"Baixando {quantidade} candles de {par}...")
    
    Iq = IQ_Option(email, senha)
    Iq.connect()
    if not Iq.check_connect():
        raise Exception("❌ Falha na conexão. Verifique login/senha.")

    print("✅ Conectado à IQ Option!")

    while True:
        try:
            agora = time.time()
            candles = Iq.get_candles(par, periodo, quantidade, agora)
            df = pd.DataFrame(candles)
            df["at"] = pd.to_datetime(df["from"], unit="s")
            df = df[["at", "open", "max", "min", "close", "volume"]]
            
            # Calcula indicadores
            df = adicionar_indicadores(df)
            
            # Gera sinal
            sinal, horario = gerar_sinal_imediato(df)
            
            if sinal:
                print(f"\n🚨 SINAL DETECTADO: ENTRE COM {sinal} às {horario.time()} no par {par}\n")
            
            # Espera o próximo candle (1 minuto)
            print("⏱️ Aguardando novo candle...\n")
            time.sleep(periodo)
        
        except KeyboardInterrupt:
            print("\n🛑 Execução interrompida pelo usuário.")
            break
        except Exception as e:
            print(f"⚠️ Erro: {e}")
            time.sleep(10)