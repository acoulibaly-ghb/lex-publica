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
1. Si l'étudiant pose une question (texte ou audio) : Réponds en te basant EXCLUSIVEMENT sur le cours.
2. Si la question est AUDIO : Commence TOUJOURS ta réponse par une transcription de ce que tu as entendu. 
   Exemple : "Vous avez demandé : 'Quelle est la définition du service public ?'. Voici la réponse : ..."
3. Si l'étudiant demande un QUIZ : Pose une question ouverte sur un point précis. Attends la réponse.

TON : Professionnel, encourageant, clair. Phrases courtes.
"""

# --- FONCTION CHARGEMENT PDF ---
@st.cache_resource
def load_and_process_pdfs():
    pdf_files = glob.glob("*.pdf")
    if not pdf_files:
        return None
    
    uploaded_refs = []
    # On utilise un conteneur vide pour le chargement pour qu'il disparaisse après
    placeholder = st.empty()
    placeholder.text(f"Chargement de {len(pdf_files)} fichiers de cours...")
    
    try:
        for pdf in pdf_files:
            uploaded_file = genai.upload_file(pdf, mime_type="application/pdf")
            uploaded_refs.append(uploaded_file)
        placeholder.empty() # Hop, on efface le message de chargement
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
    audio_active = st.toggle("🔊 Activer la réponse vocale de l'IA", value=False)
    
    st.divider()
    st.header("🎓 Entraînement")
    
    if st.button("🃏 Pose-moi une colle !"):
        if "chat_session" in st.session_state:
            prompt_quiz = "Pose-moi une question de vérification sur le cours. Ne donne pas la réponse."
            with st.spinner("Recherche d'une question..."):
                response = st.session_state.chat_session.send_message(prompt_quiz)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()

# --- AFFICHAGE DU CHAT ---
if "messages" in st.session_state:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            # Si le message vient de l'utilisateur et contient l'indicateur spécial
            if message["role"] == "user" and message["content"] == "🎤 *[Question Vocale envoyée]*":
                st.markdown("🎤 *Question Vocale envoyée*")
            else:
                st.markdown(message["content"])

# --- ZONES DE SAISIE ---
# On met le micro et le texte l'un au-dessus de l'autre
audio_input = st.audio_input("🎙️ Posez votre question vocalement")
text_input = st.chat_input("... ou écrivez votre question ici")

user_input = None
is_audio_message = False

if audio_input:
    user_input = audio_input
    is_audio_message = True
elif text_input:
    user_input = text_input
    is_audio_message = False

# --- TRAITEMENT ---
if user_input:
    # 1. On affiche un message PROPRE coté étudiant (plus de lecteur audio moche)
    if is_audio_message:
        st.session_state.messages.append({"role": "user", "content": "🎤 *[Question Vocale envoyée]*"})
        with st.chat_message("user"):
            st.markdown("🎤 *Question Vocale envoyée*")
    else:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

    # 2. Envoi à l'IA
    if "chat_session" in st.session_state:
        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours..."):
                try:
                    if is_audio_message:
                        # Gestion Audio
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio:
                            tmp_audio.write(user_input.getvalue())
                            tmp_path = tmp_audio.name
                        
                        uploaded_audio = genai.upload_file(tmp_path, mime_type="audio/wav")
                        
                        # Consigne spécifique pour forcer la transcription
                        instruction = "Écoute l'audio. Commence ta réponse par : 'Vous avez demandé : [Texte de la question]'. Puis réponds avec le cours."
                        
                        response = st.session_state.chat_session.send_message([instruction, uploaded_audio])
                    else:
                        # Gestion Texte
                        response = st.session_state.chat_session.send_message(user_input)

                    # Affichage
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})

                    # Audio IA (si activé)
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
