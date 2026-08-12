import streamlit as st
import pypdf
import re
import base64
from weasyprint import HTML

# Configuração da página e título do site
st.set_page_config(page_title="Gerador de Atestados - EBM QUINTTO", page_icon="📄", layout="centered")

st.title("📄 Gerador de Atestados Sesc / Senac")
st.write("Agência EBM QUINTTO Comunicação")

# 1. Campos de Entrada da Interface
uploaded_file = st.file_uploader("Envie a AP ou OC em PDF", type=["pdf"])
doc_type = st.radio("Tipo de Serviço:", ["Mídia (AP)", "Produção (OC)"])

if doc_type == "Mídia (AP)":
    num_id = st.text_input("Número do PI:", placeholder="Ex: 36123")
else:
    num_id = st.text_input("Número da PP:", placeholder="Ex: 17153")

data_emissao = st.text_input("Data de Emissão do Atestado:", value="12 de Agosto de 2026")

# 2. Função para ler o PDF enviado
def extrair_dados_pdf(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    texto = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    
    dados = {}
    
    # Identifica o cliente pelo CNPJ no texto
    if "03.612.122/0001-27" in texto or "SESC" in texto.upper():
        dados['cliente_nome'] = "SERVIÇO SOCIAL DO COMERCIO SESC AR/CE"
        dados['cliente_cnpj'] = "03.612.122/0001-27"
        dados['tag_cliente'] = "SESC"
    else:
        dados['cliente_nome'] = "SERVIÇO NACIONAL DE APRENDIZAGEM COMERCIAL SENAC AR/CE"
        dados['cliente_cnpj'] = "03.648.344/0001-08"
        dados['tag_cliente'] = "SENAC"
        
    # Extrai o número da Planilha AP ou da OC limpando os zeros à esquerda
    match_ap = re.search(r"Nº\s*PLANILHA:\s*0*(\d+)", texto, re.IGNORECASE)
    match_oc = re.search(r"OC\s*0*(\d+)", texto, re.IGNORECASE)
    
    dados['planilha_num'] = match_ap.group(1) if match_ap else (match_oc.group(1) if match_oc else "N/A")
    
    # Extrai a campanha
    match_campanha = re.search(r"CAMPANHA:\s*([^\n]+)", texto, re.IGNORECASE)
    dados['campanha'] = match_campanha.group(1).strip() if match_campanha else "MÍDIAS INSTITUCIONAIS"
    
    return dados

# 3. Botão para acionar a geração do PDF
if st.button("🚀 Gerar Atestado", type="primary"):
    if not uploaded_file:
        st.error("Por favor, anexe o arquivo PDF da AP ou OC.")
    elif not num_id:
        st.error("Por favor, informe o número da PI ou PP.")
    else:
        dados = extrair_dados_pdf(uploaded_file)
        
        # Carrega a imagem da assinatura
        with open("luma_signature_perfect.png", "rb") as f:
            encoded_sig = base64.b64encode(f.read()).decode('utf-8')
            
        is_midia = (doc_type == "Mídia (AP)")
        titulo_doc = f"ATESTADO DE VEICULAÇÃO DE MÍDIA | {dados['tag_cliente']}" if is_midia else f"ATESTADO DE PRODUÇÃO – {dados['tag_cliente']}"
        
        col1_header = "PLANILHA AP Nº" if is_midia else "PP Nº"
        col2_header = "PI Nº" if is_midia else "OC Nº"
        col3_header = "PEÇA" if is_midia else "SERVIÇOS"
        
        # Layout em HTML/CSS para a WeasyPrint converter em PDF
        html_code = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
        <meta charset="UTF-8">
        <style>
          @page {{ size: A4 portrait; margin: 18mm 15mm 20mm 15mm; @bottom-center {{ content: element(footer); }} }}
          * {{ box-sizing: border-box; }}
          body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #222222; font-size: 10.5pt; line-height: 1.6; margin: 0; padding: 0; }}
          .header {{ display: table; width: 100%; margin-bottom: 30px; border-bottom: 2.5px solid #ffcc00; padding-bottom: 15px; }}
          .header-left {{ display: table-cell; vertical-align: middle; }}
          .header-right {{ display: table-cell; text-align: right; vertical-align: middle; }}
          .doc-title {{ font-size: 13pt; font-weight: 800; color: #111111; text-transform: uppercase; letter-spacing: 0.5px; }}
          .brand-logo {{ font-size: 20pt; font-weight: 900; line-height: 0.9; color: #111111; letter-spacing: -0.5px; }}
          .brand-dot {{ color: #ffcc00; }}
          .brand-sub {{ font-size: 7.5pt; font-weight: bold; color: #555555; letter-spacing: 3.5px; margin-top: 3px; text-transform: uppercase; }}
          .declaration-text {{ text-align: justify; margin-bottom: 25px; font-size: 10.5pt; line-height: 1.75; }}
          .highlight {{ font-weight: bold; color: #000000; }}
          table.data-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; margin-bottom: 30px; }}
          table.data-table th {{ background-color: #111111; color: #ffffff; font-size: 8.5pt; font-weight: bold; text-transform: uppercase; padding: 10px 8px; border: 1px solid #111111; text-align: center; }}
          table.data-table td {{ padding: 12px 10px; border: 1px solid #d1d5db; font-size: 9pt; text-align: center; vertical-align: middle; background-color: #fdfdfd; }}
          .date-section {{ margin-top: 35px; margin-bottom: 35px; font-size: 10.5pt; }}
          .signature-container {{ margin-top: 10px; width: 320px; }}
          .signature-img-wrap img {{ height: 52px; width: auto; display: block; }}
          .signature-line {{ border-top: 1.5px solid #111111; margin-top: 2px; margin-bottom: 8px; }}
          .signature-company {{ font-weight: 800; font-size: 8.5pt; color: #111111; text-transform: uppercase; }}
          .signature-name {{ font-weight: bold; font-size: 10.5pt; color: #111111; margin-top: 2px; }}
          .signature-title {{ font-size: 9pt; color: #444444; }}
          .footer-container {{ position: running(footer); width: 100%; border-top: 1px solid #e5e7eb; padding-top: 10px; font-size: 7.5pt; color: #555555; line-height: 1.45; }}
          .footer-cols {{ display: table; width: 100%; }}
          .footer-col {{ display: table-cell; width: 33.33%; vertical-align: top; }}
          .city-title {{ font-weight: bold; color: #111111; }}
          .footer-web {{ text-align: center; margin-top: 8px; border-top: 1px solid #f3f4f6; padding-top: 5px; font-weight: bold; color: #333333; }}
        </style>
        </head>
        <body>
        <div class="header">
          <div class="header-left"><div class="doc-title">{titulo_doc}</div></div>
          <div class="header-right">
            <div class="brand-logo">EBM<br>QUINTTO<span class="brand-dot">.</span></div>
            <div class="brand-sub">COMUNICAÇÃO</div>
          </div>
        </div>
        <div class="content">
          <p class="declaration-text">
            Atestamos para fins de comprovação de execução de serviço prestados para o cliente <span class="highlight">{dados['cliente_nome']}</span>, CNPJ <span class="highlight">{dados['cliente_cnpj']}</span>, intermediadas por essa agência de publicidade no período de acordo com as informações relacionadas abaixo.
          </p>
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 5%;">#</th>
                <th style="width: 22%;">{col1_header}</th>
                <th style="width: 18%;">{col2_header}</th>
                <th style="width: 30%;">{col3_header}</th>
                <th style="width: 25%;">CAMPANHA</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>1</td>
                <td>{dados['planilha_num']}</td>
                <td>{num_id}</td>
                <td>Serviço de Publicidade / Mídia Contratado</td>
                <td>{dados['campanha']}</td>
              </tr>
            </tbody>
          </table>
          <div class="date-section">Fortaleza/CE, {data_emissao}.</div>
          <div class="signature-container">
            <div class="signature-img-wrap"><img src="data:image/png;base64,{encoded_sig}"></div>
            <div class="signature-line"></div>
            <div class="signature-company">EBM QUINTTO COMUNICAÇÃO LTDA</div>
            <div class="signature-name">Luma Oliveira</div>
            <div class="signature-title">Analista Financeiro</div>
          </div>
        </div>
        <div class="footer-container" id="footer">
          <div class="footer-cols">
            <div class="footer-col"><span class="city-title">Fortaleza-CE</span><br>R. Beni Carvalho, 138<br>CEP: 60135-400 | +55 85 3253.5555</div>
            <div class="footer-col"><span class="city-title">Brasília-DF</span><br>Setor Comercial Norte, Q. 01 Bloco D, Conj. 119 - Vega Luxury Mall<br>CEP: 70711-948 | +55 61 3525-7988</div>
            <div class="footer-col"><span class="city-title">Bahia-BA</span><br>Al. Salvador, 1057, Sl. 1411 - Torre Europa, Caminho das Árvores<br>CEP: 41820-790 | +55 71 3825-3178</div>
          </div>
          <div class="footer-web">ebmquintto.com.br | @ebmquintto</div>
        </div>
        </body>
        </html>
        """
        
        pdf_bytes = HTML(string=html_code).write_pdf()
        
        st.success("✅ Atestado gerado com sucesso!")
        st.download_button(
            label="📥 Baixar Atestado em PDF",
            data=pdf_bytes,
            file_name=f"ATESTADO_{dados['tag_cliente']}_{num_id}.pdf",
            mime="application/pdf"
        )
