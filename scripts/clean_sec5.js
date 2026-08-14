const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');

// 1. Read productsData.js
const prodDataPath = path.join(baseDir, 'js', 'productsData.js');
let content = fs.readFileSync(prodDataPath, 'utf-8');
const dataStr = content.replace(/^(?:const|var)\s+PRODUCTS_DATA\s*=\s*(?:window\.PRODUCTS_DATA\s*=\s*)?/, '').replace(/;\s*$/, '');
const data = JSON.parse(dataStr);

const cardsHtml = [];
const allEntries = Object.entries(data);
const initialItems = allEntries.slice(0, 16);
const totalItems = allEntries.length;
const totalPages = Math.ceil(totalItems / 16);

for (const [pid, p] of initialItems) {
  const imgs = p.images || [];
  if (!imgs.length) continue;

  const mainImg = imgs[0];
  const name = p.name || 'Sản phẩm The Gate';
  const price = p.price || '299.000đ';
  const origPrice = p.originalPrice || '';
  const code = p.code || pid;
  const badge = p.badge || 'CHÍNH HÃNG';
  const badgeColor = p.badgeColor || 'bg-slate-950 text-white shadow-sm';

  const badgeHtml = badge ? `<span class="product-card__badge-tag ${badgeColor}">${badge}</span>` : '';
  const origHtml = (p.isSale && origPrice) ? `<span class="text-[10px] sm:text-xs text-slate-400 line-through font-normal truncate">${origPrice}</span>` : '';
  const reviewCount = p.reviewCount || 50;

  const card = `          <article class="product-card group relative rounded-2xl bg-white border border-slate-200/90 shadow-sm hover:shadow-md transition-all duration-300 flex flex-col p-2 sm:p-3.5" data-id="${pid}">
            <div onclick="openEnhancedProductModal('${pid}')" class="product-card__image-wrapper relative aspect-square w-full rounded-xl overflow-hidden bg-slate-50 flex items-center justify-center p-1.5 sm:p-2 mb-2 sm:mb-3 cursor-pointer">
              ${badgeHtml}
              <img class="product-card__image w-full h-full max-w-full max-h-full object-contain group-hover:scale-105 transition-transform duration-300 cursor-pointer" src="${mainImg}" alt="${name} - The Gate VNXK" loading="lazy" width="400" height="400" />
              <div class="absolute bottom-1.5 inset-x-0 flex items-center justify-center gap-1 z-10 pointer-events-none">
                <span class="w-3 h-1 rounded-full bg-orange-600"></span>
                <span class="w-1 h-1 rounded-full bg-slate-300"></span>
                <span class="w-1 h-1 rounded-full bg-slate-300"></span>
                <span class="w-1 h-1 rounded-full bg-slate-300"></span>
              </div>
            </div>
            <div class="product-card__body flex flex-col flex-grow">
              <span class="text-[10px] sm:text-[11px] font-bold text-orange-600 block uppercase mb-0.5 sm:mb-1">MÃ: ${code}</span>
              <h3 onclick="openEnhancedProductModal('${pid}')" class="product-card__name font-bold text-slate-900 text-xs sm:text-sm leading-snug line-clamp-2 min-h-[2rem] sm:min-h-[2.5rem] mb-1 hover:text-orange-600 transition-colors cursor-pointer" title="${name}">${name}</h3>
              <div class="flex items-center gap-1 text-[10px] sm:text-xs text-amber-400 mb-1 sm:mb-1.5">
                <span>★★★★★</span>
                <span class="text-slate-400 font-normal">(${reviewCount})</span>
              </div>
              <div class="product-card__prices flex items-baseline gap-1.5 mb-2 sm:mb-3 mt-auto flex-wrap">
                <span class="product-card__price font-extrabold text-orange-600 text-xs sm:text-base">${price}</span>
                ${origHtml}
              </div>
              <button type="button" onclick="openEnhancedProductModal('${pid}')" class="w-full py-2 px-2.5 sm:py-2.5 sm:px-3 rounded-xl bg-orange-600 hover:bg-orange-700 active:scale-95 text-white font-extrabold text-[11px] sm:text-xs shadow-md shadow-orange-500/20 flex items-center justify-center gap-1.5 transition-all mt-auto cursor-pointer border-0">
                <i data-lucide="tag" class="w-3.5 h-3.5 shrink-0 text-white"></i>
                <span class="truncate tracking-wide">Xem Size & Tồn Kho</span>
              </button>
            </div>
          </article>`;

  cardsHtml.push(card);
}

