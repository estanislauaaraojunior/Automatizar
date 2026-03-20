from iqoptionapi.stable_api import IQ_Option
import pandas as pd
import numpy as np
import time
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt

# --- CONFIGURAÇÕES GLOBAIS ---
PARES_OTC = ["EURUSD", "GBPUSD", "USDJPY"]
ADX_TENDENCIA_MINIMA = 25  
PERIODO = 60  
QUANTIDADE_CANDLES = 200 
TOLERANCIA_LSTM = 0.00005 # Margem para confirmação LSTM (0.5 pips)

# --- GESTÃO DE CAPITAL ---
SALDO_INICIAL = 1000.0  
RISCO_POR_TRADE = 0.01  # 1% do saldo por trade
saldo_atual = SALDO_INICIAL 

# -------------------------
# Indicadores técnicos (Mantidos)
# -------------------------
def EMA(series, span):
    return series.ewm(span=span, adjust=False).mean()

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

def ADX(df, window=14):
    df['tr0'] = abs(df['max'] - df['min'])
    df['tr1'] = abs(df['max'] - df['close'].shift())
    df['tr2'] = abs(df['min'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['dm_plus'] = np.where((df['max'] - df['max'].shift() > df['min'].shift() - df['min']) & (df['max'] - df['max'].shift() > 0), df['max'] - df['max'].shift(), 0)
    df['dm_minus'] = np.where((df['min'].shift() - df['min'] > df['max'] - df['max'].shift()) & (df['min'].shift() - df['min'] > 0), df['min'].shift() - df['min'], 0)
    atr = EMA(df['tr'], span=window)
    dm_plus_ema = EMA(df['dm_plus'], span=window)
    dm_minus_ema = EMA(df['dm_minus'], span=window)
    df['di_plus'] = (dm_plus_ema / atr) * 100
    df['di_minus'] = (dm_minus_ema / atr) * 100
    df['di_diff'] = abs(df['di_plus'] - df['di_minus'])
    df['di_sum'] = df['di_plus'] + df['di_minus']
    df['dx'] = (df['di_diff'] / df['di_sum']) * 100
    df['adx'] = EMA(df['dx'], span=window)
    return df['adx'], df['di_plus'], df['di_minus']

def bollinger_bands(series, window=20, num_std=2):
    ma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = ma + (std * num_std)
    lower = ma - (std * num_std)
    return ma, upper, lower

# =====================================
# 1. Baixar/Obter candles & 2. Adicionar Indicadores
# =====================================
def obter_candles(Iq: IQ_Option, par, periodo, quantidade):
    agora = time.time()
    candles = Iq.get_candles(par, periodo, quantidade, agora)
    df = pd.DataFrame(candles)
    df["at"] = pd.to_datetime(df["from"], unit="s", utc=True).dt.tz_convert("America/Sao_Paulo")
    df = df[["at", "open", "max", "min", "close", "volume"]]
    return df

def adicionar_indicadores_v3(df):
    df = df.copy().reset_index(drop=True)
    df['ema_fast'] = EMA(df['close'], span=9)
    df['ema_slow'] = EMA(df['close'], span=21)
    macd_line, macd_signal, macd_hist = MACD(df['close'])
    df['macd'] = macd_line
    df['macd_hist'] = macd_hist
    df['rsi'] = RSI(df['close'], period=14)
    df['obv'] = OBV(df)
    df['adx'], df['di_plus'], df['di_minus'] = ADX(df)
    df['bb_mid'], df['bb_upper'], df['bb_lower'] = bollinger_bands(df['close'])
    
    df = df.fillna(method='bfill').fillna(method='ffill')
    return df

# =====================================
# 3. FILTRO DE QUALIDADE DE MERCADO (ABORDAGEM 2)
# =====================================
def verificar_qualidade_mercado_v2(df, par):
    """
    Abordagem 2: Rule-Based atua apenas como um filtro para garantir
    que a LSTM está operando em um mercado com boa tendência e sem extremos.
    """
    ultimo = df.iloc[-1]
    adx_val = ultimo['adx']
    tendencia_forte = adx_val > ADX_TENDENCIA_MINIMA
    
    # Condição 1: Força de Tendência (ADX)
    if not tendencia_forte:
        return False, adx_val
    
    # Condição 2: RSI não está em sobrecompra/sobrevenda extrema (Evita picos de reversão)
    rsi_nao_extremo = (ultimo['rsi'] < 78) and (ultimo['rsi'] > 22)
    
    # Condição 3: Alinhamento básico de tendência (MAs separadas, indicando movimento)
    # Usa uma pequena margem para garantir que MAs não estão muito coladas (mercado lateral)
    ma_alinhada = (ultimo['ema_fast'] > ultimo['ema_slow'] * 1.00005) or \
                  (ultimo['ema_fast'] < ultimo['ema_slow'] * 0.99995)
    
    return tendencia_forte and rsi_nao_extremo and ma_alinhada, adx_val

# =====================================
# 4. Preparar dados, 5. Treinar modelo & 8. Seleção de Par
# (Idênticas à Abordagem 1)
# =====================================
def preparar_dados_multifeature(df, janela=50, features=None):
    if features is None:
        features = ['close', 'ema_fast', 'ema_slow', 'macd_hist', 'rsi', 'obv', 'adx', 'di_plus', 'di_minus', 'bb_mid']
    dados = df[features].values.astype(float)
    scaler = MinMaxScaler(feature_range=(0,1))
    dados_scaled = scaler.fit_transform(dados)

    X, y = [], []
    for i in range(janela, len(dados_scaled)):
        X.append(dados_scaled[i-janela:i, :])
        y.append(dados_scaled[i, 0])
    X = np.array(X)
    y = np.array(y)
    return X, y, scaler

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
    
    print("⏳ Treinando modelo LSTM com dados históricos...")
    modelo.fit(X, y, epochs=epocas, batch_size=batch_size, verbose=0)
    print("✅ Treinamento concluído.")
    return modelo

def selecionar_melhor_par(Iq, lista_pares, periodo, quantidade):
    melhor_par = None
    max_adx = 0
    
    print("🔎 Verificando força de tendência nos pares OTC...")
    for par in lista_pares:
        try:
            df = obter_candles(Iq, par, periodo, quantidade)
            df = adicionar_indicadores_v3(df)
            adx_atual = df['adx'].iloc[-1]
            print(f"   - [{par}] ADX: {adx_atual:.2f}")
            
            if adx_atual > max_adx:
                max_adx = adx_atual
                melhor_par = par
                
        except Exception as e:
            print(f"   - ⚠️ Erro ao processar {par}: {e}")
            continue

    if melhor_par and max_adx >= ADX_TENDENCIA_MINIMA:
        print(f"\n✨ MELHOR PAR SELECIONADO: **{melhor_par}** (ADX: {max_adx:.2f})")
        return melhor_par
    else:
        print("\n❌ Nenhum par OTC atingiu a tendência mínima. Aguardando...")
        return None

def calcular_valor_entrada(saldo, risco_percentual):
    return round(saldo * risco_percentual, 2)


# =====================================
# 7. Execução principal (ABORDAGEM 2)
# =====================================
if __name__ == "__main__":
    email = ("estanislau.aarao@gmail.com")
    senha = ("!Q@W3e4r5t")

    Iq = IQ_Option(email, senha)
    print("🔗 Conectando à IQ Option...")
    Iq.connect()
    if not Iq.check_connect():
        raise Exception("❌ Falha na conexão. Verifique login/senha.")
    print("✅ Conectado à IQ Option!")

    par_atual = None
    modelo_treinado = None 
    janela_scaler = None

    print(f"\n💵 SALDO SIMULADO INICIAL: ${saldo_atual:.2f} | Risco por Trade: {RISCO_POR_TRADE*100:.0f}%")

    while True:
        try:
            if par_atual is None:
                par_atual = selecionar_melhor_par(Iq, PARES_OTC, PERIODO, QUANTIDADE_CANDLES)
                
                if par_atual:
                    df_historico = obter_candles(Iq, par_atual, PERIODO, QUANTIDADE_CANDLES)
                    df_historico = adicionar_indicadores_v3(df_historico)
                    X, y, scaler = preparar_dados_multifeature(df_historico, janela=50)
                    modelo_treinado = treinar_modelo_multifeature(X, y, epocas=20)
                    janela_scaler = scaler

            if par_atual is None:
                print("⏱️ Nenhum par em tendência forte. Tentando novamente em 60s.")
                time.sleep(60)
                continue
                
            df = obter_candles(Iq, par_atual, PERIODO, 100)
            df = adicionar_indicadores_v3(df)
            
            ultimo_candle = df.iloc[-1]
            adx_atual = ultimo_candle['adx']
            horario = pd.to_datetime(ultimo_candle['at']) # Hora para o log
            
            if adx_atual < ADX_TENDENCIA_MINIMA * 0.9: 
                print(f"\n📉 [{par_atual}] Tendência enfraquecida (ADX: {adx_atual:.2f}). Buscando novo par...")
                par_atual = None
                modelo_treinado = None
                continue

            # 4. GERAÇÃO DO FILTRO (Rule-Based)
            qualidade_ok, adx = verificar_qualidade_mercado_v2(df, par_atual)
            
            # --- PREVISÃO LSTM (LIDER) ---
            features_lstm = ['close', 'ema_fast', 'ema_slow', 'macd_hist', 'rsi', 'obv', 'adx', 'di_plus', 'di_minus', 'bb_mid']
            dados_novos = df[features_lstm].tail(50).values.astype(float)
            
            if janela_scaler is None: previsao_real = ultimo_candle['close']
            else:
                dados_novos_scaled = janela_scaler.transform(dados_novos)
                X_novo = dados_novos_scaled.reshape(1, dados_novos_scaled.shape[0], dados_novos_scaled.shape[1])
                previsao_scaled = modelo_treinado.predict(X_novo, verbose=0)
                dummy = np.zeros((1, janela_scaler.scale_.shape[0])); dummy[:,0] = previsao_scaled[0,0]
                previsao_real = janela_scaler.inverse_transform(dummy)[0,0]

            proximo_preco_abertura = ultimo_candle['close']
            print(f"[{par_atual}] ADX: {adx:.2f} | RSI: {ultimo_candle['rsi']:.1f} | LSTM Previsto: {previsao_real:.5f} | Fechamento: {proximo_preco_abertura:.5f}")

            # 5. CONSOLIDAÇÃO DO SINAL (LSTM Lider)
            sinal_final = None
            valor_entrada = calcular_valor_entrada(saldo_atual, RISCO_POR_TRADE)

            if qualidade_ok:
                # CALL: Previsão LSTM é significativamente maior (com margem de tolerância)
                if previsao_real > proximo_preco_abertura + TOLERANCIA_LSTM:
                    print(f"✅ CONFIRMADO! LSTM prevê alta forte. Mercado em qualidade.")
                    sinal_final = "CALL"
                # PUT: Previsão LSTM é significativamente menor (com margem de tolerância)
                elif previsao_real < proximo_preco_abertura - TOLERANCIA_LSTM:
                    print(f"✅ CONFIRMADO! LSTM prevê queda forte. Mercado em qualidade.")
                    sinal_final = "PUT"
                else:
                    print(f"⚪ [{par_atual}] Mercado OK, mas LSTM prevê estabilidade. AGUARDAR.")
            else:
                print(f"⚠️ Mercado sem qualidade para entrada (ADX: {adx:.2f}). AGUARDAR.")
            
            # INFORMAÇÃO DA ENTRADA CLARA
            if sinal_final:
                print("\n" + "="*80)
                print(f"🚀 **SINAL DE ENTRADA DETECTADO NO PAR {par_atual}**")
                print(f"⏰ **HORA EXATA PARA ENTRADA:** {horario.time()}")
                print(f"💸 **VALOR DA ENTRADA:** ${valor_entrada:.2f} (Risco {RISCO_POR_TRADE*100:.0f}%)")
                print(f"💰 **AÇÃO:** FAÇA UM **{sinal_final}** IMEDIATAMENTE! (Vencimento de {PERIODO} segundos)")
                print("="*80 + "\n")
            else:
                print(f"⚪ [{par_atual}] Sem entrada neste candle ({horario.time()}).")

            print("⏱️ Aguardando novo candle...\n")
            time.sleep(PERIODO)
        
        except KeyboardInterrupt:
            print("\n🛑 Execução interrompida pelo usuário.")
            break
        except Exception as e:
            print(f"\n⚠️ Erro inesperado: {e}. O par atual pode ter sido: {par_atual}")
            par_atual = None; modelo_treinado = None; janela_scaler = None
            time.sleep(10)