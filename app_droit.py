import streamlit as st
import google.generativeai as genai
import os
import glob
from gtts import gTTS
import tempfile
import re

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Lex Publica", page_icon="⚖️")
st.title("⚖️ Lex Publica | Assistant Juridique")

# --- RÉCUPÉRATION DE LA CLÉ API ---
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
else:
    st.error("Clé API non configurée.")
    st.stop()

# --- PROMPT SYSTÈME ---
SYSTEM_PROMPT = """
CONTEXTE : Tu es l'assistant pédagogique expert du Professeur Coulibaly.
BASE DE CONNAISSANCES : Strictement limitée aux fichiers PDF fournis ("le cours").

RÈGLES PÉDAGOGIQUES :
1. Si l'étudiant pose une question (texte ou audio) : Réponds en te basant EXCLUSIVEMENT sur le cours. Cite les arrêts et les pages.
2. Si l'étudiant demande un QUIZ ou une COLLE : 
   - Identifie un point précis du cours.
   - Pose une question ouverte.
   - NE DONNE PAS la réponse tout de suite. Attends que l'étudiant essaie de répondre.
   - Corrige avec bienveillance.

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
            model_name="gemini-2.5-flash-lite", 
            system_instruction=SYSTEM_PROMPT
        )
        # On stocke les docs dans la session pour pouvoir les réutiliser avec l'audio
        st.session_state.docs_refs = docs
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
    audio_active = st.toggle("🔊 Activer la réponse vocale", value=False)
    
    st.divider()
    st.header("🎓 Entraînement")
    
    if st.button("🃏 Pose-moi une colle !"):
        if "chat_session" in st.session_state:
            prompt_quiz = "Pose-moi une question de vérification sur le cours. Ne donne pas la réponse."
            with st.spinner("Le Professeur cherche une question..."):
                response = st.session_state.chat_session.send_message(prompt_quiz)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()

# --- AFFICHAGE DU CHAT ---
if "messages" in st.session_state:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# --- GESTION DOUBLE ENTRÉE (VOCALE OU TEXTE) ---

# 1. Le Widget Micro (Nouveauté Streamlit)
audio_input = st.audio_input("🎙️ Posez votre question vocalement")

# 2. La zone de texte classique
text_input = st.chat_input("... ou écrivez votre question ici")

user_input = None
is_audio_message = False

# Logique de priorité : Si on parle, ça prend le pas sur l'écrit
if audio_input:
    user_input = audio_input
    is_audio_message = True
elif text_input:
    user_input = text_input
    is_audio_message = False

# --- TRAITEMENT DE LA QUESTION ---
if user_input:
    # A. Affichage coté étudiant
    if is_audio_message:
        # On affiche un petit lecteur pour qu'il réécoute sa question
        with st.chat_message("user"):
            st.audio(user_input)
            st.caption("🎤 Question vocale envoyée")
        st.session_state.messages.append({"role": "user", "content": "🎤 *[Question Vocale]*"})
    else:
        # On affiche le texte
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

    # B. Envoi à l'IA
    if "chat_session" in st.session_state:
        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours..."):
                try:
                    if is_audio_message:
                        # MAGIE : On envoie le fichier audio directement à Gemini !
                        # Il faut sauvegarder le fichier audio temporairement
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio:
                            tmp_audio.write(user_input.getvalue())
                            tmp_audio_path = tmp_audio.name
                        
                        # On l'envoie à Google
                        uploaded_audio = genai.upload_file(tmp_audio_path, mime_type="audio/wav")
                        
                        # On demande à l'IA d'écouter et de répondre
                        response = st.session_state.chat_session.send_message(
                            ["Écoute cette question de l'étudiant et réponds-y en te basant sur le cours.", uploaded_audio]
                        )
                    else:
                        # Cas classique texte
                        response = st.session_state.chat_session.send_message(user_input)

                    # Affichage réponse
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})

                    # Lecture Audio de la réponse (si option activée)
                    if audio_active:
                        clean_text = re.sub(r'[\*#]', '', response.text)
                        clean_text = re.sub(r'p\.\s*(\d+)', r'page \1', clean_text)
                        clean_text = clean_text.replace("Pr.", "Professeur")
                        
                        tts = gTTS(text=clean_text, lang='fr')
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                            tts.save(fp.name)
                            st.audio(fp.name, format="audio/mp3")
                            
                except Exception as e:
                    st.error(f"Une erreur est survenue : {e}")
