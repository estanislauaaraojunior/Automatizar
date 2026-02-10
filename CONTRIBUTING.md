# Guia de Contribuição

Obrigado por considerar contribuir para o repositório Automatizar! 🎉

## Como Contribuir

### Reportando Bugs

Se você encontrou um bug:

1. Verifique se o bug já não foi reportado nas [Issues](https://github.com/estanislauaaraojunior/Automatizar/issues)
2. Se não foi, crie uma nova issue incluindo:
   - Descrição clara do problema
   - Passos para reproduzir
   - Comportamento esperado vs atual
   - Screenshots (se aplicável)
   - Versão do Python/Node.js e SO

### Sugerindo Melhorias

Para sugerir melhorias ou novas automações:

1. Abra uma issue com a tag "enhancement"
2. Descreva claramente a melhoria ou automação proposta
3. Explique por que seria útil
4. Se possível, forneça exemplos de uso

### Adicionando Novos Projetos

Ao adicionar um novo projeto de automação:

1. **Escolha a pasta apropriada** baseada no tipo de automação
2. **Crie uma subpasta** com nome descritivo em kebab-case
3. **Inclua um README.md** com:
   - Descrição do projeto
   - Pré-requisitos
   - Instalação
   - Uso
   - Exemplos
   - Possíveis problemas e soluções

4. **Adicione um arquivo de dependências**:
   - `requirements.txt` para Python
   - `package.json` para Node.js
   - Ou equivalente para outras linguagens

5. **Inclua .env.example** se usar variáveis de ambiente

6. **Comente seu código** adequadamente

### Padrões de Código

#### Python
- Siga o [PEP 8](https://pep8.org/)
- Use nomes descritivos de variáveis
- Docstrings para funções e classes

#### JavaScript
- Use ES6+ quando possível
- Utilize async/await para operações assíncronas
- Comentários JSDoc para funções

#### Geral
- Código em inglês, comentários em português (opcional)
- Mensagens de commit claras e descritivas
- Um commit por funcionalidade lógica

### Processo de Pull Request

1. Fork o repositório
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaAutomacao`)
3. Faça commits com mensagens claras
4. Push para sua branch (`git push origin feature/MinhaAutomacao`)
5. Abra um Pull Request

### Checklist para Pull Request

- [ ] O código está funcionando corretamente
- [ ] README.md foi criado/atualizado
- [ ] Dependências estão documentadas
- [ ] Não há credenciais ou dados sensíveis no código
- [ ] .env.example foi incluído (se aplicável)
- [ ] Código está comentado adequadamente
- [ ] Segue os padrões do projeto

## Código de Conduta

- Seja respeitoso com outros contribuidores
- Aceite críticas construtivas
- Foque no que é melhor para a comunidade
- Mostre empatia com outros membros

## Dúvidas?

Se tiver dúvidas, sinta-se à vontade para:
- Abrir uma issue com a tag "question"
- Entrar em contato através do GitHub

Obrigado por contribuir! 🚀
