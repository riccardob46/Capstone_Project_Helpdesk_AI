"""Prova del chatbot dal terminale prima di costruire l'app Streamlit.

    python terminale.py

Usa l'API vera: ogni conversazione costa meno di un decimo di centesimo.
Effettuare prima la chiusura dei kernel dei notebook che hanno aperto l'indice: ChromaDB può essere aperto da un processo alla volta.
Scrivere "esci" per uscire.
"""
import time
from src.conversazione import Assistente
from src.llm import costo_dollari

# Per ogni domanda con pulsanti il metodo dell'Assistente da chiamare con la scelta dell'utente
AZIONE_PER_DOMANDA = {
    "domanda_dispositivo": "scegli_dispositivo",
    "domanda_marca": "scegli_marca",
    "istruzioni": "esito_istruzioni",
}

def mostra(passo):
    print(f"\nAssistente: {passo.messaggio}")
    if passo.fonti:
        print("\nFonti:")
        for numero, e in passo.fonti:
            print(f"   [{numero}] {e.editore} - {e.titolo} ({e.dove}) {e.url}")
    if passo.ticket:
        t = passo.ticket
        print(f"\n----- Ticket -----\nTitolo: {t.titolo}\nDispositivo: {t.dispositivo}   Categoria: {t.categoria}\n"
              f"Descrizione: {t.descrizione}\nNote tecniche: {t.note_tecniche or '-'}")
        for numero, e in enumerate(t.estratti, start=1):
            print(f"   [{numero}] {e.editore} - {e.titolo} ({e.dove}) {e.url}")

def scegli(opzioni):
    """Al posto dei pulsanti: un elenco numerato."""
    for numero, opzione in enumerate(opzioni, start=1):
        print(f"   {numero}. {opzione}")
    while True:
        scelta = input("Scelta (numero): ").strip()
        if scelta.isdigit() and 1 <= int(scelta) <= len(opzioni):
            return opzioni[int(scelta) - 1]

def scrivi(invito):
    while not (testo := input(invito).strip()):
        pass
    return testo

def conversazione(assistente, richiesta):
    attesa = 0.0                                   # solo il tempo in cui l'utente aspetta l'assistente
    inizio = time.perf_counter()
    passo = assistente.nuova_richiesta(richiesta)
    attesa += time.perf_counter() - inizio
    mostra(passo)
    while passo.tipo not in ("ticket", "chiuso"):
        if passo.tipo == "domanda_dettagli":
            risposta = scrivi("\nTu: ")
            inizio = time.perf_counter()
            passo = assistente.aggiungi_dettagli(risposta)
        else:
            scelta = scegli(passo.opzioni)
            inizio = time.perf_counter()
            passo = getattr(assistente, AZIONE_PER_DOMANDA[passo.tipo])(scelta)
        attesa += time.perf_counter() - inizio
        mostra(passo)
    print(f"\n({len(assistente.consumo)} chiamate all'LLM, attesa {attesa:.1f} s, "
          f"circa {costo_dollari(assistente.consumo):.5f} dollari)")
    print(f"(tempi delle chiamate all'LLM: "
          + ", ".join(f"{u.compito} {u.secondi:.1f} s" for u in assistente.consumo) + ")")

def main():
    assistente = Assistente()
    print("HelpDesk AI - prova dal terminale. Scrivi 'esci' per uscire.")
    while (richiesta := scrivi("\nTu (nuova richiesta): ")).lower() != "esci":
        try:
            conversazione(assistente, richiesta)
        except Exception as errore:                # per esempio la rete: la prova continua con la richiesta dopo
            print(f"\nErrore: {errore}")

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print()