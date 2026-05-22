"""Visão clássica (formulário) do Crítico Jurídico Inteligente."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.container import AppContainer
from src.domain.entities import RecreatedPetition, ReviewResult
from src.presentation.streamlit.components import render_pdf_viewer

_REPORT_FILE_NAME = "relatorio_critico.md"
_RECREATED_MD_FILE = "peticao_recriada.md"
_RECREATED_PDF_FILE = "peticao_recriada.pdf"


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
            total = container.download_petitions_use_case.execute()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao baixar PDFs: {exc}")
            return
    st.success(f"Download concluído. Total de PDFs na base: {total}")


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
        st.session_state.recreated_petition = None
        st.session_state.recreated_pdf_path = None


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
    st.session_state.recreated_petition = None
    st.session_state.recreated_pdf_path = None
    st.success("Análise concluída.")


def _render_results(container: AppContainer, review: ReviewResult) -> None:
    analysis_tab, recreated_tab = st.tabs(["Análise", "Petição recriada"])
    with analysis_tab:
        _render_analysis_tab(review)
    with recreated_tab:
        _render_recreated_tab(container, review)


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


def _render_recreated_tab(container: AppContainer, review: ReviewResult) -> None:
    st.write(
        "A petição original é mantida na íntegra. As melhorias aparecem como "
        "`[COMENTÁRIO (categoria): ...]` inline, logo após o trecho ao qual se referem, "
        "e também em um resumo final. Se o PDF for escaneado, o texto é recuperado por OCR."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        use_internet = st.checkbox(
            "Usar busca na internet", value=True, key="opt_internet"
        )
    with col_b:
        use_ollama = st.checkbox("Usar Ollama local", value=True, key="opt_ollama")

    ollama_model = st.text_input(
        "Modelo do Ollama",
        value=container.settings.ollama.default_model,
        key="opt_model",
    )

    if st.button(
        "Recriar petição",
        type="primary",
        use_container_width=True,
        key="btn_recreate",
    ):
        _run_recreate(
            container=container,
            review=review,
            use_internet=use_internet,
            use_ollama=use_ollama,
            ollama_model=ollama_model.strip() or container.settings.ollama.default_model,
        )

    recreated = st.session_state.get("recreated_petition")
    if recreated:
        _render_recreated_result(container, recreated, ollama_model)


def _run_recreate(
    *,
    container: AppContainer,
    review: ReviewResult,
    use_internet: bool,
    use_ollama: bool,
    ollama_model: str,
) -> None:
    reports_dir = container.settings.paths.reports_dir
    with st.spinner("Recriando a petição com as melhorias propostas..."):
        try:
            recreated = container.recreate_petition_use_case.execute(
                petition_path=Path(review.petition_path),
                review=review,
                use_internet=use_internet,
                use_ollama=use_ollama,
                ollama_model=ollama_model,
            )
            (reports_dir / _RECREATED_MD_FILE).write_text(
                recreated.markdown, encoding="utf-8"
            )
            pdf_path = container.pdf_writer.markdown_to_pdf(
                recreated.markdown, reports_dir / _RECREATED_PDF_FILE
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao recriar petição: {exc}")
            return

    st.session_state.recreated_petition = recreated
    st.session_state.recreated_pdf_path = str(pdf_path)
    st.success("Petição recriada com a petição original preservada.")


def _render_recreated_result(
    container: AppContainer,
    recreated: RecreatedPetition,
    ollama_model: str,
) -> None:
    for warning in recreated.warnings:
        st.warning(warning)
    if recreated.used_ollama:
        st.caption(f"Comentários gerados pelo Ollama (`{ollama_model}`).")

    if recreated.web_references:
        with st.expander("Referências encontradas na internet"):
            for reference in recreated.web_references:
                st.write(f"- [{reference.title}]({reference.url})")
                if reference.snippet:
                    st.caption(reference.snippet)

    pdf_path_value = st.session_state.get("recreated_pdf_path")
    col_dl1, col_dl2 = st.columns(2)
    if pdf_path_value:
        pdf_path = Path(pdf_path_value)
        with col_dl1:
            st.download_button(
                "Baixar PDF",
                data=pdf_path.read_bytes(),
                file_name=_RECREATED_PDF_FILE,
                mime="application/pdf",
                use_container_width=True,
                key="dl_pdf",
            )
    with col_dl2:
        st.download_button(
            "Baixar Markdown",
            data=recreated.markdown,
            file_name=_RECREATED_MD_FILE,
            mime="text/markdown",
            use_container_width=True,
            key="dl_md",
        )

    st.markdown(recreated.markdown)
    if pdf_path_value:
        with st.expander("Visualizar PDF"):
            render_pdf_viewer(Path(pdf_path_value))
