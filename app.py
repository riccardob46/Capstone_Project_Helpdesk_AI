"""HelpDesk AI: l'interfaccia web del chatbot.

    streamlit run app.py

Streamlit riesegue questo file dall'inizio a ogni azione dell'utente (un messaggio, un clic). Per questo:
- il client OpenAI e l'indice si creano una volta sola per tutto il server (st.cache_resource);
- la conversazione di ogni utente vive in st.session_state, che resta tra una riesecuzione e l'altra;
- la logica è tutta in src/conversazione.py: qui mostriamo solo quello che restituisce l'Assistente,
  come fa terminale.py, con i pulsanti al posto degli elenchi numerati.

Prima di avviarla chiudere i kernel dei notebook e terminale.py: ChromaDB va aperto da un processo alla volta.
"""
import logging

import streamlit as st

from src.conversazione import Assistente
from src.llm import costo_dollari, crea_client
from src.prompt import DISPOSITIVI
from src.ricerca import apri_collezione

st.set_page_config(page_title="HelpDesk AI", page_icon="🛠️")

BENVENUTO = ("Ciao! Sono l'assistente IT di primo livello. Descrivimi il problema: se i manuali del dispositivo "
             "contengono la soluzione ti guido passo passo, altrimenti apro un ticket per il supporto tecnico.")
ERRORE = ("Mi dispiace, c'è stato un problema tecnico e non sono riuscito a completare l'operazione. "
          "Riprova tra qualche istante.")
# Per ogni domanda con pulsanti, il metodo dell'Assistente da chiamare con la scelta (come in terminale.py)
AZIONE_PER_DOMANDA = {
    "domanda_dispositivo": "scegli_dispositivo",
    "domanda_marca": "scegli_marca",
    "istruzioni": "esito_istruzioni",
}


# --- Risorse condivise e stato dell'utente -----------------------------------------------------------

@st.cache_resource(show_spinner="Avvio dell'assistente...")
def risorse():
    """Client e indice: uno solo per tutto il server, non uno per utente né uno per clic."""
    return crea_client(), apri_collezione()


def assistente():
    """L'Assistente di questo utente: creato alla prima visita poi conservato in st.session_state."""
    if "assistente" not in st.session_state:
        client, collezione = risorse()
        st.session_state.assistente = Assistente(client=client, collezione=collezione)
        st.session_state.storia = []      # cosa mostrare: dizionari con ruolo, testo ed eventuale Passo
    return st.session_state.assistente


# --- Come si mostrano messaggi, fonti, pulsanti e ticket --------------------------------------------

def md(testo):
    """Streamlit interpreta il testo tra due $ come una formula matematica: lo evitiamo."""
    return testo.replace("$", "\\$")


def etichetta(opzione):
    """Il testo del pulsante: "stampante di rete" diventa "Stampante di rete", "POS" resta "POS"."""
    return opzione[:1].upper() + opzione[1:]


def collegamento(e):
    """Il link a una fonte. Per i PDF aggiungiamo #page=N: molti browser aprono il file a quella pagina."""
    testo = f"{e.editore} – {e.titolo} ({e.dove})".replace("[", "(").replace("]", ")")
    if not e.url:
        return testo
    url = f"{e.url}#page={e.pagina}" if e.pagina and ".pdf" in e.url.lower() else e.url
    return f"[{testo}]({url})"


def mostra_fonti(fonti):
    """Le fonti citate. Pezzi diversi della stessa pagina diventano una riga sola: [1, 2, 3] Nexi – ... (pagina 7)."""
    gruppi = {}
    for numero, e in fonti:
        gruppi.setdefault((e.editore, e.titolo, e.dove), (e, []))[1].append(numero)
    righe = [f"- \\[{', '.join(map(str, numeri))}\\] {collegamento(e)}" for e, numeri in gruppi.values()]
    st.markdown("**Fonti**\n\n" + "\n".join(righe))


def mostra_ticket(t):
    """Il ticket in un riquadro. Gli estratti restano numerati uno per uno: le note tecniche li citano così."""
    with st.container(border=True):
        st.markdown(f"**🎫 Ticket per il supporto tecnico: {md(t.titolo)}**")
        st.markdown(f"**Dispositivo:** {t.dispositivo} · **Categoria:** {t.categoria}")
        st.markdown(md(t.descrizione))
        if t.note_tecniche:
            st.markdown(f"**Note tecniche:** {md(t.note_tecniche)}")
        if t.estratti:
            with st.expander(f"Documentazione allegata ({len(t.estratti)} estratti)"):
                st.markdown("\n".join(f"{n}. {collegamento(e)}" for n, e in enumerate(t.estratti, start=1)))
        st.caption("Nel prototipo il ticket viene solo mostrato: in produzione andrebbe inviato al sistema di ticketing.")


