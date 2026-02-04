# i18n.py
TEXTS = {
    "english": {
        "title": "Welcome",
        "generate": "Generate Summary",
        "upload": "Upload File",
        "regenerate": "Regenerate Summary?",
        "chapters": "📚 Chapters",
        "video_error": "Video not found or private.",
        "no_captions": "No captions available for this video.",
        "no_transcription_info": "As for now the application doesn't support direct audio transcription from Youtube. However, you can upload the video file in the 'Upload file' tab if you have it.",
        "send_file": "Send a file for transcription",
        "context": "You can add additional context for the summary here",
        "lang_info": "Summary will be generated in the language set while pressing the 'Generate Summary' button. You can always regenerate it in another language.",
        "loading": "Generoating summary, please wait..."
    },
    "polish": {
        "title": "Witamy",
        "generate": "Wygeneruj podsumowanie",
        "upload": "Prześlij plik",
        "regenerate": "Wygenerować podsumowanie ponownie?",
        "chapters": "📚 Rozdziały",
        "video_error": "Wideo nie znalezione lub prywatne.",
        "no_captions": "Brak dostępnych napisów dla tego wideo.",
        "no_transcription_info": "Obecnie aplikacja nie obsługuje bezpośredniej transkrypcji audio z YouTube. Możesz jednak przesłać plik wideo w zakładce 'Prześlij plik', jeśli go posiadasz.",
        "send_file": "Prześlij plik do transkrypcji",
        "context": "Możesz dodać dodatkowy kontekst do podsumowania tutaj",
        "lang_info": "Podsumowanie zostanie wygenerowane w języku ustawionym podczas naciskania przycisku 'Wygeneruj podsumowanie'. Zawsze możesz wygenerować je ponownie w innym języku.",
        "loading": "Generowanie podsumowania, proszę czekać..."
    },
}

def t(key: str, lang: str):
    return TEXTS[lang].get(key, key)
