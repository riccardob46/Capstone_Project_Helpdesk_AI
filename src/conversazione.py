"""Il flusso della conversazione: dalla richiesta dell'utente alla risposta o al ticket.
L'interfaccia (Streamlit o il terminale per le prove) chiama un metodo di `Assistente` ogni volta che l'utente scrive o preme un pulsante; il metodo restituisce un `Passo`: cosa mostrare e quali pulsanti offrire.
    richiesta -> analisi -> [dispositivo non chiaro?  pulsanti con "Altro dispositivo" -> ticket]
              -> [stampante di rete senza marca?  pulsanti con le marche e "Non lo so"]
              -> ricerca (T+H, filtro per dispositivo e marca) -> risposta:
                   istruzioni            -> "Risolto" / "Non risolto" -> ticket se non risolto
                   chiedi_dettagli       -> l'utente risponde -> nuova analisi, ricerca e risposta (una volta sola)
                   inoltra / non trovata -> ticket
Il flusso non sa nulla dell'interfaccia: per questo si può provare dal terminale e verificare con i test senza avviare Streamlit.
"""
from dataclasses import dataclass, field

from .configurazione import DISPOSITIVO_IN_INGLESE, MARCHE_STAMPANTE_RETE, MAX_DOMANDE_DETTAGLI, SFORZO, USA_HYDE
from .llm import chiedi, crea_client, embedding
from .prompt import (ALTRO_DISPOSITIVO, DESCRIZIONE_DISPOSITIVI, DISPOSITIVI, ISTRUZIONI_ANALISI, ISTRUZIONI_HYDE,
                     ISTRUZIONI_RISPOSTA, ISTRUZIONI_TICKET, MARCA_NON_INDICATA, NON_CHIARO, AnalisiRichiesta,
                     PassaggioIpotetico, RiepilogoTicket, RispostaChatbot)
from .ricerca import apri_collezione, cerca, testo_estratti, testo_per_ricerca

# Le etichette dei pulsanti che non sono nomi di dispositivi o di marche
OPZIONE_ALTRO_DISPOSITIVO = "Altro dispositivo"
OPZIONE_MARCA_SCONOSCIUTA = "Non lo so"
RISOLTO, NON_RISOLTO = "Risolto", "Non risolto"


@dataclass
class Ticket:
    titolo: str
    descrizione: str
    dispositivo: str
    categoria: str
    note_tecniche: str
    estratti: list = field(default_factory=list)   # tutti gli estratti trovati: li allega l'app, non l'LLM


@dataclass
class Passo:
    """Cosa mostrare all'utente dopo ogni sua azione."""
    tipo: str              # domanda_dispositivo, domanda_marca, domanda_dettagli, istruzioni, ticket, chiuso
    messaggio: str
    opzioni: list = field(default_factory=list)    # i pulsanti da mostrare (vuoto: l'utente scrive)
    fonti: list = field(default_factory=list)      # (numero, Estratto) citati nel messaggio, con il numero usato nel testo
    ticket: Ticket = None                          # solo quando tipo == "ticket"