def pulsanti(opzioni, indice):
    """I pulsanti, tre per riga. Restituisce l'opzione se l'utente ne ha appena premuto uno, altrimenti None.

    Creiamo un gruppo di colonne per ogni riga: sul telefono le colonne finiscono una sotto l'altra, e con un
    gruppo solo l'ordine diventerebbe "per colonna" (Computer, Stampante di etichette, Monitor, ...).
    """
    scelta = None
    for inizio in range(0, len(opzioni), 3):
        for colonna, opzione in zip(st.columns(3), opzioni[inizio:inizio + 3]):
            # La chiave contiene la posizione del messaggio: i pulsanti di un messaggio vecchio non si confondono con i nuovi
            if colonna.button(etichetta(opzione), key=f"{indice}-{opzione}"):
                scelta = opzione
    return scelta


def esegui(testo_utente, azione):
    """Mostra il messaggio dell'utente, chiama l'Assistente con un messaggio di attesa e ricarica la pagina."""
    storia = st.session_state.storia
    storia.append({"ruolo": "user", "testo": testo_utente})
    with st.chat_message("user"):
        st.markdown(md(testo_utente))
    with st.chat_message("assistant"):
        with st.spinner("Sto analizzando la richiesta e cercando nei manuali..."):
            try:
                passo = azione()
                storia.append({"ruolo": "assistant", "testo": passo.messaggio, "passo": passo})
            except Exception:
                logging.exception("Errore durante la conversazione")    # i dettagli nel terminale, non all'utente
                storia.append({"ruolo": "assistant", "testo": ERRORE})
    st.rerun()        # riesegue il file: la pagina viene ridisegnata con il nuovo messaggio e i nuovi pulsanti


# --- La pagina -------------------------------------------------------------------------------------

st.warning("Non scrivere password, PIN o dati dei clienti.", icon="🔒")
st.title("🛠️ HelpDesk AI")
st.caption("Prototipo di assistente IT di primo livello: le istruzioni vengono dai manuali pubblici dei dispositivi.")

try:
    a = assistente()
except RuntimeError as errore:            # manca la chiave in .env o manca l'indice: l'app non può partire
    st.error(str(errore))
    st.stop()
storia = st.session_state.storia

with st.sidebar:
    st.markdown("**Dispositivi che conosco**")
    st.markdown("\n".join(f"- {etichetta(d)}" for d in DISPOSITIVI))
    if st.button("Nuova conversazione"):
        a.reset()
        st.session_state.storia = []
        st.rerun()
    with st.expander("Dettagli tecnici"):
        if a.consumo:
            st.markdown(f"{len(a.consumo)} chiamate all'LLM · {sum(u.secondi for u in a.consumo):.1f} s · "
                        f"circa {costo_dollari(a.consumo):.5f} dollari")
            st.dataframe([{"compito": u.compito, "secondi": u.secondi, "token in": u.token_ingresso,
                           "token out": u.token_uscita} for u in a.consumo], hide_index=True)
        else:
            st.caption("Nessuna chiamata all'LLM nella conversazione in corso.")

with st.chat_message("assistant"):
    st.markdown(BENVENUTO)

scelta = None
for i, voce in enumerate(storia):
    if voce["ruolo"] == "separatore":
        st.divider()
        continue
    with st.chat_message(voce["ruolo"]):
        st.markdown(md(voce["testo"]))
        passo = voce.get("passo")
        if passo is not None:
            if passo.fonti:
                mostra_fonti(passo.fonti)
            if passo.ticket:
                mostra_ticket(passo.ticket)
            if passo.opzioni and i == len(storia) - 1:          # pulsanti solo sotto l'ultimo messaggio
                if passo.tipo == "istruzioni":
                    st.caption("Dopo aver provato i passi, fammi sapere com'è andata:")
                scelta = pulsanti(passo.opzioni, i)

segnaposto = {
    "attesa_dettagli": "Rispondi alla domanda dell'assistente",
    "attesa_dispositivo": "Scegli una delle opzioni, oppure descrivi un nuovo problema",
    "attesa_marca": "Scegli una delle opzioni, oppure descrivi un nuovo problema",
    "attesa_esito": "Scegli una delle opzioni, oppure descrivi un nuovo problema",
}.get(a.stato, "Descrivi il problema, per esempio: il POS non legge la carta")
testo = st.chat_input(segnaposto)

if scelta is not None:
    metodo = getattr(a, AZIONE_PER_DOMANDA[storia[-1]["passo"].tipo])
    esegui(etichetta(scelta), lambda: metodo(scelta))
elif testo:
    if a.stato == "attesa_dettagli":
        esegui(testo, lambda: a.aggiungi_dettagli(testo))
    else:
        if storia:                                             # una nuova richiesta: una riga la separa dalla precedente
            storia.append({"ruolo": "separatore"})
        esegui(testo, lambda: a.nuova_richiesta(testo))