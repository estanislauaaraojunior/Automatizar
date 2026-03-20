from iqoptionapi.stable_api import IQ_Option
import pandas as pd
import numpy as np
import time, datetime, os, platform, tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt

# =========================
# CONFIGURAÇÕES PRINCIPAIS
# =========================
EMAIL = "estanislau.aarao@gmail.com"
SENHA = "!Q@W3e4r5t"
MODO_CONTA = "PRACTICE"  # "REAL" para conta real
PERCENTUAL_BANCA = 2.0   # risco por operação
PERIODO = 60             # candle de 1 minuto
QUANTIDADE_CANDLES = 100
TOLERANCIA_LSTM = 0.0001
ADX_TENDENCIA_MINIMA = 25
TEMPO_DE_ESPERA_ENTRADA = 60  # segundos antes do fechamento
RISCO_POR_TRADE = 0.02        # 2% da banca

# =========================
# CONEXÃO IQ OPTION
# =========================
print("🔌 Conectando à IQ Option...")
Iq = IQ_Option(EMAIL, SENHA)
Iq.connect()
Iq.change_balance(MODO_CONTA)
if Iq.check_connect():
    print("✅ Conectado à IQ Option!")
else:
    raise ConnectionError("❌ Falha ao conectar à IQ Option.")

# =========================
# FUNÇÕES AUXILIARES
# =========================
def beep():
    """Som de alerta cross-platform."""
    if platform.system() == "Windows":
        import winsound
        winsound.Beep(1500, 400)
    else:
        os.system('printf "\a"')

def esperar_proximo_ponto_analise(periodo_candle, tempo_antecedencia):
    """Espera até 1 minuto antes do fechamento do candle atual."""
    agora = time.time()
    inicio_candle = agora - (agora % periodo_candle)
    fechamento_candle = inicio_candle + periodo_candle
    ponto_analise = fechamento_candle - tempo_antecedencia
    tempo_restante = ponto_analise - agora
    if tempo_restante < 0:
        ponto_analise += periodo_candle
        tempo_restante = ponto_analise - agora
    print(f"🕐 Aguardando {int(tempo_restante)}s até o ponto de análise (1 min antes do fechamento)...")
    time.sleep(max(1, tempo_restante))
    return True

def obter_candles(api, par, periodo, quantidade):
    """Obtém candles do ativo."""
    velas = api.get_candles(par, periodo, quantidade, time.time())
    df = pd.DataFrame(velas)
    df['at'] = pd.to_datetime(df['from'], unit='s')
    return df

