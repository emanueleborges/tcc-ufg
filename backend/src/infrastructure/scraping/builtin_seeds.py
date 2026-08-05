"""Catálogo embutido de URLs públicas de PDFs jurídicos.

Usado quando buscadores falham (DNS/captcha/rate-limit). Preferência por
decisões com sinal de improcedência/indeferimento para alimentar rejeitadas/.
"""

from __future__ import annotations

BUILTIN_PDF_URLS: tuple[str, ...] = (
    # Indeferimento / improcedência / negatória
    "https://www.tjrj.jus.br/documents/10136/31891/indeferimento-peticao-inicial.pdf",
    "https://www.conjur.com.br/wp-content/uploads/2026/06/Indefere-inicial-1-1.pdf",
    "https://bdjur.stj.jus.br/jspui/bitstream/2011/19852/Do%20indeferimento%20parcial%20da%20peti%C3%A7%C3%A3o%20inicial.pdf",
    "https://www.conjur.com.br/dl/se/sentenca-negou-pedido-indenizacao-dano.pdf",
    "https://www.conjur.com.br/wp-content/uploads/2023/09/sentenca-nega-dano-moral-empregada.pdf",
    "https://www.conjur.com.br/dl/in/indenizacao-pedido-motorista-uber-danos.pdf",
    "https://www.conjur.com.br/wp-content/uploads/2025/09/Empresa-deve-indenizar-por-exigir-exames-de-trabalhadora.pdf",
    "https://portal-legado.tjpb.jus.br/sites/default/files/anexos/2020/07/sentenca_gol.pdf",
    "https://www.tjto.jus.br/images/old/NOTICIAS/PDF/SENTENCA_BANCOBRASIL.pdf",
    "https://www.tjpb.jus.br/sites/default/files/anexos/2020/09/descarga_eletrica.pdf",
    "https://www.migalhas.com.br/arquivos/2020/4/E326E109CECB0E_decisaofundos.pdf",
    "https://www4.trf5.jus.br/data/2015/08/PJE/08058920720144058400_20150822_61514_40500002930943.pdf",
    "https://arq.migalhas.com.br/arquivos/2026/4/9A23BC1ED76D89_c5f0ac6e-5e78-4698-a021-fb1b98.pdf",
    # Petições / sentenças / acórdãos (procedente ou misto)
    "https://edisciplinas.usp.br/pluginfile.php/8131106/mod_folder/content/0/1%20-%20Peti%C3%A7%C3%A3o%20inicial..pdf?forcedownload=1",
    "https://www.migalhas.com.br/arquivos/2018/8/art20180815-20.pdf",
    "https://www.migalhas.com.br/arquivos/2022/3/91761A65004E7A_doc_78288920_uber_ok.pdf",
    "https://www10.trf2.jus.br/portal/wp-content/uploads/sites/28/2017/10/sentenca-civel-espelho-final.pdf",
    "https://mpce.mp.br/wp-content/uploads/2017/02/20180107-Sentenca-ACP-Dano-moral-coletivo-CNA.pdf",
    "https://www.mpdft.mp.br/portal/pdf/noticias/dezembro_2018/ACP_-_Banco_Inter.pdf",
    "https://www.tjrj.jus.br/documents/5736540/8415387/7-0222966-67.2020.8.19.0001.pdf/10308a48-02ee-e4aa-9f08-306441ee8e58?version=1.0&t=1646364930039",
    "https://www.estadao.com.br/blogs/blog/wp-content/uploads/sites/41/2019/10/Uberr.pdf",
    "http://www.ablj.org.br/revistas/revista11/revista11%20%20PINTO%20FERREIRA%20%E2%80%93%20Peti%C3%A7%C3%A3o%20inicial%20inepta.pdf",
    "https://www.mpsp.mp.br/portal/page/portal/documentacao_e_divulgacao/doc_biblioteca/bibli_servicos_produtos/bibli_boletim/bibli_bol_2006/RPro_n.243.04.PDF",
    "https://emerj.tjrj.jus.br/files/pages/revistas/direito_processual_civil/edicoes/n1_2013/pdf/VivianeSantosDOliveira.pdf",
    "https://www.tjdft.jus.br/informacoes/juizados-especiais/informacoes-gerais/modelos-velhos/acidente-de-transito-1/UM%20REQUERIDO%20-%20CONDUTOR%20OU%20PROPRIETARIO%20-%20DANOS%20MATERIAIS.pdf",
    "https://www.tjdft.jus.br/informacoes/juizados-especiais/informacoes-gerais/modelos-velhos/acidente-de-transito-1/MAIS%20DE%20UM%20REQUERIDO%20-%20CONDUTOR%20E%20PROPRIETARIO%20-%20DANOS%20MATERIAIS.pdf",
    "https://archive.org/download/DanoMoralPunitivo/ArtigoDanoMoral.pdf",
    "https://archive.org/download/20200810-tjpr-0024057-05-2020-8-16-0182-denian-couto-processa-jornal-plural-por-dano-moral/20200810%20TJPR%200024057%2005%202020%208%2016%200182%20Denian%20Couto%20processa%20Jornal%20Plural%20por%20dano%20moral.pdf",
    "https://esaj.tjsp.jus.br/cjsg/getArquivo.do?cdAcordao=19924821&cdForo=0",
)
