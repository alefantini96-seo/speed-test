"""Soglie Core Web Vitals (Google, agosto 2026). Funzioni pure, nessuna I/O."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Soglia:
    buono: float
    scarso: float
    unita: str = "ms"


SOGLIE = {
    "largest_contentful_paint": Soglia(2500, 4000),
    "interaction_to_next_paint": Soglia(200, 500),
    "cumulative_layout_shift": Soglia(0.10, 0.25, ""),
    "first_contentful_paint": Soglia(1800, 3000),
    "experimental_time_to_first_byte": Soglia(800, 1800),
}

ETICHETTE = {
    "largest_contentful_paint": "LCP",
    "interaction_to_next_paint": "INP",
    "cumulative_layout_shift": "CLS",
    "first_contentful_paint": "FCP",
    "experimental_time_to_first_byte": "TTFB",
}

# Le tre metriche che Google usa come Core Web Vitals.
CWV = ("largest_contentful_paint", "interaction_to_next_paint", "cumulative_layout_shift")

# CrUX espone la ripartizione dell'LCP in fasi, sugli utenti reali e con lo storico
# a 40 settimane. Sono le stesse quattro fasi che Lighthouse misura in laboratorio,
# ma stabili: il breakdown di lab e' stato visto oscillare fra 260 e 3.118 ms sulla
# stessa pagina, questo no.
#
# Esistono solo quando l'elemento LCP e' un'immagine (il nome lo dice): su un LCP
# testuale non ci sono e si ricade sul laboratorio.
CRUX_FASI_LCP = {
    "largest_contentful_paint_image_time_to_first_byte": "timeToFirstByte",
    "largest_contentful_paint_image_resource_load_delay": "resourceLoadDelay",
    "largest_contentful_paint_image_resource_load_duration": "resourceLoadDuration",
    "largest_contentful_paint_image_element_render_delay": "elementRenderDelay",
}


def fasi_dal_campo(campo: dict) -> dict:
    """Ripartizione LCP dai dati di campo, o {} se la pagina non ne ha.

    Servono tutte e quattro: una ripartizione parziale darebbe una fase dominante
    falsata da cio' che manca.
    """
    fasi = {}
    for chiave_crux, fase in CRUX_FASI_LCP.items():
        valore = (campo or {}).get(chiave_crux)
        if valore is None:
            return {}
        fasi[fase] = float(valore)
    return fasi

# Nomi usati da PSI in loadingExperience, diversi da quelli della CrUX API.
PSI_A_CRUX = {
    "LARGEST_CONTENTFUL_PAINT_MS": "largest_contentful_paint",
    "INTERACTION_TO_NEXT_PAINT": "interaction_to_next_paint",
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": "cumulative_layout_shift",
    "FIRST_CONTENTFUL_PAINT_MS": "first_contentful_paint",
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE": "experimental_time_to_first_byte",
}


def giudizio(metrica: str, valore: float | None) -> str:
    """buono | da_migliorare | scarso | sconosciuto"""
    if valore is None or metrica not in SOGLIE:
        return "sconosciuto"
    s = SOGLIE[metrica]
    if valore <= s.buono:
        return "buono"
    return "da_migliorare" if valore <= s.scarso else "scarso"


def formatta(metrica: str, valore: float | None) -> str:
    if valore is None:
        return "n/d"
    if SOGLIE.get(metrica, Soglia(0, 0)).unita == "":
        return f"{valore:.2f}"
    return f"{valore:.0f} ms"
