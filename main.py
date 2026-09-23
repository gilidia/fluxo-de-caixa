"""Controle de Fluxo de Caixa Automático - interface de linha de comando.

Uso:
    python main.py          # abre o menu
    python main.py --demo   # abre o menu já com dados de exemplo
"""
import argparse
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import database as db


# ---------- formatação e leitura de dados ----------
def formatar_reais(centavos):
    texto = f"{abs(centavos) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if centavos < 0 else ''}R$ {texto}"


def ler_valor(texto):
    """Aceita '1500', '1500.50' ou '1.500,50' e devolve centavos (int)."""
    t = texto.strip().replace("R$", "").replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(t)
    except InvalidOperation:
        raise ValueError("Valor inválido. Exemplo: 1500,50")
    if valor <= 0:
        raise ValueError("O valor deve ser maior que zero.")
    return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ler_data(texto):
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        raise ValueError("Data inválida. Use o formato dd/mm/aaaa.")


def ler_tipo(texto):
    t = texto.strip().lower()
    if t not in db.TIPOS:
        raise ValueError("Tipo inválido. Digite 'pagar' ou 'receber'.")
    return t


def ler_texto(texto):
    if not texto.strip():
        raise ValueError("Informe a descrição.")
    return texto.strip()


def data_br(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def situacao(l):
    if not l["pago"]:
        return "Pendente"
    return "Recebido" if l["tipo"] == "receber" else "Pago"


def pedir(rotulo, conversor, atual=None):
    """Repete a pergunta até a resposta ser válida. Enter mantém o valor atual (na edição)."""
    while True:
        bruto = input(rotulo)
        if atual is not None and not bruto.strip():
            return None
        try:
            return conversor(bruto)
        except ValueError as erro:
            print(f"  ! {erro}")


# ---------- telas ----------
def mostrar(lancamentos):
    if not lancamentos:
        print("\nNenhum lançamento encontrado.")
        return
    print(f"\n{'ID':>3}  {'Tipo':<8} {'Vencimento':<11} {'Situação':<9} {'Valor':>14}  Descrição")
    for l in lancamentos:
        print(f"{l['id']:>3}  {l['tipo']:<8} {data_br(l['vencimento']):<11} {situacao(l):<9} "
              f"{formatar_reais(l['valor_centavos']):>14}  {l['descricao']}")


def novo(conn):
    tipo = pedir("Tipo (pagar/receber): ", ler_tipo)
    descricao = pedir("Descrição: ", ler_texto)
    valor = pedir("Valor (R$): ", ler_valor)
    venc = pedir("Vencimento (dd/mm/aaaa): ", ler_data)
    print(f"Lançamento #{db.criar_lancamento(conn, tipo, descricao, valor, venc)} criado.")


def editar(conn):
    lid = pedir("ID do lançamento: ", int)
    atual = db.buscar(conn, lid)
    if atual is None:
        print("Lançamento não encontrado.")
        return
    print("Pressione Enter para manter o valor atual.")
    campos = {
        "tipo": pedir(f"Tipo [{atual['tipo']}]: ", ler_tipo, atual),
        "descricao": (input(f"Descrição [{atual['descricao']}]: ").strip() or None),
        "valor_centavos": pedir(f"Valor [{formatar_reais(atual['valor_centavos'])}]: ", ler_valor, atual),
        "vencimento": pedir(f"Vencimento [{data_br(atual['vencimento'])}]: ", ler_data, atual),
    }
    print("Lançamento atualizado." if db.atualizar(conn, lid, **campos) else "Nada foi alterado.")


def baixar(conn):
    lid = pedir("ID do lançamento: ", int)
    print("Baixa registrada." if db.marcar_pago(conn, lid) else "Lançamento não encontrado.")


def remover(conn):
    lid = pedir("ID do lançamento: ", int)
    if input("Confirma a exclusão? (s/n): ").strip().lower() == "s":
        print("Excluído." if db.excluir(conn, lid) else "Lançamento não encontrado.")


def mostrar_saldo(conn):
    s = db.saldo(conn)
    print("\n--- Saldo ---")
    print(f"Recebido:        {formatar_reais(s['recebido']):>14}")
    print(f"Pago:            {formatar_reais(s['total_pago']):>14}")
    print(f"SALDO REAL:      {formatar_reais(s['saldo_real']):>14}")
    print(f"A receber:       {formatar_reais(s['a_receber']):>14}")
    print(f"A pagar:         {formatar_reais(s['a_pagar']):>14}")
    print(f"Saldo projetado: {formatar_reais(s['saldo_projetado']):>14}")


def mostrar_auditoria(conn):
    print("\n--- Últimas ações registradas ---")
    for a in db.listar_auditoria(conn):
        print(f"{a['data_hora']}  {a['acao']:<8} #{a['lancamento_id']}  {a['detalhes'] or ''}")


def carregar_exemplos(conn):
    hoje = date.today()
    exemplos = [
        ("receber", "Contrato de suporte - Cliente A", 450000, 5),
        ("receber", "Manutenção de rede - Cliente B", 180000, 12),
        ("pagar", "Aluguel do escritório", 250000, 3),
        ("pagar", "Internet e telefonia", 32990, 8),
        ("pagar", "Licença de software", 89900, 15),
    ]
    for tipo, desc, valor, dias in exemplos:
        lid = db.criar_lancamento(conn, tipo, desc, valor, (hoje + timedelta(days=dias)).isoformat())
        if dias <= 5:
            db.marcar_pago(conn, lid)


MENU = """
=== Controle de Fluxo de Caixa ===
1) Novo lançamento     5) Excluir
2) Listar todos        6) Ver saldo
3) Editar              7) Histórico de auditoria
4) Marcar como pago    0) Sair
"""


def main():
    parser = argparse.ArgumentParser(description="Controle de Fluxo de Caixa")
    parser.add_argument("--demo", action="store_true", help="carrega dados de exemplo")
    args = parser.parse_args()

    conn = db.conectar()
    if args.demo and not db.listar(conn):
        carregar_exemplos(conn)
        print("Dados de exemplo carregados.")

    acoes = {"1": novo, "3": editar, "4": baixar, "5": remover, "6": mostrar_saldo, "7": mostrar_auditoria,
             "2": lambda c: mostrar(db.listar(c))}
    while True:
        print(MENU)
        opcao = input("Escolha: ").strip()
        if opcao == "0":
            break
        if opcao in acoes:
            try:
                acoes[opcao](conn)
            except sqlite3.Error as erro:
                print(f"Erro no banco de dados: {erro}")
        else:
            print("Opção inválida.")
    conn.close()


if __name__ == "__main__":
    main()
