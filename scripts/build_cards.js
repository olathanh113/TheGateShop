const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');

// 1. Read and clean productsData.js
const prodDataPath = path.join(baseDir, 'js', 'productsData.js');
let content = fs.readFileSync(prodDataPath, 'utf-8');
const dataStr = content.replace(/^const\s+PRODUCTS_DATA\s*=\s*/, '').replace(/;\s*$/, '');
const data = JSON.parse(dataStr);

delete data['1001'];
delete data['1002'];
delete data['1003'];
delete data['1004'];
delete data['1005'];
delete data['1006'];

fs.writeFileSync(prodDataPath, 'const PRODUCTS_DATA = ' + JSON.stringify(data, null, 2) + ';\n', 'utf-8');

function parseNumericPrice(val) {
  if (typeof val === 'number') return val;
  if (!val) return 0;
  const num = parseInt(String(val).replace(/[^\d]/g, ''), 10);
  return isNaN(num) ? 0 : num;
}

// 2. Generate Static Cards HTML
const cardsHtml = [];

for (const [pid, p] of Object.entries(data)) {
  const imgs = p.images || [];
  if (!imgs.length) continue;

  const mainImg = imgs[0];
  const name = p.name || 'Sản phẩm The Gate';
  const category = p.category || 'all';
  const price = p.price || '299.000đ';
  const origPrice = p.originalPrice || '';
  const code = p.code || pid;
  const badge = p.badge || '';
  let badgeColor = p.badgeColor || 'bg-slate-900 text-white';
  if (badge === 'BÁN CHẠY') badgeColor = 'bg-orange-600 text-white';
  else if (badge.includes('SALE') || badge.includes('GIẢM')) badgeColor = 'bg-red-600 text-white';
  else if (!p.badgeColor) badgeColor = 'bg-slate-900 text-white';

  const badgeHtml = badge ? `<span class="absolute top-3 left-3 z-10 px-2.5 py-1 text-[11px] font-black rounded-lg uppercase tracking-wider shadow-sm ${badgeColor}">${badge}</span>` : '';
  const origHtml = origPrice ? `<span class="text-xs text-slate-400 line-through">${origPrice}</span>` : '';
  const priceNum = parseNumericPrice(price);

  const card = `          <article class="product-card group relative rounded-3xl overflow-hidden bg-white border border-slate-200/80 shadow-md hover:shadow-xl transition-all duration-300 flex flex-col w-[260px] shrink-0 snap-start lg:w-auto lg:shrink" data-id="${pid}" data-category="${category}" data-price="${priceNum}">
            <div class="product-card__image-wrapper relative aspect-square w-full overflow-hidden bg-slate-50 flex items-center justify-center">
              ${badgeHtml}
              <img class="product-card__image w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" src="${mainImg}" alt="${name} - The Gate VNXK" loading="lazy" width="400" height="400" />
              <div class="absolute bottom-2.5 inset-x-0 flex items-center justify-center gap-1 z-10">
                <span class="w-4 h-1.5 rounded-full bg-orange-600"></span>
                <span class="w-1.5 h-1.5 rounded-full bg-slate-300/80"></span>
                <span class="w-1.5 h-1.5 rounded-full bg-slate-300/80"></span>
                <span class="w-1.5 h-1.5 rounded-full bg-slate-300/80"></span>
              </div>
            </div>
            <div class="product-card__body p-4 sm:p-5 flex flex-col flex-grow">
              <span class="text-xs font-bold text-orange-600 block mb-1">MÃ: ${code}</span>
              <h3 class="product-card__name font-bold text-slate-900 text-sm sm:text-base mb-1.5 line-clamp-1 group-hover:text-orange-600 transition-colors" title="${name}">${name}</h3>
              <div class="product-card__prices flex items-baseline gap-2 mb-3 mt-auto">
                <span class="product-card__price font-extrabold text-orange-600 text-base sm:text-lg">${price}</span>
                ${origHtml}
              </div>
              <button type="button" onclick="openEnhancedProductModal('${pid}')" class="w-full py-2.5 px-3 rounded-xl bg-orange-600 hover:bg-orange-700 active:scale-95 text-white font-bold text-xs sm:text-sm shadow-md hover:shadow-orange-500/25 flex items-center justify-center gap-1.5 transition-all mt-auto cursor-pointer">
                <i data-lucide="tag" class="w-3.5 h-3.5 sm:w-4 sm:h-4"></i>
                <span>Xem Size, Màu & Tồn Kho</span>
              </button>
            </div>
          </article>`;

  cardsHtml.push(card);
}

const staticCardsPath = path.join(baseDir, 'scripts', 'static_cards.html');
fs.writeFileSync(staticCardsPath, cardsHtml.join('\n'), 'utf-8');
console.log(`Generated ${cardsHtml.length} static cards to ${staticCardsPath}`);
