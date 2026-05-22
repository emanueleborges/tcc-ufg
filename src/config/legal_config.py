"""Configurações centrais do projeto jurídico."""

from pathlib import Path

# Pastas principais
DOWNLOADS_DIR = Path("downloads_peticoes")
ACCEPTED_PDFS_DIR = DOWNLOADS_DIR / "aceitas"
REJECTED_PDFS_DIR = DOWNLOADS_DIR / "rejeitadas"
INDEX_DIR = Path("indice_juridico")
REPORTS_DIR = Path("relatorios")
UPLOADS_DIR = Path("uploads")

# Configuração do baixador de PDFs
DOWNLOAD_LIMIT = 30
MAX_RESULTS = 80
MAX_LINKS_PER_PAGE = 12
HTTP_TIMEOUT = 25
REQUEST_PAUSE = 0.8
KEEP_REJECTED = False
MAX_RUNTIME_SECONDS = 15 * 60

SEARCH_QUERIES = [
    '"petição inicial" "ação de indenização" "dano moral" "procedente" filetype:pdf',
    '"petição inicial" "danos morais" "pedido procedente" filetype:pdf',
    '"ação de indenização por danos morais" "julgo procedente" "petição inicial" filetype:pdf',
    '"indenização por dano moral" "sentença procedente" "petição inicial" filetype:pdf',
    '"danos morais" "condeno" "petição inicial" filetype:pdf',
    '"modelo de petição inicial" "danos morais" "procedente" filetype:pdf',
    '"petição inicial" "dano moral" "sentença" "procedente" filetype:pdf',
    '"petição inicial" "dano moral" "julgo procedente" filetype:pdf',
    '"petição inicial" "danos morais" "julgo parcialmente procedente" filetype:pdf',
    '"indenização por dano moral" "petição inicial" "procedência do pedido" filetype:pdf',
    '"ação indenizatória" "dano moral" "julgo procedente" filetype:pdf',
    '"ação de reparação por danos morais" "julgo procedente" filetype:pdf',
    '"danos morais" "sentença" "pedido procedente" "petição inicial" filetype:pdf',
    '"dano moral" "petição inicial" "recurso provido" filetype:pdf',
]

# Configuração do RAG jurídico
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
TOP_K_SIMILARES = 8
MAX_CHUNK_CHARS = 1800
MIN_CHUNK_CHARS = 250
ANONIMIZAR = True
