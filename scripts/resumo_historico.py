"""Resumo da tabela de eventos de um intervalo: contagens, transicoes, municipios e meses.

Grava docs/evidencias/historico_{uf}_{anterior}_{atual}.json e imprime tabelas em Markdown.
"""

from __future__ import annotations

import argparse
import json
import sys

import duckdb

from car_aberto import config
from car_aberto.historico.diff import dir_eventos


def consultar(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def resumir(uf: str, ant: str, atu: str) -> dict:
    e = f"read_parquet('{(dir_eventos(uf, ant, atu) / '*.parquet').as_posix()}')"
    con = duckdb.connect()
    return {
        "uf": uf,
        "snapshot_anterior": ant,
        "snapshot_atual": atu,
        "total_eventos": consultar(con, f"SELECT count(*) n FROM {e}")[0]["n"],
        "imoveis_com_evento": consultar(con, f"SELECT count(DISTINCT cod_imovel) n FROM {e}")[0][
            "n"
        ],
        "por_tipo": consultar(
            con,
            f"""SELECT tipo_evento, escopo, count(*) n, count(data_provavel) com_data
                FROM {e} GROUP BY ALL ORDER BY n DESC""",
        ),
        "transicoes_ind_status": consultar(
            con,
            f"""SELECT valor_anterior AS de, valor_atual AS para, count(*) n FROM {e}
                WHERE tipo_evento = 'mudanca_ind_status' GROUP BY ALL ORDER BY n DESC""",
        ),
        "transicoes_des_condic_top10": consultar(
            con,
            f"""SELECT valor_anterior AS de, valor_atual AS para, count(*) n FROM {e}
                WHERE tipo_evento = 'mudanca_des_condic' GROUP BY ALL ORDER BY n DESC LIMIT 10""",
        ),
        "municipios_top10": consultar(
            con,
            f"""SELECT municipio,
                  count(*) FILTER (WHERE tipo_evento <> 'mudanca_dat_atuali') AS eventos,
                  count(DISTINCT cod_imovel) AS imoveis
                FROM {e} GROUP BY 1 ORDER BY eventos DESC LIMIT 10""",
        ),
        "eventos_por_mes_provavel": consultar(
            con,
            f"""SELECT strftime(data_provavel, '%Y-%m') AS mes, count(*) n FROM {e}
                WHERE data_provavel IS NOT NULL GROUP BY 1 ORDER BY 1""",
        ),
    }


def tabela(linhas: list[dict]) -> str:
    if not linhas:
        return "(vazio)"
    cab = list(linhas[0])
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    out += ["| " + " | ".join(str(v) for v in r.values()) + " |" for r in linhas]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uf", default="go")
    ap.add_argument("--anterior", required=True)
    ap.add_argument("--atual", required=True)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    r = resumir(a.uf, a.anterior, a.atual)
    saida = config.RAIZ / "docs" / "evidencias" / f"historico_{a.uf}_{a.anterior}_{a.atual}.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for k, v in r.items():
        print(f"\n### {k}\n")
        print(tabela(v) if isinstance(v, list) else v)
    print(f"\n{saida}")


if __name__ == "__main__":
    main()
