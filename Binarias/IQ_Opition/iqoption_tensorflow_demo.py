from iqoptionapi.stable_api import IQ_Option
import pandas as pd
import numpy as np
import time
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler

# =========================================
# CONFIGURAÇÕES
# =========================================
EMAIL = input("Email IQ Option: ")
SENHA = input("Senha: ")
ATIVO = "EURUSD"
PERIODO = 60          # 60s = 1m candles
VALOR = 1             # valor da aposta (em dólar)
JANELA = 50           # mesma usada no treino
MODELO_ARQ = "modelo_lstm.h5"  # salvo no treino

# =========================================
# FUNÇÕES
# =========================================
def conectar():
    Iq = IQ_Option(EMAIL, SENHA)
    Iq.connect()
    if not Iq.check_connect():
        raise Exception("Erro de conexão à IQ Option")
    Iq.change_balance("PRACTICE")  # Conta demo
    print("✅ Conectado à conta DEMO IQ Option.")
    return Iq

def pegar_candles(Iq, n=100):
    tempo = time.time()
    candles = Iq.get_candles(ATIVO, PERIODO, n, tempo)
    df = pd.DataFrame(candles)[["from","open","max","min","close","volume"]]
    df["at"] = pd.to_datetime(df["from"], unit="s")
    return df

def preparar_entrada(df, janela, scaler):
    dados = scaler.transform(df[["close"]])
    X = []
    for i in range(janela, len(dados)):
        X.append(dados[i-janela:i, 0])
    X = np.array(X)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    return X

# =========================================
# EXECUÇÃO
# =========================================
Iq = conectar()

# Carregar modelo e scaler
modelo = tf.keras.models.load_model(MODELO_ARQ)
df_treino = pd.read_csv("candles.csv")
scaler = MinMaxScaler(feature_range=(0, 1))
scaler.fit(df_treino[["close"]])

print("🔁 Iniciando monitoramento em tempo real...")

while True:
    try:
        df = pegar_candles(Iq, JANELA + 1)
        preco_atual = df["close"].iloc[-1]
        X = preparar_entrada(df, JANELA, scaler)
        previsao = modelo.predict(X)[-1][0]
        previsao_preco = scaler.inverse_transform([[previsao]])[0][0]

        direcao = "call" if previsao_preco > preco_atual else "put"
        print(f"\n💹 Preço atual: {preco_atual:.5f} | Previsto: {previsao_preco:.5f} → {direcao.upper()}")

        # Faz operação na conta demo
        status, id = Iq.buy(VALOR, ATIVO, direcao, 1)
        if status:
            print("✅ Operação enviada com sucesso!")
        else:
            print("❌ Falha ao enviar ordem.")

        time.sleep(PERIODO)  # aguarda até o próximo candle

    except KeyboardInterrupt:
        print("\n🛑 Execução encerrada manualmente.")
        break
    except Exception as e:
        print("Erro:", e)
        time.sleep(5)
