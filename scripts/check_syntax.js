const fs = require('fs');
const vm = require('vm');
const path = require('path');

const html = fs.readFileSync(path.resolve(__dirname, '../index.html'), 'utf-8');
const sIdx = html.indexOf('<script src="js/productsData.js"></script>');
const scriptStart = html.indexOf('<script>', sIdx) + '<script>'.length;
const scriptEnd = html.indexOf('</script>', scriptStart);
const code = html.substring(scriptStart, scriptEnd);

try {
  new vm.Script(code, { filename: 'inline-script.js' });
  console.log('SUCCESS: inline-script.js compiled 100% with NO syntax errors!');
} catch (e) {
  console.error('FAILED:', e.message);
  process.exit(1);
}
