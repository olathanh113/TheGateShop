const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf-8');

const sIdx = html.indexOf('<!-- ================================================================= -->\n    <!-- 5. DANH SÁCH SẢN PHẨM NỔI BẬT');
const eIdx = html.indexOf('<!-- Dark Banner "The Gate Outdoor & Sportswear" -->');

console.log('sIdx:', sIdx, 'eIdx:', eIdx);
console.log('Distance:', eIdx - sIdx);

const cards = fs.readFileSync('scripts/static_cards.html', 'utf-8');
const staticCardsList = cards.split('</article>').filter(c => c.trim().length > 0).map(c => c + '\n          </article>');
console.log('Actual static cards generated:', staticCardsList.length);
