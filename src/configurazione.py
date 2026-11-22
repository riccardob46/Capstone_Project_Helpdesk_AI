"""Percorsi, modelli e parametri dell'app.
I valori vengono dalle scelte dei notebook (06: ricerca, 07: LLM). Li scriviamo qui come costanti e non li leggiamo dai file in models/ per due motivi: la cartella models/ è esclusa da Git mentre queste scelte devono essere versionate ed ogni valore ha accanto il commento che dice da dove viene.
"""
from pathlib import Path

# --- Percorsi (relativi alla cartella del progetto, qualunque sia la cartella da cui si avvia l'app) ---
PROJECT_DIR = Path(__file__).resolve().parent.parent
KB_DIR = PROJECT_DIR / "knowledge_base"
CHROMA_DIR = KB_DIR / "chroma"
ENV_PATH = PROJECT_DIR / ".env"

# --- Ricerca (notebook 06, sezione 10) ---
MODELLO_EMBEDDINGS = "text-embedding-3-small"
COLLEZIONE = "kb_intestazione"      # testo dei chunk con l'intestazione (editore, titolo, dispositivo, sezione)
K = 5                               # estratti passati all'LLM

# --- LLM (notebook 07, sezioni 1 e 12) ---
MODELLO_LLM = "gpt-6-luna"
SFORZO = {                          # sforzo di ragionamento per compito
    "analisi": "none",
    "hyde": "none",
    "risposta": "low",
    "ticket": "none",
}
USA_HYDE = True                     # ricerca con traduzione + passaggio ipotetico (versione T+H, notebook 07 sezione 7)
MAX_OUTPUT_TOKENS = 8000
# Dollari per milione di token (ingresso, uscita) dal listino usato nel notebook 07 sezione 11: da ricontrollare se il listino cambia. Ignoriamo lo sconto sui token in cache quindi la stima è per eccesso.
PREZZI = {"gpt-6-luna": (0.10, 0.50)}

# --- Conversazione ---
MAX_DOMANDE_DETTAGLI = 1            # dopo una domanda sui dettagli, se serve ancora qualcosa si apre il ticket

# --- Dispositivi: nome nell'indice -> nome in inglese per la ricerca (notebook 06) ---
DISPOSITIVO_IN_INGLESE = {
    "computer": "Windows computer",
    "POS": "POS payment terminal (card reader)",
    "pad di firma": "electronic signature pad",
    "stampante di sportello": "counter passbook and document printer",
    "stampante di rete": "network multifunction printer",
    "stampante di etichette": "label printer",
    "monitor": "computer monitor (display)",
    "selezionatrice di banconote": "banknote counter (currency scanner)",
}

# --- Marche della stampante di rete: devono coincidere con il campo "editore" dell'indice ---
MARCHE_STAMPANTE_RETE = ["Kyocera", "Epson", "Lexmark"]