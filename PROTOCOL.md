# Protocol de comunicare client-server

Aplicatia foloseste comunicare TCP. Mesajele sunt transmise in format JSON, cate un mesaj pe linie.

Serverul functioneaza ca registru de chei si intermediar pentru transferul obiectelor intre clienti.

## 1. Conectare client

La conectarea unui client, serverul trimite lista curenta de chei publicate.

### Mesaj server -> client

```json
{
  "type": "KEY_LIST",
  "keys": ["obj1", "obj2"]
}