"""Gera o manifest.json de um snapshot bruto: datas, nome, tamanho e SHA-256 de cada arquivo."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from car_aberto import config


def sha256(caminho: Path, bloco: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        while dados := f.read(bloco):
            h.update(dados)
    return h.hexdigest()


def gerar_manifest(
    dir_snapshot: Path,
    data_download: str,
    disponibilizacao_conhecida: bool = True,
    data_referencia: str | None = None,
) -> dict:
    """dir_snapshot = data/raw/{uf}/{aaaa-mm-dd}. Por padrao a data da pasta e a data de
    disponibilizacao. Quando ela nao e conhecida (snapshot antigo baixado sem registro),
    data_disponibilizacao fica nula e data_referencia explica de onde veio a data da pasta."""
    date.fromisoformat(dir_snapshot.name)
    date.fromisoformat(data_download)
    if not disponibilizacao_conhecida and not data_referencia:
        raise ValueError("sem data de disponibilizacao, informe data_referencia")
    arquivos = []
    for p in sorted(dir_snapshot.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            arquivos.append(
                {
                    "arquivo": p.relative_to(dir_snapshot).as_posix(),
                    "camada": p.parent.name,
                    "bytes": p.stat().st_size,
                    "sha256": sha256(p),
                }
            )
    m = {
        "uf": dir_snapshot.parent.name,
        "data_disponibilizacao": dir_snapshot.name if disponibilizacao_conhecida else None,
    }
    if data_referencia:
        m["data_referencia"] = data_referencia
    return {
        **m,
        "data_download": data_download,
        "fonte": "Sicar, consulta publica, base de downloads por UF",
        "arquivos": arquivos,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uf", required=True)
    ap.add_argument("--snapshot", required=True, help="data de disponibilizacao, aaaa-mm-dd")
    ap.add_argument("--data-download", required=True, help="aaaa-mm-dd")
    ap.add_argument(
        "--sem-disponibilizacao",
        action="store_true",
        help="data de disponibilizacao desconhecida; exige --data-referencia",
    )
    ap.add_argument("--data-referencia", help="de onde vem a data da pasta, texto livre")
    a = ap.parse_args()
    d = config.DIR_RAW / a.uf.lower() / a.snapshot
    m = gerar_manifest(d, a.data_download, not a.sem_disponibilizacao, a.data_referencia)
    (d / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(m['arquivos'])} arquivos em {d / 'manifest.json'}")


if __name__ == "__main__":
    main()