const staticCardsPath = path.join(baseDir, 'scripts', 'static_cards.html');
fs.writeFileSync(staticCardsPath, cardsHtml.join('\n'), 'utf-8');

const initialPaginationHtml = `
        <div class="w-full text-center text-xs text-slate-500 font-semibold mb-3">
          Trang <span class="text-orange-600 font-extrabold">1</span> / ${totalPages} (Tổng ${totalItems.toLocaleString('vi-VN')} sản phẩm)
        </div>
        <div class="flex flex-wrap items-center justify-center gap-1 sm:gap-2">
          <button type="button" disabled class="px-3 sm:px-4 py-2 rounded-xl text-xs font-bold transition-all border flex items-center gap-1 bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed opacity-50">
            <span>◀</span> <span class="hidden sm:inline">Trang</span> trước
          </button>
          <button type="button" onclick="changePage(1)" class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl text-xs font-bold transition-all border bg-orange-600 text-white border-orange-600 shadow-md ring-2 ring-orange-400/40 scale-105">1</button>
          <button type="button" onclick="changePage(2)" class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl text-xs font-bold transition-all border bg-white text-slate-800 border-slate-200 hover:bg-orange-50 hover:border-orange-500 shadow-sm active:scale-95 cursor-pointer">2</button>
          <button type="button" onclick="changePage(3)" class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl text-xs font-bold transition-all border bg-white text-slate-800 border-slate-200 hover:bg-orange-50 hover:border-orange-500 shadow-sm active:scale-95 cursor-pointer">3</button>
          <button type="button" onclick="changePage(4)" class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl text-xs font-bold transition-all border bg-white text-slate-800 border-slate-200 hover:bg-orange-50 hover:border-orange-500 shadow-sm active:scale-95 cursor-pointer">4</button>
          <button type="button" onclick="changePage(5)" class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl text-xs font-bold transition-all border bg-white text-slate-800 border-slate-200 hover:bg-orange-50 hover:border-orange-500 shadow-sm active:scale-95 cursor-pointer">5</button>
          <span class="px-1.5 text-slate-400 font-bold text-xs">...</span>
          <button type="button" onclick="changePage(${totalPages})" class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl text-xs font-bold transition-all border bg-white text-slate-800 border-slate-200 hover:bg-orange-50 hover:border-orange-500 shadow-sm active:scale-95 cursor-pointer">${totalPages}</button>
          <button type="button" onclick="changePage(2)" class="px-3 sm:px-4 py-2 rounded-xl text-xs font-bold transition-all border flex items-center gap-1 bg-white text-slate-800 border-slate-300 hover:bg-orange-600 hover:text-white hover:border-orange-600 shadow-sm active:scale-95 cursor-pointer">
            <span class="hidden sm:inline">Trang</span> tiếp <span>▶</span>
          </button>
        </div>`;

const indexPath = path.join(baseDir, 'index.html');
let html = fs.readFileSync(indexPath, 'utf-8');
const isCRLF = html.includes('\r\n');
html = html.replace(/\r\n/g, '\n');

// 1. Update Section 4 cards and banner onclick handlers
html = html.replace(/onclick="selectCategoryAndScroll\('price_under_200'\)"/g, `onclick="selectCategoryAndScroll('donggia_199k')"`);
html = html.replace(/onclick="selectCategoryAndScroll\('price_200_350'\)"/g, `onclick="selectCategoryAndScroll('donggia_299k')"`);

// 2. Find and replace Section 5
const sec5Start = html.indexOf('<section class="py-10 sm:py-16 px-3 sm:px-6 bg-slate-50/80');
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

