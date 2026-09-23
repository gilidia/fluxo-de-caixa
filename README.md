# Sistema de Controle de Fluxo de Caixa Automático

Aplicação de linha de comando (CRUD) para gerir **contas a pagar e a receber**, mapeando entradas e saídas e calculando o **saldo real** a cada consulta.

Inspirado em uma solução real de modernização financeira que criei na minha experiência corporativa, para eliminar a falta de controle documental.

## O desafio

Criar um sistema que traga **segurança e auditoria** para a operação diária: saber quanto entrou, quanto saiu e quem alterou o quê.

## Funcionalidades

- Criar, listar, editar e excluir lançamentos (contas a pagar e a receber)
- Dar baixa em um lançamento (marcar como pago ou recebido)
- **Saldo real** (só o que já foi pago ou recebido) e **saldo projetado** (inclui os pendentes)
- **Histórico de auditoria:** toda criação, edição, baixa e exclusão fica registrada com data e hora

## Tecnologias

Python 3.9+ e SQL (SQLite). Não há dependências externas.

## Como executar localmente

1. Clone este repositório: `git clone https://github.com/gilidia/fluxo-de-caixa.git`
2. Instale as dependências: `pip install -r requirements.txt`
3. Execute a aplicação: `python main.py`

Para testar com dados de exemplo: `python main.py --demo`
Para rodar os testes automatizados: `python -m unittest discover -s tests -v`

## Estrutura

```
fluxo-de-caixa/
├── main.py            # menu e interação com o usuário
├── database.py        # tabelas, consultas SQL e regras de saldo
├── tests/             # testes automatizados
└── requirements.txt
```

## Decisões técnicas

- **Valores em centavos (inteiros):** evita erros de arredondamento de ponto flutuante em cálculos financeiros.
- **Consultas parametrizadas:** nenhum dado digitado entra direto no SQL, o que previne SQL Injection.
- **Auditoria na mesma transação:** ou a alteração e o seu registro são gravados juntos, ou nenhum dos dois.
- **Restrições no banco (`CHECK`):** tipo válido e valor maior que zero são garantidos pelo próprio banco, além da validação no Python.
- **LGPD:** o sistema não armazena dados pessoais. Ao evoluir para clientes e fornecedores, o histórico de auditoria já fornece a base para rastreabilidade.

## Próximos passos

- Categorias de despesa e receita
- Relatório mensal exportado em CSV
- Interface web
