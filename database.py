"""Camada de acesso ao banco de dados (SQLite) do Controle de Fluxo de Caixa.

Decisões técnicas:
- Valores guardados em centavos (INTEGER) para evitar erros de arredondamento.
- Consultas parametrizadas (?) em todo o código, evitando SQL Injection.
- Toda alteração grava um registro na tabela `auditoria`, na mesma transação.
"""
import sqlite3
from pathlib import Path

DB_PADRAO = Path(__file__).with_name("fluxo_caixa.db")
TIPOS = ("pagar", "receber")
CAMPOS_EDITAVEIS = ("tipo", "descricao", "valor_centavos", "vencimento")


def conectar(caminho=DB_PADRAO):
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    criar_tabelas(conn)
    return conn


def criar_tabelas(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lancamentos (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo           TEXT    NOT NULL CHECK (tipo IN ('pagar', 'receber')),
            descricao      TEXT    NOT NULL CHECK (length(trim(descricao)) > 0),
            valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
            vencimento     TEXT    NOT NULL,
            pago           INTEGER NOT NULL DEFAULT 0 CHECK (pago IN (0, 1)),
            criado_em      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS auditoria (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            acao          TEXT NOT NULL,
            lancamento_id INTEGER,
            detalhes      TEXT
        );
        """
    )


def _auditar(conn, acao, lancamento_id, detalhes=""):
    conn.execute(
        "INSERT INTO auditoria (acao, lancamento_id, detalhes) VALUES (?, ?, ?)",
        (acao, lancamento_id, detalhes),
    )


def criar_lancamento(conn, tipo, descricao, valor_centavos, vencimento):
    with conn:  # uma transação: o lançamento e o registro de auditoria juntos
        cur = conn.execute(
            "INSERT INTO lancamentos (tipo, descricao, valor_centavos, vencimento) "
            "VALUES (?, ?, ?, ?)",
            (tipo, descricao.strip(), valor_centavos, vencimento),
        )
        _auditar(conn, "CRIAR", cur.lastrowid,
                 f"{tipo} | {descricao.strip()} | {valor_centavos} centavos | venc. {vencimento}")
    return cur.lastrowid


def buscar(conn, lancamento_id):
    return conn.execute("SELECT * FROM lancamentos WHERE id = ?", (lancamento_id,)).fetchone()


def listar(conn, tipo=None, pago=None):
    filtros, params = [], []
    if tipo:
        filtros.append("tipo = ?")
        params.append(tipo)
    if pago is not None:
        filtros.append("pago = ?")
        params.append(int(pago))
    where = f" WHERE {' AND '.join(filtros)}" if filtros else ""
    return conn.execute(f"SELECT * FROM lancamentos{where} ORDER BY vencimento, id", params).fetchall()


def atualizar(conn, lancamento_id, **campos):
    campos = {k: v for k, v in campos.items() if v is not None}
    invalidos = set(campos) - set(CAMPOS_EDITAVEIS)
    if invalidos:
        raise ValueError(f"Campos não permitidos: {', '.join(sorted(invalidos))}")
    antigo = buscar(conn, lancamento_id)
    if antigo is None or not campos:
        return False
    # Os nomes das colunas vêm de uma lista fixa; os valores sempre por parâmetro.
    sets = ", ".join(f"{c} = ?" for c in campos)
    mudancas = "; ".join(f"{c}: {antigo[c]} -> {v}" for c, v in campos.items())
    with conn:
        conn.execute(f"UPDATE lancamentos SET {sets} WHERE id = ?", (*campos.values(), lancamento_id))
        _auditar(conn, "EDITAR", lancamento_id, mudancas)
    return True


def marcar_pago(conn, lancamento_id, pago=True):
    if buscar(conn, lancamento_id) is None:
        return False
    with conn:
        conn.execute("UPDATE lancamentos SET pago = ? WHERE id = ?", (int(pago), lancamento_id))
        _auditar(conn, "BAIXA" if pago else "ESTORNO", lancamento_id)
    return True


def excluir(conn, lancamento_id):
    antigo = buscar(conn, lancamento_id)
    if antigo is None:
        return False
    with conn:
        conn.execute("DELETE FROM lancamentos WHERE id = ?", (lancamento_id,))
        _auditar(conn, "EXCLUIR", lancamento_id,
                 f"{antigo['tipo']} | {antigo['descricao']} | {antigo['valor_centavos']} centavos")
    return True


def saldo(conn):
    """Saldo real = só o que já foi pago/recebido. Projetado = inclui os pendentes."""
    r = conn.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN tipo = 'receber' AND pago = 1 THEN valor_centavos END), 0) AS recebido,
          COALESCE(SUM(CASE WHEN tipo = 'pagar'   AND pago = 1 THEN valor_centavos END), 0) AS total_pago,
          COALESCE(SUM(CASE WHEN tipo = 'receber' AND pago = 0 THEN valor_centavos END), 0) AS a_receber,
          COALESCE(SUM(CASE WHEN tipo = 'pagar'   AND pago = 0 THEN valor_centavos END), 0) AS a_pagar
        FROM lancamentos
        """
    ).fetchone()
    real = r["recebido"] - r["total_pago"]
    return {**dict(r), "saldo_real": real, "saldo_projetado": real + r["a_receber"] - r["a_pagar"]}


def listar_auditoria(conn, limite=20):
    return conn.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
