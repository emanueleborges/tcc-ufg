#!/usr/bin/env python3
"""Interface web para submeter uma petição em PDF e receber análise crítica."""

from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

import streamlit as st

from legal_config import INDEX_DIR, REPORTS_DIR, UPLOADS_DIR
from rag_engine import analyze_petition, build_index, build_recreated_petition, load_index, markdown_to_pdf, write_corpus_report

PROJECT_DIR = Path(__file__).resolve().parent
WEBSCRAP_SCRIPT = PROJECT_DIR / "webscrap.py"


def show_pdf_viewer(pdf_path: Path) -> None:
    pdf_base64 = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <iframe
            src="data:application/pdf;base64,{pdf_base64}"
            width="100%"
            height="900"
            style="border: 1px solid #ddd; border-radius: 8px;"
            type="application/pdf">
        </iframe>
        """,
        unsafe_allow_html=True,
    )

st.set_page_config(page_title="Crítico Jurídico IA", page_icon="⚖️", layout="wide")

st.title("⚖️ Crítico Jurídico Inteligente")
st.caption("RAG jurídico + avaliação estrutural + comparação semântica com petições fortes")

with st.sidebar:
    st.header("Base RAG")
    st.write(f"Índice: `{INDEX_DIR}`")
    if st.button("Baixar PDFs da internet", type="primary", use_container_width=True):
        with st.spinner("Baixando PDFs. Isso pode levar alguns minutos..."):
            result = subprocess.run(
                [sys.executable, str(WEBSCRAP_SCRIPT)],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
                check=False,
            )
        if result.returncode == 0:
            st.success("Download de PDFs concluído.")
        else:
            st.error("Falha ao baixar PDFs.")
        with st.expander("Ver saída do webscrap.py"):
            if result.stdout:
                st.code(result.stdout)
            if result.stderr:
                st.code(result.stderr)

    if st.button("Recriar índice RAG", use_container_width=True):
        with st.spinner("Recriando índice a partir dos PDFs baixados..."):
            chunks, documents, _embeddings = build_index()
            report = write_corpus_report(documents, chunks)
        st.success(f"Índice atualizado. Relatório: {report}")
    st.divider()
    st.write("Fluxo recomendado:")
    st.write("1. Clique em **Baixar PDFs da internet**.")
    st.write("2. Clique em **Recriar índice RAG**.")
    st.write("3. Envie sua petição nesta interface.")

uploaded_file = st.file_uploader("Envie sua petição em PDF", type=["pdf"])

if uploaded_file is None:
    st.info("Envie um arquivo PDF para iniciar a análise.")
else:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    petition_path = UPLOADS_DIR / uploaded_file.name
    petition_path.write_bytes(uploaded_file.getbuffer())

    st.success(f"Arquivo recebido: {uploaded_file.name}")

    if st.session_state.get("uploaded_file_name") != uploaded_file.name:
        st.session_state.uploaded_file_name = uploaded_file.name
        st.session_state.analysis_result = None
        st.session_state.recreated_petition = None
        st.session_state.recreated_pdf_path = None

    if st.button("Analisar petição", type="primary", use_container_width=True):
        with st.spinner("Carregando índice RAG e analisando a petição..."):
            chunks, documents, embeddings = load_index()
            result = analyze_petition(petition_path, chunks, documents, embeddings)
            report_path = REPORTS_DIR / "relatorio_critico.md"
            report_path.write_text(result.markdown, encoding="utf-8")
            st.session_state.analysis_result = result
            st.session_state.recreated_petition = None
            st.session_state.recreated_pdf_path = None

        st.success("Análise concluída.")

    result = st.session_state.get("analysis_result")
    if result:
        analysis_tab, recreated_tab = st.tabs(["Análise", "Petição recriada"])

        with analysis_tab:
            st.subheader("Pontuação")
            cols = st.columns(len(result.scores))
            for col, (name, score) in zip(cols, result.scores.items()):
                col.metric(name.capitalize(), f"{score}/10")

            st.subheader("Pontos de melhoria")
            if result.problems:
                for problem in result.problems:
                    st.warning(problem)
            else:
                st.success("Nenhum problema estrutural grave foi detectado pelas heurísticas iniciais.")

            st.subheader("Sugestões práticas")
            for suggestion in result.suggestions:
                st.write(f"- {suggestion}")

            st.subheader("Features jurídicas detectadas")
            st.dataframe(
                [{"feature": key, "valor": value} for key, value in sorted(result.features.items())],
                use_container_width=True,
            )

            st.subheader("Trechos similares fortes da base")
            for index, similar in enumerate(result.similar_chunks, start=1):
                with st.expander(f"{index}. Similaridade {similar.score:.3f} — {similar.chunk.file_name}"):
                    st.write(f"Seção detectada: **{similar.chunk.section}**")
                    st.write(similar.chunk.text[:1800])

            st.subheader("Relatório completo")
            st.download_button(
                "Baixar relatório Markdown",
                data=result.markdown,
                file_name="relatorio_critico.md",
                mime="text/markdown",
                use_container_width=True,
            )
            st.markdown(result.markdown)

        with recreated_tab:
            st.write(
                "A petição original é mantida na íntegra. As melhorias aparecem como "
                "`[COMENTÁRIO (categoria): ...]` inline, logo após o trecho ao qual se referem, "
                "e também em um resumo final. Se o PDF for escaneado, o texto é recuperado por OCR."
            )
            col_a, col_b = st.columns(2)
            with col_a:
                use_internet = st.checkbox("Usar busca na internet", value=True, key="opt_internet")
            with col_b:
                use_ollama = st.checkbox("Usar Ollama local", value=True, key="opt_ollama")
            ollama_model = st.text_input("Modelo do Ollama", value="llama3:latest", key="opt_model")

            generate_clicked = st.button(
                "Recriar petição",
                type="primary",
                use_container_width=True,
                key="btn_recreate",
            )
            if generate_clicked:
                with st.spinner("Recriando a petição com as melhorias propostas..."):
                    recreated = build_recreated_petition(
                        Path(result.petition_path),
                        result,
                        use_internet=use_internet,
                        use_ollama=use_ollama,
                        ollama_model=ollama_model.strip() or "llama3:latest",
                    )
                    recreated_path = REPORTS_DIR / "peticao_recriada.md"
                    recreated_path.write_text(recreated.markdown, encoding="utf-8")
                    pdf_path = markdown_to_pdf(recreated.markdown, REPORTS_DIR / "peticao_recriada.pdf")
                    st.session_state.recreated_petition = recreated
                    st.session_state.recreated_pdf_path = str(pdf_path)
                st.success("Petição recriada com a petição original preservada.")

            recreated = st.session_state.get("recreated_petition")
            if recreated:
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
                            file_name="peticao_recriada.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="dl_pdf",
                        )
                with col_dl2:
                    st.download_button(
                        "Baixar Markdown",
                        data=recreated.markdown,
                        file_name="peticao_recriada.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key="dl_md",
                    )
                st.markdown(recreated.markdown)
                if pdf_path_value:
                    with st.expander("Visualizar PDF"):
                        show_pdf_viewer(Path(pdf_path_value))
