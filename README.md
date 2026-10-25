# Dimplex Wärmepumpe

Home-Assistant-Integration für Dimplex-Wärmepumpen mit Wärmepumpenmanager (WPM). Die Anbindung läuft lokal über Modbus TCP, ohne Cloud.

## Voraussetzungen

- Gateway NWPM oder NWPM Touch mit freigeschaltetem Modbus TCP (Port 502). Bei der NWPM Touch: lokale Weboberfläche → Einstellungen → Gateway-Zugang → „Netzwerkdienste freigegeben“, danach Neustart.
- WPM-Software L oder M. Getestet gegen die Registerliste für M3.17. Register, die der WPM nicht kennt, werden beim Start erkannt und ihre Entitäten nicht angelegt.

## Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → „Dimplex Wärmepumpe“. Abgefragt werden Host, Port und Unit-ID (Standard 1).

Unter „Konfigurieren“:

- **Abfrageintervall** in Sekunden (Standard 15).
- **Raumadresse für Kühlanforderung** (Standard 0 = aus). Mit einer Adresse von 50 bis 79 schreibt die Integration alle 10 Minuten den Kühl-Raumsollwert über die Raumschnittstelle (Smart-RTC+) an den WPM. 50–59 gehören zu Heizkreis 1, 60–69 zu Heizkreis 2, 70–79 zu Heizkreis 3. Ein niedriger Sollwert sorgt dafür, dass der WPM Kühlbedarf sieht.

Andere Systeme, die dieselben Register schreiben, sollten danach abgeschaltet werden, sonst überschreiben sie sich gegenseitig.

## Entitäten

Alle Entitäten hängen am Gerät „Wärmepumpe“.

| Plattform | Entitäten |
|---|---|
| Sensor | Außen-, Vorlauf-, Rücklauf-, Warmwasser-, Wärmequellentemperaturen, Rücklauf-Soll, Raumtemperatur und -feuchte; Status-, Sperr-, Stör- und Sensorfehlermeldung als Text (Rohwert im Attribut `code`); Laufzeiten; Wärmemengen Heizen und Warmwasser, Umweltenergie (für das Energie-Dashboard); Wärmeleistung und elektrische Leistung; Softwarestand |
| Binärsensor | Verdichter, Pumpen, Mischer, Flanschheizung, 2. Wärmeerzeuger, Umschaltung Raumthermostate, Sammelstörung; Eingänge EVU-Sperre, Sperre extern, Smart Grid |
| Wasserheizer | Warmwasser mit Ist- und Solltemperatur (Grenzen aus Minimal-/Maximalwert) |
| Auswahl | Betriebsmodus (Sommer, Winter, Urlaub, Party, 2. Wärmeerzeuger, Kühlen); Smart Grid (Hardwareeingang, rot, gelb, grün, dunkelgrün); Sperre extern |
| Zahl | Warmwasser minimal/maximal/Hysterese, Heizkurve Endpunkt und Parallelverschiebung (Heizkreis 1), Party- und Urlaubsdauer, Kühl-Raumsollwert |

Selten genutzte Ausgänge (zweiter Verdichter, weitere Heizungspumpen, Mischer, Schwimmbad, Solar) sind angelegt, aber standardmäßig deaktiviert.

## Verhalten

- Geschrieben wird nur, wenn sich ein Wert ändert.
- Smart Grid und Sperre extern setzt der WPM nach einem Spannungsreset auf „Hardwareeingang“ zurück. Die Integration merkt sich den zuletzt gewählten Wert und schreibt ihn beim nächsten Abfragezyklus erneut. Mit „Hardwareeingang“ endet das.
- Raumadresse und Raumsollwert werden als zusammenhängende Folge geschrieben (Adresse, 3 s Pause, Sollwert), ohne dass andere Zugriffe dazwischenkommen.
- Kein externes Python-Paket: Der Modbus-Client ist Teil der Integration.

## Registerquelle

[Dimplex Wiki: Modbus TCP](https://dimplex.atlassian.net/wiki/spaces/DW/pages/3303571683/Modbus+TCP+-+Datenpunktliste) (Betriebsdaten, Systemstatus, Laufzeiten, Wärme- und Energiemengen, Ein-/Ausgänge, Warmwasser, Heizkreis, Raumtemperaturregelung, Smart Grid, Sperre extern).

## Entwicklung

```
pip install pytest-homeassistant-custom-component
pytest
```
