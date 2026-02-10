# Guia de Boas Práticas para Automação

Este guia apresenta práticas recomendadas ao desenvolver projetos de automação.

## Princípios Gerais

### 1. Segurança em Primeiro Lugar

- **Nunca** comite credenciais no código
- Use variáveis de ambiente (arquivos `.env`)
- Adicione `.env` ao `.gitignore`
- Forneça `.env.example` como template
- Use gerenciadores de secrets quando apropriado

### 2. Código Limpo e Manutenível

- Use nomes descritivos para variáveis e funções
- Comente código complexo
- Divida tarefas grandes em funções menores
- Siga convenções da linguagem (PEP 8 para Python, etc.)
- Mantenha funções com responsabilidade única

### 3. Tratamento de Erros

```python
# Bom ✓
try:
    resultado = executar_automacao()
except ConexaoError as e:
    logger.error(f"Erro de conexão: {e}")
    # Implementar retry ou fallback
except Exception as e:
    logger.error(f"Erro inesperado: {e}")
    # Notificar e/ou registrar
```

```python
# Ruim ✗
try:
    executar_automacao()
except:
    pass  # Nunca faça isso!
```

### 4. Logging Adequado

- Use níveis de log apropriados (DEBUG, INFO, WARN, ERROR)
- Inclua timestamps nos logs
- Registre eventos importantes
- Use logs estruturados quando possível

### 5. Configuração Externa

```python
# Bom ✓
TIMEOUT = int(os.getenv('TIMEOUT', 30))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
```

```python
# Ruim ✗
TIMEOUT = 30  # hardcoded
MAX_RETRIES = 3  # hardcoded
```

## Automação Web

### Selenium/Puppeteer

1. **Use Waits Explícitos**
   - Evite `time.sleep()` fixos
   - Use waits condicionais para elementos

2. **Headless Mode**
   - Use headless para produção
   - Desative para debug

3. **Gerenciamento de Drivers**
   - Use WebDriver Manager
   - Mantenha drivers atualizados

4. **Respeite Limitações**
   - Implemente delays entre requisições
   - Respeite robots.txt
   - Não sobrecarregue servidores

### Web Scraping

1. **Headers Apropriados**
   ```python
   headers = {
       'User-Agent': 'NomeDoBot/1.0',
       'Accept': 'text/html,application/xhtml+xml'
   }
   ```

2. **Rate Limiting**
   ```python
   import time
   time.sleep(1)  # 1 segundo entre requests
   ```

3. **Rotação de User-Agents**
   - Use diferentes user agents
   - Evite bloqueios

## Bots e APIs

### Rate Limiting

```python
from time import sleep
from functools import wraps

def rate_limit(calls_per_second=1):
    min_interval = 1.0 / calls_per_second
    
    def decorator(func):
        last_called = [0.0]
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            
            if left_to_wait > 0:
                sleep(left_to_wait)
            
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        
        return wrapper
    return decorator
```

### Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def chamada_api():
    # Sua chamada à API
    pass
```

## Processamento de Dados

### 1. Validação de Entrada

```python
def processar_dados(arquivo):
    if not os.path.exists(arquivo):
        raise FileNotFoundError(f"Arquivo não encontrado: {arquivo}")
    
    # Validar formato
    if not arquivo.endswith('.csv'):
        raise ValueError("Formato de arquivo inválido")
    
    # Processar...
```

### 2. Tratamento de Dados Grandes

```python
# Use chunks para arquivos grandes
import pandas as pd

for chunk in pd.read_csv('grande.csv', chunksize=10000):
    processar_chunk(chunk)
```

### 3. Backup de Dados

```python
import shutil
from datetime import datetime

def backup_arquivo(arquivo):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = f"{arquivo}.{timestamp}.bak"
    shutil.copy2(arquivo, backup)
```

## Testing

### Testes Unitários

```python
import unittest

class TestAutomacao(unittest.TestCase):
    def test_validacao_dados(self):
        resultado = validar_dados({'campo': 'valor'})
        self.assertTrue(resultado)
    
    def test_processamento(self):
        resultado = processar(['item1', 'item2'])
        self.assertEqual(len(resultado), 2)
```

### Testes de Integração

- Teste com dados reais (ambiente de teste)
- Use mocks para APIs externas
- Implemente testes end-to-end

## Documentação

### README.md Completo

Todo projeto deve incluir:

1. **Descrição** - O que faz
2. **Pré-requisitos** - Dependências
3. **Instalação** - Como instalar
4. **Configuração** - Variáveis de ambiente
5. **Uso** - Como executar
6. **Exemplos** - Casos de uso
7. **Troubleshooting** - Problemas comuns
8. **Licença** - Tipo de licença

### Comentários no Código

```python
def calcular_preco(base, taxa, desconto=0):
    """
    Calcula o preço final com taxa e desconto.
    
    Args:
        base (float): Preço base
        taxa (float): Taxa a ser aplicada (%)
        desconto (float, optional): Desconto (%). Default 0
    
    Returns:
        float: Preço final calculado
    
    Example:
        >>> calcular_preco(100, 10, 5)
        104.5
    """
    preco_com_taxa = base * (1 + taxa/100)
    preco_final = preco_com_taxa * (1 - desconto/100)
    return preco_final
```

## Performance

### 1. Processamento Paralelo

```python
from concurrent.futures import ThreadPoolExecutor

def processar_lista(items):
    with ThreadPoolExecutor(max_workers=5) as executor:
        resultados = executor.map(processar_item, items)
    return list(resultados)
```

### 2. Cache

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def buscar_dados_api(id):
    # Resultado é cacheado
    return api.get(id)
```

### 3. Async/Await

```javascript
// Node.js
async function processarEmParalelo(items) {
  const promises = items.map(item => processarItem(item));
  const resultados = await Promise.all(promises);
  return resultados;
}
```

## Monitoramento

### 1. Logs Estruturados

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module
        }
        return json.dumps(log_obj)
```

### 2. Métricas

```python
import time

def medir_tempo(func):
    def wrapper(*args, **kwargs):
        inicio = time.time()
        resultado = func(*args, **kwargs)
        duracao = time.time() - inicio
        logger.info(f"{func.__name__} levou {duracao:.2f}s")
        return resultado
    return wrapper
```

### 3. Notificações

```python
def notificar_erro(erro):
    # Email, Slack, Telegram, etc.
    enviar_notificacao(f"Erro na automação: {erro}")
```

## Checklist Final

Antes de fazer commit:

- [ ] Código está funcionando
- [ ] Testes passando
- [ ] Sem credenciais no código
- [ ] README atualizado
- [ ] Dependências documentadas
- [ ] .env.example incluído
- [ ] Código comentado
- [ ] Tratamento de erros implementado
- [ ] Logs apropriados
- [ ] Performance verificada

## Recursos Adicionais

- [Python Best Practices](https://docs.python-guide.org/)
- [JavaScript Best Practices](https://github.com/ryanmcdermott/clean-code-javascript)
- [12 Factor App](https://12factor.net/)
- [Semantic Versioning](https://semver.org/)

---

Lembre-se: Código bom é código que outros conseguem entender e manter! 🚀
