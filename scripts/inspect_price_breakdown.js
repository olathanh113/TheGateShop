const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');
const prodDataPath = path.join(baseDir, 'js', 'productsData.js');
let content = fs.readFileSync(prodDataPath, 'utf-8');
const dataStr = content.replace(/^const\s+PRODUCTS_DATA\s*=\s*/, '').replace(/;\s*$/, '');
const data = JSON.parse(dataStr);

const products = Object.values(data);

let countUnder100k = 0;
let count100kTo200k = 0;
let count200kTo300k = 0;
let count300kTo400k = 0;
let countOver400k = 0;

products.forEach(p => {
  const pr = p.salePriceNum || 0;
  if (pr < 100000) countUnder100k++;
  else if (pr <= 200000) count100kTo200k++;
  else if (pr <= 300000) count200kTo300k++;
  else if (pr <= 400000) count300kTo400k++;
  else countOver400k++;
});

console.log('Price Breakdown:');
console.log(' - Under 100K (99K deal):', countUnder100k);
console.log(' - 100K - 200K (199K deal):', count100kTo200k);
console.log(' - 200K - 300K (299K deal):', count200kTo300k);
console.log(' - 300K - 400K:', count300kTo400k);
console.log(' - Over 400K:', countOver400k);
