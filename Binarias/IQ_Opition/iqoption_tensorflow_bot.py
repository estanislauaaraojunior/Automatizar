from iqoptionapi.stable_api import IQ_Option
import pandas as pd
import numpy as np
import time
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt

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
# 2. Preparar dados
# =====================================
def preparar_dados(df, janela=50):
    scaler = MinMaxScaler(feature_range=(0, 1))
    dados = scaler.fit_transform(df[["close"]])

    X, y = [], []
    for i in range(janela, len(dados)):
        X.append(dados[i-janela:i, 0])
        y.append(dados[i, 0])
    X, y = np.array(X), np.array(y)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    return X, y, scaler

# =====================================
# 3. Treinar modelo
# =====================================
def treinar_modelo(X, y, epocas=20, batch_size=32):
    modelo = tf.keras.models.Sequential([
        tf.keras.layers.LSTM(50, return_sequences=True, input_shape=(X.shape[1], 1)),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.LSTM(50, return_sequences=False),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(25),
        tf.keras.layers.Dense(1)
    ])
    modelo.compile(optimizer='adam', loss='mean_squared_error')
    modelo.fit(X, y, epochs=epocas, batch_size=batch_size, verbose=1)
    print("✅ Treinamento concluído.")
    return modelo

# =====================================
# 4. Testar e plotar previsões
# =====================================
def testar_modelo(modelo, X, y, scaler):
    previsoes = modelo.predict(X)
    previsoes = scaler.inverse_transform(previsoes)
    reais = scaler.inverse_transform(y.reshape(-1, 1))

    plt.figure(figsize=(10,6))
    plt.plot(reais, color='red', label='Preço Real')
    plt.plot(previsoes, color='blue', label='Previsão')
    plt.title('Previsão de Preço com TensorFlow')
    plt.xlabel('Tempo')
    plt.ylabel('Preço')
    plt.legend()
    plt.show()

# =====================================
# 5. Execução principal
# =====================================
if __name__ == "__main__":
    email = input("Digite seu e-mail IQ Option: ")
    senha = input("Digite sua senha: ")

    df = baixar_candles(email, senha)
    X, y, scaler = preparar_dados(df)
    modelo = treinar_modelo(X, y)
    testar_modelo(modelo, X, y, scaler)
    
    modelo.save("modelo_lstm.h5")
    print("💾 Modelo salvo como modelo_lstm.h5")

