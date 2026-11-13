#!/usr/bin/env bash
# Faithful lockfile install v4 (no intermediate files):
#  - rows streamed from gen-list.cjs (only entries not at the locked version)
#  - tarball bytes from npm cache content store (path from lockfile integrity), hash-verified,
#    extracted with GNU tar; fallback: curl the resolved URL
#  - rebuilds top-level .bin, audits the whole tree; prints "AUDIT ok: X bad: Y"
# Usage: install-v4.sh <project-dir>
set -u
DIR="$1"
cd "$DIR"
GEN="$HOME/workspace/.nk-test/gen-list.cjs"

fails=0; n=0
while IFS=$'\t' read -r path ver integrity url cpath; do
  [ -z "$path" ] && continue
  n=$((n+1))
  ok=0
  for attempt in 1 2 3; do
    rm -rf "$path"
    f=""
    if [ -f "$cpath" ]; then f="$cpath";
    else
      f="$HOME/workspace/.nk-test/dl-one.tgz"
      curl -sL --fail -o "$f" "$url" 2>/dev/null || { sleep 2; continue; }
    fi
    algo="${integrity%%-*}"; expect="${integrity#*-}"
    if [ "$algo" = "sha512" ]; then actual=$(openssl dgst -sha512 -binary "$f" | base64 -w0); else actual=$(openssl dgst -sha1 -binary "$f" | base64 -w0); fi
    if [ "$actual" != "$expect" ]; then sleep 1; continue; fi
    mkdir -p "$path"
    if tar -xzf "$f" -C "$path" --strip-components=1 2>/dev/null && [ -f "$path/package.json" ]; then ok=1; break; fi
    sleep 1
  done
  [ "$f" = "$HOME/workspace/.nk-test/dl-one.tgz" ] && rm -f "$f"
  if [ $ok -eq 0 ]; then echo "INSTALL FAIL: $path"; fails=$((fails+1)); fi
done < <(node "$GEN")
echo "install round done: $n attempted, fails=$fails"

node -e "
const fs=require('fs'), path=require('path');
const nm='node_modules';
if (!fs.existsSync(nm)) process.exit(0);
fs.mkdirSync(nm+'/.bin', {recursive:true});
let links=0;
for (const entry of fs.readdirSync(nm)) {
  if (entry==='.bin' || entry==='.package-lock.json') continue;
  const pkgs = entry.startsWith('@')
    ? fs.readdirSync(path.join(nm,entry)).map(s=>path.join(entry,s))
    : [entry];
  for (const rel of pkgs) {
    const pjPath = path.join(nm, rel, 'package.json');
    if (!fs.existsSync(pjPath)) continue;
    let pj; try { pj = JSON.parse(fs.readFileSync(pjPath,'utf8')); } catch(e) { continue; }
    if (!pj.bin) continue;
    const bins = typeof pj.bin==='string' ? {[pj.name.split('/').pop()]: pj.bin} : pj.bin;
    for (const [cmd, target] of Object.entries(bins)) {
      const linkPath = path.join(nm,'.bin',cmd);
      const targetPath = path.join(nm, rel, target);
      try { fs.unlinkSync(linkPath); } catch {}
      try { fs.symlinkSync(path.relative(path.join(nm,'.bin'), targetPath), linkPath); links++; } catch {}
      try { fs.chmodSync(targetPath, 0o755); } catch {}
    }
  }
}
console.log('bin links:', links);
"

node -e "
const l=require('./package-lock.json'); const fs=require('fs');
let ok=0; const bad=[];
for (const [p,pkg] of Object.entries(l.packages)) {
  if (!p) continue;
  try {
    const v=JSON.parse(fs.readFileSync(p+'/package.json','utf8')).version;
    if (v===pkg.version) ok++; else bad.push(p);
  } catch(e) { bad.push(p); }
}
console.log('AUDIT ok:', ok, 'bad:', bad.length);
"
