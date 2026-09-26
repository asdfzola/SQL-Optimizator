# SQL Query Optimizer

Cost-based SQL query optimizer koji analizira SQL upite i bira izvršni plan sa najmanjim procenjenim troškom.

## Features

* SQL `SELECT`, `FROM`, `WHERE` i `ORDER BY`
* Table aliases
* Više `AND` uslova
* Selekcija i procena broja redova/blokova
* B+ Tree i Hash indeksi
* JOIN optimizacija:

  * Nested Loop Join
  * Block Nested Loop Join
  * Index Nested Loop Join
  * Hash Join
  * Merge Join
* External Merge Sort
* Generisanje kompletnog execution plana
* Izračunavanje ukupnog cost-a

## Cost Model

Optimizer koristi statistiku iz JSON schema fajla:

* broj redova i blokova
* broj različitih vrednosti
* `unique`
* visinu B+ Tree indeksa
* clustered/non-clustered indeks

Na osnovu tih podataka poredi moguće algoritme i bira najjeftiniji plan.

## Pokretanje

```bash
python main.py
```

Schema i statistika tabela učitavaju se iz JSON fajla, a `main.py` omogućava obradu više SQL upita i prikaz njihovih execution planova.
