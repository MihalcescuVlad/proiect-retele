# Proiect Rețele — Partajarea de obiecte în memorie

## 1. Descriere generală

Acest proiect implementează o aplicație distribuită de tip client-server pentru partajarea de obiecte ținute în memoria clienților.

Serverul funcționează ca registru și intermediar de transfer. El nu stochează efectiv obiectele, ci păstrează doar asocierea dintre o cheie și clientul care deține obiectul respectiv.

Exemplu:

```text
obj1 -> Client A
obj2 -> Client A
obj3 -> Client B