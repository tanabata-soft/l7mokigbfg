// Print TSV rows for lockfile entries not yet at the locked version:
// path \t version \t integrity \t resolved \t cacache-content-path
const fs = require('fs');
const l = require(process.cwd() + '/package-lock.json');
const CACHE = '/home/hatch/.npm/_cacache';
for (const [p, pkg] of Object.entries(l.packages)) {
  if (!p || !pkg.version || !pkg.integrity) continue;
  let cur = null;
  try {
    cur = JSON.parse(fs.readFileSync(p + '/package.json', 'utf8')).version;
  } catch (e) {}
  if (cur === pkg.version) continue;
  const idx = pkg.integrity.indexOf('-');
  const algo = pkg.integrity.slice(0, idx);
  const hex = Buffer.from(pkg.integrity.slice(idx + 1), 'base64').toString('hex');
  const cpath =
    CACHE + '/content-v2/' + algo + '/' + hex.slice(0, 2) + '/' + hex.slice(2, 4) + '/' + hex.slice(4);
  console.log([p, pkg.version, pkg.integrity, pkg.resolved || '', cpath].join('\t'));
}
