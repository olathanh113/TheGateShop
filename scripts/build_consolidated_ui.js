const fs = require('fs');
const path = require('path');
const vm = require('vm');

const baseDir = path.resolve(__dirname, '..');
const indexPath = path.join(baseDir, 'index.html');
let html = fs.readFileSync(indexPath, 'utf-8');
const isCRLF = html.includes('\r\n');
html = html.replace(/\r\n/g, '\n');

// 1. Load consolidated products
const pData = fs.readFileSync(path.join(baseDir, 'js', 'productsData.js'), 'utf-8');
const sandbox = { window: {} };
sandbox.window = sandbox;
vm.runInNewContext(pData, sandbox);
const products = Object.values(sandbox.PRODUCTS_DATA);

// 2. Generate 16 static HTML cards for page 1
const page1Products = products.slice(0, 16);
const staticCardsHtml = page1Products.map(p => {
  const pid = p.id || p.code;
  const mainImg = (p.images && p.images[0]) || 'assets/images/products/product-01.svg';
  const name = p.name || 'Sản phẩm The Gate';
  const price = p.price || '299.000đ';
  const origPrice = p.originalPrice || '';
  const code = p.code || pid;
  const badge = p.badgeText || (p.discountPercent ? `🔥 GIẢM ${p.discountPercent}%` : '');
  const badgeColor = p.badgeColor || 'bg-orange-600 text-white shadow-sm';
  const sizeCount = p.sizes ? p.sizes.length : 1;
  const colorCount = p.colors ? p.colors.length : 1;

  const badgeHtml = badge ? `<span class="product-card__badge-tag ${badgeColor}">${badge}</span>` : '';
  const origHtml = origPrice ? `<span class="text-[10px] sm:text-xs text-slate-400 line-through font-normal truncate">${origPrice}</span>` : '';

  return `          <article class="product-card group relative rounded-2xl bg-white border border-slate-200/90 shadow-sm hover:shadow-md transition-all duration-300 flex flex-col p-2 sm:p-3.5" data-id="${pid}">
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
              <div class="flex items-center justify-between gap-1 mb-0.5 sm:mb-1">
                <span class="text-[10px] sm:text-[11px] font-extrabold text-orange-600 block uppercase">MÃ: ${code}</span>
                <span class="text-[9px] sm:text-[10px] font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">${sizeCount} Size • ${colorCount} Màu</span>
              </div>
              <h3 onclick="openEnhancedProductModal('${pid}')" class="product-card__name font-bold text-slate-900 text-xs sm:text-sm leading-snug line-clamp-2 min-h-[2rem] sm:min-h-[2.5rem] mb-1 hover:text-orange-600 transition-colors cursor-pointer" title="${name}">${name}</h3>
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
}).join('\n');

// 3. Update the static grid container in HTML
const gridStartMarker = '<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5 sm:gap-6" id="productsGridContainer">';
const gridEndMarker = '<!-- Dãy nút Phân trang Pagination -->';

const gIdx = html.indexOf(gridStartMarker);
const gEndIdx = html.indexOf(gridEndMarker, gIdx);

if (gIdx !== -1 && gEndIdx !== -1) {
  html = html.substring(0, gIdx + gridStartMarker.length) + '\n' + staticCardsHtml + '\n        </div>\n\n        ' + html.substring(gEndIdx);
}

// 4. Update Pagination text on initial load
const totalPages = Math.ceil(products.length / 16);
const pagTextMatch = html.match(/Trang <span class="text-orange-600 font-extrabold">1<\/span> \/ \d+ \(Tổng [^)]+\)/);
if (pagTextMatch) {
  html = html.replace(pagTextMatch[0], `Trang <span class="text-orange-600 font-extrabold">1</span> / ${totalPages} (Tổng ${products.length.toLocaleString('vi-VN')} sản phẩm)`);
}

// 5. Update Modal Header in HTML
const modalNameIdx = html.indexOf('<h3 class="text-xl sm:text-2xl font-extrabold text-slate-900 leading-tight mb-1" id="modalProductName">');
if (modalNameIdx !== -1) {
  const modalHeaderSnippet = `<h3 class="text-xl sm:text-2xl font-extrabold text-slate-900 leading-tight mb-1" id="modalProductName">Tên sản phẩm</h3>
        <div class="flex items-center justify-center gap-2 mb-2" id="modalVariantCodeContainer">
          <span class="px-3 py-1 rounded-full text-xs font-extrabold bg-orange-100 text-orange-700 border border-orange-300" id="modalSelectedVariantCode">MÃ GỐC: [201]</span>
        </div>`;
  
  const nextPriceIdx = html.indexOf('<div class="flex items-center justify-center gap-3">', modalNameIdx);
  if (nextPriceIdx !== -1) {
    html = html.substring(0, modalNameIdx) + modalHeaderSnippet + '\n        ' + html.substring(nextPriceIdx);
  }
}

// 6. Update JavaScript code block for products rendering and dynamic variant switching
const sIdx = html.indexOf('<script src="js/productsData.js"></script>');
const scriptStart = html.indexOf('<script>', sIdx) + '<script>'.length;
const scriptEnd = html.indexOf('</script>', scriptStart);

const newJsCode = `
    const STORES_INFO = {
      cs1: {
        code: "CS1",
        name: "HN CS1: Tôn Thất Thiệp (Ba Đình)",
        shortAddr: "27 ngõ 8 Tôn Thất Thiệp, Ba Đình, Hà Nội",
        phone: "0395251095",
        zalo: "0395251095"
      },
      cs2: {
        code: "CS2",
        name: "HN CS2: Nguyễn Trãi (Thanh Xuân)",
        shortAddr: "86 ngõ 72 Nguyễn Trãi, Thanh Xuân, Hà Nội",
        phone: "0355393871",
        zalo: "0355393871"
      },
      cs3: {
        code: "CS3",
        name: "CS3 Ninh Bình: Tam Cốc (Ninh Thắng)",
        shortAddr: "Cổng làng Tuân Cáo, Ninh Thắng, Hoa Lư, Ninh Bình",
        phone: "0942326993",
        zalo: "0942326993"
      }
    };

    let activeFilterCategory = 'all';
    let currentPage = 1;
    const itemsPerPage = 16;

    let activeProduct = null;
    let selectedSize = 'M';
    let selectedColor = 'Tiêu chuẩn';

    window.scrollTabsNav = function(direction) {
      const tabsContainer = document.getElementById('filterTabs');
      if (tabsContainer) {
        tabsContainer.scrollBy({ left: direction * 240, behavior: 'smooth' });
      }
    };

    window.scrollCategoriesNav = function(direction) {
      const catContainer = document.getElementById('categoriesContainer');
      if (catContainer) {
        catContainer.scrollBy({ left: direction * 280, behavior: 'smooth' });
      }
    };

    window.selectCategoryAndScroll = function(categoryName) {
      setActiveFilterTab(categoryName);
      const featuredSec = document.getElementById('featured');
      if (featuredSec) {
        const topPos = featuredSec.getBoundingClientRect().top + window.pageYOffset - 80;
        window.scrollTo({ top: topPos, behavior: 'smooth' });
      }
    };

    window.setActiveFilterTab = function(category) {
      activeFilterCategory = category;
      currentPage = 1;

      const buttons = document.querySelectorAll('.filter-tab-btn');
      buttons.forEach(btn => {
        const btnCat = btn.getAttribute('data-category');
        if (btnCat === category) {
          btn.className = 'px-4 sm:px-5 py-2.5 rounded-full text-xs font-bold transition-all bg-orange-600 text-white shadow-md filter-tab-btn shrink-0 flex items-center gap-1 active-tab ring-2 ring-orange-400/40';
          btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        } else {
          btn.className = 'px-3.5 sm:px-4 py-2.5 rounded-full text-xs font-medium transition-all bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 filter-tab-btn shrink-0 flex items-center gap-1 shadow-sm';
        }
      });

      renderProductsPage();
    };

    function renderProductsPage() {
      const gridContainer = document.getElementById('productsGridContainer');
      if (!gridContainer) return;

      const dataObj = window.PRODUCTS_DATA || (typeof PRODUCTS_DATA !== 'undefined' ? PRODUCTS_DATA : {});
      const allProducts = Object.values(dataObj);

      const matchingProducts = allProducts.filter(p => {
        if (activeFilterCategory === 'all') return true;
        if (activeFilterCategory === 'sale') return p.categories && p.categories.includes('sale');
        if (activeFilterCategory === 'donggia_99k') return p.categories && p.categories.includes('donggia_99k');
        if (activeFilterCategory === 'sale_50') return p.categories && p.categories.includes('sale_50');
        if (activeFilterCategory === 'sale_30') return p.categories && p.categories.includes('sale_30');
        if (activeFilterCategory === 'sale_10') return p.categories && p.categories.includes('sale_10');
        if (activeFilterCategory === 'nam') return p.categories && p.categories.includes('nam');
        if (activeFilterCategory === 'nu') return p.categories && p.categories.includes('nu');
        if (activeFilterCategory === 'treem') return p.categories && p.categories.includes('treem');
        if (activeFilterCategory === 'phukien') return p.categories && p.categories.includes('phukien');
        return true;
      });

      const totalItems = matchingProducts.length;
      const totalPages = Math.ceil(totalItems / itemsPerPage) || 1;

      if (currentPage > totalPages) currentPage = totalPages;
      if (currentPage < 1) currentPage = 1;

      const startIndex = (currentPage - 1) * itemsPerPage;
      const visibleProducts = matchingProducts.slice(startIndex, startIndex + itemsPerPage);

      if (visibleProducts.length === 0) {
        gridContainer.innerHTML = \`
          <div class="col-span-2 md:col-span-3 lg:col-span-4 py-12 text-center text-slate-500">
            <p class="font-bold text-base mb-1">Không tìm thấy sản phẩm phù hợp</p>
            <p class="text-xs">Vui lòng chọn danh mục khác hoặc quay lại tất cả sản phẩm.</p>
          </div>
        \`;
        renderPaginationControls(0, 0);
        return;
      }

      gridContainer.innerHTML = visibleProducts.map(p => {
        const pid = p.id || p.code;
        const mainImg = (p.images && p.images[0]) || 'assets/images/products/product-01.svg';
        const name = p.name || 'Sản phẩm The Gate';
        const price = p.price || '299.000đ';
        const origPrice = p.originalPrice || '';
        const code = p.code || pid;
        const badge = p.badgeText || (p.discountPercent ? \`🔥 GIẢM \${p.discountPercent}%\` : '');
        const badgeColor = p.badgeColor || 'bg-orange-600 text-white shadow-sm';
        const sizeCount = p.sizes ? p.sizes.length : 1;
        const colorCount = p.colors ? p.colors.length : 1;

        const badgeHtml = badge ? \`<span class="product-card__badge-tag \${badgeColor}">\${badge}</span>\` : '';
        const origHtml = origPrice ? \`<span class="text-[10px] sm:text-xs text-slate-400 line-through font-normal truncate">\${origPrice}</span>\` : '';

        return \`
          <article class="product-card group relative rounded-2xl bg-white border border-slate-200/90 shadow-sm hover:shadow-md transition-all duration-300 flex flex-col p-2 sm:p-3.5" data-id="\${pid}">
            <div onclick="openEnhancedProductModal('\${pid}')" class="product-card__image-wrapper relative aspect-square w-full rounded-xl overflow-hidden bg-slate-50 flex items-center justify-center p-1.5 sm:p-2 mb-2 sm:mb-3 cursor-pointer">
              \${badgeHtml}
              <img class="product-card__image w-full h-full max-w-full max-h-full object-contain group-hover:scale-105 transition-transform duration-300 cursor-pointer" src="\${mainImg}" alt="\${name} - The Gate VNXK" loading="lazy" width="400" height="400" />
              <div class="absolute bottom-1.5 inset-x-0 flex items-center justify-center gap-1 z-10 pointer-events-none">
                <span class="w-3 h-1 rounded-full bg-orange-600"></span>
                <span class="w-1 h-1 rounded-full bg-slate-300"></span>
                <span class="w-1 h-1 rounded-full bg-slate-300"></span>
                <span class="w-1 h-1 rounded-full bg-slate-300"></span>
              </div>
            </div>
            <div class="product-card__body flex flex-col flex-grow">
              <div class="flex items-center justify-between gap-1 mb-0.5 sm:mb-1">
                <span class="text-[10px] sm:text-[11px] font-extrabold text-orange-600 block uppercase">MÃ: \${code}</span>
                <span class="text-[9px] sm:text-[10px] font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">\${sizeCount} Size • \${colorCount} Màu</span>
              </div>
              <h3 onclick="openEnhancedProductModal('\${pid}')" class="product-card__name font-bold text-slate-900 text-xs sm:text-sm leading-snug line-clamp-2 min-h-[2rem] sm:min-h-[2.5rem] mb-1 hover:text-orange-600 transition-colors cursor-pointer" title="\${name}">\${name}</h3>
              <div class="product-card__prices flex items-baseline gap-1.5 mb-2 sm:mb-3 mt-auto flex-wrap">
                <span class="product-card__price font-extrabold text-orange-600 text-xs sm:text-base">\${price}</span>
                \${origHtml}
              </div>
              <button type="button" onclick="openEnhancedProductModal('\${pid}')" class="w-full py-2 px-2.5 sm:py-2.5 sm:px-3 rounded-xl bg-orange-600 hover:bg-orange-700 active:scale-95 text-white font-extrabold text-[11px] sm:text-xs shadow-md shadow-orange-500/20 flex items-center justify-center gap-1.5 transition-all mt-auto cursor-pointer border-0">
                <i data-lucide="tag" class="w-3.5 h-3.5 shrink-0 text-white"></i>
                <span class="truncate tracking-wide">Xem Size & Tồn Kho</span>
              </button>
            </div>
          </article>
        \`;
      }).join('');

      renderPaginationControls(totalPages, totalItems);

      if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
      }
    }

    function renderPaginationControls(totalPages, totalItems) {
      const container = document.getElementById('paginationContainer');
      if (!container) return;

      if (totalPages <= 1) {
        container.innerHTML = \`
          <div class="w-full text-center text-xs text-slate-500 font-semibold">
            Hiển thị <span class="text-orange-600 font-bold">\${totalItems}</span> sản phẩm
          </div>
        \`;
        return;
      }

      let html = \`
        <div class="w-full text-center text-xs text-slate-500 font-semibold mb-3">
          Trang <span class="text-orange-600 font-extrabold">\${currentPage}</span> / \${totalPages} (Tổng \${totalItems.toLocaleString('vi-VN')} sản phẩm)
        </div>
        <div class="flex flex-wrap items-center justify-center gap-1 sm:gap-2">
      \`;

      const isPrevDisabled = currentPage === 1;
      html += \`
        <button type="button" onclick="changePage(\${currentPage - 1})" \${isPrevDisabled ? 'disabled' : ''} class="px-3 sm:px-4 py-2 rounded-xl text-xs font-bold transition-all border flex items-center gap-1 \${
          isPrevDisabled ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed opacity-50' : 'bg-white text-slate-800 border-slate-300 hover:bg-orange-600 hover:text-white hover:border-orange-600 shadow-sm active:scale-95 cursor-pointer'
        }">
          <span>◀</span> <span class="hidden sm:inline">Trang</span> trước
        </button>
      \`;

      let pages = [];
      if (totalPages <= 7) {
        for (let i = 1; i <= totalPages; i++) pages.push(i);
      } else {
        if (currentPage <= 4) {
          pages = [1, 2, 3, 4, 5, '...', totalPages];
        } else if (currentPage >= totalPages - 3) {
          pages = [1, '...', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
        } else {
          pages = [1, '...', currentPage - 1, currentPage, currentPage + 1, '...', totalPages];
        }
      }

      pages.forEach(p => {
        if (p === '...') {
          html += \`<span class="px-1.5 text-slate-400 font-bold text-xs">...</span>\`;
        } else {
          const isCurrent = p === currentPage;
          html += \`
            <button type="button" onclick="changePage(\${p})" class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl text-xs font-bold transition-all border \${
              isCurrent ? 'bg-orange-600 text-white border-orange-600 shadow-md ring-2 ring-orange-400/40 scale-105' : 'bg-white text-slate-800 border-slate-200 hover:bg-orange-50 hover:border-orange-500 shadow-sm active:scale-95 cursor-pointer'
            }">
              \${p}
            </button>
          \`;
        }
      });

      const isNextDisabled = currentPage === totalPages;
      html += \`
        <button type="button" onclick="changePage(\${currentPage + 1})" \${isNextDisabled ? 'disabled' : ''} class="px-3 sm:px-4 py-2 rounded-xl text-xs font-bold transition-all border flex items-center gap-1 \${
          isNextDisabled ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed opacity-50' : 'bg-white text-slate-800 border-slate-300 hover:bg-orange-600 hover:text-white hover:border-orange-600 shadow-sm active:scale-95 cursor-pointer'
        }">
          <span class="hidden sm:inline">Trang</span> tiếp <span>▶</span>
        </button>
      </div>\`;

      container.innerHTML = html;
    }

    window.changePage = function(pageNumber) {
      currentPage = pageNumber;
      renderProductsPage();

      const featuredSec = document.getElementById('featured');
      if (featuredSec) {
        const topPos = featuredSec.getBoundingClientRect().top + window.pageYOffset - 80;
        window.scrollTo({ top: topPos, behavior: 'smooth' });
      }
    };

    function getActiveVariant(product, size, color) {
      if (!product || !product.variants || !product.variants.length) return null;
      let match = product.variants.find(v => (v.size === size || size === 'Tiêu chuẩn') && (v.color === color || color === 'Tiêu chuẩn'));
      if (match) return match;
      match = product.variants.find(v => v.size === size && v.color === color);
      if (match) return match;
      match = product.variants.find(v => v.size === size);
      if (match) return match;
      match = product.variants.find(v => v.color === color);
      if (match) return match;
      return product.variants[0];
    }

    function scrollToModalImage(index) {
      const slider = document.getElementById('modalImagesSlider');
      if (slider) {
        const width = slider.clientWidth || 340;
        if (typeof slider.scrollTo === 'function') {
          slider.scrollTo({ left: index * width, behavior: 'smooth' });
        } else {
          slider.scrollLeft = index * width;
        }
      }
    }

    window.slideModalImage = function(direction) {
      const slider = document.getElementById('modalImagesSlider');
      if (slider) {
        const width = slider.clientWidth || 340;
        if (typeof slider.scrollBy === 'function') {
          slider.scrollBy({ left: direction * width, behavior: 'smooth' });
        } else {
          slider.scrollLeft += direction * width;
        }
      }
    };

    window.openEnhancedProductModal = window.openEnhancedModal = function(productId) {
      const dataObj = window.PRODUCTS_DATA || (typeof PRODUCTS_DATA !== 'undefined' ? PRODUCTS_DATA : {});
      activeProduct = dataObj[productId] || Object.values(dataObj)[0];
      if (!activeProduct) return;

      if (!activeProduct.sizes || !activeProduct.sizes.length) {
        activeProduct.sizes = ['Tiêu chuẩn'];
      }
      if (!activeProduct.colors || !activeProduct.colors.length) {
        activeProduct.colors = [{ name: 'Tiêu chuẩn', label: 'Tiêu chuẩn', hex: '#1e293b' }];
      }

      selectedSize = activeProduct.sizes[0] || 'Tiêu chuẩn';
      selectedColor = activeProduct.colors[0]?.name || 'Tiêu chuẩn';

      renderModalImagesSlider(selectedColor);
      renderSizeButtons();
      renderColorButtons();
      updateVariantDetails();

      const modal = document.getElementById('enhancedSizeModal');
      const modalCard = document.getElementById('enhancedModalCard');
      if (modal) {
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        if (modalCard) {
          setTimeout(() => {
            modalCard.classList.remove('scale-95', 'opacity-0');
            modalCard.classList.add('scale-100', 'opacity-100');
          }, 10);
        }
      }
    };

    window.closeEnhancedModal = window.closeEnhancedProductModal = function() {
      const modal = document.getElementById('enhancedSizeModal');
      const modalCard = document.getElementById('enhancedModalCard');
      if (modalCard) {
        modalCard.classList.remove('scale-100', 'opacity-100');
        modalCard.classList.add('scale-95', 'opacity-0');
      }
      setTimeout(() => {
        if (modal) modal.classList.add('hidden');
        document.body.style.overflow = '';
      }, 200);
    };

    function renderModalImagesSlider(targetColor) {
      const sliderContainer = document.getElementById('modalImagesSlider');
      const dotsContainer = document.getElementById('modalImageDots');
      if (!sliderContainer || !activeProduct) return;

      sliderContainer.innerHTML = '';
      if (dotsContainer) dotsContainer.innerHTML = '';

      const colorKey = targetColor || selectedColor;
      let imgs = [];

      if (activeProduct.colorImages && activeProduct.colorImages[colorKey] && activeProduct.colorImages[colorKey].length > 0) {
        imgs = activeProduct.colorImages[colorKey];
      } else if (activeProduct.images && activeProduct.images.length > 0) {
        imgs = activeProduct.images;
      } else {
        imgs = ['assets/images/products/product-01.svg'];
      }

      // Strict Deduplication & keep max 3 photos per color
      const uniqueImgs = Array.from(new Set(imgs)).slice(0, 3);

      uniqueImgs.forEach((img, idx) => {
        const slide = document.createElement('div');
        slide.className = 'w-full h-full min-w-full shrink-0 snap-start flex items-center justify-center p-1';
        slide.innerHTML = \`<img src="\${img}" alt="\${activeProduct.name} - \${idx+1}" class="max-w-full max-h-full w-auto h-auto object-contain rounded-2xl drop-shadow-sm select-none" loading="lazy" />\`;
        sliderContainer.appendChild(slide);

        if (dotsContainer && uniqueImgs.length > 1) {
          const dot = document.createElement('button');
          dot.type = 'button';
          dot.className = \`modal-dot-item \${idx === 0 ? 'w-5 bg-orange-600' : 'w-2 bg-slate-300'} h-2 rounded-full transition-all duration-300 cursor-pointer\`;
          dot.title = \`Xem ảnh \${idx+1}\`;
          dot.onclick = () => scrollToModalImage(idx);
          dotsContainer.appendChild(dot);
        }
      });

      sliderContainer.scrollLeft = 0;

      sliderContainer.onscroll = () => {
        if (!dotsContainer) return;
        const scrollLeft = sliderContainer.scrollLeft;
        const width = sliderContainer.clientWidth || 340;
        const activeIndex = Math.round(scrollLeft / (width || 1));
        const dots = dotsContainer.querySelectorAll('.modal-dot-item');
        dots.forEach((d, i) => {
          if (i === activeIndex) {
            d.className = 'modal-dot-item w-5 bg-orange-600 h-2 rounded-full transition-all duration-300 cursor-pointer';
          } else {
            d.className = 'modal-dot-item w-2 bg-slate-300 h-2 rounded-full transition-all duration-300 cursor-pointer';
          }
        });
      };
    }

    function renderSizeButtons() {
      const container = document.getElementById('sizeButtonsContainer');
      const label = document.getElementById('selectedSizeLabel');
      if (label) label.textContent = selectedSize;
      if (!container || !activeProduct) return;

      container.innerHTML = activeProduct.sizes.map(s => \`
        <button type="button" onclick="selectModalSize('\${s}')" class="px-3.5 py-2 rounded-xl text-xs font-bold border transition-all \${
          selectedSize === s ? 'bg-orange-600 text-white border-orange-600 shadow-md ring-2 ring-orange-400/40' : 'bg-slate-50 text-slate-800 border-slate-200 hover:bg-slate-100'
        }">\${s}</button>
      \`).join('');
    }

    window.selectModalSize = function(size) {
      selectedSize = size;
      renderSizeButtons();
      const currentVariant = getActiveVariant(activeProduct, selectedSize, selectedColor);
      if (currentVariant && currentVariant.color && currentVariant.color !== selectedColor) {
        selectedColor = currentVariant.color;
        renderColorButtons();
      }
      renderModalImagesSlider(selectedColor);
      updateVariantDetails();
    };

    function renderColorButtons() {
      const container = document.getElementById('colorButtonsContainer');
      const label = document.getElementById('selectedColorLabel');
      if (label) label.textContent = selectedColor;
      if (!container || !activeProduct) return;

      container.innerHTML = activeProduct.colors.map(c => \`
        <button type="button" onclick="selectModalColor('\${c.name}')" class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border transition-all \${
          selectedColor === c.name ? 'bg-orange-50 text-orange-700 border-orange-500 ring-2 ring-orange-400/30' : 'bg-slate-50 text-slate-800 border-slate-200 hover:bg-slate-100'
        }">
          <span class="w-3.5 h-3.5 rounded-full border border-slate-300" style="background-color: \${c.hex};"></span>
          <span>\${c.label || c.name}</span>
        </button>
      \`).join('');
    }

    window.selectModalColor = function(colorName) {
      selectedColor = colorName;
      renderColorButtons();
      renderModalImagesSlider(selectedColor);
      updateVariantDetails();
    };

    function updateVariantDetails() {
      if (!activeProduct) return;
      const currentVariant = getActiveVariant(activeProduct, selectedSize, selectedColor);

      const nameEl = document.getElementById('modalProductName');
      const variantCodeEl = document.getElementById('modalSelectedVariantCode');
      const priceEl = document.getElementById('modalProductPrice');
      const origPriceEl = document.getElementById('modalProductOriginalPrice');

      if (nameEl) nameEl.textContent = activeProduct.name;

      if (variantCodeEl) {
        if (currentVariant && currentVariant.code && currentVariant.code !== activeProduct.code) {
          variantCodeEl.innerHTML = \`MÃ BIẾN THỂ: <span class="text-slate-900 underline font-black">[\${currentVariant.code}]</span> • Size: \${selectedSize} • Màu: \${selectedColor}\`;
        } else {
          variantCodeEl.innerHTML = \`MÃ GỐC: <span class="text-slate-900 font-black">[\${activeProduct.code}]</span> • Size: \${selectedSize} • Màu: \${selectedColor}\`;
        }
      }

      const displayPrice = (currentVariant && currentVariant.price) ? currentVariant.price : activeProduct.price;
      const displayOrigPrice = (currentVariant && currentVariant.originalPrice) ? currentVariant.originalPrice : activeProduct.originalPrice;

      if (priceEl) priceEl.textContent = displayPrice;
      if (origPriceEl) {
        if (displayOrigPrice) {
          origPriceEl.textContent = displayOrigPrice;
          origPriceEl.classList.remove('hidden');
        } else {
          origPriceEl.classList.add('hidden');
        }
      }

      if (currentVariant && currentVariant.images && currentVariant.images.length > 0) {
        const vImg = currentVariant.images[0];
        const imgIdx = activeProduct.images.indexOf(vImg);
        if (imgIdx !== -1) {
          scrollToModalImage(imgIdx);
        }
      }

      updateStockAndStoresDisplay(currentVariant);
      updateMainFbLink(currentVariant);
    }

    function updateStockAndStoresDisplay(currentVariant) {
      if (!activeProduct) return;

      const variant = currentVariant || getActiveVariant(activeProduct, selectedSize, selectedColor) || activeProduct;
      const avail = variant.availability || activeProduct.availability || {};
      const isCs1 = avail.ton_that_thiep === 'in_stock';
      const isCs2 = avail.nguyen_trai === 'in_stock';
      const isCs3 = avail.tam_coc === 'in_stock';

      const inStockCount = [isCs1, isCs2, isCs3].filter(Boolean).length;
      const badgeContainer = document.getElementById('stockBadgeContainer');
      if (badgeContainer) {
        if (inStockCount > 0) {
          badgeContainer.className = 'px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 inline-flex items-center gap-1.5';
          badgeContainer.innerHTML = \`<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> Còn hàng tại \${inStockCount}/3 cơ sở\`;
        } else {
          badgeContainer.className = 'px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300 inline-flex items-center gap-1.5';
          badgeContainer.innerHTML = \`<span class="w-2 h-2 rounded-full bg-rose-500"></span> Tạm hết hàng\`;
        }
      }

      const variantCode = variant.code || activeProduct.code || 'XK';
      const variantName = variant.name || activeProduct.name;
      const productImgFullUrl = (variant.images && variant.images[0]) || (activeProduct.images && activeProduct.images[0]) || (window.location.origin + '/assets/images/products/product-01.svg');

      const storeListContainer = document.getElementById('storeStockListContainer');
      if (storeListContainer) {
        storeListContainer.innerHTML = '';

        Object.keys(STORES_INFO).forEach(storeKey => {
          const store = STORES_INFO[storeKey];
          let isAvailable = false;
          if (storeKey === 'cs1') isAvailable = isCs1;
          else if (storeKey === 'cs2') isAvailable = isCs2;
          else if (storeKey === 'cs3') isAvailable = isCs3;

          const msgText = \`Chào The Gate, tôi muốn tư vấn mua tại \${store.name}:\\n- Mã SP: [\${variantCode}] — \${variantName}\\n- Size: \${selectedSize} | Màu: \${selectedColor} | Giá: \${variant.price || activeProduct.price}\\n- 📷 Link ảnh SP: \${productImgFullUrl}\`;
          const encodedMsg = encodeURIComponent(msgText);
          const zaloUrl = \`https://zalo.me/\${store.zalo}?text=\${encodedMsg}\`;
          const telUrl = \`tel:\${store.phone}\`;

          const card = document.createElement('div');
          card.className = \`p-3.5 rounded-2xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 transition-all \${
            isAvailable ? 'bg-white border-slate-200 shadow-sm hover:border-orange-400' : 'bg-slate-50 border-slate-200 opacity-60'
          }\`;

          card.innerHTML = \`
            <div>
              <div class="flex items-center gap-2 mb-0.5">
                <span class="font-bold text-xs text-slate-900">\${store.name}</span>
                \${
                  isAvailable
                    ? \`<span class="text-xs font-bold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-md border border-emerald-200 flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span> Còn hàng</span>\`
                    : \`<span class="text-xs font-bold text-slate-400 bg-slate-100 px-2.5 py-1 rounded-md">Tạm hết hàng</span>\`
                }
              </div>
              <p class="text-xs text-slate-500">\${store.shortAddr}</p>
            </div>

            <div class="flex items-center gap-2 w-full sm:w-auto shrink-0">
              <a href="\${telUrl}" class="flex-1 sm:flex-none px-3 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white font-bold text-xs flex items-center justify-center gap-1 transition-colors shadow">
                <i data-lucide="phone" class="w-3.5 h-3.5"></i>
                <span>Gọi Hotline</span>
              </a>
              <a href="\${zaloUrl}" target="_blank" rel="noopener noreferrer" class="flex-1 sm:flex-none px-3 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs flex items-center justify-center gap-1 transition-colors shadow">
                <i data-lucide="message-circle" class="w-3.5 h-3.5"></i>
                <span>Zalo \${store.code}</span>
              </a>
            </div>
          \`;

          storeListContainer.appendChild(card);
        });
      }

      if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
      }
    }

    function updateMainFbLink(currentVariant) {
      const fbBtn = document.getElementById('mainFbFanpageLink');
      if (fbBtn && activeProduct) {
        const variant = currentVariant || getActiveVariant(activeProduct, selectedSize, selectedColor) || activeProduct;
        const variantCode = variant.code || activeProduct.code || 'XK';
        const variantName = variant.name || activeProduct.name;
        const productImgFullUrl = (variant.images && variant.images[0]) || (activeProduct.images && activeProduct.images[0]) || (window.location.origin + '/assets/images/products/product-01.svg');
        const msgText = \`Chào The Gate, tôi muốn tư vấn sản phẩm [\${variantCode}] \${variantName} - Size: \${selectedSize} - Màu: \${selectedColor} - Giá Sale: \${variant.price || activeProduct.price} - 📷 Link ảnh: \${productImgFullUrl}\`;
        fbBtn.href = \`https://www.facebook.com/thegatevietnamxk?text=\${encodeURIComponent(msgText)}\`;
      }
    }

    function checkAndHideEmptyCategories() {
      const filterBtns = document.querySelectorAll('.filter-tab-btn');
      if (!filterBtns.length) return;

      const dataObj = window.PRODUCTS_DATA || (typeof PRODUCTS_DATA !== 'undefined' ? PRODUCTS_DATA : {});
      const allProducts = Object.values(dataObj);
      if (!allProducts.length) return;

      filterBtns.forEach(btn => {
        const cat = btn.getAttribute('data-category') || 'all';
        if (cat === 'all') return;

        const count = allProducts.filter(p => {
          if (Array.isArray(p.categories) && p.categories.includes(cat)) return true;
          return p.category === cat;
        }).length;

        if (count === 0) {
          btn.style.display = 'none';
        } else {
          btn.style.display = '';
        }
      });
    }

    document.addEventListener('DOMContentLoaded', () => {
      checkAndHideEmptyCategories();
      renderProductsPage();

      const toggleBtn = document.getElementById('navbarToggle');
      const mobileMenu = document.getElementById('mobileMenu');
      if (toggleBtn && mobileMenu) {
        toggleBtn.addEventListener('click', () => {
          mobileMenu.classList.toggle('hidden');
        });
      }

      const backToTopBtn = document.getElementById('backToTop');
      window.addEventListener('scroll', () => {
        if (window.scrollY > 400) {
          backToTopBtn?.classList.remove('opacity-0', 'pointer-events-none');
        } else {
          backToTopBtn?.classList.add('opacity-0', 'pointer-events-none');
        }
      });
    });
`;

html = html.substring(0, scriptStart) + '\n' + newJsCode + '\n  ' + html.substring(scriptEnd);

if (isCRLF) {
  html = html.replace(/\n/g, '\r\n');
}

fs.writeFileSync(indexPath, html, 'utf-8');
console.log('Successfully updated consolidated UI and dynamic variant logic in index.html!');
