import streamlit as st
import re
import os
import io
from datetime import datetime
from fpdf import FPDF
import pytesseract
from pdf2image import convert_from_bytes
from PIL import ImageOps
import pdfplumber

st.set_page_config(page_title="Gerador de Atestados - EBM QUINTTO", page_icon="📄", layout="wide")

st.title("📄 Gerador Automático de Atestados")
st.write("Agência EBM QUINTTO Comunicação (Modo Paisagem com Revisão)")

# ---------------------------------------------------------------------------
# 1. CADASTRO DE CLIENTES
# Em vez de if/else hardcoded, um dicionário fácil de estender quando a
# agência atender novos clientes. Se o CNPJ não bater com nenhum cadastrado,
# NÃO assume SESC por padrão — deixa em branco para preenchimento manual.
# ---------------------------------------------------------------------------
CLIENTES_CADASTRADOS = {
    "03.648.344/0001-08": {
        "nome": "SERVIÇO NACIONAL DE APRENDIZAGEM COMERCIAL SENAC AR/CE",
        "tag": "SENAC",
    },
    "03.612.122/0001-27": {
        "nome": "SERVIÇO SOCIAL DO COMERCIO SESC AR/CE",
        "tag": "SESC",
    },
    # Adicione novos clientes aqui: "CNPJ": {"nome": "...", "tag": "..."}
}

CNPJS_AGENCIA_E_CLIENTES = list(CLIENTES_CADASTRADOS.keys()) + ["14.470.051/0001-91"]


def limpar_texto(texto):
    if not texto:
        return ""
    texto = str(texto).replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return texto.encode('latin-1', 'replace').decode('latin-1')


def limitar_tamanho(texto, max_len):
    texto = limpar_texto(texto)
    return texto[:max_len - 3] + "..." if len(texto) > max_len else texto


def extrair_texto_nativo_pdf(pdf_bytes):
    """Tenta ler o texto real embutido no PDF (documentos gerados por
    computador, como este formulário da AP). Muito mais confiável que OCR
    quando existe — sem erro de leitura de caractere. Retorna None se o PDF
    não tiver camada de texto (aí sim é preciso cair para OCR de imagem)."""
    try:
        texto = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for pagina in pdf.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto += texto_pagina + "\n"
        # Um PDF puramente escaneado (imagem) retorna pouco ou nenhum texto
        if len(texto.strip()) > 40:
            return texto
    except Exception:
        pass
    return None


