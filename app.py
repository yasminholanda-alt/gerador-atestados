import streamlit as st
import re
import os
from datetime import datetime
from fpdf import FPDF
import pytesseract
from pdf2image import convert_from_bytes

st.set_page_config(page_title="Gerador de Atestados - EBM QUINTTO", page_icon="📄", layout="centered")

st.title("📄 Gerador Automático de Atestados")
st.write("Agência EBM QUINTTO Comunicação (Lê PDFs Escaneados)")

uploaded_file = st.file_uploader("1. Envie a AP ou OC em PDF", type=["pdf"])
pi_pp_input = st.text_input("2. Digite o Número do PI ou PP:", placeholder="Ex: 37710")

def limpar_texto(texto):
    if not texto: return ""
    texto = str(texto).replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return texto.encode('latin-1', 'replace').decode('latin-1')

def limitar_tamanho(texto, max_len):
    texto = limpar_texto(texto)
    return texto[:max_len-3] + "..." if len(texto) > max_len else texto

@st.cache_data
def extrair_dados_pdf_escaneado(pdf_bytes):
    imagens = convert_from_bytes(pdf_bytes)
    texto = ""
    for img in imagens:
        # O comando --psm 6 ajuda o Tesseract a alinhar melhor as colunas
        texto += pytesseract.image_to_string(img, lang='por', config='--psm 6') + "\n"
        
    texto_upper = texto.upper()
    dados = {}
    
    # 1. CLIENTE
    if "03.648.344" in texto_upper or "SERVIÇO NACIONAL" in texto_upper or "SERVICO NACIONAL" in texto_upper:
        dados['cliente_nome'] = "SERVIÇO NACIONAL DE APRENDIZAGEM COMERCIAL SENAC AR/CE"
        dados['cliente_cnpj'] = "03.648.344/0001-08"
        dados['tag_cliente'] = "SENAC"
    else:
        dados['cliente_nome'] = "SERVIÇO SOCIAL DO COMERCIO SESC AR/CE"
        dados['cliente_cnpj'] = "03.612.122/0001-27"
        dados['tag_cliente'] = "SESC"
        
    # 2. AP OU OC
    match_ap = re.search(r"(?:PLANILHA|AP|Nº|N|NO)\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    match_oc = re.search(r"OC\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    dados['is_midia'] = bool(match_ap)
    dados['ap_oc'] = match_ap.group(1) if match_ap else (match_oc.group(1) if match_oc else "N/A")
    
    # 3. CNPJ FORNECEDOR
    cnpjs_encontrados = re.findall(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    cnpjs_ignorados = ["03.612.122/0001-27", "03.648.344/0001-08", "14.470.051/0001-91"]
    fornecedor_cnpj = next((c for c in cnpjs_encontrados if c not in cnpjs_ignorados), "")
    dados['fornecedor_cnpj'] = fornecedor_cnpj
    
    # 4. FORNECEDOR
    fornecedor_nome = ""
    if fornecedor_cnpj:
        linhas = [l.strip() for l in texto_upper.split('\n') if l.strip()]
        for i, linha in enumerate(linhas):
            if fornecedor_cnpj in linha and i > 0:
                fornecedor_nome = linhas[i-1]
                if "FONE" in fornecedor_nome or "FAX" in fornecedor_nome:
                    fornecedor_nome = linhas[i-2] if i > 1 else fornecedor_nome
                fornecedor_nome = re.sub(r"^(FORNECEDOR|VE[IÍ]CULO|RAZ[ÃA]O SOCIAL|EMPRESA)\s*[:\-]?\s*", "", fornecedor_nome)
                fornecedor_nome = re.split(r"\||\+|=|_|\d{1,3}DFM|\d{1,3}\s*DIAS", fornecedor_nome)[0].strip()
                break

    if len(fornecedor_nome) < 3:
        match_fornecedor = re.search(r"(?:FORNECEDOR|VE[IÍ]CULO|RAZ[ÃA]O SOCIAL|EMPRESA)\s*[:\-]?\s*([^\n\r]+)", texto_upper)
        if match_fornecedor:
            fornecedor_nome = re.split(r"(MEIO|FORMATO|PER[ÍI]ODO|CAMPANHA|VALOR|DATA|VE[IÍ]CULO|CNPJ|CLIENTE)", match_fornecedor.group(1))[0].strip()
            fornecedor_nome = re.split(r"\||\+|=|_", fornecedor_nome)[0].strip()

    dados['fornecedor'] = fornecedor_nome if fornecedor_nome else "FORNECEDOR NÃO IDENTIFICADO"

    # 5. CAMPANHA E TÍTULO (Busca simplificada extrema)
    match_camp = re.search(r"CAMPANHA\s*[:\.]?\s*(.*?)(?:PROJETO|PRODUTO|ESP[EÉ]CIE|T[IÍ]TULO|MEIO|FORMATO|CNPJ|\n|$)", texto_upper)
    dados['campanha'] = match_camp.group(1).strip() if match_camp and len(match_camp.group(1).strip()) > 2 else "MÍDIAS INSTITUCIONAIS"

    match_tit = re.search(r"T[IÍ]TULO\s*[:\.]?\s*(.*?)(?:ACABAMENTO|VALIDADE|CORES|PZ\.ENTREGA|\n|$)", texto_upper)
    dados['titulo'] = match_tit.group(1).strip() if match_tit and len(match_tit.group(1).strip()) > 2 else "N/A"
        
    # MÊS
    match_mes = re.search(r"(?:M[ÊE]S|PER[ÍI]ODO|DATA)\s*[:\-]?\s*([^\n\r]+)", texto_upper)
    if match_mes:
        mes = re.split(r"\s{2,}|\n|PROJETO|PRODUTO", match_mes.group(1))[0].strip()
        dados['mes_ano'] = re.sub(r"^(M[ÊE]S DE\s*|M[ÊE]S\s*)", "", mes)
    else:
        dados['mes_ano'] = "Agosto/2026"

    # 6. MÍDIA (PEÇA)
    match_peca = re.search(r"(?:PE[ÇC]A|SERVI[ÇC]O)\s*[:\-]?\s*([^\n\r]+)", texto_upper)
    peca_header = re.split(r"\s{2,}|\n|FORMATO", match_peca.group(1))[0].strip() if match_peca else "Serviço de Publicidade"
    
    match_aut = re.search(r"REFERENTE\s*[AÀ]\s*([^\n\r]+)", texto_upper)
    if match_aut:
        texto_peca = match_aut.group(1).strip()
    else:
        match_veic = re.search(r"(VEICULA[ÇC][ÃA]O DE\s*[^\n\r]+)", texto_upper)
        texto_peca = match_veic.group(1).strip() if match_veic else peca_header
            
    match_vol = re.search(r"VOLUME:\s*([^\n\r]+)", texto_upper)
    if match_vol and texto_peca != peca_header:
        texto_peca += f" - {match_vol.group(1).strip()}"
    dados['peca'] = texto_peca if len(texto_peca) > 2 else "Serviço de Publicidade"

    # 7. PRODUÇÃO (SERVIÇOS)
    # Procura a área de Opção e pega a linha que tem o número 1
    match_serv = re.search(r"OP[ÇC][ÃA]O.*?\n\s*(?:1|01)\s+([A-Z].*?)(?:\d{1,3}\s*DFM|R\$|\d{2,}\.|CNPJ|\n|$)", texto_upper, re.DOTALL)
    if match_serv:
        dados['servicos'] = match_serv.group(1).strip()
    else:
        dados['servicos'] = "Serviços de Produção"
    
    return dados

if st.button("🚀 Gerar Atestado Oficial", type="primary"):
    if not uploaded_file or not pi_pp_input:
        st.error("Por favor, envie o arquivo PDF e digite o número do PI/PP.")
    else:
        with st.spinner("Lendo documento escaneado..."):
            pdf_bytes = uploaded_file.read()
            dados = extrair_dados_pdf_escaneado(pdf_bytes)
        
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        data_hoje = f"{datetime.now().day} de {meses[datetime.now().month - 1]} de {datetime.now().year}"
        
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=10)
        pdf.add_page()
        pdf.set_margins(15, 15, 15)
        
        pdf.set_font("Helvetica", "B", 12)
        titulo_doc = f"ATESTADO DE VEICULAÇÃO DE MÍDIA | {dados['tag_cliente']}" if dados['is_midia'] else f"ATESTADO DE PRODUÇÃO - {dados['tag_cliente']}"
        pdf.cell(130, 10, limpar_texto(titulo_doc), ln=0)
        
        logo_path = "logo ebmquintto preta BG transparente.png"
        if os.path.exists(logo_path):
            pdf.image(logo_path, x=150, y=12, w=45)
        else:
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(50, 10, "EBM QUINTTO.", ln=0, align="R")
            
        pdf.ln(12)
        pdf.set_draw_color(255, 204, 0)
        pdf.set_line_width(1.5)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(8)
        
        fornecedor_formatado = f"{dados['fornecedor']}"
        if dados['fornecedor_cnpj']:
            fornecedor_formatado += f", CNPJ: {dados['fornecedor_cnpj']}"

        pdf.set_font("Helvetica", "", 10)
        if dados['is_midia']:
            texto = f"Atestamos para fins de comprovação de execução de serviço prestados que no mês de {dados['mes_ano']}, o veículo {fornecedor_formatado} a veiculações de mídias publicitárias do cliente {dados['cliente_nome']}, CNPJ {dados['cliente_cnpj']} intermediadas por essa agência de publicidade no período de acordo com as planilhas de AP e PI relacionadas abaixo."
        else:
            texto = f"Atestamos para fins de comprovação de execução de serviço prestados, que o fornecedor {fornecedor_formatado} produziu material publicitário para o {dados['cliente_nome']}, CNPJ {dados['cliente_cnpj']} intermediadas por essa agência de publicidade no período de acordo com as OC e PP relacionadas abaixo."
            
        pdf.multi_cell(0, 6, limpar_texto(texto))
        pdf.ln(8)
        
        pdf.set_draw_color(255, 204, 0)
        pdf.set_line_width(1.0)
        pdf.set_fill_color(0, 0, 0)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        
        if dados['is_midia']:
            pdf.cell(10, 9, "#", border=1, fill=True, align="C")
            pdf.cell(35, 9, "Planilha AP n°", border=1, fill=True, align="C")
            pdf.cell(30, 9, "PI n°", border=1, fill=True, align="C")
            pdf.cell(60, 9, "PEÇA", border=1, fill=True, align="C")
            pdf.cell(45, 9, "CAMPANHA", border=1, fill=True, align="C")
            pdf.ln()
            
            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 7.5) 
            pdf.cell(10, 10, "1", border=1, align="C")
            pdf.cell(35, 10, limitar_tamanho(dados['ap_oc'], 20), border=1, align="C")
            pdf.cell(30, 10, limitar_tamanho(pi_pp_input, 15), border=1, align="C")
            pdf.cell(60, 10, limitar_tamanho(dados['peca'], 60), border=1, align="C")
            pdf.cell(45, 10, limitar_tamanho(dados['campanha'], 35), border=1, align="C")
            
        else:
            pdf.cell(10, 9, "#", border=1, fill=True, align="C")
            pdf.cell(25, 9, "PP n°", border=1, fill=True, align="C")
            pdf.cell(25, 9, "OC n°", border=1, fill=True, align="C")
            pdf.cell(45, 9, "SERVIÇOS", border=1, fill=True, align="C")
            pdf.cell(35, 9, "TÍTULO", border=1, fill=True, align="C")
            pdf.cell(40, 9, "CAMPANHA", border=1, fill=True, align="C")
            pdf.ln()
            
            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 7.5)
            pdf.cell(10, 10, "1", border=1, align="C")
            pdf.cell(25, 10, limitar_tamanho(pi_pp_input, 15), border=1, align="C")
            pdf.cell(25, 10, limitar_tamanho(dados['ap_oc'], 15), border=1, align="C")
            pdf.cell(45, 10, limitar_tamanho(dados['servicos'], 40), border=1, align="C")
            pdf.cell(35, 10, limitar_tamanho(dados['titulo'], 30), border=1, align="C")
            pdf.cell(40, 10, limitar_tamanho(dados['campanha'], 30), border=1, align="C")
            
        pdf.ln(10)
        
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, limpar_texto(f"Fortaleza/CE, {data_hoje}."), ln=1)
        pdf.ln(5)
        
        if os.path.exists("luma_signature_perfect.png"):
            pdf.image("luma_signature_perfect.png", x=15, w=60)
        
        pdf.set_y(-30)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(100, 100, 100)
        
        pdf.cell(60, 3, "Fortaleza-CE", ln=0, align="C")
        pdf.cell(60, 3, "Brasília-DF- Setor Comercial Norte,", ln=0, align="C")
        pdf.cell(60, 3, "Bahia-BA Al. Salvador, 1057, Sl. 1411,", ln=1, align="C")
        
        pdf.cell(60, 3, "R. Beni Carvalho, 138 CEP: 60135-400", ln=0, align="C")
        pdf.cell(60, 3, "01 Bloco D, Conj 119 Vega Luxury Mall", ln=0, align="C")
        pdf.cell(60, 3, "Torre Europa Caminho das Arvores", ln=1, align="C")
        
        pdf.cell(60, 3, "+55 85 3253.5555", ln=0, align="C")
        pdf.cell(60, 3, "CEP: 70711-948 - 55 61 3525-7988", ln=0, align="C")
        pdf.cell(60, 3, "CEP: 41820-790 +55 71 3825-3178", ln=1, align="C")
        
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(0, 3, "@ebmquintto       ebmquintto.com.br", align="C")
        
        pdf_bytes = pdf.output()
        
        st.success("✅ Atestado gerado com sucesso!")
        st.download_button(
            label="📥 Baixar Atestado PDF",
            data=bytes(pdf_bytes),
            file_name=limpar_texto(f"ATESTADO_{dados['tag_cliente']}_{dados['ap_oc']}.pdf"),
            mime="application/pdf"
        )
