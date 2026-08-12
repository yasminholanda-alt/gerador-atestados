import streamlit as st
import pypdf
import re
import os
from datetime import datetime
from fpdf import FPDF

# Configuração da Página
st.set_page_config(page_title="Gerador de Atestados - EBM QUINTTO", page_icon="📄", layout="centered")

st.title("📄 Gerador Automático de Atestados")
st.write("Agência EBM QUINTTO Comunicação")

# Apenas 2 campos na tela: O Arquivo e o Número do PI/PP
uploaded_file = st.file_uploader("1. Envie a AP ou OC em PDF", type=["pdf"])
pi_pp_input = st.text_input("2. Digite o Número do PI ou PP:", placeholder="Ex: 37710")

# Função que lê o PDF e descobre tudo sozinho
def extrair_dados_pdf(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    texto = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    
    dados = {}
    
    # 1. Identifica Cliente
    if "03.612.122/0001-27" in texto or "SESC" in texto.upper():
        dados['cliente_nome'] = "SERVIÇO SOCIAL DO COMERCIO SESC AR/CE"
        dados['cliente_cnpj'] = "03.612.122/0001-27"
        dados['tag_cliente'] = "SESC"
    else:
        dados['cliente_nome'] = "SERVIÇO NACIONAL DE APRENDIZAGEM COMERCIAL SENAC AR/CE"
        dados['cliente_cnpj'] = "03.648.344/0001-08"
        dados['tag_cliente'] = "SENAC"
        
    # 2. Identifica se é Mídia (AP) ou Produção (OC)
    match_ap = re.search(r"(?:PLANILHA|AP|Nº)\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    match_oc = re.search(r"OC\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    dados['is_midia'] = bool(match_ap)
    dados['ap_oc'] = match_ap.group(1) if match_ap else (match_oc.group(1) if match_oc else "N/A")
    
    # 3. Busca Campanha
    match_campanha = re.search(r"CAMPANHA:\s*([^\n\r]+)", texto, re.IGNORECASE)
    dados['campanha'] = match_campanha.group(1).strip() if match_campanha else "MÍDIAS INSTITUCIONAIS"
    
    # 4. Busca Fornecedor / Veículo
    match_fornecedor = re.search(r"(?:FORNECEDOR|VE[IÍ]CULO|RAZ[ÃA]O SOCIAL|EMPRESA)\s*[:\-]?\s*([^\n\r]+)", texto, re.IGNORECASE)
    dados['fornecedor'] = match_fornecedor.group(1).strip().upper() if match_fornecedor else "FORNECEDOR NÃO IDENTIFICADO"
    
    # 5. Busca Peça / Título / Serviço
    match_peca = re.search(r"(?:PE[ÇC]A|SERVI[ÇC]O|T[ÍI]TULO)\s*[:\-]?\s*([^\n\r]+)", texto, re.IGNORECASE)
    dados['peca'] = match_peca.group(1).strip() if match_peca else "Serviço de Publicidade"
    
    # 6. Busca Mês / Período
    match_mes = re.search(r"(?:M[ÊE]S|PER[ÍI]ODO|DATA)\s*[:\-]?\s*([^\n\r]+)", texto, re.IGNORECASE)
    dados['mes_ano'] = match_mes.group(1).strip() if match_mes else "Agosto de 2026"
    
    return dados

# Botão para gerar direto
if st.button("🚀 Gerar Atestado", type="primary"):
    if not uploaded_file or not pi_pp_input:
        st.error("Por favor, envie o arquivo PDF e digite o número do PI/PP.")
    else:
        # Extrai tudo automaticamente
        dados = extrair_dados_pdf(uploaded_file)
        
        # Pega a data de hoje para a assinatura
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        data_hoje = f"{datetime.now().day} de {meses[datetime.now().month - 1]} de {datetime.now().year}"
        
        # Inicia o PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(15, 15, 15)
        
        # Cabeçalho
        pdf.set_font("Helvetica", "B", 12)
        titulo_doc = f"ATESTADO DE VEICULAÇÃO DE MÍDIA | {dados['tag_cliente']}" if dados['is_midia'] else f"ATESTADO DE PRODUÇÃO – {dados['tag_cliente']}"
        pdf.cell(130, 10, titulo_doc, ln=0)
        
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(50, 5, "EBM", ln=1, align="R")
        pdf.cell(180, 5, "QUINTTO.", ln=1, align="R")
        pdf.ln(8)
        
        # Texto Principal exato dos modelos
        pdf.set_font("Helvetica", "", 10)
        if dados['is_midia']:
            texto = f"Atestamos para fins de comprovação de execução de serviço prestados que no {dados['mes_ano']}, o veículo {dados['fornecedor']} a veiculações de mídias publicitárias do cliente {dados['cliente_nome']}, CNPJ {dados['cliente_cnpj']} intermediadas por essa agência de publicidade no período de acordo com as planilhas de AP e PI relacionadas abaixo."
        else:
            texto = f"Atestamos para fins de comprovação de execução de serviço prestados, que o fornecedor {dados['fornecedor']} produziu material publicitário para o {dados['cliente_nome']}, CNPJ {dados['cliente_cnpj']} intermediadas por essa agência de publicidade no período de acordo com as OC e PP relacionadas abaixo."
            
        pdf.multi_cell(0, 6, texto)
        pdf.ln(8)
        
        # Desenha a Tabela
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
            pdf.cell(35, 10, str(dados['ap_oc']), border=1, align="C")
            pdf.cell(30, 10, str(pi_pp_input), border=1, align="C")
            pdf.cell(60, 10, str(dados['peca']), border=1, align="C")
            pdf.cell(45, 10, str(dados['campanha']), border=1, align="C")
            
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
            pdf.cell(25, 10, str(pi_pp_input), border=1, align="C")
            pdf.cell(25, 10, str(dados['ap_oc']), border=1, align="C")
            pdf.cell(45, 10, str(dados['peca']), border=1, align="C")
            pdf.cell(35, 10, str(dados['peca']), border=1, align="C")
            pdf.cell(40, 10, str(dados['campanha']), border=1, align="C")
            
        pdf.ln(15)
        
        # Data e Assinatura
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Fortaleza/CE, {data_hoje}.", ln=1)
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
        
        st.success("✅ Atestado gerado com sucesso!")
        st.download_button(
            label="📥 Baixar Atestado PDF",
            data=bytes(pdf_bytes),
            file_name=f"ATESTADO_{dados['tag_cliente']}_{dados['ap_oc']}.pdf",
            mime="application/pdf"
        )
