const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');

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
        badgeClass: 'bg-slate-950 text-white shadow-md' 
      };
    }
  }
  
  if (isSale && regularPrice && regularPrice > salePrice) {
    const discount = Math.round(((regularPrice - salePrice) / regularPrice) * 100);
    if (discount >= 40) {
      return { 
        badge: `⚡ GIẢM ${discount}%`, 
        badgeClass: 'bg-red-600 text-white shadow-md' 
      };
    }
    return { 
      badge: `🔥 BÁN CHẠY`, 
      badgeClass: 'bg-orange-600 text-white shadow-md' 
    };
  }
  
  return { 
    badge: 'CHÍNH HÃNG', 
    badgeClass: 'bg-slate-950 text-white shadow-md' 
  };
}

function detectCategory(name) {
  const n = (name || '').toLowerCase();
  
  // 1. Trẻ em (Ưu tiên phân loại trước để không lẫn vào Đồ Nam / Đồ Nữ)
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
  
  // 4. Nam
  return 'nam';
}

function formatVND(num) {
  return new Intl.NumberFormat('vi-VN').format(num) + 'đ';
}

async function buildFullCatalog() {
  const urlCatalog = 'https://catalog-api-production-6f96.up.railway.app/v1/website/catalog';
  console.log('Fetching live catalog from Railway...');
  const res = await fetch(urlCatalog, { headers: { 'Accept': 'application/json' } });
  const data = await res.json();
  
  console.log(`Fetched ${data.items.length} items from Railway.`);
  
  const productsObj = {};
  
  data.items.forEach((it, idx) => {
    const pid = String(it.code || (idx + 1));
    const isSale = Boolean(it.is_sale && it.sale_price && it.regular_price && it.regular_price > it.sale_price);
    
    const displayPrice = isSale ? it.sale_price : (it.regular_price || it.price || it.sale_price || 299000);
    const displayOriginalPrice = isSale ? it.regular_price : null;
    
    const { badge, badgeClass } = extractBrandAndBadge(it.name, isSale, it.sale_price, it.regular_price);
    const category = detectCategory(it.name);
    
    productsObj[pid] = {
      id: pid,
      code: it.code || pid,
      name: it.name,
      category: category,
      price: formatVND(displayPrice),
      originalPrice: displayOriginalPrice ? formatVND(displayOriginalPrice) : '',
      salePriceNum: displayPrice,
      regularPriceNum: displayOriginalPrice,
      isSale: isSale,
      badge: badge,
      badgeColor: badgeClass,
      rating: 5,
      reviewCount: 30 + (idx % 70),
      images: it.images && it.images.length > 0 ? it.images : ['assets/images/products/product-01.svg'],
      availability: it.availability || {
        ton_that_thiep: 'in_stock',
        nguyen_trai: 'in_stock',
        tam_coc: 'in_stock'
      }
    };
  });
  
  const prodDataPath = path.join(baseDir, 'js', 'productsData.js');
  fs.writeFileSync(prodDataPath, 'const PRODUCTS_DATA = ' + JSON.stringify(productsObj, null, 2) + ';\n', 'utf-8');
  console.log(`Updated ${Object.keys(productsObj).length} products in js/productsData.js`);
}

buildFullCatalog().catch(console.error);
