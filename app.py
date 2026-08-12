import streamlit as st
import re
import os
from datetime import datetime
from fpdf import FPDF
import pytesseract
from pdf2image import convert_from_bytes

# Configuração da Página
st.set_page_config(page_title="Gerador de Atestados - EBM QUINTTO", page_icon="📄", layout="centered")

st.title("📄 Gerador Automático de Atestados")
st.write("Agência EBM QUINTTO Comunicação (Lê PDFs Escaneados)")

uploaded_file = st.file_uploader("1. Envie a AP ou OC em PDF", type=["pdf"])
pi_pp_input = st.text_input("2. Digite o Número do PI ou PP:", placeholder="Ex: 37710")

# Funções de limpeza e limite de caracteres
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
        texto += pytesseract.image_to_string(img, lang='por') + "\n"
        
    texto_upper = texto.upper()
    dados = {}
    
    # 1. IDENTIFICAÇÃO DO CLIENTE (SESC x SENAC)
    if "03.648.344" in texto_upper or "SERVIÇO NACIONAL DE APRENDIZAGEM COMERCIAL" in texto_upper or "SERVICO NACIONAL" in texto_upper:
        is_senac = True
    elif "03.612.122" in texto_upper or "SERVIÇO SOCIAL DO COMERCIO" in texto_upper or "SERVICO SOCIAL" in texto_upper:
        is_senac = False
    else:
        contagem_senac = texto_upper.count("SENAC")
        contagem_sesc = texto_upper.count("SESC")
        is_senac = contagem_senac > contagem_sesc

    if is_senac:
        dados['cliente_nome'] = "SERVIÇO NACIONAL DE APRENDIZAGEM COMERCIAL SENAC AR/CE"
        dados['cliente_cnpj'] = "03.648.344/0001-08"
        dados['tag_cliente'] = "SENAC"
    else:
        dados['cliente_nome'] = "SERVIÇO SOCIAL DO COMERCIO SESC AR/CE"
        dados['cliente_cnpj'] = "03.612.122/0001-27"
        dados['tag_cliente'] = "SESC"
        
    # 2. IDENTIFICA AP OU OC
    match_ap = re.search(r"(?:PLANILHA|AP|Nº|N|NO)\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    match_oc = re.search(r"OC\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    dados['is_midia'] = bool(match_ap)
    dados['ap_oc'] = match_ap.group(1) if match_ap else (match_oc.group(1) if match_oc else "N/A")
    
    # 3. EXTRAI O CNPJ DO FORNECEDOR/VEÍCULO (Ignorando o do SESC/SENAC)
    cnpjs_encontrados = re.findall(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    fornecedor_cnpj = ""
    for c in cnpjs_encontrados:
        if c not in ["03.612.122/0001-27", "03.648.344/0001-08"]:
            fornecedor_cnpj = c
            break
    dados['fornecedor_cnpj'] = fornecedor_cnpj
    
    # 4. EXTRAI A RAZÃO SOCIAL DO FORNECEDOR (Lendo a linha acima do CNPJ)
    fornecedor_nome = ""
    linhas = [l.strip() for l in texto.split('\n') if l.strip()]
    if fornecedor_cnpj:
        for i, linha in enumerate(linhas):
            if fornecedor_cnpj in linha and i > 0:
                fornecedor_nome = linhas[i-1]
                fornecedor_nome = re.sub(r"^(FORNECEDOR|VE[IÍ]CULO|RAZ[ÃA]O SOCIAL|EMPRESA)\s*[:\-]?\s*", "", fornecedor_nome, flags=re.IGNORECASE)
                break
                
    if len(fornecedor_nome) < 3:
        match_fornecedor = re.search(r"(?:FORNECEDOR|VE[IÍ]CULO|RAZ[ÃA]O SOCIAL|EMPRESA)\s*[:\-]?\s*([^\n\r]+)", texto, re.IGNORECASE)
        if match_fornecedor:
            fornecedor_nome = match_fornecedor.group(1).strip()
            fornecedor_nome = re.split(r"(MEIO|FORMATO|PER[ÍI]ODO|CAMPANHA|VALOR|DATA|VE[IÍ]CULO|CNPJ|CLIENTE)", fornecedor_nome, flags=re.IGNORECASE)[0].strip()

    dados['fornecedor'] = fornecedor_nome.upper() if fornecedor_nome else "FORNECEDOR NÃO IDENTIFICADO"

    # 5. DEMAIS DADOS
    def extrair_e_limpar(padrao):
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            res = match.group(1).strip()
            res = re.split(r"(MEIO|FORMATO|PER[ÍI]ODO|CAMPANHA|VALOR|DATA|VE[IÍ]CULO|CNPJ|CLIENTE)", res, flags=re.IGNORECASE)[0].strip()
            return res
        return ""

    campanha = extrair_e_limpar(r"CAMPANHA:\s*([^\n\r]+)")
    dados['campanha'] = campanha if campanha else "MÍDIAS INSTITUCIONAIS"
    
    peca = extrair_e_limpar(r"(?:PE[ÇC]A|SERVI[ÇC]O|T[ÍI]TULO)\s*[:\-]?\s*([^\n\r]+)")
    dados['peca'] = peca if peca else "Serviço de Publicidade"
    
    mes = extrair_e_limpar(r"(?:M[ÊE]S|PER[ÍI]ODO|DATA)\s*[:\-]?\s*([^\n\r]+)")
    dados['mes_ano'] = mes if mes else "Agosto de 2026"
    
    return dados

if st.button("🚀 Gerar Atestado Oficial", type="primary"):
    if not uploaded_file or not pi_pp_input:
        st.error("Por favor, envie o arquivo PDF e digite o número do PI/PP.")
    else:
        with st.spinner("Analisando PDF e extraindo Razão Social/CNPJ..."):
            pdf_bytes = uploaded_file.read()
            dados = extrair_dados_pdf_escaneado(pdf_bytes)
        
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        data_hoje = f"{datetime.now().day} de {meses[datetime.now().month - 1]} de {datetime.now().year}"
        
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=10)
        pdf.add_page()
        pdf.set_margins(15, 15, 15)
        
        # Cabeçalho: Título + Nova Logo
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
        
        # Linha amarela do cabeçalho
        pdf.set_draw_color(255, 204, 0)
        pdf.set_line_width(1.5)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(8)
        
        # Monta a string do Fornecedor + CNPJ
        fornecedor_formatado = f"{dados['fornecedor']}"
        if dados['fornecedor_cnpj']:
            fornecedor_formatado += f", CNPJ: {dados['fornecedor_cnpj']}"

        # Texto Principal
        pdf.set_font("Helvetica", "", 10)
        if dados['is_midia']:
            texto = f"Atestamos para fins de comprovação de execução de serviço prestados que no {dados['mes_ano']}, o veículo {fornecedor_formatado} a veiculações de mídias publicitárias do cliente {dados['cliente_nome']}, CNPJ {dados['cliente_cnpj']} intermediadas por essa agência de publicidade no período de acordo com as planilhas de AP e PI relacionadas abaixo."
        else:
            texto = f"Atestamos para fins de comprovação de execução de serviço prestados, que o fornecedor {fornecedor_formatado} produziu material publicitário para o {dados['cliente_nome']}, CNPJ {dados['cliente_cnpj']} intermediadas por essa agência de publicidade no período de acordo com as OC e PP relacionadas abaixo."
            
        pdf.multi_cell(0, 6, limpar_texto(texto))
        pdf.ln(8)
        
        # Tabela
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
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(10, 10, "1", border=1, align="C")
            pdf.cell(35, 10, limitar_tamanho(dados['ap_oc'], 20), border=1, align="C")
            pdf.cell(30, 10, limitar_tamanho(pi_pp_input, 15), border=1, align="C")
            pdf.cell(60, 10, limitar_tamanho(dados['peca'], 40), border=1, align="C")
            pdf.cell(45, 10, limitar_tamanho(dados['campanha'], 25), border=1, align="C")
            
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
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(10, 10, "1", border=1, align="C")
            pdf.cell(25, 10, limitar_tamanho(pi_pp_input, 15), border=1, align="C")
            pdf.cell(25, 10, limitar_tamanho(dados['ap_oc'], 15), border=1, align="C")
            pdf.cell(45, 10, limitar_tamanho(dados['peca'], 28), border=1, align="C")
            pdf.cell(35, 10, limitar_tamanho(dados['peca'], 20), border=1, align="C")
            pdf.cell(40, 10, limitar_tamanho(dados['campanha'], 22), border=1, align="C")
            
        pdf.ln(10)
        
        # Data e Assinatura
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, limpar_texto(f"Fortaleza/CE, {data_hoje}."), ln=1)
        pdf.ln(5)
        
        if os.path.exists("luma_signature_perfect.png"):
            pdf.image("luma_signature_perfect.png", x=15, w=60)
        
        # Rodapé Exato
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
