const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');
const prodDataPath = path.join(baseDir, 'js', 'productsData.js');
let content = fs.readFileSync(prodDataPath, 'utf-8');
const dataStr = content.replace(/^const\s+PRODUCTS_DATA\s*=\s*/, '').replace(/;\s*$/, '');
const data = JSON.parse(dataStr);

function detectCategory(name) {
  const n = (name || '').toLowerCase();
  
  // 1. Trẻ em
  if (
    n.includes('kid') || 
    n.includes('kids') || 
    n.includes('junior') || 
    n.includes('baby') || 
    n.includes('bé') || 
    n.includes('trẻ em') || 
    n.includes('bebedepino') || 
    n.includes('bebe de pino') || 
    n.includes('child') || 
    n.includes('toddler') || 
    n.includes('infant')
  ) {
    return 'treem';
  }
  
  // 2. Phụ kiện
  if (
    n.includes('mũ') || n.includes('nón') || n.includes('túi') || 
    n.includes('balo') || n.includes('găng') || n.includes('glove') || 
    n.includes('tất') || n.includes('vớ') || n.includes('kính') || 
    n.includes('khăn') || n.includes('belt') || n.includes('hat') || 
    n.includes('cap') || n.includes('bag')
  ) {
    return 'phukien';
  }
  
  // 3. Nữ
  if (
    n.includes('nữ') || n.includes('women') || n.includes('váy') || 
    n.includes('đầm') || n.includes('swimsuit') || n.includes('bikini') || 
    n.includes('crop') || n.includes('bra') || n.includes('legging') || 
    n.includes('chân váy') || n.includes('skirt') || n.includes('dress')
  ) {
    return 'nu';
  }
  
  return 'nam';
}

const counts = { treem: 0, nam: 0, nu: 0, phukien: 0 };
const sampleKids = [];

Object.values(data).forEach(p => {
  const cat = detectCategory(p.name);
  counts[cat]++;
  if (cat === 'treem' && sampleKids.length < 10) {
    sampleKids.push(`[${p.code}] ${p.name}`);
  }
});

console.log('Category breakdown with Đồ Trẻ Em:', counts);
console.log('\nSample Kids products:');
sampleKids.forEach(k => console.log(' -', k));
