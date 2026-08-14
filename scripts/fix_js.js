const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');
const indexPath = path.join(baseDir, 'index.html');

let html = fs.readFileSync(indexPath, 'utf-8');
const isCRLF = html.includes('\r\n');
html = html.replace(/\r\n/g, '\n');

const targetStartMarker = '    function parseNumericPrice(val) {';
const targetEndMarker = '    window.openEnhancedProductModal = function(productId) {';

const startIndex = html.indexOf(targetStartMarker);
const endIndex = html.indexOf(targetEndMarker);

if (startIndex === -1 || endIndex === -1) {
  console.error('Could not locate markers in index.html, startIndex:', startIndex, 'endIndex:', endIndex);
  process.exit(1);
}

const replacement = `    function parseNumericPrice(val) {
      if (typeof val === 'number') return val;
      if (!val) return 0;
      const num = parseInt(String(val).replace(/[^\\d]/g, ''), 10);
      return isNaN(num) ? 0 : num;
    }

    function filterStaticProductCards() {
      const gridContainer = document.getElementById('productsGridContainer');
      if (!gridContainer) return;

      const cards = Array.from(gridContainer.querySelectorAll('.product-card'));
      const matchingCards = cards.filter(card => {
        const cat = card.getAttribute('data-category');
        const priceNum = parseInt(card.getAttribute('data-price') || '0', 10);
        const cardText = card.textContent || '';
        const hasSaleBadge = cardText.includes('SALE') || cardText.includes('GIẢM') || card.querySelector('.line-through') !== null;

        if (currentCategoryFilter === 'all') return true;
        if (currentCategoryFilter === 'sale') return cat === 'sale' || hasSaleBadge;
        if (currentCategoryFilter === 'sale_50') return cat === 'sale' || cardText.includes('50%') || cardText.includes('52%') || cardText.includes('56%');
        if (currentCategoryFilter === 'nam') return cat === 'nam';
        if (currentCategoryFilter === 'nu') return cat === 'nu';
        if (currentCategoryFilter === 'phukien') return cat === 'phukien';
        
        if (currentCategoryFilter === 'price_under_200') return priceNum > 0 && priceNum < 200000;
        if (currentCategoryFilter === 'price_200_350') return priceNum >= 200000 && priceNum <= 350000;
        if (currentCategoryFilter === 'price_350_500') return priceNum > 350000 && priceNum <= 500000;
        if (currentCategoryFilter === 'price_over_500') return priceNum > 500000;

        return cat === currentCategoryFilter;
      });

      cards.forEach(card => card.style.display = 'none');

      const totalPages = Math.ceil(matchingCards.length / itemsPerPage) || 1;
      if (currentPage > totalPages) currentPage = totalPages;

      const startIndex = (currentPage - 1) * itemsPerPage;
      const visibleCards = matchingCards.slice(startIndex, startIndex + itemsPerPage);
      visibleCards.forEach(card => card.style.display = 'flex');

      renderPaginationControls(totalPages, matchingCards.length);
    }

    // Render Dãy Nút Phân Trang Trang 1, 2, 3... Tối ưu Mobile First
    function renderPaginationControls(totalPages, totalItems) {
      const container = document.getElementById('paginationContainer');
      if (!container) return;

      if (totalPages <= 1) {
        container.innerHTML = '';
        return;
      }

      let html = \`
        <div class="w-full text-center text-xs text-slate-500 font-semibold mb-2">
          Trang <span class="text-orange-600 font-bold">\${currentPage}</span> / \${totalPages} (Tổng \${totalItems} sản phẩm)
        </div>
        <div class="flex flex-wrap items-center justify-center gap-1.5">
      \`;

      const isPrevDisabled = currentPage === 1;
      html += \`
        <button type="button" onclick="changePage(\${currentPage - 1})" \${isPrevDisabled ? 'disabled' : ''} class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all border flex items-center gap-1 \${
          isPrevDisabled ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed opacity-50' : 'bg-white text-slate-700 border-slate-300 hover:bg-orange-50 hover:border-orange-500 shadow-sm active:scale-95'
        }">
          <span>◀</span> <span class="hidden sm:inline">Trang</span> trước
        </button>
      \`;

      for (let i = 1; i <= totalPages; i++) {
        const isCurrent = i === currentPage;
        html += \`
          <button type="button" onclick="changePage(\${i})" class="w-9 h-9 rounded-xl text-xs font-bold transition-all border \${
            isCurrent ? 'bg-orange-600 text-white border-orange-600 shadow-md ring-2 ring-orange-400/40 scale-105' : 'bg-white text-slate-700 border-slate-200 hover:bg-orange-50 hover:border-orange-500 shadow-sm active:scale-95'
          }">
            \${i}
          </button>
        \`;
      }

      const isNextDisabled = currentPage === totalPages;
      html += \`
        <button type="button" onclick="changePage(\${currentPage + 1})" \${isNextDisabled ? 'disabled' : ''} class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all border flex items-center gap-1 \${
          isNextDisabled ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed opacity-50' : 'bg-white text-slate-700 border-slate-300 hover:bg-orange-50 hover:border-orange-500 shadow-sm active:scale-95'
        }">
          <span class="hidden sm:inline">Trang</span> tiếp <span>▶</span>
        </button>
      </div>\`;

      container.innerHTML = html;
    }

    window.changePage = function(pageNumber) {
      currentPage = pageNumber;
      filterStaticProductCards();
      
      const gridContainer = document.getElementById('productsGridContainer');
      if (gridContainer) {
        gridContainer.scrollLeft = 0;
      }

      const featuredSec = document.getElementById('featured');
      if (featuredSec) {
        featuredSec.scrollIntoView({ behavior: 'smooth' });
      }
    };\n\n`;

html = html.substring(0, startIndex) + replacement + html.substring(endIndex);
if (isCRLF) {
  html = html.replace(/\n/g, '\r\n');
}
fs.writeFileSync(indexPath, html, 'utf-8');
console.log('Fixed JS in index.html successfully!');
