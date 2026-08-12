import streamlit as st
import pypdf
import re
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT, TA_LEFT

# Configuração da Página Web
st.set_page_config(page_title="Gerador de Atestados - EBM QUINTTO", page_icon="📄", layout="centered")

st.title("📄 Gerador de Atestados Sesc / Senac")
st.write("Agência EBM QUINTTO Comunicação")

uploaded_file = st.file_uploader("Envie a AP ou OC em PDF", type=["pdf"])
doc_type = st.radio("Tipo de Serviço:", ["Mídia (AP)", "Produção (OC)"])

if doc_type == "Mídia (AP)":
    num_id = st.text_input("Número do PI:", placeholder="Ex: 36123")
else:
    num_id = st.text_input("Número da PP:", placeholder="Ex: 17153")

data_emissao = st.text_input("Data de Emissão do Atestado:", value="12 de Agosto de 2026")

def extrair_dados_pdf(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    texto = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    
    dados = {}
    if "03.612.122/0001-27" in texto or "SESC" in texto.upper():
        dados['cliente_nome'] = "SERVIÇO SOCIAL DO COMERCIO SESC AR/CE"
        dados['cliente_cnpj'] = "03.612.122/0001-27"
        dados['tag_cliente'] = "SESC"
    else:
        dados['cliente_nome'] = "SERVIÇO NACIONAL DE APRENDIZAGEM COMERCIAL SENAC AR/CE"
        dados['cliente_cnpj'] = "03.648.344/0001-08"
        dados['tag_cliente'] = "SENAC"
        
    match_ap = re.search(r"Nº\s*PLANILHA:\s*0*(\d+)", texto, re.IGNORECASE)
    match_oc = re.search(r"OC\s*0*(\d+)", texto, re.IGNORECASE)
    dados['planilha_num'] = match_ap.group(1) if match_ap else (match_oc.group(1) if match_oc else "N/A")
    
    match_campanha = re.search(r"CAMPANHA:\s*([^\n]+)", texto, re.IGNORECASE)
    dados['campanha'] = match_campanha.group(1).strip() if match_campanha else "MÍDIAS INSTITUCIONAIS"
    return dados

def gerar_pdf(dados, num_id, data_emissao, is_midia):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=60
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        textColor=colors.HexColor('#111111')
    )
    
    brand_style = ParagraphStyle(
        'BrandLogo',
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=16,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#111111')
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        fontName='Helvetica',
        fontSize=10,
        leading=16,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor('#222222')
    )
    
    header_title = f"ATESTADO DE VEICULAÇÃO DE MÍDIA | {dados['tag_cliente']}" if is_midia else f"ATESTADO DE PRODUÇÃO – {dados['tag_cliente']}"
    
    elements = []
    
    # Cabeçalho
    header_data = [
        [Paragraph(header_title, title_style), Paragraph("EBM<br/><b>QUINTTO.</b>", brand_style)]
    ]
    header_table = Table(header_data, colWidths=[360, 155])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    
    # Linha Amarela
    elements.append(HRFlowable(width="100%", thickness=2.5, color=colors.HexColor('#FFCC00'), spaceAfter=20))
    
    # Texto
    texto = f"Atestamos para fins de comprovação de execução de serviço prestados que para o cliente <b>{dados['cliente_nome']}</b>, CNPJ <b>{dados['cliente_cnpj']}</b>, intermediadas por essa agência de publicidade no período de acordo com as informações relacionadas abaixo."
    elements.append(Paragraph(texto, body_style))
    elements.append(Spacer(1, 20))
    
    # Tabela
    col1 = "PLANILHA AP Nº" if is_midia else "PP Nº"
    col2 = "PI Nº" if is_midia else "OC Nº"
    col3 = "PEÇA" if is_midia else "SERVIÇOS"
    
    th_style = ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.white)
    td_style = ParagraphStyle('TD', fontName='Helvetica', fontSize=8, leading=11, alignment=TA_CENTER, textColor=colors.HexColor('#222222'))
    
    table_data = [
        [Paragraph("#", th_style), Paragraph(col1, th_style), Paragraph(col2, th_style), Paragraph(col3, th_style), Paragraph("CAMPANHA", th_style)],
        [Paragraph("1", td_style), Paragraph(str(dados['planilha_num']), td_style), Paragraph(str(num_id), td_style), Paragraph("Serviço de Publicidade / Mídia", td_style), Paragraph(str(dados['campanha']), td_style)]
    ]
    
    table = Table(table_data, colWidths=[25, 110, 80, 160, 140])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111111')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D1D5DB')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 25))
    
    # Data
    elements.append(Paragraph(f"Fortaleza/CE, {data_emissao}.", body_style))
    elements.append(Spacer(1, 15))
    
    # Assinatura
    try:
        elements.append(Image("luma_signature_perfect.png", width=140, height=35, hAlign='LEFT'))
    except:
        pass
        
    elements.append(HRFlowable(width=220, thickness=1.5, color=colors.HexColor('#111111'), hAlign='LEFT', spaceAfter=8))
    
    sig_text = "<b>EBM QUINTTO COMUNICAÇÃO LTDA</b><br/><b>Luma Oliveira</b><br/>Analista Financeiro"
    elements.append(Paragraph(sig_text, ParagraphStyle('Sig', fontName='Helvetica', fontSize=9, leading=13)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

if st.button("🚀 Gerar Atestado", type="primary"):
    if not uploaded_file or not num_id:
        st.error("Por favor, anexe o PDF e preencha o número do PI/PP.")
    else:
        dados = extrair_dados_pdf(uploaded_file)
        pdf_buffer = gerar_pdf(dados, num_id, data_emissao, (doc_type == "Mídia (AP)"))
        
        st.success("✅ Atestado gerado com sucesso!")
        st.download_button(
            label="📥 Baixar Atestado PDF",
            data=pdf_buffer,
            file_name=f"ATESTADO_{dados['tag_cliente']}_{num_id}.pdf",
            mime="application/pdf"
        )
