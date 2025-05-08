from typing import Optional, Tuple, Dict, Any, List
import re
# ────────────────────────────────────────────────────────────────────────────
# Holiday / window map by ISO‑3166 country code.
#   • Each entry: ((start_mm, start_dd), (end_mm, end_dd)) → label
#   • Inclusive windows. Movable feasts use an average range.
#   • Keep it coarse (± 1 week) — good enough for release‑window tagging.
# ────────────────────────────────────────────────────────────────────────────
COUNTRY_WINDOWS: dict[str, List[Tuple[Tuple[Tuple[int, int], Tuple[int, int]], str]]] = {
    # United States 🇺🇸
    "US": [
        (((1,  1), (2, 14)),  "winter_dump"),            # Jan–mid‑Feb
        (((2, 15), (3, 15)),  "presidents_window"),
        (((5,  1), (5, 31)),  "memorial_lead"),          # incl. early summer kicks
        (((5, 25), (8, 15)),  "summer_blockbuster"),
        (((8, 25), (9, 10)),  "labor_day"),
        (((11,20), (11,30)),  "thanksgiving"),
        (((12,15), (12,31)),  "christmas_awards"),
    ],

    # Canada 🇨🇦
    "CA": [
        (((6, 15), (8, 31)),  "summer"),
        (((10, 5), (10,15)),  "thanksgiving_ca"),
        (((12,15), (12,31)),  "christmas"),
    ],

    # United Kingdom 🇬🇧
    "GB": [
        (((2, 10), (2, 28)),  "half_term_feb"),
        (((3, 25), (4, 25)),  "easter"),
        (((5, 20), (6, 10)),  "half_term_may"),
        (((7, 10), (8, 31)),  "school_summer"),
        (((10,15), (10,31)),  "half_term_oct"),
        (((12,15), (12,31)),  "christmas"),
    ],

    # Germany 🇩🇪
    "DE": [
        (((3, 20), (4, 20)),  "osterferien"),
        (((6, 20), (9, 10)),  "sommerferien_de"),
        (((10, 1), (10,15)),  "herbstferien"),
        (((12,20), (12,31)),  "weihnachten"),
    ],

    # France 🇫🇷
    "FR": [
        (((2,  5), (3, 10)),  "vacances_hiver"),
        (((4,  5), (5,  5)),  "vacances_printemps"),
        (((7,  1), (8, 31)),  "vacances_ete"),
        (((10,15), (11, 5)),  "vacances_toussaint"),
        (((12,15), (12,31)),  "vacances_noel"),
    ],

    # Italy 🇮🇹
    "IT": [
        (((4, 10), (4, 30)),  "pasqua"),
        (((8,  1), (8, 31)),  "ferragosto"),
        (((12,20), (12,31)),  "natale"),
    ],

    # Spain 🇪🇸
    "ES": [
        (((4,  1), (4, 15)),  "semana_santa"),
        (((6, 20), (8, 31)),  "verano"),
        (((12,20), (1,  6)),  "navidad_reyes"),
    ],

    # Russia 🇷🇺
    "RU": [
        (((1,  1), (1, 10)),  "new_year_rus"),
        (((3,  5), (3, 15)),  "womens_day"),
        (((5,  1), (5, 10)),  "may_holidays"),
        (((12,25), (1,  8)),  "winter_fest"),
    ],

    # Turkey 🇹🇷
    "TR": [
        (((4,  1), (4, 30)),  "ramadan_bayram"),
        (((7,  1), (8, 10)),  "sacrifice_bayram"),
        (((10,25), (11,10)),  "republic_day"),
    ],

    # Brazil 🇧🇷
    "BR": [
        (((2,  5), (3,  5)),  "carnaval"),
        (((6, 10), (7, 31)),  "winter_break_br"),
        (((12,20), (12,31)),  "natal"),
    ],

    # Mexico 🇲🇽
    "MX": [
        (((9, 10), (9, 20)),  "independencia"),
        (((10,25), (11, 5)),  "dia_de_muertos"),
        (((12,12), (12,31)),  "navidad"),
    ],

    # Argentina 🇦🇷
    "AR": [
        (((7, 10), (7, 31)),  "winter_vac_ar"),
        (((12,20), (1, 10)), "summer_ar"),
    ],

    # Colombia 🇨🇴
    "CO": [
        (((6, 15), (7, 15)),  "mitad_de_ano"),
        (((12,15), (1, 15)),  "navidad"),
    ],

    # Chile 🇨🇱
    "CL": [
        (((7,  1), (7, 28)),  "vacaciones_invierno"),
        (((9, 10), (9, 25)),  "fiestas_patrias"),
        (((12,15), (1, 15)),  "verano_cl"),
    ],

    # China 🇨🇳
    "CN": [
        (((1, 15), (2, 20)),  "spring_festival"),
        (((4,  3), (4, 10)),  "qingming"),
        (((6,  1), (6, 30)),  "dragon_boat"),
        (((9,  1), (10,10)), "golden_week_autumn"),
    ],

    # Japan 🇯🇵
    "JP": [
        (((4, 29), (5,  6)), "golden_week"),
        (((8, 10), (8, 20)), "obon"),
        (((12,23), (1,  7)), "year_end"),
    ],

    # South Korea 🇰🇷
    "KR": [
        (((1, 20), (2, 10)),  "seollal"),
        (((5,  1), (5, 10)),  "children_day"),
        (((7, 20), (8, 20)),  "summer_peak"),
        (((9,  5), (10,10)),  "chuseok"),
    ],

    # India 🇮🇳
    "IN": [
        (((8, 10), (8, 25)),  "independence_window"),
        (((10,15), (11,15)), "diwali"),
        (((12,20), (1,  5)), "christmas_newyear"),
    ],

    # Thailand 🇹🇭
    "TH": [
        (((4, 10), (4, 20)),  "songkran"),
        (((12,20), (1,  5)),  "new_year_th"),
    ],

    # Philippines 🇵🇭
    "PH": [
        (((4,  5), (4, 25)),  "holy_week"),
        (((12,15), (12,31)),  "christmas_ph"),
    ],

    # Indonesia 🇮🇩
    "ID": [
        (((4,  1), (4, 30)),  "eid_al_fitr"),
        (((12,20), (1, 10)), "year_end_id"),
    ],

    # Nigeria 🇳🇬
    "NG": [
        (((3, 25), (4, 25)),  "easter_ng"),
        (((6,  1), (6, 30)),  "eid_al_adha"),
        (((12,20), (1, 10)), "christmas_ng"),
    ],

    # South Africa 🇿🇦
    "ZA": [
        (((4,  1), (4, 25)),  "easter_za"),
        (((12, 1), (1, 10)),  "summer_holidays_za"),
    ],

    # Saudi Arabia 🇸🇦
    "SA": [
        (((3, 25), (4, 30)),  "eid_fitr_sa"),
        (((6, 10), (7, 10)),  "eid_adha_sa"),
        (((9, 20), (9, 30)),  "national_day_sa"),
    ],

    # United Arab Emirates 🇦🇪
    "AE": [
        (((3, 25), (4, 30)), "eid_fitr_ae"),
        (((6, 10), (7, 10)), "eid_adha_ae"),
        (((11,20), (12, 5)), "national_day_ae"),
    ],

    # Egypt 🇪🇬
    "EG": [
        (((3, 25), (4, 25)),  "sham_el_nessim"),
        (((6, 20), (7, 20)),  "eid_adha_eg"),
        (((1,  1), (1, 10)),  "christmas_copt"),
    ],

    # Sweden 🇸🇪
    "SE": [
        (((2, 15), (3, 10)),  "sportlov"),
        (((6, 15), (8, 15)),  "sommar"),
        (((12,20), (1,  5)), "jul"),
    ],
    
    # Norway 🇳🇴
    "NO": [
        (((2, 15), (3,  5)), "winter_break_no"),  # vinterferie weeks 8–9
        (((6, 20), (8, 15)), "summer_no"),
        (((12,15), (12,31)), "jul_no"),
    ],
    # Denmark 🇩🇰
    "DK": [
        (((2,  5), (2, 20)), "winter_break_dk"),
        (((6, 25), (8, 10)), "summer_dk"),
        (((10,15), (10,25)), "autumn_break_dk"),  # uge 42
        (((12,15), (12,31)), "jul_dk"),
    ],
    # Finland 🇫🇮
    "FI": [
        (((2, 20), (3, 10)), "ski_break_fi"),
        (((6,  5), (8, 10)), "kesaloma"),
        (((12,20), (1,  5)), "joulu_fi"),
    ],
    # Poland 🇵🇱
    "PL": [
        (((1, 15), (2, 28)), "ferie_zimowe"),
        (((4,  1), (4, 15)), "wielkanoc"),
        (((5,  1), (5,  5)), "majowka"),
        (((6, 25), (8, 31)), "wakacje"),
        (((12,20), (12,31)), "boze_narodzenie"),
    ],
    # Vietnam 🇻🇳
    "VN": [
        (((1, 15), (2, 15)), "tet"),
        (((4, 28), (5,  3)), "reunification"),
        (((9,  1), (9,  5)), "national_day_vn"),
    ],
    # Taiwan 🇹🇼
    "TW": [
        (((1, 20), (2, 10)), "lunar_new_year_tw"),
        (((6,  1), (6, 10)), "dragon_boat_tw"),
        (((9, 15), (10,10)), "mid_autumn_tw"),
        (((7,  1), (8, 31)), "summer_tw"),
    ],
}

