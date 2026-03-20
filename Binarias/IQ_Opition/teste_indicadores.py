from iqoptionapi.stable_api import IQ_Option
import pandas as pd
import numpy as np
import time
# IMPORTANTE: TensorFlow e Scaler foram removidos

# --- CONFIGURAÇÕES GLOBAIS ---
PARES_OTC = ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC"]
ADX_TENDENCIA_MINIMA = 25  
PERIODO = 60  
QUANTIDADE_CANDLES = 200 
# TOLERANCIA_LSTM foi removida

# --- NOVA CONFIGURAÇÃO DE TEMPO ---
INTERVALO_VERIFICACAO = 5 # Verifica o sinal a cada 5 segundos

# --- GESTÃO DE CAPITAL ---
SALDO_INICIAL = 1000.0  
RISCO_POR_TRADE = 0.01  # 1% do saldo por trade
saldo_atual = SALDO_INICIAL 

# -------------------------
# Indicadores técnicos (Mantidos - Omissão para brevidade)
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
# 3. Gerador de sinais RULE-BASED (PURO)
# =====================================
def gerar_sinal_puro(df, par):
    """
    Abordagem Pura: Regras focadas no Cruzamento de MAs (EMA 9 e BB_Mid 20) como gatilho.
    """
    ultimo = df.iloc[-1]
    anterior = df.iloc[-2]

    adx_val = ultimo['adx']
    tendencia_forte = adx_val > ADX_TENDENCIA_MINIMA
    agora_ts = pd.to_datetime(ultimo['at'])
    
    if not tendencia_forte:
        return (None, agora_ts, adx_val)

    # Condições CALL 
    # Gatilho: Cruzamento de EMA(9) sobre BB_Mid(20)
    cond_ma_cruzamento_call = (anterior['ema_fast'] < anterior['bb_mid']) and (ultimo['ema_fast'] > ultimo['bb_mid']) 
    # Alinhamento: DI+ > DI- e preço acima da EMA longa
    cond_alinhamento_call = (ultimo['di_plus'] > ultimo['di_minus']) and (ultimo['close'] > ultimo['ema_slow'])

    # Condições PUT 
    # Gatilho: Cruzamento de EMA(9) sob BB_Mid(20)
    cond_ma_cruzamento_put = (anterior['ema_fast'] > anterior['bb_mid']) and (ultimo['ema_fast'] < ultimo['bb_mid'])
    # Alinhamento: DI- > DI+ e preço abaixo da EMA longa
    cond_alinhamento_put = (ultimo['di_minus'] > ultimo['di_plus']) and (ultimo['close'] < ultimo['ema_slow'])
    
    if cond_ma_cruzamento_call and cond_alinhamento_call:
        return ("CALL", agora_ts, adx_val)
    elif cond_ma_cruzamento_put and cond_alinhamento_put:
        return ("PUT", agora_ts, adx_val)
    else:
        return (None, agora_ts, adx_val)


