const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');

// 1. Load and enrich productsData.js
const prodDataPath = path.join(baseDir, 'js', 'productsData.js');
let content = fs.readFileSync(prodDataPath, 'utf-8');
const dataStr = content.replace(/^(?:const|var)\s+PRODUCTS_DATA\s*=\s*(?:window\.PRODUCTS_DATA\s*=\s*)?/, '').replace(/;\s*$/, '');
const data = JSON.parse(dataStr);

function parsePrice(val) {
  if (typeof val === 'number') return val;
  if (!val) return 0;
  const num = parseInt(String(val).replace(/[^\d]/g, ''), 10);
  return isNaN(num) ? 0 : num;
}

const BRANDS = [
  'ROYAL ROBBINS', 'BEBEDEPINO', 'BEBE DE PINO', 'PUMA', 'NIKE', 'ADIDAS', 'ARENA', 
  'LAND ROVER', 'WEGO', 'COVERNAT', 'ROXY', 'SALTY CREW', 'UNDER ARMOUR', 'CHAMPION', 
  'PATAGONIA', 'COLUMBIA', 'NORTH FACE', 'THE NORTH FACE', 'LEVIS', 'LEVI\'S', 'UNIQLO', 
  'ZARA', 'GAP', 'PGA', 'FREE ASSEMBLY', 'ISENBERG', 'TJO', 'HOLDEN', 'QUIKSILVER', 
  'BILLABONG', 'VOLCOM', 'O\'NEILL', 'OAKLEY', 'MLB', 'NEW BALANCE', 'FILA', 'REEBOK',
  'ASICS', 'MIZUNO', 'DESCENTE', 'LACOSTE', 'TOMMY', 'CALVIN KLEIN', 'CK'
];

function extractBrandAndBadge(name, isSale, salePrice, regularPrice) {
  const upperName = (name || '').toUpperCase();
  for (const b of BRANDS) {
    if (upperName.includes(b)) {
      const cleanB = b === 'BEBE DE PINO' ? 'BEBEDEPINO' : b;
      return { 
        badge: cleanB, 
        badgeColor: 'bg-slate-950 text-white shadow-sm' 
      };
    }
  }
  
  if (salePrice === 99000 || (salePrice >= 90000 && salePrice <= 99000)) {
    return { badge: '🏷️ 99K', badgeColor: 'bg-red-600 text-white shadow-sm' };
  }
  if (salePrice === 199000 || (salePrice >= 190000 && salePrice <= 199000)) {
    return { badge: '🏷️ 199K', badgeColor: 'bg-orange-600 text-white shadow-sm' };
  }
  if (salePrice === 299000 || (salePrice >= 290000 && salePrice <= 299000)) {
    return { badge: '💎 299K', badgeColor: 'bg-purple-600 text-white shadow-sm' };
  }

  if (isSale && regularPrice && regularPrice > salePrice) {
    const discount = Math.round(((regularPrice - salePrice) / regularPrice) * 100);
    if (discount >= 40) {
      return { 
        badge: `⚡ GIẢM ${discount}%`, 
        badgeColor: 'bg-red-600 text-white shadow-sm' 
      };
    }
    if (discount >= 20) {
      return { 
        badge: `🔥 GIẢM ${discount}%`, 
        badgeColor: 'bg-orange-600 text-white shadow-sm' 
      };
    }
    return { 
      badge: `✨ GIẢM ${discount}%`, 
      badgeColor: 'bg-amber-600 text-white shadow-sm' 
    };
  }
  
  return { 
    badge: 'CHÍNH HÃNG', 
    badgeColor: 'bg-slate-950 text-white shadow-sm' 
  };
}

