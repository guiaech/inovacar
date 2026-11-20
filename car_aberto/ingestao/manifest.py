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


def gerar_manifest(dir_snapshot: Path, data_download: str) -> dict:
    """dir_snapshot = data/raw/{uf}/{aaaa-mm-dd}. A data da pasta e a data de disponibilizacao."""
    date.fromisoformat(dir_snapshot.name)
    date.fromisoformat(data_download)
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
    return {
        "uf": dir_snapshot.parent.name,
        "data_disponibilizacao": dir_snapshot.name,
        "data_download": data_download,
        "fonte": "Sicar, consulta publica, base de downloads por UF",
        "arquivos": arquivos,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uf", required=True)
    ap.add_argument("--snapshot", required=True, help="data de disponibilizacao, aaaa-mm-dd")
    ap.add_argument("--data-download", required=True, help="aaaa-mm-dd")
    a = ap.parse_args()
    d = config.DIR_RAW / a.uf.lower() / a.snapshot
    m = gerar_manifest(d, a.data_download)
    (d / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(m['arquivos'])} arquivos em {d / 'manifest.json'}")


if __name__ == "__main__":
    main()
