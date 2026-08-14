const fs = require('fs');

const pData = fs.readFileSync('js/productsData.js', 'utf-8');
const dataStr = pData.replace(/^(?:const|var)\s+PRODUCTS_DATA\s*=\s*(?:window\.PRODUCTS_DATA\s*=\s*)?/, '').replace(/;\s*$/, '');
const data = JSON.parse(dataStr);
console.log('Keys in productsData.js:', Object.keys(data).length);

const sCards = fs.readFileSync('scripts/static_cards.html', 'utf-8');
console.log('Cards in static_cards.html:', (sCards.match(/<article class="product-card\b/g) || []).length);

const html = fs.readFileSync('index.html', 'utf-8');
const sIdx = html.indexOf('id="productsGridContainer"');
const eIdx = html.indexOf('id="paginationContainer"');
const grid = html.substring(sIdx, eIdx);
console.log('Cards in productsGridContainer:', (grid.match(/<article class="product-card\b/g) || []).length);
