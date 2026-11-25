"""L'interfaccia Streamlit provata senza browser con AppTest: esegue app.py come farebbe il server
e permette di scrivere nella chat e premere i pulsanti. Client e indice sono i sostituti dei test."""
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src import llm, ricerca

from .sostituti import ClientFinto, CollezioneFinta, analisi, hyde, risposta, ticket


class CollezioneStessaPagina(CollezioneFinta):
    """Tutti gli estratti dalla stessa pagina dello stesso manuale, come i [1], [2], [3] del POS Nexi."""

    def query(self, **parametri):
        risultato = super().query(**parametri)
        for m in risultato["metadatas"][0]:
            m.update(titolo="Guida POS", pagina=7, url="https://esempio.it/guida.pdf")
        return risultato


@pytest.fixture
def app(monkeypatch):
    """Prepara l'app con le risposte "dell'LLM" scelte dal test."""
    def prepara(*risposte, collezione=None):
        st.cache_resource.clear()               # le risorse create da un test non devono passare al successivo
        monkeypatch.setattr(llm, "crea_client", lambda: ClientFinto(risposte))
        monkeypatch.setattr(ricerca, "apri_collezione", lambda: collezione or CollezioneFinta())
        return AppTest.from_file("../app.py", default_timeout=10).run()
    return prepara


def premi(at, etichetta):
    [pulsante] = [b for b in at.button if b.label == etichetta]
    return pulsante.click().run()


def testi(at):
    return "\n".join(m.value for m in at.markdown)


def test_avvio(app):
    at = app()
    assert not at.exception
    assert "Sono l'assistente IT di primo livello" in testi(at)


def test_percorso_completo_con_pulsanti(app):
    at = app(analisi(dispositivo="non chiaro"), hyde(), risposta("istruzioni", fonti=[1, 2]), ticket())
    at.chat_input[0].set_value("La stampante non funziona").run()
    etichette = [b.label for b in at.button]
    assert "Stampante di sportello" in etichette and "Altro dispositivo" in etichette

    at = premi(at, "Stampante di sportello")
    assert "Messaggio con esito istruzioni" in testi(at)
    assert "Manuale 1" in testi(at) and "Manuale 2" in testi(at)              # le fonti, con i link
    assert "Risolto" in [b.label for b in at.button]

    at = premi(at, "Non risolto")
    assert not at.exception
    assert "Ticket per il supporto tecnico: Il POS non legge la carta" in testi(at)
    assert "Risolto" not in [b.label for b in at.button]                      # niente pulsanti dopo il ticket


def test_fonti_della_stessa_pagina_raggruppate(app):
    at = app(analisi(), hyde(), risposta("istruzioni", fonti=[1, 2, 3]), collezione=CollezioneStessaPagina())
    at.chat_input[0].set_value("Il POS non legge la carta").run()
    fonti = [m.value for m in at.markdown if m.value.startswith("**Fonti**")]
    assert len(fonti) == 1 and "\\[1, 2, 3\\]" in fonti[0] and fonti[0].count("Guida POS") == 1
    assert "guida.pdf#page=7" in fonti[0]                                    # il link apre la pagina giusta


def test_dettagli_scritti_nella_chat(app):
    at = app(analisi(), hyde(), risposta("chiedi_dettagli"), analisi(), hyde(), risposta("istruzioni"))
    at.chat_input[0].set_value("Il POS dà errore").run()
    assert at.chat_input[0].placeholder == "Rispondi alla domanda dell'assistente"
    at.chat_input[0].set_value("Il codice è E05").run()
    assert "Messaggio con esito istruzioni" in testi(at)


def test_errore_dell_api_mostrato_con_garbo(app):
    at = app()                                  # nessuna risposta preparata: la prima chiamata all'LLM fallisce
    at.chat_input[0].set_value("Il POS non legge la carta").run()
    assert not at.exception                     # l'app non si ferma con un errore ...
    assert "c'è stato un problema tecnico" in testi(at)                    # ...ma lo dice all'utente


def test_indice_mancante(monkeypatch):
    st.cache_resource.clear()
    monkeypatch.setattr(llm, "crea_client", lambda: ClientFinto([]))
    def senza_indice():
        raise RuntimeError("Indice non trovato")
    monkeypatch.setattr(ricerca, "apri_collezione", senza_indice)
    at = AppTest.from_file("../app.py", default_timeout=10).run()
    assert [e.value for e in at.error] == ["Indice non trovato"]