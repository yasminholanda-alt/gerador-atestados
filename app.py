import streamlit as st
import re
import os
from datetime import datetime
from fpdf import FPDF
import pytesseract
from pdf2image import convert_from_bytes

st.set_page_config(page_title="Gerador de Atestados - EBM QUINTTO", page_icon="📄", layout="wide")

st.title("📄 Gerador Automático de Atestados")
st.write("Agência EBM QUINTTO Comunicação (Modo Paisagem com Revisão)")

uploaded_file = st.file_uploader("1. Envie a AP ou OC em PDF escaneado", type=["pdf"])

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
    
    # 1. CLIENTE
    if "03.648.344" in texto_upper or "SERVIÇO NACIONAL DE APRENDIZAGEM" in texto_upper:
        dados['cliente_nome'] = "SERVIÇO NACIONAL DE APRENDIZAGEM COMERCIAL SENAC AR/CE"
        dados['cliente_cnpj'] = "03.648.344/0001-08"
        dados['tag_cliente'] = "SENAC"
    else:
        dados['cliente_nome'] = "SERVIÇO SOCIAL DO COMERCIO SESC AR/CE"
        dados['cliente_cnpj'] = "03.612.122/0001-27"
        dados['tag_cliente'] = "SESC"
        
    # 2. TIPO E NÚMERO (AP/OC)
    match_ap = re.search(r"(?:PLANILHA|AP|Nº|N|NO)\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    match_oc = re.search(r"OC\s*[:\.]?\s*0*(\d{4,6})", texto, re.IGNORECASE)
    dados['is_midia'] = bool(match_ap)
    dados['ap_oc'] = match_ap.group(1) if match_ap else (match_oc.group(1) if match_oc else "")
    
    # 3. CNPJ FORNECEDOR
    cnpjs_ignorados = ["03.612.122/0001-27", "03.648.344/0001-08", "14.470.051/0001-91"]
    cnpjs_encontrados = re.findall(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    dados['fornecedor_cnpj'] = next((c for c in cnpjs_encontrados if c not in cnpjs_ignorados), "")
    
    # 4. FORNECEDOR NOME
    fornecedor_nome = ""
    linhas = [l.strip() for l in texto.split('\n') if l.strip()]
    if dados['fornecedor_cnpj']:
        for i, linha in enumerate(linhas):
            if dados['fornecedor_cnpj'] in linha and i > 0:
                fornecedor_nome = linhas[i-1]
                if "FONE" in fornecedor_nome.upper() or "FAX" in fornecedor_nome.upper():
                    fornecedor_nome = linhas[i-2] if i > 1 else fornecedor_nome
                fornecedor_nome = re.sub(r"^(FORNECEDOR|VE[IÍ]CULO|RAZ[ÃA]O SOCIAL|EMPRESA)\s*[:\-]?\s*", "", fornecedor_nome, flags=re.IGNORECASE)
                fornecedor_nome = re.split(r"\||\+|=|_", fornecedor_nome)[0].strip()
                break
    dados['fornecedor'] = fornecedor_nome.upper() if fornecedor_nome else ""

    # 5. CAMPANHA E TÍTULO
    match_camp = re.search(r"CAMPANHA\s*[:\-]?\s*([^\n\r\|]+)", texto_upper)
    dados['campanha'] = match_camp.group(1).strip() if match_camp else ""
    
    # O Título agora é uma cópia exata da Campanha, conforme você pediu!
    dados['titulo'] = dados['campanha'] if dados['campanha'] else "N/A"
    
    # 6. MÊS
    match_mes = re.search(r"(?:M[ÊE]S|PER[ÍI]ODO|DATA)\s*[:\-]?\s*([^\n\r\|]+)", texto_upper)
    mes = match_mes.group(1).strip() if match_mes else ""
    dados['mes_ano'] = re.sub(r"^(M[ÊE]S DE\s*|M[ÊE]S\s*)", "", mes, flags=re.IGNORECASE)
    
    # 7. PEÇA / SERVIÇOS (Busca flexível)
    if dados['is_midia']:
        match_aut = re.search(r"REFERENTE\s*[AÀ]\s*([^\n\r]+)", texto_upper)
        match_veic = re.search(r"(VEICULA[ÇC][ÃA]O DE\s*[^\n\r]+)", texto_upper)
        match_peca = re.search(r"(?:PE[ÇC]A|SERVI[ÇC]O)\s*[:\-]?\s*([^\n\r\|]+)", texto_upper)
        
        texto_peca = match_aut.group(1).strip() if match_aut else (match_veic.group(1).strip() if match_veic else (match_peca.group(1).strip() if match_peca else ""))
        
        match_vol = re.search(r"VOLUME:\s*([^\n\r]+)", texto_upper)
        if match_vol and texto_peca:
            texto_peca += f" - {match_vol.group(1).strip()}"
            
        dados['peca'] = texto_peca
    else:
        match_serv = re.search(r"(?:OP[ÇC][ÃA]O|DESCRI[ÇC][ÃA]O.*?FORNECEDOR)[\s\S]{1,200}?(?:^|\n)\s*(?:1|01)\s+([^\n\r]+)", texto_upper)
        dados['peca'] = re.split(r"\s{2,}|\d{1,3}\s*DFM|CNPJ|R\$", match_serv.group(1))[0].strip() if match_serv else ""

    return dados

if uploaded_file:
    with st.spinner("Lendo documento escaneado..."):
        dados = extrair_dados_pdf_escaneado(uploaded_file.read())
        
    st.subheader("2. Revise os dados e complete o PI/PP")
    st.info("💡 Como o documento é escaneado, revise se o robô leu os campos corretamente. Corrija o que precisar abaixo:")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        doc_type = st.radio("Tipo de Serviço:", ["Mídia (AP)", "Produção (OC)"], index=0 if dados['is_midia'] else 1)
        pi_pp_val = st.text_input("Nº da PI / PP (Obrigatório):", placeholder="Ex: 37710")
        ap_oc_val = st.text_input("Nº da AP / OC:", value=dados['ap_oc'])
        
    with col2:
        fornecedor_val = st.text_input("Fornecedor / Veículo:", value=dados['fornecedor'])
        cnpj_val = st.text_input("CNPJ do Fornecedor:", value=dados['fornecedor_cnpj'])
        mes_ano_val = st.text_input("Mês / Período:", value=dados['mes_ano'])
        
    with col3:
        campanha_val = st.text_input("Campanha:", value=dados['campanha'])
        peca_servico_val = st.text_input("Peça / Serviços (Pode colar textos longos aqui):", value=dados['peca'])
        # Título amarrado à Campanha se for Produção
        titulo_val = st.text_input("Título (Apenas Produção):", value=campanha_val if doc_type == "Produção (OC)" else "N/A", disabled=doc_type == "Mídia (AP)")
        
    if st.button("🚀 Gerar Atestado Oficial", type="primary"):
        if not pi_pp_val:
            st.error("Por favor, preencha o número do PI/PP.")
        else:
            meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            data_hoje = f"{datetime.now().day} de {meses[datetime.now().month - 1]} de {datetime.now().year}"
            
            pdf = FPDF(orientation='L')
            pdf.set_auto_page_break(auto=True, margin=10)
            pdf.add_page()
            pdf.set_margins(15, 15, 15)
            
            pdf.set_font("Helvetica", "B", 12)
            is_midia_selecionado = (doc_type == "Mídia (AP)")
            titulo_doc = f"ATESTADO DE VEICULAÇÃO DE MÍDIA | {dados['tag_cliente']}" if is_midia_selecionado else f"ATESTADO DE PRODUÇÃO - {dados['tag_cliente']}"
            pdf.cell(130, 10, limpar_texto(titulo_doc), ln=0)
            
            logo_path = "logo ebmquintto preta BG transparente.png"
            if os.path.exists(logo_path):
                pdf.image(logo_path, x=235, y=12, w=45)
            else:
                pdf.set_font("Helvetica", "B", 16)
                pdf.cell(137, 10, "EBM QUINTTO.", ln=0, align="R")
                
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
                texto = f"Atestamos para fins de comprovação de execução de serviço prestados que no mês de {mes_ano_val}, o veículo {fornecedor_formatado} a veiculações de mídias publicitárias do cliente {dados['cliente_nome']}, CNPJ {dados['cliente_cnpj']} intermediadas por essa agência de publicidade no período de acordo com as planilhas de AP e PI relacionadas abaixo."
            else:
                texto = f"Atestamos para fins de comprovação de execução de serviço prestados, que o fornecedor {fornecedor_formatado} produziu material publicitário para o {dados['cliente_nome']}, CNPJ {dados['cliente_cnpj']} intermediadas por essa agência de publicidade no período de acordo com as OC e PP relacionadas abaixo."
                
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
                # Aqui o PDF vai receber a cópia da campanha se estiver gerando Produção
                pdf.cell(60, 10, limitar_tamanho(campanha_val, 50), border=1, align="C")
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
                file_name=limpar_texto(f"ATESTADO_{dados['tag_cliente']}_{ap_oc_val}.pdf"),
                mime="application/pdf"
            )
