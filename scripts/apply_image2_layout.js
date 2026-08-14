const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');
const indexPath = path.join(baseDir, 'index.html');
const staticCardsPath = path.join(baseDir, 'scripts', 'static_cards.html');

let html = fs.readFileSync(indexPath, 'utf-8');
const isCRLF = html.includes('\r\n');
html = html.replace(/\r\n/g, '\n');

const staticCards = fs.readFileSync(staticCardsPath, 'utf-8');

// Find <section ... id="featured"
const featuredStartRegex = /<section[^>]*id=["']featured["'][^>]*>/;
const match = html.match(featuredStartRegex);

if (!match) {
  console.error('Could not find #featured section in index.html');
  process.exit(1);
}

const sIndex = match.index;
// Find the closing </section> of #featured
const nextSectionMarker = '<!-- Dark Banner "The Gate Outdoor & Sportswear" -->';
const nextSecIdx = html.indexOf(nextSectionMarker, sIndex);

if (nextSecIdx === -1) {
  console.error('Could not find nextSectionMarker in index.html');
  process.exit(1);
}

const lastSectionClose = html.lastIndexOf('</section>', nextSecIdx);
const eIndex = lastSectionClose + '</section>'.length;

console.log('Replacing from index', sIndex, 'to', eIndex);

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
${staticCards}
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
console.log('Successfully replaced Section 5 with clean 100 cards!');
