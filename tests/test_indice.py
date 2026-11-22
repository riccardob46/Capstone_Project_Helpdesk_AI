"""L'indice vero: si esegue solo se la cartella knowledge_base/chroma esiste (cioè dopo i notebook 05 e 06).
Non chiama l'API: legge solo l'indice. Controlla che i nomi usati dall'app (dispositivi e marche) coincidano con quelli scritti nell'indice e che il filtro per marca funzioni con la versione di ChromaDB installata: un errore qui darebbe ricerche vuote o sbagliate, senza nessun messaggio di errore.
Prima dell'esecuzione chiudere i Kernel dei notebook.
"""
from collections import Counter
import numpy as np
import pytest
from src.configurazione import CHROMA_DIR, MARCHE_STAMPANTE_RETE
from src.prompt import DISPOSITIVI
from src.ricerca import apri_collezione, cerca

pytestmark = pytest.mark.skipif(not CHROMA_DIR.exists(), reason="indice non presente: esegui i notebook 05 e 06")

@pytest.fixture(scope="module")
def collezione():
    collezione = apri_collezione()
    assert collezione.metadata.get("hnsw:space") == "cosine"
    return collezione

@pytest.fixture(scope="module")
def metadati(collezione):
    return collezione.get(include=["metadatas"])["metadatas"]

def test_ogni_dispositivo_ha_estratti(metadati):
    per_dispositivo = Counter(m["dispositivo"] for m in metadati)
    assert set(per_dispositivo) == set(DISPOSITIVI), per_dispositivo

def test_ogni_marca_della_stampante_di_rete_ha_estratti(metadati):
    marche = Counter(m["editore"] for m in metadati if m["dispositivo"] == "stampante di rete")
    assert set(marche) == set(MARCHE_STAMPANTE_RETE), marche

@pytest.mark.parametrize("marca", MARCHE_STAMPANTE_RETE)
def test_il_filtro_per_marca_funziona_sull_indice_vero(collezione, marca):
    # Come vettore di ricerca usiamo quello di un estratto già nell'indice: così non serve l'API
    vettore = np.array(collezione.get(limit=1, include=["embeddings"])["embeddings"][0], dtype=np.float32)
    estratti = cerca(collezione, vettore, "stampante di rete", marca)
    assert estratti and {e.editore for e in estratti} == {marca}