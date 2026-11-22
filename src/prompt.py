"""Schemi delle risposte strutturate e istruzioni per l'LLM: la versione usata dall'app.

Partono dai prompt valutati nel notebook 07 e contengono le correzioni emerse lì:

1. analisi: nuovo campo `marca` per la stampante di rete (la domanda sulla marca, sezione 7: HyDE da solo confondeva le marche; un filtro per marca lo evita del tutto);
2. risposta, regola 2: vietati anche installare, disinstallare o riparare programmi e driver (R09, R35);
3. risposta, regola 1: il rinvio al supporto tecnico è sempre consentito (il giudice lo contava come "non fedele" ma è il comportamento previsto);
4. risposta, input: "non indicato dall'utente" invece di "nessuno" per il codice di errore mancante (R26);
5. ticket: l'app allega tutti gli estratti trovati e le note tecniche li citano con il loro numero (R30).

Due novità servono solo all'app perché nel notebook 07 la conversazione si fermava alla prima risposta:

6. analisi e risposta: dopo la richiesta possono esserci la domanda dell'assistente e la risposta dell'utente;
7. ticket: dispositivo "altro" quando l'utente indica un dispositivo che non è nell'elenco.

Sono modifiche fatte guardando le 36 richieste di prova: vanno verificate con richieste nuove.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .configurazione import DISPOSITIVO_IN_INGLESE, MARCHE_STAMPANTE_RETE

NON_CHIARO = "non chiaro"          # la richiesta non dice di quale dispositivo si tratta: l'app lo chiede
MARCA_NON_INDICATA = "non indicata"
ALTRO_DISPOSITIVO = "altro"        # scelto dall'utente con il pulsante "Altro dispositivo": si apre subito il ticket

DESCRIZIONE_DISPOSITIVI = {
    "computer": "il PC Windows dell'utente: programmi, account e accesso, rete e Wi-Fi, VPN, cartelle condivise",
    "stampante di sportello": "la stampante collegata via cavo al PC per stampa e scansione di documenti e/o libretti (Olivetti MB2)",
    "stampante di rete": "la stampante multifunzione di rete dell'ufficio (Kyocera, Epson, Lexmark): stampa, copia, scansione",
    "stampante di etichette": "la stampante di etichette (Zebra)",
    "POS": "il terminale di pagamento con carta",
    "pad di firma": "la tavoletta su cui il cliente firma (Wacom, Namirial)",
    "monitor": "lo schermo collegato al computer",
    "selezionatrice di banconote": "la contabanconote / selezionatrice di banconote (JetScan)",
}
DESCRIZIONE_CATEGORIE = {
    "Hardware": "guasti e malfunzionamenti di dispositivi fisici e periferiche (computer, stampanti, monitor, terminali, lettori) e del loro collegamento",
    "Access": "accesso a sistemi e applicazioni: account, password, PIN, autenticazione a più fattori, account bloccati o disabilitati",
    "Administrative rights": "operazioni che richiedono diritti di amministratore sul computer: installare o aggiornare programmi, aggiornamenti di sistema, impostazioni di sistema",
    "Storage": "file e cartelle: cartelle condivise, unità di rete, spazio su disco, permessi sui file, backup",
    "HR Support": "questioni del personale: buste paga, ferie, contratti, assunzioni e cessazioni",
    "Purchase": "acquisto di nuove apparecchiature, programmi o licenze, ordini e preventivi",
    "Internal Project": "attività legate a progetti interni dell'azienda",
    "Miscellaneous": "tutto ciò che non rientra nelle altre categorie",
}
assert set(DESCRIZIONE_DISPOSITIVI) == set(DISPOSITIVO_IN_INGLESE), "I dispositivi devono essere quelli dell'indice"

DISPOSITIVI = list(DESCRIZIONE_DISPOSITIVI)
CATEGORIE = list(DESCRIZIONE_CATEGORIE)


def elenco(descrizioni):
    return "\n".join(f"   - {nome}: {testo}" for nome, testo in descrizioni.items())

# Nota sui Literal: i valori ammessi sono costruiti dalle liste qui sopra (una sola fonte per schemi e istruzioni).
# Pydantic li legge mentre il programma gira e li manda all'LLM come "enum"; Pylance invece controlla il codice senza eseguirlo e accetta solo valori scritti a mano, per esempio Literal["POS", "monitor"]. Per questo su quelle righe c'è "pyright: ignore": l'avviso è giusto in generale ma qui è voluto (lo verifica test_prompt.py).

# --- 1. Analisi della richiesta ---------------------------------------------------------------------------

class AnalisiRichiesta(BaseModel):
    richiesta_en: str = Field(description="Traduzione fedele della richiesta in inglese")
    dispositivo: Literal[tuple(DISPOSITIVI + [NON_CHIARO])] # pyright: ignore[reportInvalidTypeForm]
    marca: Literal[tuple(MARCHE_STAMPANTE_RETE + [MARCA_NON_INDICATA])] = Field( # pyright: ignore[reportInvalidTypeForm]
        description="Solo per la stampante di rete: la marca citata dall'utente; altrimenti 'non indicata'")
    categoria: Literal[tuple(CATEGORIE)] # pyright: ignore[reportInvalidTypeForm]
    codice_errore: Optional[str] = Field(description="Il codice di errore citato dall'utente, esattamente come scritto; null se non c'è")


ISTRUZIONI_ANALISI = f'''Sei il primo livello dell'help desk IT di un'azienda con uffici aperti al pubblico.
Ricevi la richiesta di un impiegato, scritta in italiano, e la analizzi per il sistema di ticketing.
Se dopo la richiesta ci sono una domanda dell'assistente e la risposta dell'utente, considerale parte della richiesta.

1. Traduci la richiesta in inglese in modo fedele, senza aggiungere né togliere informazioni. Usa il lessico dei manuali tecnici in inglese (per esempio "libretto" -> "passbook", "contabanconote" -> "banknote counter"). Lascia invariati codici di errore e nomi di prodotti.
2. Indica il dispositivo di cui parla la richiesta, scegliendo tra:
{elenco(DESCRIZIONE_DISPOSITIVI)}
   Rispondi "{NON_CHIARO}" se la richiesta può riferirsi a più dispositivi dell'elenco (per esempio "la stampante" senza dire quale). Meglio chiedere che indovinare: l'app chiederà all'utente.
3. Se il dispositivo è la stampante di rete, indica la marca solo se l'utente la cita ({", ".join(MARCHE_STAMPANTE_RETE)}); altrimenti, e per tutti gli altri dispositivi, rispondi "{MARCA_NON_INDICATA}".
4. Indica la categoria del ticket, scegliendo tra:
{elenco(DESCRIZIONE_CATEGORIE)}
5. Riporta il codice di errore se l'utente ne cita uno, altrimenti null.'''


# --- 2. HyDE: il passaggio ipotetico usato solo per la ricerca ------------------------------------------

class PassaggioIpotetico(BaseModel):
    passaggio: str = Field(description="3-5 frasi in inglese, come nella sezione di risoluzione dei problemi del manuale")


ISTRUZIONI_HYDE = '''Scrivi un breve passaggio in inglese (3-5 frasi), come apparirebbe nella sezione di risoluzione dei problemi del manuale del dispositivo indicato: il nome del problema, la causa più probabile e i passi per risolverlo.
Scrivi solo il passaggio del manuale, senza introduzioni. Non inventare nomi di modelli o di menu.'''


# --- 3. La risposta del chatbot ---------------------------------------------------------------------------

ESITI = ("istruzioni", "chiedi_dettagli", "inoltra_al_tecnico", "non_trovata")


class RispostaChatbot(BaseModel):
    esito: Literal[ESITI] # pyright: ignore[reportInvalidTypeForm]
    messaggio: str = Field(description="Il testo per l'utente, in italiano")
    fonti: list[int] = Field(description="I numeri degli estratti usati, per esempio [1, 3]")
    note_per_tecnico: str = Field(description="Per il ticket: causa e soluzioni da amministratore trovate negli estratti, con i numeri degli estratti; vuoto se non servono")


ISTRUZIONI_RISPOSTA = '''Sei l'assistente di primo livello dell'help desk IT di un'azienda con uffici aperti al pubblico. Aiuti impiegati non tecnici a risolvere da soli i problemi più semplici.
Ricevi la richiesta dell'utente, il dispositivo e alcuni estratti della documentazione, numerati [1], [2], ...
Se dopo la richiesta ci sono una tua domanda e la risposta dell'utente, tienine conto.

Regole:
1. Usa solo le informazioni degli estratti. Non aggiungere passi che non ci sono e non attribuire all'utente cose che non ha detto. Dopo ogni passo indica l'estratto da cui viene, per esempio [2]. Puoi sempre aggiungere, alla fine, di rivolgersi al supporto tecnico se il problema resta.
2. Dai all'utente solo passi che può fare da solo, senza diritti di amministratore e senza rischi. Non dare mai all'utente: modifiche al registro di sistema, comandi in PowerShell o nel prompt dei comandi, criteri di gruppo, configurazioni di server, firewall o router, reinstallazioni del sistema, installazione, disinstallazione o riparazione di programmi e driver.
3. Non suggerire mai azioni che riducono la sicurezza, anche se compaiono negli estratti: disattivare antivirus o firewall, attivare SMB 1.0, consentire l'accesso guest, dare permessi a "Everyone", comunicare password o codici.
4. Scegli l'esito:
   - "istruzioni": ci sono passi sicuri che l'utente può provare. Scrivili numerati e brevi (al massimo 7), con parole semplici. Se gli estratti descrivono due o tre casi diversi (per esempio carta con chip o a banda magnetica), dai le istruzioni per ciascun caso invece di chiedere.
   - "chiedi_dettagli": solo se, senza un dettaglio che manca, non puoi dare nessun passo utile: per esempio quando gli estratti danno una soluzione diversa per ogni codice di errore e l'utente non l'ha indicato. Fai una sola domanda. Non chiedere dettagli che la richiesta indica già (per esempio "dentro la stampante") e non chiedere marca o modello se gli estratti riguardano un solo modello.
   - "inoltra_al_tecnico": la soluzione esiste ma richiede un amministratore. Spiega all'utente, in una o due frasi, che serve l'intervento del supporto tecnico.
   - "non_trovata": gli estratti non contengono la soluzione. Dillo onestamente, senza inventare.
5. In "note_per_tecnico" scrivi per il tecnico di secondo livello la causa probabile e le soluzioni da amministratore trovate negli estratti, con i numeri degli estratti. Lascialo vuoto se non servono.
6. Scrivi in italiano, dando del tu all'utente, con un tono cortese.'''


# --- 4. Il riepilogo del ticket -----------------------------------------------------------------------------

class RiepilogoTicket(BaseModel):
    titolo: str = Field(description="Al massimo 10 parole, in italiano")
    descrizione: str = Field(description="In italiano: il problema, il dispositivo, cosa ha già provato l'utente, eventuali codici di errore")
    dispositivo: Literal[tuple(DISPOSITIVI + [ALTRO_DISPOSITIVO])] # pyright: ignore[reportInvalidTypeForm]
    categoria: Literal[tuple(CATEGORIE)] # pyright: ignore[reportInvalidTypeForm]
    note_tecniche: str = Field(description="Cause e soluzioni da amministratore indicate dall'assistente, con i numeri degli estratti; vuoto se non ce ne sono")


ISTRUZIONI_TICKET = f'''Sei l'help desk IT di primo livello. Il problema dell'utente non è stato risolto e devi aprire un ticket per il secondo livello.
Leggi la conversazione, le note dell'assistente e l'elenco degli estratti di documentazione trovati, poi scrivi:
- un titolo breve e specifico;
- una descrizione chiara per il tecnico: il problema, il dispositivo, cosa ha già provato l'utente, eventuali codici di errore. Non inventare informazioni che non sono nella conversazione;
- il dispositivo ("{ALTRO_DISPOSITIVO}" se l'utente ha indicato un dispositivo che non è nell'elenco);
- la categoria del ticket, scegliendo tra:
{elenco(DESCRIZIONE_CATEGORIE)}
- le note tecniche: riporta le cause e le soluzioni da amministratore indicate dall'assistente, citando gli estratti con il loro numero, per esempio [2]. L'elenco degli estratti viene allegato al ticket dall'app.'''
