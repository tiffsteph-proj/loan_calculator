
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import time
from datetime import datetime, date
from ml_logic.loan_analysis_txEsforco import loan_analysis, LoanAnalysisError
from ml_logic.euribor import output_euriborRate
from ml_logic.user_input import calculate_age

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TXFIXA = float(os.getenv("TXFIXA"))
SPREAD1 = float(os.getenv("SPREAD1"))
SPREAD2 = float(os.getenv("SPREAD2"))
SPREAD3 = float(os.getenv("SPREAD3"))


# --- Streamlit Page Setup ---
st.set_page_config(
    page_title="Simulador Crédito Bancário",
    page_icon=":classical_building:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CSS Style ---
st.markdown("""
<style>
    .title-container {
        background-color: #E88E82;
        padding: 0.9rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    .section-title {
        border-bottom: 2px solid #0077b6;
        padding-bottom: 0.5rem;
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
    }

    .subtitle {
        margin-bottom: 0.1rem;
        padding-bottom: 0.1rem;
    }

    .footer {
        text-align: center;
        margin-top: 3rem;
        color: #6c757d;
        font-size: 0.8rem;
    }

</style>
""", unsafe_allow_html=True)


# --- Title and Introduction ---
st.markdown('<div class="title-container"><h1>Simulador de Crédito Bancário</h1></div>', unsafe_allow_html=True)

st.markdown("""
## Preencha os dados e carregue os documentos para simular a viabilidade do empréstimo.

#### **Instruções e Notas Importante :**
- Esta ferramenta serve apenas para simulação.
- Os termos e condições serão fornecidos por cada entidade bancária.
- 6 campos de preenchimento obrigatório. A etapa 4 estará disponível após o preenchimento da data de nascimento.
- 2 documentos obrigatórios para a simulação. Só o formato PDF é aceite.
    - IRS = Comprovativo de Entrega da Declaração Modelo 3 de IRS fornecido no Portal das Finanças.
    - Mapa CRC = Central de Responsabilidades de Crédito fornecido pelo Banco de Portugal.
- Todos os dados fornecidos e carregados **NÃO** são guardados em nenhuma base de dados. **TODOS OS DOCUMENTOS SERÃO APAGADOS APÓS CADA ANÁLISE**.
""")
st.markdown('</div>', unsafe_allow_html=True)


# --- Sidebar Inputs ---
st.markdown("""
    <style>
    /* Target all paragraphs inside sidebar (including st.sidebar.write) */
    section[data-testid="stSidebar"] p {
        font-size: 14px !important;
        line-height: 1.3;
        padding: 0.2px;
        margin:0.5px;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("""
    <style>
    section[data-testid="stSidebar"] {
        background-color: #EDC88C;
    }
    </style>
    """, unsafe_allow_html=True)

# Loan
st.sidebar.header("Dados do Empréstimo")
loan_amount = st.sidebar.number_input(f"**Etapa 1**: Valor do Empréstimo Pretendido (€)", min_value=0, step=1000)


# Collect birthdate(s) and marital status
marital_status = st.sidebar.radio(f"**Etapa 2**: Estado Civil", ["solteiro", "casado"])

if marital_status == "casado":
    birthdate1 = st.sidebar.text_input("Data de Nascimento Suj A (DD/MM/YYYY)")
    birthdate2 = st.sidebar.text_input("Data de Nascimento Suj B (DD/MM/YYYY)")
    birthdates = (birthdate1, birthdate2)

    # Only call if both birthdates are non-empty
    if birthdate1 and birthdate2:
        max_years = calculate_age(birthdates, marital_status)
    else:
        max_years = None

else:
    birthdate = st.sidebar.text_input(f"**Etapa 3**: Data de Nascimento (DD/MM/YYYY)")
    birthdates = birthdate

    # Only call if birthdate is non-empty
    if birthdate:
        max_years = calculate_age(birthdates, marital_status)
    else:
        max_years = None

loan_term = st.sidebar.write(f"**Etapa 4**: Prazo do Empréstimo pretendido")
if max_years is not None:
    loan_years = st.sidebar.slider(
        f"Escolha o prazo para o empréstimo ( min 5 a {int(max_years/12)} anos):",
        min_value=5, max_value=int(max_years/12), step=1
    )
    loan_term = loan_years*12

else:
    # No error shown initially; show only if inputs are filled but data invalid
    if (marital_status == "casado" and birthdate1 and birthdate2) or (marital_status == "solteiro" and birthdate):
        st.error("Empréstimo não concedido ou dados inválidos.")


# Rate
euribor_rate = output_euriborRate()
st.sidebar.write(f"**Taxa Fixa**: {TXFIXA*100:.2f}%")

for record in euribor_rate:
    euribor_3m = record.get('Euribor 3 meses', None)
    euribor_6m = record.get('Euribor 6 meses', None)
    euribor_12m = record.get('Euribor 12 meses', None)

    if euribor_3m is not None:
        st.sidebar.write(f"**Euribor 3 meses**: {euribor_3m * 100:.3f}%")
    if euribor_6m is not None:
        st.sidebar.write(f"**Euribor 6 meses**: {euribor_6m * 100:.3f}%")
    if euribor_12m is not None:
        st.sidebar.write(f"**Euribor 12 meses**: {euribor_12m * 100:.3f}%")

rate_type = st.sidebar.radio(f"**Etapa 5**: Taxa para análise", ("Euribor 3 meses", "Euribor 6 meses", "Euribor 12 meses", "Taxa Fixa"))

if rate_type == "Euribor 3 meses":
    base_rate = euribor_rate[0]['Euribor 3 meses']

elif rate_type == "Euribor 6 meses":
    base_rate = euribor_rate[0]['Euribor 6 meses']

elif rate_type == "Euribor 12 meses":
    base_rate = euribor_rate[0]['Euribor 12 meses']

else:
    base_rate = TXFIXA


# Spread
spread = st.sidebar.radio(f"**Etapa 6**: Escolha um possível spread para análise (ex: 0.006 -> 0.6%)", (SPREAD1, SPREAD2, SPREAD3))

# File uploads
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<h2 class="section-title">Documentação e Análise</h2>', unsafe_allow_html=True)

# 2 columns = 2 documents (IRS + Mapa CRC)
def progressbar():
    progress_bar = st.progress(0)
    for i in range(100):
        time.sleep(0.01)
        progress_bar.progress(i + 1)
    return None

col1, col2, col3, col4 = st.columns(4)
# === Column 1: IRS upload ===
with col1:
    st.markdown('<h3 class="subtitle">IRS</h3>', unsafe_allow_html=True)
    uploaded_IRS = st.file_uploader(" ", type=["pdf"])

# === Column 2: Mapa CRC upload ===
with col2:
    st.markdown('<h3 class="subtitle">Mapa CRC</h3>', unsafe_allow_html=True)
    uploaded_CRC = st.file_uploader("", type=["pdf"])

st.markdown('</div>', unsafe_allow_html=True)


# === Column 3: Button and Results ===
st.markdown("""
    <style>
    /* Reduce space at the top inside columns */
    div[data-testid="stColumn"] {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    div[data-testid="stFileUploader"] {
        margin-top: -2rem !important;
        padding-top: -2rem !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    /* Target the outer button wrapper */
    div.stButton > button {
        background-color: #AB3E03;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5em 1em;
        font-size: 16px;
        font-weight: bold;
    }
    div.stButton > button:hover {
        background-color: #802D04;
    }
    </style>
""", unsafe_allow_html=True)

with col3:
    st.markdown('<h3 class="subtitle">Análise</h3>', unsafe_allow_html=True)
    analisar = st.button(f"**Pedir Simulação**")

    if analisar:
        if not uploaded_IRS or not uploaded_CRC:
            st.error("☝️ Carregue ambos os documentos (IRS + Mapa CRC)")
        else:
            temp_irs = "temp_IRS.pdf"
            temp_crc = "temp_CRC.pdf"
            try:
                # Save uploaded files temporarily
                with open(temp_irs, "wb") as f:
                    f.write(uploaded_IRS.getvalue())
                with open(temp_crc, "wb") as f:
                    f.write(uploaded_CRC.getvalue())

                # Run loan analysis
                results = loan_analysis(
                    rate=base_rate,
                    spread=spread,
                    loan=loan_amount,
                    birthdate_str=birthdates,
                    marital_status=marital_status,
                    pdf_pathA=temp_irs,
                    pdf_pathB=temp_crc
                )

                st.write(f"**{results['Mensagem']}**")

                with st.spinner("Analyse em curso..."):
                    progress_bar = progressbar()
                    st.markdown("""
                                <style>
                                div[data-result="stMetric"] > div > div:first-child {
                                    font-size: 25px;
                                    font-weight: bold;
                                }
                                </style>
                                """, unsafe_allow_html=True)
                    st.metric("Taxa de Esforço", results["Taxa Esforco"])
                    st.metric("Mensalidade Prevista", f"{results['Mensalidade Prevista']:,.2f} €")
                    st.metric("Encargos Bancários", f"{results['Encargos bancários']:,.2f} €")
                    st.metric("Rendimento Mensal", f"{results['Rendimento Mensal']:,.2f} €")

                with col4:
                    st.markdown('<h3 class="subtitle">Detalhes</h3>', unsafe_allow_html=True)
                    with st.expander("Rendimentos"):
                        st.json(results["detalhes_rendimento"])
                    with st.expander("Empréstimo"):
                        st.json(results["detalhes_emprestimo"])

            except LoanAnalysisError as e:
                    st.error(f"Erro: {e}")
            except Exception as e:
                st.error(f"Erro inesperado: {e}")
            finally:
                # Delete temporary files
                for file in [temp_irs, temp_crc]:
                    if os.path.exists(file):
                        os.remove(file)


# footer
st.markdown('<div class="footer">', unsafe_allow_html=True)
st.markdown("""
© 2025 - Todos os direitos reservados. Desenvolvido por Stéphanie Santos
""")
st.markdown('</div>', unsafe_allow_html=True)
