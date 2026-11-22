"""Il flusso della conversazione, percorso per percorso, con le risposte dell'LLM preparate dal test."""
import pytest
from src.conversazione import (NON_RISOLTO, OPZIONE_ALTRO_DISPOSITIVO, OPZIONE_MARCA_SCONOSCIUTA, RISOLTO, Assistente)
from src.prompt import DISPOSITIVI
from .sostituti import ClientFinto, CollezioneFinta, analisi, hyde, risposta, ticket

def assistente(*risposte):
    return Assistente(client=ClientFinto(risposte), collezione=CollezioneFinta())

# --- Il percorso più semplice -------------------------------------------------------------------------

def test_istruzioni_e_risolto():
    a = assistente(analisi(), hyde(), risposta("istruzioni", fonti=[2, 9, 2]))
    passo = a.nuova_richiesta("Il POS non legge la carta")
    assert passo.tipo == "istruzioni" and passo.opzioni == [RISOLTO, NON_RISOLTO]
    # Le fonti tengono il numero citato nel testo; [9] non esiste (gli estratti sono 5) e [2] ripetuto conta una volta
    assert [n for n, _ in passo.fonti] == [2] and passo.fonti[0][1].titolo == "Manuale 2"
    assert a.client.compiti() == ["AnalisiRichiesta", "PassaggioIpotetico", "RispostaChatbot"]

    passo = a.esito_istruzioni(RISOLTO)
    assert passo.tipo == "chiuso" and passo.ticket is None and a.stato == "chiusa"
    assert len(a.client.chiamate) == 3                     # nessun ticket, nessuna chiamata in più

def test_non_risolto_apre_il_ticket_con_tutti_gli_estratti():
    a = assistente(analisi(), hyde(), risposta("istruzioni", note="Causa probabile [3]"), ticket())
    a.nuova_richiesta("Il POS non legge la carta")
    passo = a.esito_istruzioni(NON_RISOLTO)
    assert passo.tipo == "ticket" and passo.ticket.titolo == "Il POS non legge la carta"
    assert len(passo.ticket.estratti) == 5                 # tutti, non solo quelli citati
    testo_ticket = a.client.chiamate[-1]["input"]
    assert "Causa probabile [3]" in testo_ticket
    assert "[5] Editore - Manuale 5 (pagina 5)" in testo_ticket
    assert "il problema c'è ancora" in testo_ticket        # il ticket sa che l'utente ha già provato i passi

# --- La ricerca: testo, filtri, codice di errore ---------------------------------------------------------

def test_la_ricerca_usa_traduzione_e_passaggio_ipotetico():
    a = assistente(analisi(), hyde(), risposta())
    a.nuova_richiesta("Il POS non legge la carta")
    assert a.client.testi_embedding == ["The POS does not read the card\n\n"
                                        "Card read error. Clean the reader and insert the card again."]
    assert a.collezione.filtri == [{"dispositivo": "POS"}]

@pytest.mark.parametrize("codice, atteso", [(None, "Codice di errore: non indicato dall'utente"),
                                            ("E05", "Codice di errore: E05")])
def test_codice_di_errore_nella_risposta(codice, atteso):
    a = assistente(analisi(codice_errore=codice), hyde(), risposta())
    a.nuova_richiesta("Il POS non legge la carta")
    assert atteso in a.client.chiamate[2]["input"]

# --- Dispositivo non chiaro ----------------------------------------------------------------------------

def test_dispositivo_non_chiaro_viene_chiesto():
    a = assistente(analisi(dispositivo="non chiaro"), hyde(), risposta())
    passo = a.nuova_richiesta("La stampante non funziona")
    assert passo.tipo == "domanda_dispositivo"
    assert passo.opzioni == DISPOSITIVI + [OPZIONE_ALTRO_DISPOSITIVO]
    assert len(a.client.chiamate) == 1                     # ancora nessuna ricerca né risposta

    passo = a.scegli_dispositivo("stampante di etichette")
    assert passo.tipo == "istruzioni"
    assert a.collezione.filtri == [{"dispositivo": "stampante di etichette"}]

def test_altro_dispositivo_apre_subito_il_ticket_senza_ricerca():
    a = assistente(analisi(dispositivo="non chiaro"), ticket(dispositivo="altro"))
    a.nuova_richiesta("Il telefono fisso non squilla")
    passo = a.scegli_dispositivo(OPZIONE_ALTRO_DISPOSITIVO)
    assert passo.tipo == "ticket" and passo.ticket.dispositivo == "altro"
    assert a.collezione.filtri == [] and passo.ticket.estratti == []

