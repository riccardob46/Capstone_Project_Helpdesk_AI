"""Coerenza tra schemi, istruzioni e configurazione: errori che altrimenti si scoprirebbero solo usando l'app."""
import pytest
from pydantic import ValidationError
from src import prompt
from src.configurazione import DISPOSITIVO_IN_INGLESE, SFORZO
from src.prompt import AnalisiRichiesta, RiepilogoTicket

def test_ogni_dispositivo_ha_descrizione_e_nome_inglese():
    assert set(prompt.DESCRIZIONE_DISPOSITIVI) == set(DISPOSITIVO_IN_INGLESE)

def test_analisi_accetta_solo_valori_previsti():
    valida = dict(richiesta_en="x", dispositivo="POS", marca="non indicata", categoria="Hardware", codice_errore=None)
    AnalisiRichiesta(**valida)
    for campo, valore in [("dispositivo", "stampante"), ("marca", "HP"), ("categoria", "Rete")]:
        with pytest.raises(ValidationError):
            AnalisiRichiesta(**{**valida, campo: valore})

def test_ticket_accetta_altro_dispositivo_ma_non_non_chiaro():
    valido = dict(titolo="t", descrizione="d", categoria="Hardware", note_tecniche="")
    RiepilogoTicket(**valido, dispositivo="altro")
    with pytest.raises(ValidationError):
        RiepilogoTicket(**valido, dispositivo="non chiaro")

def test_istruzioni_senza_parole_vecchie():
    # "brani" è stato sostituito da "estratti" ovunque (notebook 07): un prompt deve usare una parola sola
    for nome in ["ISTRUZIONI_ANALISI", "ISTRUZIONI_HYDE", "ISTRUZIONI_RISPOSTA", "ISTRUZIONI_TICKET"]:
        assert "brani" not in getattr(prompt, nome), nome

def test_le_istruzioni_elencano_tutti_i_dispositivi_e_le_categorie():
    for dispositivo in prompt.DISPOSITIVI:
        assert f"- {dispositivo}:" in prompt.ISTRUZIONI_ANALISI
    for categoria in prompt.CATEGORIE:
        assert f"- {categoria}:" in prompt.ISTRUZIONI_ANALISI and f"- {categoria}:" in prompt.ISTRUZIONI_TICKET

def test_sforzo_definito_per_ogni_compito():
    assert set(SFORZO) == {"analisi", "hyde", "risposta", "ticket"}
    assert set(SFORZO.values()) <= {"none", "low", "medium", "high"}