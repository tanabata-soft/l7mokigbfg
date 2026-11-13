// Extract one package from the local npm cache via pacote (cache-only, no registry access needed).
// Usage: node extract-one.js <spec> <dest>
const pacote = require('/opt/hatch-image/bin/npm-package/node_modules/pacote');
const [spec, dest] = process.argv.slice(2);
pacote
  .extract(spec, dest, { cache: '/home/hatch/.npm', preferOffline: true })
  .then(() => console.log('OK', spec))
  .catch((e) => {
    console.error('FAIL', spec, e.code || '', String(e.message).split('\n')[0]);
    process.exit(1);
  });