def adicionar_indicadores_v3(df):
    """Adiciona indicadores técnicos."""
    df['ema_fast'] = df['close'].ewm(span=5).mean()
    df['ema_slow'] = df['close'].ewm(span=20).mean()
    df['macd'] = df['ema_fast'] - df['ema_slow']
    df['signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['signal']
    df['rsi'] = calcular_rsi(df['close'])
    df['obv'] = calcular_obv(df)
    df['adx'], df['di_plus'], df['di_minus'] = calcular_adx(df)
    df['bb_mid'] = df['close'].rolling(20).mean()
    return df

def calcular_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calcular_obv(df):
    obv = [0]
    for i in range(1, len(df)):
        if df['close'][i] > df['close'][i-1]:
            obv.append(obv[-1] + df['volume'][i])
        elif df['close'][i] < df['close'][i-1]:
            obv.append(obv[-1] - df['volume'][i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=df.index)

def calcular_adx(df, period=14):
    """ADX e DI+/-"""
    high = df['max']
    low = df['min']
    close = df['close']
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    di_plus = 100 * (plus_dm.rolling(period).mean() / atr)
    di_minus = 100 * (abs(minus_dm).rolling(period).mean() / atr)
    dx = (abs(di_plus - di_minus) / (di_plus + di_minus)) * 100
    adx = dx.rolling(period).mean()
    return adx.fillna(0), di_plus.fillna(0), di_minus.fillna(0)

def verificar_qualidade_mercado_v2(df, par):
    """Valida tendência e volatilidade."""
    adx = df['adx'].iloc[-1]
    di_plus = df['di_plus'].iloc[-1]
    di_minus = df['di_minus'].iloc[-1]
    volatilidade = df['close'].pct_change().std() * 100
    if adx > ADX_TENDENCIA_MINIMA and volatilidade > 0.05 and abs(di_plus - di_minus) > 5:
        return True, adx
    return False, adx

def calcular_valor_entrada(saldo, risco):
    return round(saldo * risco, 2)

# =========================
# LOOP PRINCIPAL
# =========================
pares = [p for p in Iq.get_all_open_time()['turbo'] if Iq.get_all_open_time()['turbo'][p]['open']]
print(f"🎯 Ativos disponíveis: {len(pares)} pares.")
modelo_treinado = None
janela_scaler = None
par_atual = None
saldo_atual = Iq.get_balance()

while True:
    try:
        # Selecionar ativo com tendência forte
        if par_atual is None:
            print("\n🔍 Buscando ativo com tendência significativa...")
            melhor_par = None
            melhor_adx = 0
            for par in pares:
                df = obter_candles(Iq, par, PERIODO, QUANTIDADE_CANDLES)
                df = adicionar_indicadores_v3(df)
                adx = df['adx'].iloc[-1]
                if adx > melhor_adx:
                    melhor_par = par
                    melhor_adx = adx
            par_atual = melhor_par
            print(f"✅ Ativo escolhido: {par_atual} (ADX: {melhor_adx:.2f})")

        # Esperar até 1 min antes do fechamento
        esperar_proximo_ponto_analise(PERIODO, TEMPO_DE_ESPERA_ENTRADA)

        # Obter candles recentes
        df = obter_candles(Iq, par_atual, PERIODO, QUANTIDADE_CANDLES)
        df = adicionar_indicadores_v3(df)
        ultimo = df.iloc[-1]
        adx_atual = ultimo['adx']
        horario_fechamento = pd.to_datetime(ultimo['at']) + pd.Timedelta(seconds=PERIODO)
        horario_entrada = horario_fechamento.strftime("%H:%M:%S")

        # Verificar qualidade do mercado
        qualidade_ok, adx = verificar_qualidade_mercado_v2(df, par_atual)
        preco_atual = ultimo['close']

        # --- PREVISÃO LSTM ---
        features = ['close','ema_fast','ema_slow','macd_hist','rsi','obv','adx','di_plus','di_minus','bb_mid']
        dados_novos = df[features].tail(50).values.astype(float)
        if modelo_treinado and janela_scaler:
            dados_scaled = janela_scaler.transform(dados_novos)
            X_novo = dados_scaled.reshape(1, dados_scaled.shape[0], dados_scaled.shape[1])
            previsao_scaled = modelo_treinado.predict(X_novo, verbose=0)
            dummy = np.zeros((1, janela_scaler.scale_.shape[0]))
            dummy[:,0] = previsao_scaled[0,0]
            previsao_real = janela_scaler.inverse_transform(dummy)[0,0]
        else:
            previsao_real = preco_atual

        # --- DECISÃO FINAL ---
        sinal = None
        if qualidade_ok:
            if previsao_real > preco_atual + TOLERANCIA_LSTM and ultimo['rsi'] < 70 and ultimo['ema_fast'] > ultimo['ema_slow']:
                sinal = "CALL"
            elif previsao_real < preco_atual - TOLERANCIA_LSTM and ultimo['rsi'] > 30 and ultimo['ema_fast'] < ultimo['ema_slow']:
                sinal = "PUT"

        valor_entrada = calcular_valor_entrada(saldo_atual, RISCO_POR_TRADE)

        print(f"[{par_atual}] ADX: {adx:.2f} | RSI: {ultimo['rsi']:.1f} | Previsão: {previsao_real:.5f} | Atual: {preco_atual:.5f}")

        if sinal:
            beep()
            print("\n" + "="*80)
            print(f"🚀 SINAL DETECTADO: {sinal} no par {par_atual}")
            print(f"⏰ ENTRADA EM: {horario_entrada} (faltando 1 minuto)")
            print(f"💵 Valor sugerido: ${valor_entrada:.2f}")
            print("="*80 + "\n")
        else:
            print(f"⚪ Nenhum sinal confirmado neste ciclo.\n")

        time.sleep(5)

    except Exception as e:
        print(f"⚠️ Erro: {e}")
        par_atual = None
        time.sleep(5)