_LETTER_TO_AGE = {
    "G": 0, "U": 0, "L": 0, "A": 0, "AA": 0, "ATP": 0, "TE": 0, "TP": 0,
    "PG": 8, "P": 8, "PG-13": 13, "PG12": 12, "PG15": 15,
    "M": 15, "B-15": 15, "R": 17, "C": 18, "D": 18, "X": 18,
    "NC-17": 17, "R15+": 15, "R18+": 18,
    "MA 15+": 15, "MA": 15, "16": 16, "18": 18, "20": 20, "21+": 21,
}
_DEF_ADULT_AGE = 18  # default if everything fails
RATING_SCHEMES: Dict[str, Dict[str, Any]] = {
    # North America
    "US": {"body": "MPA", "levels": ["G", "PG", "PG-13", "R", "NC-17"], "adult_cutoff": "NC-17"},
    "CA": {"body": "Consumer Protection BC / Régie", "levels": ["G", "PG", "14A", "18A", "R"], "adult_cutoff": "R"},
    
    # Europe ‑ Anglosphere
    "GB": {"body": "BBFC", "levels": ["U", "PG", "12A", "15", "18"], "adult_cutoff": "18"},
    "IE": {"body": "IFCO", "levels": ["G", "PG", "12A", "15A", "16", "18"], "adult_cutoff": "18"},

    # Scandinavia
    "SE": {"body": "Statens Medieråd", "levels": ["A", "7", "11", "15"], "adult_cutoff": "15"},
    "NO": {"body": "Medietilsynet", "levels": ["A", "6", "9", "12", "15", "18"], "adult_cutoff": "18"},
    "DK": {"body": "Medierådet", "levels": ["A", "7", "11", "15"], "adult_cutoff": "15"},
    "FI": {"body": "KAVI", "levels": ["S", "7", "12", "16", "18"], "adult_cutoff": "18"},

    # Western / Central Europe
    "DE": {"body": "FSK", "levels": ["0", "6", "12", "16", "18"], "adult_cutoff": "18"},
    "FR": {"body": "CNC Visa", "levels": ["U", "10", "12", "16", "18"], "adult_cutoff": "18"},
    "IT": {"body": "DGCA", "levels": ["T", "12", "14", "18"], "adult_cutoff": "18"},
    "ES": {"body": "ICAA", "levels": ["APT", "7", "12", "16", "18"], "adult_cutoff": "18"},
    "PL": {"body": "PISF", "levels": ["G", "12", "15", "18"], "adult_cutoff": "18"},

    # Russia & CIS
    "RU": {"body": "Min. Culture", "levels": ["0+", "6+", "12+", "16+", "18+"], "adult_cutoff": "18+"},

    # Middle East & North Africa
    "SA": {"body": "GCAM", "levels": ["G", "PG", "PG12", "PG15", "18"], "adult_cutoff": "18"},
    "AE": {"body": "UAE Media Office", "levels": ["G", "PG13", "PG15", "15+", "18", "21"], "adult_cutoff": "18"},
    "EG": {"body": "Censorship Authority", "levels": ["General", "12+", "16+", "18+"], "adult_cutoff": "18+"},
    "TR": {"body": "MoC Kültür", "levels": ["Genel", "6+", "10+", "13+", "16+", "18+"], "adult_cutoff": "18+"},

    # Asia‑Pacific
    "JP": {"body": "EIRIN", "levels": ["G", "PG12", "R15+", "R18+"], "adult_cutoff": "R18+"},
    "KR": {"body": "KMRB", "levels": ["ALL", "12", "15", "18", "Restricted"], "adult_cutoff": "18"},
    "CN": {"body": "SAPPRFT (Cut)", "levels": ["Not Rated"], "adult_cutoff": "Not Rated"},
    "IN": {"body": "CBFC", "levels": ["U", "UA", "A", "S"], "adult_cutoff": "A"},
    "TH": {"body": "NBTC", "levels": ["G", "P", "13", "15", "18", "20"], "adult_cutoff": "18"},
    "PH": {"body": "MTRCB", "levels": ["G", "PG", "R‑13", "R‑16", "R‑18", "X"], "adult_cutoff": "R‑18"},
    "ID": {"body": "LSF", "levels": ["SU", "13+", "17+", "21+"], "adult_cutoff": "21+"},
    "VN": {"body": "DPRA", "levels": ["P", "C13", "T16", "T18"], "adult_cutoff": "T18"},
    "TW": {"body": "Govie Rating", "levels": ["G", "P", "PG12", "PG15", "R"], "adult_cutoff": "R"},

    # Latin America
    "BR": {"body": "DJCTQ", "levels": ["L", "10", "12", "14", "16", "18"], "adult_cutoff": "18"},
    "MX": {"body": "RTC", "levels": ["AA", "A", "B", "B‑15", "C", "D"], "adult_cutoff": "C"},
    "AR": {"body": "INCAA", "levels": ["ATP", "13", "16", "18"], "adult_cutoff": "18"},
    "CO": {"body": "MinTIC", "levels": ["TP", "12", "15", "18"], "adult_cutoff": "18"},
    "CL": {"body": "Consejo Cine", "levels": ["TE", "7", "14", "18"], "adult_cutoff": "18"},

    # Africa
    "NG": {"body": "NFVCB", "levels": ["G", "PG", "12", "15", "18"], "adult_cutoff": "18"},
    "ZA": {"body": "FPB", "levels": ["A", "PG", "7‑9PG", "10‑12PG", "13", "16", "18", "X18"], "adult_cutoff": "18"},}


def rating_min_age(country: str, symbol: str) -> int | None:
    """Return the minimum recommended age implied by *symbol* in *country*.

    If digits appear in the symbol → first digit group.
    Else fallback to _LETTER_TO_AGE.
    If still unknown → None.
    """
    s = symbol.upper().strip()
    m = re.search(r"\d+", s)
    if m:
        return int(m.group(0))
    return _LETTER_TO_AGE.get(s)


def rating_to_age_group(country: str, symbol: str) -> str:
    """Map a local rating symbol to broad buckets: all_ages, kids, teen, adult."""
    age = rating_min_age(country, symbol)
    if age is None:
        # fall back to adult_cutoff from scheme if available
        scheme = RATING_SCHEMES.get(country.upper())
        if scheme and symbol == scheme.get("adult_cutoff"):
            return "adult"
        return "unknown"
    if age < 7:
        return "all_ages"
    if age < 13:
        return "kids"
    if age < 17:
        return "teen"
    return "adult"
SEASONS_NORTH = ("winter", "spring", "summer", "fall")
SEASONS_SOUTH = ("summer", "fall", "winter", "spring")
SOUTH_HEMI = {"AU", "NZ", "ZA", "AR", "CL", "UY"}