#!/usr/bin/env python3
"""
verifica.py — controlla che ogni page_id in competitors.json sia davvero di chi dice.

Nasce da un errore vero: nel set di Butternut "Dog Heroes" puntava alla pagina di
un'influencer e il cliente aveva l'id di un concorrente. Un page_id sbagliato non da'
errore da nessuna parte: mette le inserzioni di qualcun altro nella riga di qualcuno,
e il numero sembra plausibile. Si controlla, non si assume.

    ~/tools/Scrapling/.venv/bin/python tools/verifica.py
    ... --correggi        ricerca il nome e sistema gli id che non tornano
"""
import argparse, os, re, sys, time, unicodedata
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adlib import api_get, load_competitors, save_competitors
from enrich_reach import load_key


def slug(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def chi_e(pid, key, paese="IT"):
    """
    Il nome vero della pagina e' quello che compare piu' spesso, non quello della prima
    inserzione: una parte degli annunci e' branded content e gira sull'account di un
    creator, quindi la prima puo' benissimo intestarsi a un'influencer. Leggendo solo
    quella il controllo dava per sbagliati id che erano giusti.
    """
    from collections import Counter
    d = api_get(f"company/ads?pageId={pid}&country={paese}&status=ACTIVE", key)
    res = d.get("results") or []
    nomi = Counter((r.get("snapshot") or {}).get("page_name")
                   for r in res if not (r.get("snapshot") or {}).get("branded_content"))
    if not nomi:
        nomi = Counter((r.get("snapshot") or {}).get("page_name") for r in res)
    nome = nomi.most_common(1)[0][0] if nomi else None
    return nome, d.get("searchResultsCount")


def cerca(nome, key):
    d = api_get(f"search/companies?query={quote(nome)}", key)
    want = slug(nome)
    for r in (d.get("searchResults") or []):
        n = slug(r.get("name"))
        if n == want or n.startswith(want + " ") or want.startswith(n + " "):
            return r["page_id"], r.get("name")
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--correggi", action="store_true")
    ap.add_argument("--paese", default="IT")
    a = ap.parse_args()
    key = load_key()
    if not key:
        sys.exit("SCRAPECREATORS_API_KEY non trovata")

    cfg = load_competitors()
    cli = cfg.get("cliente") or {}
    voci = [("_cliente", cli.get("nome_esteso") or cli.get("brand"), cli)]
    voci += [(c["slug"], c["nome"], c) for c in cfg["competitors"] if c.get("attivo", True)]

    visti, problemi, corretti = {}, 0, 0
    print(f"{'slug':20} {'atteso':26} {'pagina reale':26} esito")
    print("-" * 92)
    for slug_, nome, voce in voci:
        pid = voce.get("page_id")
        if not pid:
            print(f"{slug_:20} {(nome or '')[:25]:26} {'':26} page_id mancante")
            problemi += 1
            continue
        if pid in visti:
            print(f"{slug_:20} {(nome or '')[:25]:26} {'':26} ! stesso id di {visti[pid]}")
            problemi += 1
            if a.correggi and slug_ != "_cliente":
                voce["page_id"] = ""
            continue
        visti[pid] = slug_
        try:
            vero, quante = chi_e(pid, key, voce.get("mercato") or a.paese)
        except Exception as e:
            print(f"{slug_:20} {(nome or '')[:25]:26} {'':26} ! {type(e).__name__}")
            continue
        if vero is None:
            print(f"{slug_:20} {(nome or '')[:25]:26} {'(nessuna attiva)':26} non verificabile")
            continue
        ok = slug(vero).startswith(slug(nome)[:12]) or slug(nome).startswith(slug(vero)[:12])
        print(f"{slug_:20} {(nome or '')[:25]:26} {vero[:25]:26} "
              f"{'ok' if ok else '! NON CORRISPONDE'} ({quante})")
        if not ok:
            problemi += 1
            if a.correggi:
                nuovo, trovato = cerca(nome, key)
                if nuovo and nuovo not in visti:
                    voce["page_id"] = nuovo
                    visti[nuovo] = slug_
                    corretti += 1
                    print(f"{'':20} -> corretto in {nuovo} ({trovato})")
                else:
                    voce["page_id"] = ""
                    print(f"{'':20} -> non trovato, svuotato")
        time.sleep(0.25)

    if a.correggi:
        save_competitors(cfg)
    print(f"\n{problemi} problemi" +
          (f", {corretti} corretti" if a.correggi else " (rilancia con --correggi)"))


if __name__ == "__main__":
    main()
