"""Visão clássica (formulário) do Crítico Jurídico Inteligente."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.container import AppContainer
from src.domain.entities import ReviewResult

_REPORT_FILE_NAME = "relatorio_critico.md"


def render(container: AppContainer) -> None:
    """Renderiza a visão clássica baseada em upload + botão de análise."""
    st.title("⚖️ Crítico Jurídico Inteligente — modo clássico")
    st.caption(
        "RAG jurídico + avaliação estrutural + comparação semântica com petições fortes"
    )

    _render_sidebar(container)

    uploaded_file = st.file_uploader("Envie sua petição em PDF", type=["pdf"])
    if uploaded_file is None:
        st.info("Envie um arquivo PDF para iniciar a análise.")
        return

    petition_path = _persist_upload(container, uploaded_file)
    _reset_session_for_new_upload(uploaded_file.name)
    st.success(f"Arquivo recebido: {uploaded_file.name}")

    if st.button("Analisar petição", type="primary", use_container_width=True):
        _run_analysis(container, petition_path)

    review = st.session_state.get("analysis_result")
    if review:
        _render_results(container, review)


def _render_sidebar(container: AppContainer) -> None:
    with st.sidebar:
        st.header("Base RAG")
        st.write(f"Índice: `{container.settings.paths.index_dir}`")

        if st.button(
            "Baixar PDFs da internet", type="primary", use_container_width=True
        ):
            _run_scraping(container)

        if st.button("Recriar índice RAG", use_container_width=True):
            _rebuild_index(container)

        st.divider()
        st.write("Fluxo recomendado:")
        st.write("1. Clique em **Baixar PDFs da internet**.")
        st.write("2. Clique em **Recriar índice RAG**.")
        st.write("3. Envie sua petição nesta interface.")


def _run_scraping(container: AppContainer) -> None:
    with st.spinner("Baixando PDFs. Isso pode levar alguns minutos..."):
        try:
            result = container.download_petitions_use_case.execute()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao baixar PDFs: {exc}")
            return
    st.success(result.message)


def _rebuild_index(container: AppContainer) -> None:
    with st.spinner("Recriando índice a partir dos PDFs baixados..."):
        try:
            chunks, documents, _ = container.build_index_use_case.execute()
            report_path = container.generate_corpus_report_use_case.execute(
                documents, chunks
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao recriar índice: {exc}")
            return
    st.success(f"Índice atualizado. Relatório: {report_path}")


def _persist_upload(container: AppContainer, uploaded_file) -> Path:
    uploads_dir = container.settings.paths.uploads_dir
    reports_dir = container.settings.paths.reports_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    petition_path = uploads_dir / uploaded_file.name
    petition_path.write_bytes(uploaded_file.getbuffer())
    return petition_path


def _reset_session_for_new_upload(file_name: str) -> None:
    if st.session_state.get("uploaded_file_name") != file_name:
        st.session_state.uploaded_file_name = file_name
        st.session_state.analysis_result = None


def _run_analysis(container: AppContainer, petition_path: Path) -> None:
    with st.spinner("Carregando índice RAG e analisando a petição..."):
        try:
            chunks, documents, embeddings = (
                container.load_or_build_index_use_case.execute()
            )
            review = container.analyze_petition_use_case.execute(
                petition_path=petition_path,
                chunks=chunks,
                documents=documents,
                embeddings=embeddings,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha na análise: {exc}")
            return

    reports_dir = container.settings.paths.reports_dir
    (reports_dir / _REPORT_FILE_NAME).write_text(review.markdown, encoding="utf-8")
    st.session_state.analysis_result = review
    st.success("Análise concluída.")


def _render_results(container: AppContainer, review: ReviewResult) -> None:
    _render_analysis_tab(review)


def _render_analysis_tab(review: ReviewResult) -> None:
    st.subheader("Pontuação")
    if review.scores:
        cols = st.columns(len(review.scores))
        for col, (name, score) in zip(cols, review.scores.items()):
            col.metric(name.capitalize(), f"{score}/10")

    st.subheader("Pontos de melhoria")
    if review.problems:
        for problem in review.problems:
            st.warning(problem)
    else:
        st.success(
            "Nenhum problema estrutural grave foi detectado pelas heurísticas iniciais."
        )

    st.subheader("Sugestões práticas")
    for suggestion in review.suggestions:
        st.write(f"- {suggestion}")

    st.subheader("Features jurídicas detectadas")
    st.dataframe(
        [{"feature": key, "valor": value} for key, value in sorted(review.features.items())],
        use_container_width=True,
    )

    st.subheader("Trechos similares fortes da base")
    for index, similar in enumerate(review.similar_chunks, start=1):
        with st.expander(
            f"{index}. Similaridade {similar.score:.3f} — {similar.chunk.file_name}"
        ):
            st.write(f"Seção detectada: **{similar.chunk.section}**")
            st.write(similar.chunk.text[:1800])

    st.subheader("Relatório completo")
    st.download_button(
        "Baixar relatório Markdown",
        data=review.markdown,
        file_name=_REPORT_FILE_NAME,
        mime="text/markdown",
        use_container_width=True,
    )
    st.markdown(review.markdown)
