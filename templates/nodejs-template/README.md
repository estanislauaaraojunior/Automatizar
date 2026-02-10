# Template Node.js - Projeto de Automação

Template básico para criar projetos de automação em Node.js.

## Estrutura do Projeto

```
nodejs-template/
├── README.md           # Este arquivo
├── package.json        # Dependências e scripts
├── .env.example       # Exemplo de variáveis de ambiente
├── index.js           # Script principal
└── utils.js           # Funções auxiliares
```

## Pré-requisitos

- Node.js 16 ou superior
- npm ou yarn

## Instalação

1. Copie este template para um novo diretório
2. Renomeie conforme seu projeto
3. Instale as dependências:

```bash
npm install
```

4. Configure as variáveis de ambiente:

```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

## Uso

```bash
npm start
```

## Scripts Disponíveis

- `npm start` - Executa o script principal
- `npm run dev` - Executa em modo desenvolvimento (com nodemon)

## Customização

1. Edite `index.js` com sua lógica de automação
2. Adicione funções auxiliares em `utils.js`
3. Atualize `package.json` com novas dependências
4. Documente as mudanças neste README

## Dependências

Veja `package.json` para a lista completa de dependências.

## Licença

MIT License - veja LICENSE no repositório principal
