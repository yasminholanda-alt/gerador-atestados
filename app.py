import streamlit as st
import pypdf
import re
import os
from fpdf import FPDF

st.set_page_config(page_title="Gerador de Atestados - EBM QUINTTO", page_icon="📄", layout="centered")

st.title("📄 Gerador de Atestados SESC / SENAC")
st.write("Agência EBM QUINTTO Comunicação")

uploaded_file = st.file_uploader("Envie a AP ou OC em PDF", type=["pdf"])

# Função de extração inteligente do PDF
def extrair_dados_pdf(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    texto = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    
    dados = {}
    
    # Identifica Cliente (SESC ou SENAC)
    if "03.612.122/0001-27" in texto or "SESC" in texto.upper():
        dados['cliente_nome'] = "SERVIÇO SOCIAL DO COMERCIO SESC AR/CE"
        dados['cliente_cnpj'] = "03.612.122/0001-27"
        dados['tag_cliente'] = "SESC"
    else:
        dados['cliente_nome'] = "SERVIÇO NACIONAL DE APRENDIZAGEM COMERCIAL SENAC AR/CE"
        dados['cliente_cnpj'] = "03.648.344/0001-08"
        dados['tag_cliente'] = "SENAC"
        
    # Extrai AP ou OC
    match_ap = re.search(r"(?:PLANILHA|AP|Nº)\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    match_oc = re.search(r"OC\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    dados['ap_oc'] = match_ap.group(1) if match_ap else (match_oc.group(1) if match_oc else "N/A")
    
    # Extrai PI ou PP
    match_pi = re.search(r"(?:PI|PEDIDO|PP)\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    dados['pi_pp'] = match_pi.group(1) if match_pi else "37710"
    
    # Extrai Campanha
    match_campanha = re.search(r"CAMPANHA:\s*([^\n\r]+)", texto, re.IGNORECASE)
    dados['campanha'] = match_campanha.group(1).strip() if match_campanha else "MÍDIAS INSTITUCIONAIS"
    
    return dados

# Se um arquivo for enviado, extrai e preenche os campos automaticamente
if uploaded_file:
    dados_extraidos = extrair_dados_pdf(uploaded_file)
    
    col1, col2 = st.columns(2)
    with col1:
        doc_type = st.radio("Tipo de Serviço:", ["Mídia (AP)", "Produção (OC)"])
        ap_oc_val = st.text_input("Número da AP/OC:", value=dados_extraidos['ap_oc'])
    with col2:
        num_id_val = st.text_input("Número do PI/PP:", value=dados_extraidos['pi_pp'])
        campanha_val = st.text_input("Campanha:", value=dados_extraidos['campanha'])
        
    data_emissao = st.text_input("Data de Emissão:", value="11 de Agosto de 2026")
    
    # Classe do PDF com cabeçalho e bordas exatas
    class AtestadoPDF(FPDF):
        pass

    if st.button("🚀 Gerar Atestado PDF", type="primary"):
        is_midia = (doc_type == "Mídia (AP)")
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(15, 15, 15)
        
        # Cabeçalho
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(11, 11, 11)
        titulo = f"ATESTADO DE VEICULAÇÃO DE MÍDIA | {dados_extraidos['tag_cliente']}" if is_midia else f"ATESTADO DE PRODUÇÃO – {dados_extraidos['tag_cliente']}"
        pdf.cell(130, 10, titulo, ln=0)
        
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(50, 5, "EBM", ln=1, align="R")
        pdf.cell(180, 5, "QUINTTO.", ln=1, align="R")
        
        # Linha Divisória Amarela Superior
        pdf.set_draw_color(255, 204, 0)
        pdf.set_line_width(2.0)
        pdf.line(15, 30, 195, 30)
        pdf.ln(12)
        
        # Texto Principal
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(34, 34, 34)
        texto = f"Atestamos para fins de comprovação de execução de serviço prestados que para o cliente {dados_extraidos['cliente_nome']}, CNPJ {dados_extraidos['cliente_cnpj']}, intermediadas por essa agência de publicidade no período de acordo com as informações relacionadas abaixo."
        pdf.multi_cell(0, 6, texto)
        pdf.ln(8)
        
        # Configuração da Tabela
        col1_title = "PLANILHA AP Nº" if is_midia else "PP Nº"
        col2_title = "PI Nº" if is_midia else "OC Nº"
        col3_title = "PEÇA" if is_midia else "SERVIÇOS"
        
        pdf.set_draw_color(255, 204, 0) # Bordas Amarelas na Tabela
        pdf.set_line_width(1.5)
        
        # Cabeçalho da Tabela
        pdf.set_fill_color(17, 17, 17) # Fundo Preto
        pdf.set_text_color(255, 255, 255) # Texto Branco
        pdf.set_font("Helvetica", "B", 8)
        
        pdf.cell(10, 9, "#", border=1, fill=True, align="C")
        pdf.cell(38, 9, col1_title, border=1, fill=True, align="C")
        pdf.cell(32, 9, col2_title, border=1, fill=True, align="C")
        pdf.cell(55, 9, col3_title, border=1, fill=True, align="C")
        pdf.cell(45, 9, "CAMPANHA", border=1, fill=True, align="C")
        pdf.ln()
        
        # Dados da Tabela
        pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(34, 34, 34)
        pdf.set_font("Helvetica", "", 8)
        
        pdf.cell(10, 10, "1", border=1, align="C")
        pdf.cell(38, 10, str(ap_oc_val), border=1, align="C")
        pdf.cell(32, 10, str(num_id_val), border=1, align="C")
        pdf.cell(55, 10, "Serviço de Publicidade / Mídia", border=1, align="C")
        pdf.cell(45, 10, str(campanha_val), border=1, align="C")
        pdf.ln(16)
        
        # Data
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Fortaleza/CE, {data_emissao}.", ln=1)
        pdf.ln(4)
        
        # Assinatura
        if os.path.exists("luma_signature_perfect.png"):
            pdf.image("luma_signature_perfect.png", x=15, w=50)
            
        pdf.set_draw_color(17, 17, 17)
        pdf.set_line_width(0.8)
        pdf.line(15, pdf.get_y(), 75, pdf.get_y())
        pdf.ln(2)
        
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(0, 4, "EBM QUINTTO COMUNICAÇÃO LTDA", ln=1)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 4, "Luma Oliveira", ln=1)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(0, 4, "Analista Financeiro", ln=1)
        
        pdf_bytes = pdf.output()
        
        st.success("✅ Atestado gerado no padrão oficial!")
        st.download_button(
            label="📥 Baixar Atestado PDF",
            data=bytes(pdf_bytes),
            file_name=f"ATESTADO_{dados_extraidos['tag_cliente']}_{num_id_val}.pdf",
            mime="application/pdf"
        )