let count = 0;
for (const [pid, p] of Object.entries(data)) {
  const name = (p.name || '').toLowerCase();
  const salePrice = p.salePriceNum || parsePrice(p.price) || 0;
  const regPrice = p.regularPriceNum || parsePrice(p.originalPrice) || 0;
  const discount = (regPrice > 0 && regPrice > salePrice) ? Math.round(((regPrice - salePrice) / regPrice) * 100) : 0;
  const isSale = p.isSale || discount > 0;

  const cats = new Set();
  cats.add('all');

  // 1. Phân loại theo Giới tính / Loại hình
  // Trẻ em
  const isKid = name.includes('kid') || name.includes('kids') || name.includes('junior') || 
                name.includes('baby') || name.includes('bé') || name.includes('trẻ em') || 
                name.includes('bebedepino') || name.includes('bebe de pino') || 
                name.includes('child') || name.includes('toddler') || name.includes('infant');
  if (isKid) {
    cats.add('treem');
  }

  // Phụ kiện / Outdoor
  const isAccessory = name.includes('mũ') || name.includes('nón') || name.includes('túi') || 
                      name.includes('balo') || name.includes('găng') || name.includes('glove') || 
                      name.includes('tất') || name.includes('vớ') || name.includes('kính') || 
                      name.includes('khăn') || name.includes('belt') || name.includes('hat') || 
                      name.includes('cap') || name.includes('bag') || name.includes('pouch');
  if (isAccessory) {
    cats.add('phukien');
  }

  // Nữ
  const isWomen = name.includes('nữ') || name.includes('women') || name.includes('váy') || 
                  name.includes('đầm') || name.includes('swimsuit') || name.includes('bikini') || 
                  name.includes('crop') || name.includes('bra') || name.includes('legging') || 
                  name.includes('chân váy') || name.includes('skirt') || name.includes('dress') ||
                  name.includes(' mulawear ') || name.includes(' andar ') ||
                  name.includes(' f -') || name.includes(' 0526 f') || name.includes(' 0325 f');
  if (isWomen && !isKid) {
    cats.add('nu');
  }

  // Nam
  const isMen = name.includes('nam') || name.includes('men') || name.includes(' m -') || 
                name.includes(' 0426 m') || name.includes(' 1025 m') || name.includes(' 0824 m') ||
                name.includes(' 0522 m') || name.includes(' 0525 m') || name.includes(' 0126 m');
  if (!isKid && !isAccessory && (isMen || !cats.has('nu'))) {
    cats.add('nam');
  }

  // 2. Mức giá Đồng giá
  if (salePrice === 99000 || (salePrice >= 90000 && salePrice <= 99000)) {
    cats.add('donggia_99k');
    cats.add('price_under_200');
  }
  if (salePrice === 199000 || (salePrice >= 190000 && salePrice <= 199000)) {
    cats.add('donggia_199k');
    cats.add('price_under_200');
  }
  if (salePrice === 299000 || (salePrice >= 290000 && salePrice <= 299000)) {
    cats.add('donggia_299k');
    cats.add('price_200_350');
  }
  if (salePrice > 0 && salePrice <= 200000) {
    cats.add('price_under_200');
  }
  if (salePrice >= 200000 && salePrice <= 350000) {
    cats.add('price_200_350');
  }

  // 3. Mức Giảm giá Sale
  if (isSale) {
    cats.add('sale');
  }
  if (discount >= 40 || (p.badge && p.badge.includes('50%'))) {
    cats.add('sale_50');
    cats.add('sale');
  } else if (discount >= 20 || (p.badge && p.badge.includes('30%'))) {
    cats.add('sale_30');
    cats.add('sale');
  } else if (discount >= 8 || (p.badge && p.badge.includes('10%'))) {
    cats.add('sale_10');
    cats.add('sale');
  }

  p.categories = Array.from(cats);
  p.category = p.categories.find(c => ['nam', 'nu', 'treem', 'phukien'].includes(c)) || 'nam';

  const { badge, badgeColor } = extractBrandAndBadge(p.name, isSale, salePrice, regPrice);
  p.badge = badge;
  p.badgeColor = badgeColor;

  count++;
}

fs.writeFileSync(prodDataPath, 'var PRODUCTS_DATA = window.PRODUCTS_DATA = ' + JSON.stringify(data, null, 2) + ';\n', 'utf-8');
console.log(`Updated ${count} products in productsData.js with multi-catalog tags.`);