class Assistente:
    """Una conversazione alla volta: l'app ne crea uno per ogni utente collegato."""

    def __init__(self, client=None, collezione=None):
        # client e collezione si possono passare da fuori: i test passano dei sostituti che non usano la rete
        self.client = client if client is not None else crea_client()
        self.collezione = collezione if collezione is not None else apri_collezione()
        self.reset()

    def reset(self):
        self.stato = "attesa_richiesta"
        self.messaggi = []            # (ruolo, testo): tutta la conversazione, che finisce nel ticket
        self.richiesta = None
        self.dettagli = []            # (domanda dell'assistente, risposta dell'utente)
        self.analisi = None
        self.dispositivo = None
        self.marca = None
        self.estratti = []
        self.risposta = None
        self.consumo = []             # un Uso per ogni chiamata all'LLM: token e secondi

    # --- Le azioni dell'utente: una per ogni cosa che può fare nell'interfaccia ------------------------

    def nuova_richiesta(self, testo):
        self.reset()
        self._scrive("utente", testo)
        self.richiesta = testo
        return self._analizza_e_procedi()

    def scegli_dispositivo(self, scelta):
        self._controlla("attesa_dispositivo", scelta, DISPOSITIVI + [OPZIONE_ALTRO_DISPOSITIVO])
        self._scrive("utente", scelta)
        self.dispositivo = ALTRO_DISPOSITIVO if scelta == OPZIONE_ALTRO_DISPOSITIVO else scelta
        return self._procedi()

    def scegli_marca(self, scelta):
        self._controlla("attesa_marca", scelta, MARCHE_STAMPANTE_RETE + [OPZIONE_MARCA_SCONOSCIUTA])
        self._scrive("utente", scelta)
        self.marca = MARCA_NON_INDICATA if scelta == OPZIONE_MARCA_SCONOSCIUTA else scelta
        return self._procedi()

    def aggiungi_dettagli(self, testo):
        self._controlla("attesa_dettagli")
        self._scrive("utente", testo)
        self.dettagli.append((self.risposta.messaggio, testo))
        return self._analizza_e_procedi()

    def esito_istruzioni(self, scelta):
        self._controlla("attesa_esito", scelta, [RISOLTO, NON_RISOLTO])
        if scelta == RISOLTO:
            self._scrive("utente", "Ho risolto.")
            self.stato = "chiusa"
            return self._passo("chiuso", "Bene, sono contento che il problema sia risolto!")
        self._scrive("utente", "Ho provato i passi, ma il problema c'è ancora.")
        return self._apri_ticket("Mi dispiace. Apro un ticket per il supporto tecnico, con quello che hai già provato.")

    # --- Il flusso --------------------------------------------------------------------------------------

    def _analizza_e_procedi(self):
        self.analisi = self._chiedi("analisi", ISTRUZIONI_ANALISI, self._testo_richiesta(), AnalisiRichiesta)
        # Dispositivo e marca, una volta stabiliti (dall'analisi o dai pulsanti), non cambiano più:
        # dopo i dettagli l'analisi viene rifatta, ma non deve rimettere in discussione una scelta dell'utente.
        if self.dispositivo is None and self.analisi.dispositivo != NON_CHIARO:
            self.dispositivo = self.analisi.dispositivo
        if self.marca is None and self.analisi.marca != MARCA_NON_INDICATA:
            self.marca = self.analisi.marca
        return self._procedi()

    def _procedi(self):
        """Fa la prossima domanda che manca o, se non manca nulla, risponde."""
        if self.dispositivo is None:
            self.stato = "attesa_dispositivo"
            return self._passo("domanda_dispositivo", "Di quale dispositivo si tratta?",
                               opzioni=DISPOSITIVI + [OPZIONE_ALTRO_DISPOSITIVO])
        if self.dispositivo == ALTRO_DISPOSITIVO:
            return self._apri_ticket("La documentazione che conosco non riguarda questo dispositivo: "
                                     "apro un ticket per il supporto tecnico.")
        if self.dispositivo == "stampante di rete" and self.marca is None:
            self.stato = "attesa_marca"
            return self._passo("domanda_marca", "Di che marca è la stampante di rete?",
                               opzioni=MARCHE_STAMPANTE_RETE + [OPZIONE_MARCA_SCONOSCIUTA])
        return self._rispondi()

    def _rispondi(self):
        # 1. La ricerca: traduzione + passaggio ipotetico (T+H), filtrata per dispositivo e marca
        richiesta_en = self.analisi.richiesta_en
        passaggio = None
        if USA_HYDE:
            testo_hyde = f"Device: {DISPOSITIVO_IN_INGLESE[self.dispositivo]}\nProblem reported by the user: {richiesta_en}"
            passaggio = self._chiedi("hyde", ISTRUZIONI_HYDE, testo_hyde, PassaggioIpotetico).passaggio
        vettore = embedding(self.client, testo_per_ricerca(richiesta_en, passaggio))
        self.estratti = cerca(self.collezione, vettore, self.dispositivo, self.marca)

        # 2. La risposta, con le fonti: teniamo solo i numeri che corrispondono a un estratto, senza ripetizioni
        self.risposta = self._chiedi("risposta", ISTRUZIONI_RISPOSTA, self._input_risposta(), RispostaChatbot)
        numeri = [n for n in dict.fromkeys(self.risposta.fonti) if 1 <= n <= len(self.estratti)]
        fonti = [(n, self.estratti[n - 1]) for n in numeri]

        # 3. Cosa succede dopo dipende dall'esito
        esito = self.risposta.esito
        if esito == "istruzioni":
            self.stato = "attesa_esito"
            return self._passo("istruzioni", self.risposta.messaggio, opzioni=[RISOLTO, NON_RISOLTO], fonti=fonti)
        if esito == "chiedi_dettagli" and len(self.dettagli) < MAX_DOMANDE_DETTAGLI:
            self.stato = "attesa_dettagli"
            return self._passo("domanda_dettagli", self.risposta.messaggio, fonti=fonti)
        if esito == "chiedi_dettagli":
            return self._apri_ticket("Con le informazioni che ho non riesco a guidarti oltre: "
                                     "apro un ticket per il supporto tecnico.")
        return self._apri_ticket(self.risposta.messaggio)          # inoltra_al_tecnico o non_trovata

    def _apri_ticket(self, messaggio):
        self._scrive("assistente", messaggio)
        conversazione = "\n".join(f"{'Utente' if ruolo == 'utente' else 'Assistente'}: {testo}"
                                  for ruolo, testo in self.messaggi)
        note = self.risposta.note_per_tecnico if self.risposta else ""
        elenco = "\n".join(f"[{n}] {e.editore} - {e.titolo} ({e.dove})" for n, e in enumerate(self.estratti, start=1))
        testo = (f"Conversazione:\n{conversazione}\n\n"
                 f"Note dell'assistente per il tecnico: {note or 'nessuna'}\n\n"
                 f"Estratti di documentazione trovati:\n{elenco or 'nessuno'}")
        riepilogo = self._chiedi("ticket", ISTRUZIONI_TICKET, testo, RiepilogoTicket)
        self.stato = "chiusa"
        return Passo("ticket", messaggio, ticket=Ticket(**riepilogo.model_dump(), estratti=list(self.estratti)))

    # --- Aiuti ------------------------------------------------------------------------------------------

    def _testo_richiesta(self):
        """La richiesta, seguita dalle eventuali domande dell'assistente e risposte dell'utente."""
        righe = [self.richiesta]
        for domanda, risposta in self.dettagli:
            righe += [f"Domanda dell'assistente: {domanda}", f"Risposta dell'utente: {risposta}"]
        return "\n".join(righe)

    def _input_risposta(self):
        dispositivo = f"{self.dispositivo} ({DESCRIZIONE_DISPOSITIVI[self.dispositivo]})"
        if self.dispositivo == "stampante di rete" and self.marca in MARCHE_STAMPANTE_RETE:
            dispositivo += f", marca {self.marca}"
        codice = self.analisi.codice_errore or "non indicato dall'utente"     # None o "" se l'utente non l'ha scritto
        return (f"Richiesta dell'utente: {self._testo_richiesta()}\n"
                f"Dispositivo: {dispositivo}\n"
                f"Codice di errore: {codice}\n\n"
                f"Estratti della documentazione:\n\n{testo_estratti(self.estratti)}")

    def _chiedi(self, compito, istruzioni, testo, formato):
        risposta, uso = chiedi(self.client, compito, istruzioni, testo, formato, SFORZO[compito])
        self.consumo.append(uso)
        return risposta

    def _controlla(self, stato_atteso, scelta=None, ammesse=None):
        """Un pulsante vecchio premuto due volte non deve far ripartire il flusso da un punto sbagliato."""
        if self.stato != stato_atteso or (ammesse is not None and scelta not in ammesse):
            raise ValueError(f"Azione non attesa: stato '{self.stato}', scelta '{scelta}'")

    def _scrive(self, ruolo, testo):
        self.messaggi.append((ruolo, testo))

    def _passo(self, tipo, messaggio, **altro):
        self._scrive("assistente", messaggio)
        return Passo(tipo, messaggio, **altro)