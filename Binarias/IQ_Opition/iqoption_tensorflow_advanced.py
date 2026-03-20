from iqoptionapi.stable_api import IQ_Option
import pandas as pd
import numpy as np
import time
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
import ta

# =========================================
# CONFIGURAÇÕES
# =========================================
EMAIL = input("Email IQ Option: ")
SENHA = input("Senha: ")
ATIVO = "BTCUSD"
PERIODO = 60          # candle de 1 minuto
VALOR = 1             # valor da operação
JANELA = 50
MODELO_ARQ = "modelo_lstm.h5"
SCALER_BASE = "candles.csv"
LOG_ARQ = "operacoes_log.csv"

# =========================================
# FUNÇÕES
# =========================================
def conectar():
    Iq = IQ_Option(EMAIL, SENHA)
    Iq.connect()
    if not Iq.check_connect():
        raise Exception("Erro ao conectar na IQ Option.")
    Iq.change_balance("PRACTICE")  # conta demo
    print("✅ Conectado à conta DEMO IQ Option.")
    return Iq

def pegar_candles(Iq, n=200):
    tempo = time.time()
    candles = Iq.get_candles(ATIVO, PERIODO, n, tempo)
    df = pd.DataFrame(candles)[["from", "open", "max", "min", "close", "volume"]]
    df["at"] = pd.to_datetime(df["from"], unit="s")
    return df

def adicionar_indicadores(df):
    df["ema_fast"] = ta.trend.EMAIndicator(df["close"], window=9).ema_indicator()
    df["ema_slow"] = ta.trend.EMAIndicator(df["close"], window=21).ema_indicator()
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd = ta.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd.macd()
    df["signal"] = macd.macd_signal()
    df.dropna(inplace=True)
    return df

def preparar_entrada(df, janela, scaler):
    dados = scaler.transform(df[["close"]])
    X = []
    for i in range(janela, len(dados)):
        X.append(dados[i-janela:i, 0])
    X = np.array(X)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    return X

def gerar_sinal(df, previsao_preco, preco_atual):
    ultima = df.iloc[-1]
    tendencia = "alta" if ultima["ema_fast"] > ultima["ema_slow"] else "baixa"
    rsi = ultima["rsi"]
    macd_pos = ultima["macd"] > ultima["signal"]

    if previsao_preco > preco_atual and tendencia == "alta" and rsi < 70 and macd_pos:
        return "call"
    elif previsao_preco < preco_atual and tendencia == "baixa" and rsi > 30 and not macd_pos:
        return "put"
    return None

# =========================================
# EXECUÇÃO PRINCIPAL
# =========================================
Iq = conectar()

modelo = tf.keras.models.load_model(MODELO_ARQ)
df_treino = pd.read_csv(SCALER_BASE)
scaler = MinMaxScaler(feature_range=(0, 1))
scaler.fit(df_treino[["close"]])

print("🚀 Iniciando bot inteligente com indicadores técnicos...\n")

while True:
    try:
        df = pegar_candles(Iq, JANELA + 100)
        df = adicionar_indicadores(df)
        preco_atual = df["close"].iloc[-1]

        X = preparar_entrada(df, JANELA, scaler)
        previsao = modelo.predict(X)[-1][0]
        previsao_preco = scaler.inverse_transform([[previsao]])[0][0]

        direcao = gerar_sinal(df, previsao_preco, preco_atual)

        print(f"\n💹 Preço atual: {preco_atual:.5f} | Previsto: {previsao_preco:.5f}")
        print(f"📊 Tendência: {'Alta' if df['ema_fast'].iloc[-1] > df['ema_slow'].iloc[-1] else 'Baixa'} | RSI: {df['rsi'].iloc[-1]:.2f}")

        if direcao:
            print(f"⚡ Sinal confirmado → {direcao.upper()}")

            status, id = Iq.buy(VALOR, ATIVO, direcao, 1)
            if status:
                print("✅ Ordem executada com sucesso!")
                pd.DataFrame([{
                    "horario": pd.Timestamp.now(),
                    "ativo": ATIVO,
                    "direcao": direcao,
                    "preco_atual": preco_atual,
                    "preco_previsto": previsao_preco
                }]).to_csv(LOG_ARQ, mode='a', header=False, index=False)
            else:
                print("❌ Falha ao enviar ordem.")
        else:
            print("⏸️ Nenhum sinal forte detectado (condições não ideais).")

        time.sleep(PERIODO)

    except KeyboardInterrupt:
        print("\n🛑 Execução encerrada manualmente.")
        break
    except Exception as e:
        print("⚠️ Erro:", e)
        time.sleep(5)