@st.cache_data
def extrair_dados_pdf_escaneado(pdf_bytes):
    """Retorna (dados, texto_bruto, erro, fonte). Nunca lança exceção pra
    fora — devolve erro=str para a UI tratar de forma amigável.
    'fonte' indica se o texto veio do PDF nativo ou de OCR, útil pra
    diagnosticar quando algum campo não é encontrado."""
    texto = extrair_texto_nativo_pdf(pdf_bytes)
    fonte = "texto nativo do PDF"

    if texto is None:
        fonte = "OCR (imagem)"
        try:
            # DPI mais alto = mais detalhe para o OCR reconhecer letras
            # pequenas (padrão do pdf2image é 200; documentos escaneados
            # com texto miúdo se beneficiam de 300).
            imagens = convert_from_bytes(pdf_bytes, dpi=300)
        except Exception as e:
            return {}, "", f"Falha ao converter o PDF em imagem (poppler indisponível?): {e}", fonte

        texto = ""
        try:
            for img in imagens:
                # Escala de cinza reduz ruído de fundo (sombra de scanner,
                # papel amarelado) e geralmente melhora a taxa de acerto do
                # Tesseract.
                img_processada = ImageOps.grayscale(img)
                # --psm 6: trata a página como um bloco único de texto,
                # funciona bem para formulários tabulares como AP/OC.
                texto += pytesseract.image_to_string(img_processada, lang='por', config='--psm 6') + "\n"
        except Exception as e:
            return {}, texto, f"Falha no OCR (tesseract indisponível ou idioma 'por' não instalado?): {e}", fonte

    texto_upper = texto.upper()
    dados = {}

    # 1. CLIENTE — cadastro em vez de hardcode; sem suposição por padrão
    cliente_encontrado = None
    for cnpj, info in CLIENTES_CADASTRADOS.items():
        if cnpj in texto_upper or info["nome"] in texto_upper:
            cliente_encontrado = {"cnpj": cnpj, **info}
            break

    if cliente_encontrado:
        dados['cliente_nome'] = cliente_encontrado["nome"]
        dados['cliente_cnpj'] = cliente_encontrado["cnpj"]
        dados['tag_cliente'] = cliente_encontrado["tag"]
        dados['cliente_identificado'] = True
    else:
        dados['cliente_nome'] = ""
        dados['cliente_cnpj'] = ""
        dados['tag_cliente'] = ""
        dados['cliente_identificado'] = False

    # 2. TIPO E NÚMERO (AP/OC)
    match_ap = re.search(r"(?:PLANILHA|AP|Nº|N|NO)\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    match_oc = re.search(r"OC\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    dados['is_midia'] = bool(match_ap)
    dados['ap_oc'] = match_ap.group(1) if match_ap else (match_oc.group(1) if match_oc else "")

    # 3. CNPJ FORNECEDOR
    cnpjs_encontrados = re.findall(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    dados['fornecedor_cnpj'] = next((c for c in cnpjs_encontrados if c not in CNPJS_AGENCIA_E_CLIENTES), "")

    # 4. FORNECEDOR NOME — prioriza o rótulo "VEÍCULO:" quando existe (mais
    # confiável), já que a heurística de "linha anterior ao CNPJ" pode pegar
    # o nome de outra entidade que aparece perto de um CNPJ na tabela (ex:
    # o responsável legal/MEI, que é diferente do nome comercial do veículo).
    match_veiculo_label = re.search(r"VE[ÍI]CULO\s*[:\-]?\s*([^\n\r\|]+)", texto_upper)
    fornecedor_nome = match_veiculo_label.group(1).strip() if match_veiculo_label else ""

    if not fornecedor_nome and dados['fornecedor_cnpj']:
        linhas = [l.strip() for l in texto.split('\n') if l.strip()]
        for i, linha in enumerate(linhas):
            if dados['fornecedor_cnpj'] in linha and i > 0:
                fornecedor_nome = linhas[i - 1]
                if "FONE" in fornecedor_nome.upper() or "FAX" in fornecedor_nome.upper():
                    fornecedor_nome = linhas[i - 2] if i > 1 else fornecedor_nome
                fornecedor_nome = re.sub(r"^(FORNECEDOR|VE[IÍ]CULO|RAZ[ÃA]O SOCIAL|EMPRESA)\s*[:\-]?\s*", "", fornecedor_nome, flags=re.IGNORECASE)
                fornecedor_nome = re.split(r"\||\+|=|_", fornecedor_nome)[0].strip()
                break
    dados['fornecedor'] = fornecedor_nome.upper() if fornecedor_nome else ""

    # 5. CAMPANHA E TÍTULO
    match_camp = re.search(r"CAMPANHA\s*[:\-]?\s*([^\n\r\|]+)", texto_upper)
    dados['campanha'] = match_camp.group(1).strip() if match_camp else ""
    dados['titulo'] = dados['campanha'] if dados['campanha'] else "N/A"

    # 6. MÊS
    match_mes = re.search(r"(?:M[ÊE]S|PER[ÍI]ODO)\s*[:\-]?\s*([^\n\r\|]+)", texto_upper)
    mes = match_mes.group(1).strip() if match_mes else ""
    dados['mes_ano'] = re.sub(r"^(M[ÊE]S DE\s*|M[ÊE]S\s*)", "", mes, flags=re.IGNORECASE)

    # 6b. PERÍODO DE VEICULAÇÃO detalhado — algumas AP trazem o período
    # exato de execução dentro do texto da proposta (ex: "no período de 09
    # a 19/Julho/26"), diferente do campo "PERÍODO:" acima, que só traz o
    # mês/ano de referência.
    match_periodo_detalhe = re.search(r"PER[ÍI]ODO DE\s+([^\n\r,\.]+)", texto_upper)
    dados['periodo_veiculacao'] = match_periodo_detalhe.group(1).strip() if match_periodo_detalhe else ""

    # 7. PEÇA / SERVIÇOS
    if dados['is_midia']:
        match_aut = re.search(r"REFERENTE\s*[AÀ]\s*([^\n\r]+)", texto_upper)
        match_veic = re.search(r"(VEICULA[ÇC][ÃA]O DE\s*[^\n\r]+)", texto_upper)
        match_peca = re.search(r"(?:PE[ÇC]A|SERVI[ÇC]O)\s*[:\-]?\s*([^\n\r\|]+)", texto_upper)
        # Fallback final: linha descritiva da proposta comercial, que costuma
        # citar chamadas/inserções e o período de veiculação por extenso.
        match_desc = re.search(r"([^\n\r]*(?:CHAMADAS|INSER[ÇC][ÕO]ES)[^\n\r]*)", texto_upper)
        texto_peca = (
            match_aut.group(1).strip() if match_aut else
            match_veic.group(1).strip() if match_veic else
            match_peca.group(1).strip() if match_peca else
            match_desc.group(1).strip() if match_desc else ""
        )
        match_vol = re.search(r"VOLUME:\s*([^\n\r]+)", texto_upper)
        if match_vol and texto_peca:
            texto_peca += f" - {match_vol.group(1).strip()}"
        if dados['periodo_veiculacao'] and dados['periodo_veiculacao'] not in texto_peca:
            texto_peca += f" (período de veiculação: {dados['periodo_veiculacao']})"
        dados['peca'] = texto_peca
    else:
        match_serv = re.search(r"(?:OP[ÇC][ÃA]O|DESCRI[ÇC][ÃA]O.*?FORNECEDOR)[\s\S]{1,200}?(?:^|\n)\s*(?:1|01)\s+([^\n\r]+)", texto_upper)
        dados['peca'] = re.split(r"\s{2,}|\d{1,3}\s*DFM|CNPJ|R\$", match_serv.group(1))[0].strip() if match_serv else ""

    return dados, texto, None, fonte


uploaded_file = st.file_uploader("1. Envie a AP ou OC em PDF (escaneada ou nativa)", type=["pdf"])

if uploaded_file:
    with st.spinner("Lendo documento..."):
        dados, texto_bruto, erro, fonte_texto = extrair_dados_pdf_escaneado(uploaded_file.read())

    if erro:
        st.error(f"❌ {erro}")
        st.stop()

    # Painel de conferência do texto extraído — facilita detectar quando
    # algum campo veio errado antes de confiar nos dados. Mostra também a
    # origem (texto nativo do PDF é bem mais confiável que OCR de imagem).
    with st.expander(f"🔍 Ver texto extraído para conferência (fonte: {fonte_texto})"):
        st.text(texto_bruto if texto_bruto else "Nenhum texto foi extraído.")

    if not dados.get('cliente_identificado'):
        st.warning("⚠️ Cliente não reconhecido automaticamente pelo CNPJ/nome no documento. Preencha manualmente abaixo.")

    st.subheader("2. Confira os dados extraídos automaticamente")
    st.info("💡 Os campos abaixo já vêm preenchidos com o que o OCR leu do documento. Você só precisa digitar algo se algum campo aparecer errado ou vazio.")

    campos_vazios = [nome for nome, val in [
        ("Fornecedor", dados['fornecedor']),
        ("Campanha", dados['campanha']),
        ("Peça/Serviço", dados['peca']),
        ("Mês/Período", dados['mes_ano']),
    ] if not val]
    if campos_vazios:
        st.warning(f"⚠️ Campos não identificados automaticamente, confira com atenção: {', '.join(campos_vazios)}")

    col1, col2, col3 = st.columns(3)

    with col1:
        doc_type = st.radio("Tipo de Serviço:", ["Mídia (AP)", "Produção (OC)"], index=0 if dados['is_midia'] else 1)
        pi_pp_val = st.text_input("Nº da PI / PP (Obrigatório - não consta no documento escaneado):", placeholder="Ex: 37710")
        ap_oc_val = st.text_input("Nº da AP / OC:", value=dados['ap_oc'])

    with col2:
        fornecedor_val = st.text_input("Fornecedor / Veículo:", value=dados['fornecedor'])
        cnpj_val = st.text_input("CNPJ do Fornecedor:", value=dados['fornecedor_cnpj'])
        mes_ano_val = st.text_input("Mês / Período:", value=dados['mes_ano'])

    with col3:
        cliente_nome_val = st.text_input("Cliente:", value=dados['cliente_nome'])
        cliente_cnpj_val = st.text_input("CNPJ do Cliente:", value=dados['cliente_cnpj'])
        campanha_val = st.text_input("Campanha:", value=dados['campanha'])
        peca_servico_val = st.text_input("Peça / Serviços (Pode colar textos longos aqui):", value=dados['peca'])
        titulo_val = st.text_input("Título (Apenas Produção):", value=campanha_val if doc_type == "Produção (OC)" else "N/A", disabled=doc_type == "Mídia (AP)")

    st.divider()
    st.subheader("3. Confirmação")
    confirmo = st.checkbox(
        "Revisei todos os campos acima, eles estão corretos e confirmo a emissão deste atestado com a assinatura da agência."
    )

    if st.button("🚀 Gerar Atestado Oficial", type="primary", disabled=not confirmo):
        if not pi_pp_val:
            st.error("Por favor, preencha o número do PI/PP.")
        elif not cliente_nome_val or not cliente_cnpj_val:
            st.error("Por favor, preencha o cliente e o CNPJ do cliente.")
        else:
            tag_cliente = dados['tag_cliente'] or re.sub(r"[^A-Z]", "", cliente_nome_val.upper())[:15]

            meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            data_hoje = f"{datetime.now().day} de {meses[datetime.now().month - 1]} de {datetime.now().year}"

            pdf = FPDF(orientation='L')
            pdf.set_auto_page_break(auto=True, margin=10)
            pdf.add_page()
            pdf.set_margins(15, 15, 15)

            pdf.set_font("Helvetica", "B", 12)
            is_midia_selecionado = (doc_type == "Mídia (AP)")
            titulo_doc = f"ATESTADO DE VEICULAÇÃO DE MÍDIA | {tag_cliente}" if is_midia_selecionado else f"ATESTADO DE PRODUÇÃO - {tag_cliente}"
            pdf.cell(200, 10, limpar_texto(titulo_doc), ln=0)

            logo_path = "logo ebmquintto preta BG transparente.png"
            if os.path.exists(logo_path):
                pdf.image(logo_path, x=235, y=12, w=45)
            else:
                pdf.set_font("Helvetica", "B", 16)
                pdf.cell(67, 10, "EBM QUINTTO.", ln=0, align="R")

            pdf.ln(12)
            pdf.set_draw_color(255, 204, 0)
            pdf.set_line_width(1.5)
            pdf.line(15, pdf.get_y(), 282, pdf.get_y())
            pdf.ln(8)

            fornecedor_formatado = f"{fornecedor_val}"
            if cnpj_val:
                fornecedor_formatado += f", CNPJ: {cnpj_val}"

            pdf.set_font("Helvetica", "", 10)
            if is_midia_selecionado:
                texto = f"Atestamos para fins de comprovação de execução de serviço prestados que no mês de {mes_ano_val}, o veículo {fornecedor_formatado} a veiculações de mídias publicitárias do cliente {cliente_nome_val}, CNPJ {cliente_cnpj_val} intermediadas por essa agência de publicidade no período de acordo com as planilhas de AP e PI relacionadas abaixo."
            else:
                texto = f"Atestamos para fins de comprovação de execução de serviço prestados, que o fornecedor {fornecedor_formatado} produziu material publicitário para o {cliente_nome_val}, CNPJ {cliente_cnpj_val} intermediadas por essa agência de publicidade no período de acordo com as OC e PP relacionadas abaixo."

            pdf.multi_cell(0, 6, limpar_texto(texto))
            pdf.ln(8)

            pdf.set_draw_color(255, 204, 0)
            pdf.set_line_width(1.0)
            pdf.set_fill_color(0, 0, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 8)

            if is_midia_selecionado:
                pdf.cell(15, 9, "#", border=1, fill=True, align="C")
                pdf.cell(40, 9, "Planilha AP n°", border=1, fill=True, align="C")
                pdf.cell(40, 9, "PI n°", border=1, fill=True, align="C")
                pdf.cell(100, 9, "PEÇA", border=1, fill=True, align="C")
                pdf.cell(72, 9, "CAMPANHA", border=1, fill=True, align="C")
                pdf.ln()

                pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", "", 7.5)
                pdf.cell(15, 10, "1", border=1, align="C")
                pdf.cell(40, 10, limitar_tamanho(ap_oc_val, 20), border=1, align="C")
                pdf.cell(40, 10, limitar_tamanho(pi_pp_val, 15), border=1, align="C")
                pdf.cell(100, 10, limitar_tamanho(peca_servico_val, 90), border=1, align="C")
                pdf.cell(72, 10, limitar_tamanho(campanha_val, 50), border=1, align="C")

            else:
                pdf.cell(15, 9, "#", border=1, fill=True, align="C")
                pdf.cell(30, 9, "PP n°", border=1, fill=True, align="C")
                pdf.cell(30, 9, "OC n°", border=1, fill=True, align="C")
                pdf.cell(72, 9, "SERVIÇOS", border=1, fill=True, align="C")
                pdf.cell(60, 9, "TÍTULO", border=1, fill=True, align="C")
                pdf.cell(60, 9, "CAMPANHA", border=1, fill=True, align="C")
                pdf.ln()

                pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", "", 7.5)
                pdf.cell(15, 10, "1", border=1, align="C")
                pdf.cell(30, 10, limitar_tamanho(pi_pp_val, 15), border=1, align="C")
                pdf.cell(30, 10, limitar_tamanho(ap_oc_val, 15), border=1, align="C")
                pdf.cell(72, 10, limitar_tamanho(peca_servico_val, 65), border=1, align="C")
                pdf.cell(60, 10, limitar_tamanho(titulo_val, 50), border=1, align="C")
                pdf.cell(60, 10, limitar_tamanho(campanha_val, 50), border=1, align="C")

            pdf.ln(10)

            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, limpar_texto(f"Fortaleza/CE, {data_hoje}."), ln=1)
            pdf.ln(5)

            if os.path.exists("luma_signature_perfect.png"):
                pdf.image("luma_signature_perfect.png", x=15, w=60)

            pdf.set_y(-30)
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(100, 100, 100)

            pdf.cell(89, 3, "Fortaleza-CE", ln=0, align="C")
            pdf.cell(89, 3, "Brasília-DF- Setor Comercial Norte,", ln=0, align="C")
            pdf.cell(89, 3, "Bahia-BA Al. Salvador, 1057, Sl. 1411,", ln=1, align="C")

            pdf.cell(89, 3, "R. Beni Carvalho, 138 CEP: 60135-400", ln=0, align="C")
            pdf.cell(89, 3, "01 Bloco D, Conj 119 Vega Luxury Mall", ln=0, align="C")
            pdf.cell(89, 3, "Torre Europa Caminho das Arvores", ln=1, align="C")

            pdf.cell(89, 3, "+55 85 3253.5555", ln=0, align="C")
            pdf.cell(89, 3, "CEP: 70711-948 - 55 61 3525-7988", ln=0, align="C")
            pdf.cell(89, 3, "CEP: 41820-790 +55 71 3825-3178", ln=1, align="C")

            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(0, 3, "@ebmquintto       ebmquintto.com.br", align="C")

            pdf_bytes = pdf.output()

            st.success("✅ Atestado gerado com sucesso!")
            st.download_button(
                label="📥 Baixar Atestado PDF",
                data=bytes(pdf_bytes),
                file_name=limpar_texto(f"ATESTADO_{tag_cliente}_{ap_oc_val}.pdf"),
                mime="application/pdf"
            )
