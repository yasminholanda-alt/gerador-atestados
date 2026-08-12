import streamlit as st
import pypdf
import re
import os
from datetime import datetime
from fpdf import FPDF

st.set_page_config(page_title="Gerador de Atestados - EBM QUINTTO", page_icon="📄", layout="wide")

st.title("📄 Gerador de Atestados SESC / SENAC")
st.write("Agência EBM QUINTTO Comunicação")

uploaded_file = st.file_uploader("Envie a AP ou OC em PDF", type=["pdf"])

def extrair_dados_pdf(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    texto = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    
    dados = {}
    
    # Identifica Cliente
    if "03.612.122/0001-27" in texto or "SESC" in texto.upper():
        dados['cliente_nome'] = "SERVIÇO SOCIAL DO COMERCIO SESC AR/CE"
        dados['cliente_cnpj'] = "03.612.122/0001-27"
        dados['tag_cliente'] = "SESC"
    else:
        dados['cliente_nome'] = "SERVIÇO NACIONAL DE APRENDIZAGEM COMERCIAL SENAC AR/CE"
        dados['cliente_cnpj'] = "03.648.344/0001-08"
        dados['tag_cliente'] = "SENAC"
        
    # Extrai números
    match_ap = re.search(r"(?:PLANILHA|AP|Nº)\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    match_oc = re.search(r"OC\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    dados['ap_oc'] = match_ap.group(1) if match_ap else (match_oc.group(1) if match_oc else "")
    
    match_pi = re.search(r"(?:PI|PEDIDO|PP)\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    dados['pi_pp'] = match_pi.group(1) if match_pi else ""
    
    match_campanha = re.search(r"CAMPANHA:\s*([^\n\r]+)", texto, re.IGNORECASE)
    dados['campanha'] = match_campanha.group(1).strip() if match_campanha else ""
    
    # Define o tipo com base no que foi encontrado
    dados['tipo'] = "Mídia (AP)" if match_ap else "Produção (OC)"
    
    return dados

if uploaded_file:
    dados_extraidos = extrair_dados_pdf(uploaded_file)
    
    st.subheader("Revisão de Dados")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        doc_type = st.radio("Tipo de Serviço:", ["Mídia (AP)", "Produção (OC)"], index=0 if dados_extraidos['tipo'] == "Mídia (AP)" else 1)
        ap_oc_val = st.text_input("Nº da AP / OC:", value=dados_extraidos['ap_oc'])
        pi_pp_val = st.text_input("Nº da PI / PP:", value=dados_extraidos['pi_pp'])
        
    with col2:
        fornecedor_val = st.text_input("Razão Social do Fornecedor/Veículo:", placeholder="Ex: TV VERDES MARES LTDA")
        mes_ano_val = st.text_input("Mês e Ano (Apenas p/ Mídia):", placeholder="Ex: Agosto de 2026")
        campanha_val = st.text_input("Campanha:", value=dados_extraidos['campanha'])
        
    with col3:
        if doc_type == "Produção (OC)":
            servicos_val = st.text_input("Serviços:", value="Produção de Vídeo")
            titulo_val = st.text_input("Título:", value="Institucional")
        else:
            peca_val = st.text_input("Peça / Formato:", value="Serviço de Publicidade / Mídia")
            
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        data_hoje = f"{datetime.now().day} de {meses[datetime.now().month - 1]} de {datetime.now().year}"
        data_emissao = st.text_input("Data de Emissão:", value=data_hoje)

    if st.button("🚀 Gerar Atestado Oficial", type="primary"):
        is_midia = (doc_type == "Mídia (AP)")
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(15, 15, 15)
        
        # Cabeçalho
        pdf.set_font("Helvetica", "B", 12)
        titulo_doc = f"ATESTADO DE VEICULAÇÃO DE MÍDIA | {dados_extraidos['tag_cliente']}" if is_midia else f"ATESTADO DE PRODUÇÃO – {dados_extraidos['tag_cliente']}"
        pdf.cell(130, 10, titulo_doc, ln=0)
        
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(50, 5, "EBM", ln=1, align="R")
        pdf.cell(180, 5, "QUINTTO.", ln=1, align="R")
        
        pdf.ln(8)
        
        # Texto Principal exato dos modelos
        pdf.set_font("Helvetica", "", 10)
        if is_midia:
            texto = f"Atestamos para fins de comprovação de execução de serviço prestados que no {mes_ano_val}, o veículo {fornecedor_val} a veiculações de mídias publicitárias do cliente {dados_extraidos['cliente_nome']}, CNPJ {dados_extraidos['cliente_cnpj']} intermediadas por essa agência de publicidade no período de acordo com as planilhas de AP e PI relacionadas abaixo."
        else:
            texto = f"Atestamos para fins de comprovação de execução de serviço prestados, que o fornecedor {fornecedor_val} produziu material publicitário para o {dados_extraidos['cliente_nome']}, CNPJ {dados_extraidos['cliente_cnpj']} intermediadas por essa agência de publicidade no período de acordo com as OC e PP relacionadas abaixo."
            
        pdf.multi_cell(0, 6, texto)
        pdf.ln(8)
        
        # Tabela
        pdf.set_fill_color(0, 0, 0)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        
        if is_midia:
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
            pdf.cell(35, 10, str(ap_oc_val), border=1, align="C")
            pdf.cell(30, 10, str(pi_pp_val), border=1, align="C")
            pdf.cell(60, 10, str(peca_val), border=1, align="C")
            pdf.cell(45, 10, str(campanha_val), border=1, align="C")
            
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
            pdf.cell(25, 10, str(pi_pp_val), border=1, align="C")
            pdf.cell(25, 10, str(ap_oc_val), border=1, align="C")
            pdf.cell(45, 10, str(servicos_val), border=1, align="C")
            pdf.cell(35, 10, str(titulo_val), border=1, align="C")
            pdf.cell(40, 10, str(campanha_val), border=1, align="C")
            
        pdf.ln(15)
        
        # Data e Assinatura
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Fortaleza/CE, {data_emissao}.", ln=1)
        pdf.ln(8)
        
        if os.path.exists("luma_signature_perfect.png"):
            pdf.image("luma_signature_perfect.png", x=15, w=40)
            
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.5)
        pdf.line(15, pdf.get_y(), 85, pdf.get_y())
        pdf.ln(2)
        
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(0, 4, "EBM QUINTTO COMUNICAÇÃO LTDA", ln=1)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 4, "Luma Oliveira", ln=1)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(0, 4, "Analista Financeiro", ln=1)
        
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
        
        st.success("✅ Atestado gerado no padrão oficial!")
        st.download_button(
            label="📥 Baixar Atestado Oficial",
            data=bytes(pdf_bytes),
            file_name=f"ATESTADO_{dados_extraidos['tag_cliente']}_{ap_oc_val}.pdf",
            mime="application/pdf"
        )
