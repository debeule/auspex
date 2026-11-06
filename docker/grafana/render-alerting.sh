#!/bin/sh
# Copies Grafana's provisioning tree and expands $VAR and ${VAR} in the alerting files from the
# environment; a doubled $$ becomes one literal $. Grafana 13 provisions alert rules without
# expanding them. With no arguments it renders the compose mounts and then starts Grafana.
set -eu

src=${1:-/etc/grafana/provisioning-src}
out=${2:-/tmp/provisioning}

rm -rf "$out"
mkdir -p "$out"
cp -R "$src"/. "$out"/

for f in "$out"/alerting/*.yaml; do
  [ -e "$f" ] || continue
  awk '
    function expand(s,    r, name, m) {
      r = ""
      while ((m = index(s, "$")) > 0) {
        r = r substr(s, 1, m - 1)
        s = substr(s, m + 1)
        if (match(s, /^\{[A-Za-z_][A-Za-z0-9_]*\}/)) {
          name = substr(s, 2, RLENGTH - 2)
        } else if (match(s, /^[A-Za-z_][A-Za-z0-9_]*/)) {
          name = substr(s, 1, RLENGTH)
        } else {
          r = r "$"
          continue
        }
        r = r ENVIRON[name]
        s = substr(s, RLENGTH + 1)
      }
      return r s
    }
    {
      line = $0
      res = ""
      while ((p = index(line, "$$")) > 0) {
        res = res expand(substr(line, 1, p - 1)) "$"
        line = substr(line, p + 2)
      }
      print res expand(line)
    }
  ' "$f" > "$f.tmp"
  mv "$f.tmp" "$f"
done

if [ $# -eq 0 ]; then
  exec /run.sh
fi