def test_la_scelta_dell_utente_non_cambia_dopo_i_dettagli():
    # Dopo i dettagli l'analisi viene rifatta: anche se ora "vede" un altro dispositivo, vale quello scelto
    a = assistente(analisi(dispositivo="non chiaro"), hyde(), risposta("chiedi_dettagli"),
                   analisi(dispositivo="computer"), hyde(), risposta("istruzioni"))
    a.nuova_richiesta("Non stampa")
    a.scegli_dispositivo("stampante di sportello")
    a.aggiungi_dettagli("Si accende la spia rossa")
    assert a.dispositivo == "stampante di sportello"
    assert a.collezione.filtri[-1] == {"dispositivo": "stampante di sportello"}

# --- Stampante di rete e marca -----------------------------------------------------------------------

def test_marca_chiesta_e_usata_nel_filtro():
    a = assistente(analisi(dispositivo="stampante di rete"), hyde(), risposta())
    passo = a.nuova_richiesta("La stampante dell'ufficio non scansiona")
    assert passo.tipo == "domanda_marca" and OPZIONE_MARCA_SCONOSCIUTA in passo.opzioni

    a.scegli_marca("Kyocera")
    assert a.collezione.filtri == [{"$and": [{"dispositivo": "stampante di rete"}, {"editore": "Kyocera"}]}]
    assert "marca Kyocera" in a.client.chiamate[-1]["input"]

def test_marca_sconosciuta_cerca_su_tutte_le_marche():
    a = assistente(analisi(dispositivo="stampante di rete"), hyde(), risposta())
    a.nuova_richiesta("La stampante dell'ufficio non scansiona")
    a.scegli_marca(OPZIONE_MARCA_SCONOSCIUTA)
    assert a.collezione.filtri == [{"dispositivo": "stampante di rete"}]
    assert ", marca " not in a.client.chiamate[-1]["input"]

def test_marca_citata_nella_richiesta_non_viene_chiesta():
    a = assistente(analisi(dispositivo="stampante di rete", marca="Epson"), hyde(), risposta())
    passo = a.nuova_richiesta("La Epson dell'ufficio non scansiona")
    assert passo.tipo == "istruzioni"
    assert a.collezione.filtri[0]["$and"][1] == {"editore": "Epson"}

# --- Dettagli, inoltro, non trovata -----------------------------------------------------------------

def test_dettagli_una_volta_sola_poi_ticket():
    a = assistente(analisi(), hyde(), risposta("chiedi_dettagli"),
                   analisi(), hyde(), risposta("chiedi_dettagli"), ticket())
    passo = a.nuova_richiesta("Il POS dà errore")
    assert passo.tipo == "domanda_dettagli" and passo.opzioni == []      # l'utente risponde scrivendo

    passo = a.aggiungi_dettagli("Il codice è E05")
    # La seconda analisi riceve la domanda dell'assistente e la risposta dell'utente
    seconda_analisi = a.client.chiamate[3]["input"]
    assert "Domanda dell'assistente: Messaggio con esito chiedi_dettagli" in seconda_analisi
    assert "Risposta dell'utente: Il codice è E05" in seconda_analisi
    assert passo.tipo == "ticket"                                       # seconda richiesta di dettagli: ticket

@pytest.mark.parametrize("esito", ["inoltra_al_tecnico", "non_trovata"])
def test_inoltro_e_non_trovata_aprono_il_ticket(esito):
    a = assistente(analisi(), hyde(), risposta(esito), ticket())
    passo = a.nuova_richiesta("Il POS non si accende")
    assert passo.tipo == "ticket" and passo.messaggio == f"Messaggio con esito {esito} [1]"
    assert a.stato == "chiusa"

# --- Azioni non attese ------------------------------------------------------------------------------

def test_azioni_fuori_ordine_vengono_rifiutate():
    a = assistente(analisi(), hyde(), risposta())
    a.nuova_richiesta("Il POS non legge la carta")             # ora si aspetta Risolto / Non risolto
    with pytest.raises(ValueError):
        a.scegli_marca("Kyocera")
    with pytest.raises(ValueError):
        a.esito_istruzioni("Forse")
    with pytest.raises(ValueError):
        a.aggiungi_dettagli("Altro testo")

def test_nuova_richiesta_riparte_da_zero():
    a = assistente(analisi(dispositivo="stampante di rete", marca="Epson"), hyde(), risposta(),
                   analisi(), hyde(), risposta())
    a.nuova_richiesta("La Epson non scansiona")
    a.nuova_richiesta("Il POS non legge la carta")
    assert a.dispositivo == "POS" and a.marca is None
    assert [ruolo for ruolo, _ in a.messaggi] == ["utente", "assistente"]

def test_consumo_registrato_per_ogni_chiamata():
    a = assistente(analisi(), hyde(), risposta())
    a.nuova_richiesta("Il POS non legge la carta")
    assert [u.compito for u in a.consumo] == ["analisi", "hyde", "risposta"]