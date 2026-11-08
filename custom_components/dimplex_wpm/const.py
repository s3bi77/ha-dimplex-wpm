"""Konstanten und Registertabelle (WPM-Software L/M, Dimplex-Wiki "Modbus TCP")."""

from __future__ import annotations

DOMAIN = "dimplex_wpm"

CONF_UNIT = "unit"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_COOLING_ROOM = "cooling_room"

DEFAULT_PORT = 502
DEFAULT_UNIT = 1
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_COOLING_ROOM = 0  # 0 = aus, sonst Raumadresse 50–79
DEFAULT_COOLING_SETPOINT = 18.0

# Raumwerte werden zyklisch geschrieben (Smart-RTC+), Dimplex empfiehlt etwa 1 Raum pro Minute
ROOM_WRITE_INTERVAL = 600
ROOM_SWITCH_DELAY = 3.0

# Zusammenhängende Registerblöcke, die pro Zyklus gelesen werden
REGISTER_BLOCKS: tuple[tuple[int, int], ...] = (
    (1, 7),  # Außen, Rücklauf, Warmwasser, (4), Vorlauf, Quelle ein, Quelle aus
    (9, 1),  # Vorlauf 2. Heizkreis (R5)
    (11, 3),  # Raumtemperatur 1, (12), Raumfeuchte 1
    (19, 2),  # Kühlen passiv Vorlauf/Rücklauf
    (53, 2),  # Rücklauf-Soll, Soll 2. Heizkreis
    (58, 1),  # Warmwasser-Soll (Betrieb)
    (65, 3),  # Softwarestand
    (71, 9),  # Laufzeiten
    (103, 4),  # Status, Sperre, Störung, Sensorfehler
    (5015, 3),  # Betriebsmodus, Partystunden, Urlaubstage
    (5036, 3),  # HK1 Parallelverschiebung, Festwert, Heizkurvenendpunkt
    (5045, 4),  # Warmwasser Hysterese, (5046), Soll, Max
    (5096, 6),  # Wärmemengen Heizen, Warmwasser
    (5127, 4),  # Umweltenergie, Sperre extern
    (5145, 1),  # Warmwasser Min
    (5167, 4),  # Smart Grid, Wärmeleistung, (5169), elektrische Leistung
)

COIL_BLOCKS: tuple[tuple[int, int], ...] = (
    (3, 4),  # Eingänge SmartGrid 1/2, EVU-Sperre, Sperre extern
    (41, 31),  # Ausgänge 41–71
)

REG_MODE = 5015
REG_SMART_GRID = 5167
REG_EXTERNAL_LOCK = 5130
REG_ROOM_ADDRESS = 5065
REG_ROOM_TEMPERATURE = 11
REG_ROOM_SETPOINT = 5081

OPERATING_MODES = ["summer", "winter", "holiday", "party", "second_heat_source", "cooling"]

# Auswahlwerte → Registerwert
SMART_GRID_OPTIONS = {"hardware": 0, "normal": 10, "boost": 11, "reduced": 12, "boost_max": 13}
EXTERNAL_LOCK_OPTIONS = {"hardware": 0, "inactive": 10, "active": 11}

STATUS_TEXT = {
    0: "Aus",
    1: "Aus",
    2: "Heizen",
    3: "Schwimmbad",
    4: "Warmwasser",
    5: "Kühlen",
    10: "Abtauen",
    11: "Durchflussüberwachung",
    24: "Verzögerung Betriebsmodusumschaltung",
    30: "Sperre",
}

LOCK_TEXT = {
    0: "Keine",
    2: "Volumenstrom",
    5: "Funktionskontrolle",
    6: "Einsatzgrenze HT",
    7: "Systemkontrolle",
    8: "Verzögerung Umschaltung Kühlen",
    9: "Pumpenvorlauf",
    10: "Mindeststandzeit",
    11: "Netzbelastung",
    12: "Schaltspielsperre",
    13: "Warmwasser Nacherwärmung",
    14: "Regenerativ",
    15: "EVU-Sperre",
    16: "Sanftanlasser",
    17: "Durchfluss",
    18: "Einsatzgrenze Wärmepumpe",
    19: "Hochdruck",
    20: "Niederdruck",
    21: "Einsatzgrenze Wärmequelle",
    23: "Systemgrenze",
    24: "Last Primärkreis",
    25: "Sperre extern",
    29: "Inverter",
    31: "Aufwärmen",
    33: "EvD Initialisierung",
    34: "2. Wärmeerzeuger freigegeben",
    35: "Störung",
}

FAULT_TEXT = {
    0: "Keine",
    1: "Fehler N17.1",
    2: "Fehler N17.2",
    3: "Fehler N17.3",
    4: "Fehler N17.4",
    5: "Fehler N17",
    6: "Elektronisches Expansionsventil",
    7: "Raumregler RTM Econ",
    8: "Fehler ODU",
    9: "Durchfluss Frostschutz",
    10: "Erweiterung WPIO",
    12: "Inverter",
    13: "Erweiterung WQIF",
    14: "Nasslauf",
    15: "Sensorik",
    16: "Niederdruck Sole",
    19: "Primärkreis",
    20: "Abtauen",
    21: "Niederdruck Sole",
    22: "Warmwasser",
    23: "Last Verdichter",
    24: "Codierung",
    25: "Niederdruck",
    26: "Frostschutz",
    28: "Hochdruck",
    29: "Temperaturdifferenz",
    30: "Heißgasthermostat",
    31: "Durchfluss",
    32: "Aufwärmen",
    50: "Propan-Alarm",
    51: "Propan-Sensorfehler",
}

SENSOR_FAULT_TEXT = {
    0: "Keine",
    1: "Außenfühler (R1)",
    2: "Rücklauffühler (R2)",
    3: "Warmwasserfühler (R3)",
    4: "Codierung (R7)",
    5: "Vorlauffühler (R9)",
    6: "2. Heizkreisfühler (R5)",
    7: "3. Heizkreisfühler (R13)",
    8: "Regenerativfühler (R13)",
    9: "Raumfühler 1",
    10: "Raumfühler 2",
    11: "Fühler Wärmequellenaustritt (R6)",
    12: "Fühler Wärmequelleneintritt (R24)",
    14: "Kollektorfühler (R23)",
    15: "Niederdrucksensor (R25)",
    16: "Hochdrucksensor (R26)",
    17: "Raumfeuchte 1",
    18: "Raumfeuchte 2",
    19: "Fühler Frostschutz Kälte",
    20: "Heißgas",
    21: "Rücklauffühler (R2.1)",
    22: "Schwimmbadfühler (R20)",
    23: "Vorlauffühler Kühlen passiv (R11)",
    24: "Rücklauffühler Kühlen passiv (R4)",
    26: "Fühler Solarspeicher (R22)",
    28: "Anforderungsfühler Heizen (R2.2)",
    29: "RTM Econ",
    30: "Anforderungsfühler Kühlen (R39)",
    37: "Öltemperaturfühler Verdichter 1",
    39: "Öltemperaturfühler Verdichter 2",
    41: "Heißgasfühler Verdichter 1",
    43: "Heißgasfühler Verdichter 2",
    45: "Verdampfer Lufteintrittsfühler",
    48: "Durchflusssensor Sekundärkreis",
    49: "Drucksensor Sekundärkreis",
    50: "Durchflusssensor Primärkreis",
    51: "Drucksensor Primärkreis",
    52: "Sauggasfühler",
}
