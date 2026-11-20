"""Instrumentacao: sistema de arquivos fsspec que conta os bytes que o DuckDB realmente le.

Uso: con.register_filesystem(fs) e caminhos com prefixo conta://. Soma total e por arquivo.
"""

from __future__ import annotations

from collections import Counter

from fsspec.implementations.local import LocalFileSystem


class _Contador:
    def __init__(self, f, fs, caminho: str):
        self._f, self._fs, self._caminho = f, fs, caminho

    def _somar(self, n: int) -> None:
        self._fs.bytes_lidos += n
        self._fs.por_arquivo[self._caminho] += n

    def read(self, n=-1):
        dados = self._f.read(n)
        self._somar(len(dados))
        return dados

    def readinto(self, b):
        n = self._f.readinto(b)
        self._somar(n or 0)
        return n

    def __getattr__(self, nome):
        return getattr(self._f, nome)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self._f.close()


class FSContador(LocalFileSystem):
    """LocalFileSystem com protocolo conta:// que soma os bytes efetivamente lidos."""

    protocol = ("conta",)
    root_marker = ""
    cachable = False

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.zerar()

    def zerar(self) -> None:
        self.bytes_lidos = 0
        self.por_arquivo: Counter[str] = Counter()

    @classmethod
    def _strip_protocol(cls, path):
        path = path[len("conta://") :] if str(path).startswith("conta://") else path
        return super()._strip_protocol(path)

    def _open(self, path, mode="rb", **kw):
        return _Contador(super()._open(path, mode, **kw), self, str(path))

    def unstrip_protocol(self, name):
        return "conta://" + name
