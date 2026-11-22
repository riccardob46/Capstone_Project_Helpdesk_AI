"""L'indice ChromaDB e la ricerca degli estratti (notebook 06 e 07).
La ricerca usa la variante scelta nel notebook 07: traduzione e passaggio ipotetico insieme (T+H), filtrata per dispositivo e per la stampante di rete, anche per marca.
"""
from dataclasses import dataclass

import chromadb

from .configurazione import CHROMA_DIR, COLLEZIONE, K, MARCHE_STAMPANTE_RETE


@dataclass
class Estratto:
    """Un chunk trovato dalla ricerca con quello che serve per citarlo."""
    id_fonte: str
    titolo: str
    editore: str
    url: str
    pagina: int
    sezione: str
    testo: str
    distanza: float

    @property
    def dove(self):
        return f"pagina {self.pagina}" if self.pagina else f"sezione: {self.sezione}"


def apri_collezione():
    """La collezione scelta nel notebook 06. Un solo processo alla volta deve aprire l'indice."""
    if not CHROMA_DIR.exists():
        raise RuntimeError(f"Indice non trovato in {CHROMA_DIR}: esegui prima i notebook 05 e 06")
    return chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection(COLLEZIONE)


def filtro(dispositivo, marca=None):
    """Il filtro sui metadati: dispositivo e, solo per la stampante di rete, marca (campo "editore")."""
    if marca in MARCHE_STAMPANTE_RETE and dispositivo == "stampante di rete":
        return {"$and": [{"dispositivo": dispositivo}, {"editore": marca}]}
    return {"dispositivo": dispositivo}


def cerca(collezione, vettore, dispositivo, marca=None, k=K):
    """I k estratti più vicini al vettore filtrati per dispositivo (e marca)."""
    risultato = collezione.query(query_embeddings=[vettore.tolist()], n_results=k, where=filtro(dispositivo, marca),
                                 include=["metadatas", "distances", "documents"])
    return [Estratto(id_fonte=m["id_fonte"], titolo=m["titolo"], editore=m["editore"], url=m.get("url", ""),
                     pagina=int(m.get("pagina") or 0), sezione=m.get("sezione", ""), testo=t, distanza=round(d, 3))
            for m, d, t in zip(risultato["metadatas"][0], risultato["distances"][0], risultato["documents"][0])]


def testo_estratti(estratti):
    """Gli estratti numerati come li legge l'LLM: [1], [2], ..."""
    return "\n\n".join(f"[{n}] {e.editore} - {e.titolo} ({e.dove})\n{e.testo}" for n, e in enumerate(estratti, start=1))


def testo_per_ricerca(richiesta_en, passaggio_ipotetico=None):
    """Il testo da trasformare in vettore: la traduzione, più il passaggio ipotetico se usiamo HyDE (T+H)."""
    return f"{richiesta_en}\n\n{passaggio_ipotetico}" if passaggio_ipotetico else richiesta_en