import streamlit as st
import google.generativeai as genai
import os
import glob
from gtts import gTTS
import tempfile
import re

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Tuteur DIP", page_icon="⚖️")
st.title("⚖️ Droit administratif")
st.html("<p style='text-align: center; font: italic 1.5em Arial, sans-serif;'>par A. Coulibaly</p>")

# --- RÉCUPÉRATION DE LA CLÉ API ---
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
else:
    st.error("Clé API non configurée.")
    st.stop()

# --- PROMPT SYSTÈME (VERSION CORRIGÉE QUIZ) ---
SYSTEM_PROMPT = """
CONTEXTE : Tu es **Ada**, l'assistante pédagogique virtuelle experte en Droit administratif du Professeur Coulibaly..
BASE DE CONNAISSANCES : Strictement limitée aux fichiers PDF fournis ("le cours").

RÈGLES ABSOLUES :
1. IDENTITÉ : Si l'utilisateur demande ton nom ou qui tu es, réponds EXACTEMENT : "Je suis Ada, l'assistante pédagogique virtuelle du Professeur Coulibaly, spécialisée enDroit administratif. Le professeur Coulibaly m’a donné ce nom, en hommage à Ada Lovelace, la femme qui a conçu et décrit, au 19e siècle, le premier programme informatique."
2. IDENTITÉ : Si l'utilisateur demande qui est le professeur Coulibaly ou qui est M. Coulibaly, réponds EXACTEMENT : "Le professeur Coulibaly est professeur agrégé de droit public. Il est en poste à l’Université Toulouse Capitole. Il est l’auteur du cours sur lequel sont basées mes questions et mes réponses."
3. SOURCE UNIQUE : Tes réponses doivent provenir EXCLUSIVEMENT du cours fourni. N'utilise jamais tes connaissances externes pour combler un vide.
4. HONNÊTETÉ : Si la réponse n'est pas dans le cours, dis : "Cette précision ne figure pas dans le cours du Professeur Coulibaly." Ne tente pas d'inventer.
5. PRÉCISION : Cite toujours les arrêts tels qu'ils apparaissent dans le document.

RÈGLES PÉDAGOGIQUES :
1. Si l'étudiant pose une question : Réponds en te basant EXCLUSIVEMENT sur le cours. Cite les arrêts et les pages.
2. Si l'étudiant demande un QUIZ ou une COLLE : 
   - Identifie un point précis du cours (ex: les critères d'un arrêt).
   - Pose une question ouverte (ex: "Quels sont les critères de...") plutôt que de donner un nombre arbitraire ("Quels sont les 2 critères..."), sauf si le cours précise explicitement ce nombre.
   - NE DONNE PAS la réponse tout de suite. Attends que l'étudiant essaie de répondre.
   - Une fois que l'étudiant a répondu, corrige-le avec bienveillance. Si sa réponse est incomplète, guide-le vers l'élément manquant.

TON : Professionnel, encourageant, clair. Phrases courtes.
"""

# --- FONCTION CHARGEMENT PDF ---
@st.cache_resource
def load_and_process_pdfs():
    pdf_files = glob.glob("*.pdf")
    if not pdf_files:
        return None
    
    uploaded_refs = []
    status = st.empty()
    status.text(f"Chargement de {len(pdf_files)} fichiers de cours...")
    
    try:
        for pdf in pdf_files:
            uploaded_file = genai.upload_file(pdf, mime_type="application/pdf")
            uploaded_refs.append(uploaded_file)
        status.empty()
        return uploaded_refs
    except:
        return None

# --- INITIALISATION SESSION ---
if "chat_session" not in st.session_state:
    docs = load_and_process_pdfs()
    if docs:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite", # Le modèle rapide
            system_instruction=SYSTEM_PROMPT
        )
        st.session_state.chat_session = model.start_chat(
            history=[
                {"role": "user", "parts": docs},
                {"role": "model", "parts": ["Je suis prêt."]}
            ]
        )
        st.session_state.messages = []
    else:
        st.warning("Veuillez ajouter des PDF sur GitHub.")

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.header("⚙️ Options")
    audio_active = st.toggle("🔊 Activer la voix", value=False)
    
    st.divider()
    st.header("🎓 Entraînement")
    
    # BOUTON QUIZ : C'est ici que la magie opère
    if st.button("🃏 Pose-moi une colle !"):
        if "chat_session" in st.session_state and st.session_state.chat_session:
            # On envoie une instruction cachée à l'IA
            prompt_quiz = "Pose-moi une question de vérification de connaissances sur un point aléatoire du cours. Ne donne pas la réponse."
            
            # On traite la réponse comme un message normal
            with st.spinner("Le Professeur cherche une question..."):
                response = st.session_state.chat_session.send_message(prompt_quiz)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                # On force le rechargement pour afficher la question tout de suite
                st.rerun()

# --- AFFICHAGE DU CHAT ---
if "messages" in st.session_state:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# --- ZONE DE SAISIE ---
if prompt := st.chat_input("Votre réponse ou votre question..."):
    # 1. Affiche le message utilisateur
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Réponse de l'IA
    if "chat_session" in st.session_state:
        with st.chat_message("assistant"):
            with st.spinner("Réflexion..."):
                try:
                    response = st.session_state.chat_session.send_message(prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})

                    # Audio optionnel
                    if audio_active:
                        clean_text = re.sub(r'[\*#]', '', response.text)
                        clean_text = re.sub(r'p\.\s*(\d+)', r'page \1', clean_text)
                        clean_text = clean_text.replace("Pr.", "Professeur")
                        
                        tts = gTTS(text=clean_text, lang='fr')
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                            tts.save(fp.name)
                            st.audio(fp.name, format="audio/mp3")
                            
                except Exception as e:
                    st.error(f"Erreur : {e}")
