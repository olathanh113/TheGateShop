const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');

// 1. Read productsData.js
const prodDataPath = path.join(baseDir, 'js', 'productsData.js');
let content = fs.readFileSync(prodDataPath, 'utf-8');
const dataStr = content.replace(/^const\s+PRODUCTS_DATA\s*=\s*/, '').replace(/;\s*$/, '');
const data = JSON.parse(dataStr);

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
  let badgeColor = 'bg-slate-900 text-white';
  if (badge === 'BÁN CHẠY') badgeColor = 'bg-orange-600 text-white';
  else if (badge.includes('SALE') || badge.includes('GIẢM')) badgeColor = 'bg-red-600 text-white';

  const badgeHtml = badge ? `<span class="absolute top-2.5 left-2.5 z-10 px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-wider ${badgeColor}">${badge}</span>` : '';
  const origHtml = origPrice ? `<span class="text-xs text-slate-400 line-through font-normal">${origPrice}</span>` : '';
  const priceNum = parseNumericPrice(price);
  const reviewCount = p.reviewCount || 50;

  const card = `          <article class="product-card group relative rounded-2xl bg-white border border-slate-200/90 shadow-sm hover:shadow-md transition-all duration-300 flex flex-col p-3.5 sm:p-4" data-id="${pid}" data-category="${category}" data-price="${priceNum}">
            <div class="product-card__image-wrapper relative aspect-square w-full rounded-xl overflow-hidden bg-slate-100 flex items-center justify-center mb-3">
              ${badgeHtml}
              <img class="product-card__image w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" src="${mainImg}" alt="${name} - The Gate VNXK" loading="lazy" width="400" height="400" />
              <div class="absolute bottom-2 inset-x-0 flex items-center justify-center gap-1 z-10">
                <span class="w-3.5 h-1 rounded-full bg-orange-600"></span>
                <span class="w-1 h-1 rounded-full bg-slate-300"></span>
                <span class="w-1 h-1 rounded-full bg-slate-300"></span>
                <span class="w-1 h-1 rounded-full bg-slate-300"></span>
              </div>
            </div>
            <div class="product-card__body flex flex-col flex-grow">
              <span class="text-[11px] font-bold text-orange-600 block uppercase mb-1">MÃ: ${code}</span>
              <h3 class="product-card__name font-bold text-slate-900 text-sm sm:text-base leading-snug line-clamp-2 min-h-[2.75rem] mb-1.5 group-hover:text-orange-600 transition-colors" title="${name}">${name}</h3>
              <div class="flex items-center gap-1 text-xs text-amber-400 mb-2">
                <span>★★★★★</span>
                <span class="text-slate-400 font-normal">(${reviewCount})</span>
              </div>
              <div class="product-card__prices flex items-baseline gap-2 mb-3 mt-auto">
                <span class="product-card__price font-extrabold text-orange-600 text-base sm:text-lg">${price}</span>
                ${origHtml}
              </div>
              <button type="button" onclick="openEnhancedProductModal('${pid}')" class="w-full py-2.5 px-3 rounded-xl bg-orange-600 hover:bg-orange-700 active:scale-95 text-white font-bold text-xs sm:text-sm shadow hover:shadow-orange-500/25 flex items-center justify-center gap-1.5 transition-all mt-auto cursor-pointer">
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

// 3. Clean and replace Section 5 in index.html
const indexPath = path.join(baseDir, 'index.html');
let html = fs.readFileSync(indexPath, 'utf-8');
const isCRLF = html.includes('\r\n');
html = html.replace(/\r\n/g, '\n');

// Find section 5
const sec5Start = html.indexOf('<section class="py-12 sm:py-16 px-4 sm:px-6 bg-slate-50/80');
const fallbackSec5Start = html.indexOf('id="featured"');

let sIndex = sec5Start !== -1 ? sec5Start : html.lastIndexOf('<section', fallbackSec5Start);
const nextSectionMarker = '<!-- Dark Banner "The Gate Outdoor & Sportswear" -->';
const nextSecIdx = html.indexOf(nextSectionMarker);

if (sIndex === -1 || nextSecIdx === -1) {
  console.error('Indices not found:', sIndex, nextSecIdx);
  process.exit(1);
}

const lastSectionClose = html.lastIndexOf('</section>', nextSecIdx);
const eIndex = lastSectionClose + '</section>'.length;

const newSec5 = `<section class="py-12 sm:py-16 px-4 sm:px-6 bg-slate-50/80 border-t border-slate-200" id="featured" aria-label="Sản phẩm nổi bật">
      <div class="max-w-7xl mx-auto">

        <!-- Filter Tabs Header exactly matching Image 2 -->
        <div class="flex items-center gap-2 mb-6 sm:mb-8 max-w-full">
          <!-- Nút điều hướng Trái -->
          <button type="button" onclick="scrollTabsNav(-1)" class="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-white text-slate-700 border border-slate-200 shadow-sm hover:bg-orange-600 hover:text-white hover:border-orange-600 active:scale-95 transition-all flex items-center justify-center shrink-0 cursor-pointer" title="Cuộn sang trái" aria-label="Cuộn sang trái">
            <i data-lucide="chevron-left" class="w-4 h-4"></i>
          </button>

          <!-- Filter Tabs List -->
          <div class="flex overflow-x-auto no-scrollbar whitespace-nowrap gap-2 py-1 scroll-smooth flex-grow" id="filterTabs">
            <button onclick="setActiveFilterTab('all')" class="px-5 py-2 rounded-full text-xs font-bold transition-all bg-orange-600 text-white shadow-sm filter-tab-btn shrink-0 flex items-center gap-1.5 active-tab" data-category="all">Tất cả sản phẩm</button>
            <button onclick="setActiveFilterTab('sale')" class="px-4 py-2 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-orange-50 filter-tab-btn shrink-0 flex items-center gap-1.5" data-category="sale">
              <span class="text-red-500">🔥</span> <span>SĂN SALE GIẢM SÂU</span>
            </button>
            <button onclick="setActiveFilterTab('sale_50')" class="px-4 py-2 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-red-50 filter-tab-btn shrink-0 flex items-center gap-1.5" data-category="sale_50">
              <span class="text-amber-500">⚡</span> <span>Giảm 40% - 50%</span>
            </button>
            <button onclick="setActiveFilterTab('nam')" class="px-4 py-2 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 filter-tab-btn shrink-0 flex items-center gap-1.5" data-category="nam">Đồ Nam</button>
            <button onclick="setActiveFilterTab('nu')" class="px-4 py-2 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 filter-tab-btn shrink-0 flex items-center gap-1.5" data-category="nu">Đồ Nữ</button>
            <button onclick="setActiveFilterTab('phukien')" class="px-4 py-2 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 filter-tab-btn shrink-0 flex items-center gap-1.5" data-category="phukien">Outdoor & Phụ kiện</button>
            <button onclick="setActiveFilterTab('price_under_200')" class="px-4 py-2 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-amber-50 filter-tab-btn shrink-0 flex items-center gap-1.5" data-category="price_under_200">🏷️ Dưới 200K</button>
            <button onclick="setActiveFilterTab('price_200_350')" class="px-4 py-2 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-amber-50 filter-tab-btn shrink-0 flex items-center gap-1.5" data-category="price_200_350">🏷️ 200K - 350K</button>
            <button onclick="setActiveFilterTab('price_350_500')" class="px-4 py-2 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-amber-50 filter-tab-btn shrink-0 flex items-center gap-1.5" data-category="price_350_500">🏷️ 350K - 500K</button>
            <button onclick="setActiveFilterTab('price_over_500')" class="px-4 py-2 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-amber-50 filter-tab-btn shrink-0 flex items-center gap-1.5" data-category="price_over_500">🏷️ Trên 500K</button>
          </div>

          <!-- Nút điều hướng Phải -->
          <button type="button" onclick="scrollTabsNav(1)" class="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-white text-slate-700 border border-slate-200 shadow-sm hover:bg-orange-600 hover:text-white hover:border-orange-600 active:scale-95 transition-all flex items-center justify-center shrink-0 cursor-pointer" title="Cuộn sang phải" aria-label="Cuộn sang phải">
            <i data-lucide="chevron-right" class="w-4 h-4"></i>
          </button>
        </div>

        <!-- Products Grid Container: 4 columns desktop, 2 columns mobile exactly like Image 2 -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5 sm:gap-6" id="productsGridContainer">
${cardsHtml.join('\n')}
        </div>

        <!-- Dãy nút Phân trang Pagination -->
        <div class="flex flex-wrap items-center justify-center gap-2 mt-10 pt-6 border-t border-slate-200" id="paginationContainer"></div>
      </div>
    </section>`;

html = html.substring(0, sIndex) + newSec5 + html.substring(eIndex);

if (isCRLF) {
  html = html.replace(/\n/g, '\r\n');
}

fs.writeFileSync(indexPath, html, 'utf-8');
console.log('Successfully written clean single Section 5 to index.html!');
