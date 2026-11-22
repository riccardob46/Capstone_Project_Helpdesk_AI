"""Filtri, testo per la ricerca e formato degli estratti: funzioni senza rete, si provano direttamente."""
import numpy as np
import pytest
from src.ricerca import Estratto, cerca, filtro, testo_estratti, testo_per_ricerca
from .sostituti import CollezioneFinta

@pytest.mark.parametrize("dispositivo, marca, atteso", [
    ("stampante di rete", "Lexmark", {"$and": [{"dispositivo": "stampante di rete"}, {"editore": "Lexmark"}]}),
    ("stampante di rete", "non indicata", {"dispositivo": "stampante di rete"}),
    ("stampante di rete", None, {"dispositivo": "stampante di rete"}),
    ("computer", "Kyocera", {"dispositivo": "computer"}),        # la marca conta solo per la stampante di rete
])
def test_filtro(dispositivo, marca, atteso):
    assert filtro(dispositivo, marca) == atteso

def test_testo_per_ricerca():
    assert testo_per_ricerca("The POS is off") == "The POS is off"
    assert testo_per_ricerca("The POS is off", "Check the cable.") == "The POS is off\n\nCheck the cable."

def test_estratti_numerati_con_pagina_o_sezione():
    estratti = [Estratto("a", "Manuale", "Olivetti", "", 17, "Ribbon", "Testo A", 0.2),
                Estratto("b", "Articolo", "Microsoft", "https://learn.microsoft.com/x", 0, "Resolution", "Testo B", 0.3)]
    assert testo_estratti(estratti) == ("[1] Olivetti - Manuale (pagina 17)\nTesto A\n\n"
                                        "[2] Microsoft - Articolo (sezione: Resolution)\nTesto B")

def test_cerca_restituisce_k_estratti_con_il_filtro():
    collezione = CollezioneFinta()
    estratti = cerca(collezione, np.array([0.1, 0.2], dtype=np.float32), "POS", k=3)
    assert len(estratti) == 3 and estratti[0].titolo == "Manuale 1" and estratti[2].pagina == 3
    assert collezione.filtri == [{"dispositivo": "POS"}]