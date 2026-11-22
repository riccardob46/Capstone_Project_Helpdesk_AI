"""Sostituti del client OpenAI e dell'indice ChromaDB per provare il flusso senza rete e senza costi
Non imitano il modello: restituiscono le risposte che il test ha preparato, nell'ordine, e registrano come sono stati chiamati. Così il test decide cosa "risponde l'LLM" e verifica cosa fa l'app di conseguenza.
"""
from types import SimpleNamespace
from src.prompt import AnalisiRichiesta, PassaggioIpotetico, RiepilogoTicket, RispostaChatbot

class ClientFinto:
    def __init__(self, risposte):
        self.risposte = list(risposte)       # oggetti Pydantic, nell'ordine in cui il flusso li chiederà
        self.chiamate = []                   # i parametri di ogni chiamata a responses.parse
        self.testi_embedding = []            # i testi trasformati in vettore
        self.responses = SimpleNamespace(parse=self._parse)
        self.embeddings = SimpleNamespace(create=self._embedding)

    def _parse(self, **parametri):
        self.chiamate.append(parametri)
        assert self.risposte, f"Il flusso ha chiesto una risposta in più ({parametri['text_format'].__name__})"
        risposta = self.risposte.pop(0)
        assert isinstance(risposta, parametri["text_format"]), (
            f"Il flusso chiede {parametri['text_format'].__name__}, il test aveva preparato {type(risposta).__name__}")
        return SimpleNamespace(status="completed", output_parsed=risposta, incomplete_details=None,
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=200))

    def _embedding(self, model, input):
        self.testi_embedding.append(input[0])
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])

    def compiti(self):
        """Quali risposte strutturate ha chiesto il flusso, in ordine: utile per verificare il percorso."""
        return [c["text_format"].__name__ for c in self.chiamate]

class CollezioneFinta:
    """Restituisce sempre n estratti finti e registra i filtri usati."""

    def __init__(self):
        self.filtri = []

    def query(self, query_embeddings, n_results, where, include):
        self.filtri.append(where)
        numeri = range(1, n_results + 1)
        metadati = [{"id_fonte": f"fonte_{i}", "titolo": f"Manuale {i}", "editore": "Editore", "url": f"https://esempio.it/{i}",
                     "pagina": i, "sezione": "Troubleshooting"} for i in numeri]
        return {"metadatas": [metadati], "distances": [[0.1 * i for i in numeri]], "documents": [[f"Testo {i}" for i in numeri]]}

# --- Risposte "dell'LLM" già pronte, con valori di default modificabili --------------------------------

def analisi(dispositivo="POS", marca="non indicata", categoria="Hardware", codice_errore=None):
    return AnalisiRichiesta(richiesta_en="The POS does not read the card", dispositivo=dispositivo, marca=marca,
                            categoria=categoria, codice_errore=codice_errore)

def hyde():
    return PassaggioIpotetico(passaggio="Card read error. Clean the reader and insert the card again.")

def risposta(esito="istruzioni", fonti=(1,), note=""):
    return RispostaChatbot(esito=esito, messaggio=f"Messaggio con esito {esito} [1]", fonti=list(fonti), note_per_tecnico=note)

def ticket(dispositivo="POS"):
    return RiepilogoTicket(titolo="Il POS non legge la carta", descrizione="Descrizione per il tecnico",
                           dispositivo=dispositivo, categoria="Hardware", note_tecniche="Vedi [2]")