"""Chiamate all'LLM e agli embeddings.
Come nei notebook, tutte le chiamate passano da due funzioni: per cambiare fornitore delle API (per esempio da OpenAI a un altro servizio) basterebbe riscrivere questo file. Con un altro modello di embeddings, però, andrebbe ricostruito anche l'indice: i vettori di modelli diversi non sono confrontabili. A differenza del notebook 07 qui non c'è la cache su file: nell'app ogni richiesta è nuova e la cache serviva solo a rendere ripetibile la valutazione.
"""
import os
import time
from dataclasses import dataclass

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

from .configurazione import ENV_PATH, MAX_OUTPUT_TOKENS, MODELLO_EMBEDDINGS, MODELLO_LLM, PREZZI


@dataclass
class Uso:
    """Token e tempo di una chiamata per stimare costi e attese."""
    compito: str
    modello: str
    token_ingresso: int
    token_uscita: int
    secondi: float


def crea_client():
    """Il client OpenAI con la chiave letta da .env (in locale) o dalle variabili d'ambiente (online)."""
    load_dotenv(ENV_PATH)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Chiave non trovata: crea il file .env nella cartella del progetto con OPENAI_API_KEY=...")
    return OpenAI(max_retries=3)


def chiedi(client, compito, istruzioni, testo, formato, sforzo, modello=MODELLO_LLM):
    """Risposta strutturata secondo `formato` (una classe Pydantic). Restituisce (risposta, uso)."""
    inizio = time.perf_counter()
    risposta = client.responses.parse(
        model=modello, instructions=istruzioni, input=testo, text_format=formato,
        reasoning={"effort": sforzo}, max_output_tokens=MAX_OUTPUT_TOKENS, store=False,
    )
    if risposta.status != "completed" or risposta.output_parsed is None:
        raise RuntimeError(f"Risposta non valida per '{compito}': stato {risposta.status}, {risposta.incomplete_details}")
    uso = Uso(compito, modello, risposta.usage.input_tokens, risposta.usage.output_tokens,
              round(time.perf_counter() - inizio, 2))
    return risposta.output_parsed, uso


def costo_dollari(consumo):
    """Il costo stimato di un elenco di Uso (gli embeddings costano così poco che li trascuriamo)."""
    return sum(u.token_ingresso / 1e6 * PREZZI[u.modello][0] + u.token_uscita / 1e6 * PREZZI[u.modello][1]
               for u in consumo)


def embedding(client, testo):
    """Il vettore di un testo con lo stesso modello usato per costruire l'indice."""
    risposta = client.embeddings.create(model=MODELLO_EMBEDDINGS, input=[testo])
    return np.array(risposta.data[0].embedding, dtype=np.float32)