const newSec5 = `<section class="py-10 sm:py-16 px-3 sm:px-6 bg-slate-50/80 border-t border-slate-200" id="featured" aria-label="Sản phẩm nổi bật">
      <div class="max-w-7xl mx-auto">

        <!-- Filter Tabs Header with Beautiful Ergonomic Navigation Arrows -->
        <div class="flex items-center gap-2 sm:gap-3 mb-6 sm:mb-8 max-w-full">
          <!-- Nút điều hướng Trái -->
          <button type="button" onclick="scrollTabsNav(-1)" class="w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-white text-slate-800 border border-slate-200/90 shadow-md hover:bg-orange-600 hover:text-white hover:border-orange-600 active:scale-90 transition-all flex items-center justify-center shrink-0 cursor-pointer focus:outline-none focus:ring-2 focus:ring-orange-500/40" title="Cuộn danh mục sang trái" aria-label="Cuộn danh mục sang trái">
            <i data-lucide="chevron-left" class="w-5 h-5 pointer-events-none stroke-[2.5]"></i>
          </button>

          <!-- Filter Tabs List with Full Multi-Catalogs (Tất cả, Săn Sale, 99K, 199K, 299K, Giảm 50%, 30%, 10%, Nam, Nữ, Trẻ Em, Phụ Kiện) -->
          <div class="flex overflow-x-auto no-scrollbar whitespace-nowrap gap-1.5 sm:gap-2.5 py-1.5 scroll-smooth flex-grow" id="filterTabs">
            <button type="button" onclick="setActiveFilterTab('all')" class="px-4 sm:px-5 py-2.5 rounded-full text-xs font-bold transition-all bg-orange-600 text-white shadow-md filter-tab-btn shrink-0 flex items-center gap-1 active-tab ring-2 ring-orange-400/40" data-category="all">Tất cả sản phẩm</button>
            <button type="button" onclick="setActiveFilterTab('sale')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-bold transition-all bg-white text-red-600 border border-red-200 hover:bg-red-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="sale">
              <span>🔥</span> <span>Săn Sale</span>
            </button>
            <button type="button" onclick="setActiveFilterTab('donggia_99k')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-bold transition-all bg-white text-red-600 border border-red-200 hover:bg-red-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="donggia_99k">
              <span>🏷️</span> <span>Đồng Giá 99K</span>
            </button>
            <button type="button" onclick="setActiveFilterTab('donggia_199k')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-bold transition-all bg-white text-orange-600 border border-orange-200 hover:bg-orange-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="donggia_199k">
              <span>🏷️</span> <span>Đồng Giá 199K</span>
            </button>
            <button type="button" onclick="setActiveFilterTab('donggia_299k')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-bold transition-all bg-white text-purple-600 border border-purple-200 hover:bg-purple-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="donggia_299k">
              <span>💎</span> <span>Đồng Giá 299K</span>
            </button>
            <button type="button" onclick="setActiveFilterTab('sale_50')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-red-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="sale_50">
              <span class="text-red-500">⚡</span> <span>Giảm 50%</span>
            </button>
            <button type="button" onclick="setActiveFilterTab('sale_30')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-orange-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="sale_30">
              <span class="text-orange-500">🔥</span> <span>Giảm 30%</span>
            </button>
            <button type="button" onclick="setActiveFilterTab('sale_10')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-amber-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="sale_10">
              <span class="text-amber-500">🎉</span> <span>Giảm 10%</span>
            </button>
            <button type="button" onclick="setActiveFilterTab('nam')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="nam">Đồ Nam</button>
            <button type="button" onclick="setActiveFilterTab('nu')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="nu">Đồ Nữ</button>
            <button type="button" onclick="setActiveFilterTab('treem')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-orange-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="treem">
              <span>👶</span> <span>Đồ Trẻ Em</span>
            </button>
            <button type="button" onclick="setActiveFilterTab('phukien')" class="px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm" data-category="phukien">Outdoor & Phụ kiện</button>
          </div>

          <!-- Nút điều hướng Phải -->
          <button type="button" onclick="scrollTabsNav(1)" class="w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-white text-slate-800 border border-slate-200/90 shadow-md hover:bg-orange-600 hover:text-white hover:border-orange-600 active:scale-90 transition-all flex items-center justify-center shrink-0 cursor-pointer focus:outline-none focus:ring-2 focus:ring-orange-500/40" title="Cuộn danh mục sang phải" aria-label="Cuộn danh mục sang phải">
            <i data-lucide="chevron-right" class="w-5 h-5 pointer-events-none stroke-[2.5]"></i>
          </button>
        </div>

        <!-- Products Grid Container: 2 columns mobile, 3 columns tablet, 4 columns desktop -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5 sm:gap-6" id="productsGridContainer">
${cardsHtml.join('\n')}
        </div>

        <!-- Dãy nút Phân trang Pagination -->
        <div class="flex flex-col items-center justify-center gap-2 mt-8 sm:mt-10 pt-4 sm:pt-6 border-t border-slate-200" id="paginationContainer">
${initialPaginationHtml}
        </div>
      </div>
    </section>`;

html = html.substring(0, sIndex) + newSec5 + html.substring(eIndex);

if (isCRLF) {
  html = html.replace(/\n/g, '\r\n');
}

fs.writeFileSync(indexPath, html, 'utf-8');
console.log(`Rebuilt Section 5 with multi-catalog tabs.`);