# =====================================
# Funções de Suporte e Seleção de Par
# (Mantidas - Omissão para brevidade)
# =====================================

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
# 7. Execução principal (ABORDAGEM PURA) - MODIFICADA
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
    
    # Variável de controle para o pré-aviso
    proximo_candle_entrada = 0 # Tempo UNIX do próximo candle de entrada
    sinal_ativo = None
    
    print(f"\n💵 SALDO SIMULADO INICIAL: ${saldo_atual:.2f} | Risco por Trade: {RISCO_POR_TRADE*100:.0f}%")

    while True:
        try:
            # 1. SELEÇÃO/VERIFICAÇÃO DE PAR (Não exige treinamento)
            if par_atual is None:
                par_atual = selecionar_melhor_par(Iq, PARES_OTC, PERIODO, QUANTIDADE_CANDLES)
            
            if par_atual is None:
                print("⏱️ Nenhum par em tendência forte. Tentando novamente em 60s.")
                time.sleep(60)
                continue
                
            # 2. OBTENÇÃO E ANÁLISE EM TEMPO REAL
            # Obtemos apenas os dados necessários para a verificação rápida (último candle)
            df = obter_candles(Iq, par_atual, PERIODO, 100)
            df = adicionar_indicadores_v3(df)
            
            ultimo_candle = df.iloc[-1]
            adx_atual = ultimo_candle['adx']
            
            # --- Controle de Tempo e Entrada ---
            agora = time.time()
            tempo_inicio_candle = ultimo_candle['at'].timestamp()
            
            # 3. VERIFICAÇÃO CONTÍNUA DE TENDÊNCIA
            if adx_atual < ADX_TENDENCIA_MINIMA * 0.9: 
                print(f"\n📉 [{par_atual}] Tendência enfraquecida (ADX: {adx_atual:.2f}). Buscando novo par...")
                par_atual = None
                sinal_ativo = None # Cancela qualquer sinal pendente
                proximo_candle_entrada = 0
                continue
            
            # Se já temos um sinal ativo, verificamos se é hora de 'executar'
            if sinal_ativo:
                # Se já passamos do tempo de entrada do próximo candle (ou seja, abriu o candle da operação)
                if agora >= proximo_candle_entrada:
                    valor_entrada = calcular_valor_entrada(saldo_atual, RISCO_POR_TRADE)
                    
                    print("\n" + "="*80)
                    print(f"🔥 **EXECUTANDO ENTRADA EM {par_atual} AGORA!**")
                    print(f"⏰ **HORA DA AÇÃO:** {pd.to_datetime(agora, unit='s', utc=True).tz_convert('America/Sao_Paulo').time()}")
                    print(f"💸 **VALOR DA ENTRADA:** ${valor_entrada:.2f} (Risco {RISCO_POR_TRADE*100:.0f}%)")
                    print(f"💰 **AÇÃO:** FAÇA UM **{sinal_ativo}** IMEDIATAMENTE! (Vencimento de {PERIODO} segundos)")
                    print("="*80 + "\n")
                    
                    # AQUI VOCÊ FARIA A CHAMADA REAL À API:
                    # Iq.buy(valor_entrada, par_atual, sinal_ativo, PERIODO)
                    
                    # Após a 'execução' (simulada ou real), resetamos o sinal e agendamos a próxima verificação completa
                    sinal_ativo = None
                    proximo_candle_entrada = 0
                    print("⏱️ Esperando 5 segundos para garantir que o candle da operação foi fechado na plataforma e continuar a rotina...")
                    time.sleep(5)
                    continue # Volta para o topo do loop
                else:
                    # Aguardando o momento da entrada
                    tempo_restante = proximo_candle_entrada - agora
                    print(f"⏳ [{par_atual}] **Pré-aviso ATIVO.** Entrada em {sinal_ativo} será em ~{tempo_restante:.0f}s (no próximo candle).")
                    time.sleep(INTERVALO_VERIFICACAO)
                    continue
            
            # 4. GERAÇÃO E CONSOLIDAÇÃO DO SINAL (Somente se não houver um sinal ativo)
            sinal_rb, horario, adx = gerar_sinal_puro(df, par_atual)
            sinal_final = sinal_rb
            
            # Se detectou um sinal NOVO (no início do candle atual)
            if sinal_final:
                
                # O sinal é gerado no início do candle T. A entrada deve ser no início de T+1 (T + PERIODO)
                proximo_candle_entrada = tempo_inicio_candle + PERIODO 
                sinal_ativo = sinal_final
                
                valor_entrada = calcular_valor_entrada(saldo_atual, RISCO_POR_TRADE)
                
                print("\n" + "="*80)
                print("📢 **PRÉ-AVISO DE ENTRADA (1 MINUTO)!**")
                print(f"🚀 **SINAL DETECTADO NO PAR {par_atual}**")
                print(f"⏰ **HORA PREVISTA PARA ENTRADA:** {pd.to_datetime(proximo_candle_entrada, unit='s', utc=True).tz_convert('America/Sao_Paulo').time()}")
                print(f"💸 **VALOR DA ENTRADA:** ${valor_entrada:.2f} (Risco {RISCO_POR_TRADE*100:.0f}%)")
                print(f"💰 **AÇÃO AGENDADA:** **{sinal_ativo}** (Vencimento de {PERIODO} segundos)")
                print("="*80 + "\n")
                
                # Após o aviso, dorme o intervalo e o loop acima cuidará da execução
                time.sleep(INTERVALO_VERIFICACAO)
            
            else:
                # Sem sinal detectado
                print(f"⚪ [{par_atual}] ADX: {adx:.2f} | RSI: {ultimo_candle['rsi']:.1f} | Sem entrada neste ciclo ({horario.time()}).")
                
                # Dorme pelo intervalo de verificação e checa novamente (o candle estará 'em aberto' por 60s)
                time.sleep(INTERVALO_VERIFICACAO) 
        
        except KeyboardInterrupt:
            print("\n🛑 Execução interrompida pelo usuário.")
            break
        except Exception as e:
            print(f"\n⚠️ Erro inesperado: {e}. O par atual pode ter sido: {par_atual}")
            par_atual = None # Reseta o par em caso de erro
            sinal_ativo = None
            proximo_candle_entrada = 0
            time.sleep(10)
  