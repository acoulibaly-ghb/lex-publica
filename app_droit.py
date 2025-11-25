import streamlit as st
import google.generativeai as genai
import os
import glob
from gtts import gTTS
import tempfile
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="Tuteur Droit Admin", page_icon="⚖️")
st.title("⚖️ Assistant Droit Administratif")

# --- RÉCUPÉRATION DE LA CLÉ API SECRÈTE ---
api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=api_key)

# --- PROMPT SYSTÈME ---
SYSTEM_PROMPT = """
CONTEXTE ET RÔLE :
Tu es l'assistant pédagogique virtuel expert en Droit Administratif du Professeur Coulibaly.
Ta base de connaissances est STRICTEMENT limitée aux documents fournis en contexte ("le cours du professeur Coulibaly").

RÈGLES ABSOLUES :
1. SOURCE UNIQUE : Tes réponses doivent provenir EXCLUSIVEMENT du cours fourni. N'utilise jamais tes connaissances externes pour combler un vide.
2. HONNÊTETÉ : Si la réponse n'est pas dans le cours, dis : "Cette précision ne figure pas dans le cours du Pr. Coulibaly." Ne tente pas d'inventer.
3. PRÉCISION : Cite toujours les arrêts (ex: **CE, 1933, Benjamin**) tels qu'ils apparaissent dans le document.

STYLE ET FORMAT :
- Ton : Professionnel, pédagogique, encourageant.
- Oralité : Fais des phrases courtes et claires.
- Structure : Utilise des titres, des listes à puces et du gras pour les mots-clés.
"""

# --- FONCTION DE CHARGEMENT DES COURS ---
@st.cache_resource
def load_and_process_pdfs():
    """Charge tous les PDF du dossier et les envoie à Gemini une seule fois."""
    pdf_files = glob.glob("*.pdf")
    
    if not pdf_files:
        st.error("Aucun fichier PDF trouvé dans le dossier !")
        return None

    uploaded_files_refs = []
    status_text = st.empty()
    status_text.text(f"Chargement de {len(pdf_files)} chapitres de cours...")

    for pdf in pdf_files:
        uploaded_file = genai.upload_file(pdf, mime_type="application/pdf")
        uploaded_files_refs.append(uploaded_file)
    
    status_text.empty()
    return uploaded_files_refs

# --- DÉMARRAGE DE LA SESSION ---
if "chat_session" not in st.session_state:
    try:
        docs = load_and_process_pdfs()
        
        if docs:
            # Note : On utilise bien gemini-2.5-flash ici
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=SYSTEM_PROMPT
            )
            st.session_state.chat_session = model.start_chat(
                history=[
                    {"role": "user", "parts": docs},
                    {"role": "model", "parts": ["Bien reçu. Je suis prêt."]}
                ]
            )
            st.session_state.messages = []
            st.success("✅ Le cours est chargé. Posez votre question !")
            
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")

# --- INTERFACE DE CHAT ---
if "messages" in st.session_state:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Zone de saisie
if prompt := st.chat_input("Votre question sur le cours..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Réponse IA + Audio
    if st.session_state.chat_session:
        with st.chat_message("assistant"):
            with st.spinner("Recherche et synthèse vocale..."):
                # 1. Texte
                response = st.session_state.chat_session.send_message(prompt)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                
                # 2. Audio
                try:
                    # --- NETTOYAGE ---
                    # Enlever * et #
                    text_for_audio = re.sub(r'[\*#]', '', response.text)
                    # Remplacer p. 12 par page 12
                    text_for_audio = re.sub(r'p\.\s*(\d+)', r'page \1', text_for_audio)
                    # Remplacer Pr. par Professeur
                    text_for_audio = text_for_audio.replace("Pr.", "Professeur")
                    
                    # Génération
                    tts = gTTS(text=text_for_audio, lang='fr')
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                        tts.save(fp.name)
                        audio_path = fp.name
                    
                    st.audio(audio_path, format="audio/mp3")
                    
                except Exception as e:
                    st.warning(f"Note : Audio non disponible ({e})")
