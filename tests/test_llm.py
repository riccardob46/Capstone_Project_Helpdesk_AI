"""Le chiamate all'LLM: parametri passati all'API, errori e costo stimato."""
from types import SimpleNamespace
import pytest
from src import llm
from src.llm import Uso, chiedi, costo_dollari
from src.prompt import AnalisiRichiesta
from .sostituti import ClientFinto, analisi

def test_parametri_della_chiamata():
    client = ClientFinto([analisi()])
    risposta, uso = chiedi(client, "analisi", "Istruzioni", "Testo", AnalisiRichiesta, "none")
    parametri = client.chiamate[0]
    assert parametri["reasoning"] == {"effort": "none"}
    assert parametri["store"] is False                    # le richieste degli utenti non restano salvate da OpenAI
    assert "temperature" not in parametri                 # i modelli con ragionamento non la accettano
    assert risposta.dispositivo == "POS" and (uso.compito, uso.token_ingresso, uso.token_uscita) == ("analisi", 1000, 200)

def test_risposta_incompleta_solleva_errore():
    incompleta = SimpleNamespace(status="incomplete", output_parsed=None,
                                 incomplete_details=SimpleNamespace(reason="max_output_tokens"))
    client = SimpleNamespace(responses=SimpleNamespace(parse=lambda **_: incompleta))
    with pytest.raises(RuntimeError, match="max_output_tokens"):
        chiedi(client, "risposta", "Istruzioni", "Testo", AnalisiRichiesta, "low")

def test_chiave_mancante(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(llm, "ENV_PATH", tmp_path / ".env")   # un .env che non esiste: non leggiamo quello vero
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        llm.crea_client()

def test_costo():
    consumo = [Uso("analisi", "gpt-6-luna", 1_000_000, 0, 1.0), Uso("risposta", "gpt-6-luna", 0, 1_000_000, 2.0)]
    assert costo_dollari(consumo) == pytest.approx(0.10 + 0.50)