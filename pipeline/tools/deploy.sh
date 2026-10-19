#!/usr/bin/env bash
# Pubblica site/ su GitHub Pages.
#
# Il sito sta alla RADICE del repo, non in una sottocartella: il sottodominio e' gia'
# tag.namstudio.it, quindi un /tag/ dentro sarebbe ripetuto. Un cliente = un repo = un
# sottodominio (GitHub Pages accetta un solo dominio custom per repo).
set -euo pipefail
cd "$(dirname "$0")/.."
# repo e dominio stanno in competitors.json, uno per cliente: cosi' lo stesso script
# serve tutti e non c'e' un default che pubblica sul repo sbagliato.
leggi() { python3 -c "import json;print((json.load(open('competitors.json')).get('cliente') or {}).get('$1',''))"; }
REPO="${REPO:-$(leggi repo)}"
DOMINIO="${DOMINIO:-$(leggi dominio)}"
[ -n "$REPO" ] && [ -n "$DOMINIO" ] || { echo "manca repo o dominio in competitors.json"; exit 1; }
WORK="${WORK:-$HOME/.deploy-$(basename "$REPO")}"

[ -d "site" ] || { echo "manca site/: lancia tools/build_site.py"; exit 1; }

if [ ! -d "$WORK/.git" ]; then
  mkdir -p "$WORK"
  git -C "$WORK" init -q -b main
  git -C "$WORK" remote add origin "https://github.com/$REPO.git"
fi

# si rimuove solo quello che pubblichiamo noi, mai .git e mai il CNAME
rm -rf "${WORK:?}/media" "${WORK:?}/v" "${WORK:?}/index.html" "${WORK:?}/tag"
cp -R site/. "$WORK/"
touch "$WORK/.nojekyll"
printf 'User-agent: *\nDisallow: /\n' > "$WORK/robots.txt"
# Il CNAME si riscrive a ogni giro: il push e' --force, e una volta che il file
# sparisce dal repo GitHub stacca il dominio custom senza dire niente.
printf '%s\n' "$DOMINIO" > "$WORK/CNAME"

# Da quando c'e' il giro settimanale in cloud, il repo non lo scrive piu' solo questo
# script: prima si allinea a quello che ha fatto l'automazione, altrimenti un push
# forzato da qui cancella il suo lavoro. E' lo stesso errore che ci e' costato il CNAME.
git -C "$WORK" fetch -q origin main || true
if git -C "$WORK" rev-parse --verify -q origin/main >/dev/null; then
  git -C "$WORK" stash -q -u 2>/dev/null || true
  git -C "$WORK" reset -q --hard origin/main
  git -C "$WORK" stash pop -q 2>/dev/null || true
  rm -rf "${WORK:?}/media" "${WORK:?}/v" "${WORK:?}/index.html"
  cp -R site/. "$WORK/"
  printf '%s\n' "$DOMINIO" > "$WORK/CNAME"
  printf 'User-agent: *\nDisallow: /\n' > "$WORK/robots.txt"
  touch "$WORK/.nojekyll"
fi

git -C "$WORK" add -A
git -C "$WORK" -c user.email="abbonamenti@namstudio.it" -c user.name="NAM Studio" \
    commit -q -m "Radar TAG — $(date +%Y-%m-%d)" || echo "niente da committare"
git -C "$WORK" push -q -u origin main --force-with-lease

echo "-> https://$DOMINIO/  (repo $REPO)"
