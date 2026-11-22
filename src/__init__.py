"""HelpDesk AI: il codice dell'applicazione.
I notebook documentano come abbiamo scelto ogni cosa; qui c'è solo quello che serve all'app:
- configurazione.py  percorsi, modelli e parametri scelti nei notebook 06 e 07
- prompt.py          schemi delle risposte e istruzioni per l'LLM (versione per l'app)
- llm.py             chiamate all'LLM e agli embeddings
- ricerca.py         l'indice ChromaDB e la ricerca degli estratti
- conversazione.py   il flusso della conversazione, dalla richiesta al ticket
"""