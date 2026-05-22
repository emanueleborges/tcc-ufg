#!/usr/bin/env python3
"""Script separado para criar/atualizar o índice RAG jurídico."""

from rag_engine import build_index, write_corpus_report


def main() -> int:
    chunks, documents, _embeddings = build_index()
    report = write_corpus_report(documents, chunks)
    print("Base RAG criada/atualizada em: indice_juridico")
    print(f"Relatório da base: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
