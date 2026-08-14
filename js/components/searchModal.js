/**
 * TheGateShop — Search Modal Component
 */

import { formatPrice, debounce } from '../utils/helpers.js';
import { openQuickView } from './quickView.js';

let allProducts = [];

export function initSearchModal(products = []) {
  allProducts = products;
  createModalElement();

  const searchBtn = document.getElementById('searchBtn');
  if (searchBtn) {
    searchBtn.addEventListener('click', (e) => {
      e.preventDefault();
      openSearchModal();
    });
  }
}

function createModalElement() {
  if (document.getElementById('searchModal')) return;

  const modal = document.createElement('div');
  modal.className = 'search-modal';
  modal.id = 'searchModal';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  modal.setAttribute('aria-hidden', 'true');

  modal.innerHTML = `
    <div class="search-modal__backdrop" id="searchModalBackdrop"></div>
    <div class="search-modal__container glass-card">
      <div class="search-modal__header">
        <div class="search-modal__input-wrapper">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            class="search-modal__input"
            id="searchInput"
            name="q"
            aria-label="Tìm kiếm sản phẩm"
            placeholder="Tìm kiếm sản phẩm, danh mục, xu hướng..."
            autocomplete="off"
          />
          <button class="search-modal__clear" id="searchClearBtn" aria-label="Xóa">✕</button>
        </div>
        <button class="search-modal__close" id="searchModalClose" aria-label="Đóng tìm kiếm">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- Suggestion Tags -->
      <div class="search-modal__tags">
        <span class="search-modal__tags-label">Gợi ý tìm kiếm:</span>
        <button class="search-tag" data-query="Khoác">Áo khoác dù</button>
        <button class="search-tag" data-query="Polo">Polo Supplex</button>
        <button class="search-tag" data-query="Kaki">Quần Kaki Slim</button>
        <button class="search-tag" data-query="Rashguard">Áo chống nắng UPF50+</button>
        <button class="search-tag" data-query="Phao">Áo phao siêu nhẹ</button>
        <button class="search-tag" data-query="Outdoor">Đồ Outdoor</button>
      </div>

      <!-- Search Results Area -->
      <div class="search-modal__results" id="searchResults">
        <div class="search-modal__initial">
          <p>Nhập từ khóa để tìm kiếm các sản phẩm cao cấp tại TheGateShop</p>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  // Close listeners
  document.getElementById('searchModalClose').addEventListener('click', closeSearchModal);
  document.getElementById('searchModalBackdrop').addEventListener('click', closeSearchModal);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('open')) {
      closeSearchModal();
    }
  });

  // Input listeners
  const input = document.getElementById('searchInput');
  const clearBtn = document.getElementById('searchClearBtn');

  input.addEventListener('input', debounce((e) => {
    const query = e.target.value.trim();
    clearBtn.style.display = query ? 'block' : 'none';
    performSearch(query);
  }, 250));

  clearBtn.addEventListener('click', () => {
    input.value = '';
    clearBtn.style.display = 'none';
    performSearch('');
    input.focus();
  });

  // Tag clicks
  modal.querySelectorAll('.search-tag').forEach(tag => {
    tag.addEventListener('click', () => {
      const q = tag.dataset.query;
      input.value = q;
      clearBtn.style.display = 'block';
      performSearch(q);
    });
  });
}

export function openSearchModal() {
  const modal = document.getElementById('searchModal');
  const input = document.getElementById('searchInput');
  if (!modal) return;

  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';

  setTimeout(() => {
    if (input) input.focus();
  }, 100);
}

export function closeSearchModal() {
  const modal = document.getElementById('searchModal');
  if (!modal) return;

  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}

function performSearch(query) {
  const resultsContainer = document.getElementById('searchResults');
  if (!resultsContainer) return;

  if (!query) {
    resultsContainer.innerHTML = `
      <div class="search-modal__initial">
        <p>Nhập từ khóa để tìm kiếm các sản phẩm cao cấp tại TheGateShop</p>
      </div>
    `;
    return;
  }

  const q = query.toLowerCase();
  const matched = allProducts.filter(p =>
    p.name.toLowerCase().includes(q) ||
    p.categoryDisplay.toLowerCase().includes(q) ||
    p.category.toLowerCase().includes(q) ||
    (p.description && p.description.toLowerCase().includes(q))
  );

  if (matched.length === 0) {
    resultsContainer.innerHTML = `
      <div class="search-modal__no-results">
        <p>Không tìm thấy sản phẩm nào phù hợp với từ khóa "<strong>${query}</strong>"</p>
      </div>
    `;
    return;
  }

  resultsContainer.innerHTML = `
    <div class="search-modal__count">Tìm thấy ${matched.length} sản phẩm</div>
    <div class="search-results-grid">
      ${matched.map(p => `
        <div class="search-result-item" data-id="${p.id}">
          <img class="search-result-item__img" src="${p.images[0]}" alt="${p.name}" />
          <div class="search-result-item__info">
            <span class="search-result-item__cat">${p.categoryDisplay}</span>
            <h4 class="search-result-item__title">${p.name}</h4>
            <div class="search-result-item__price">${formatPrice(p.salePrice || p.price)}</div>
          </div>
        </div>
      `).join('')}
    </div>
  `;

  // Attach quick view click to result items
  resultsContainer.querySelectorAll('.search-result-item').forEach(item => {
    item.addEventListener('click', () => {
      const prodId = item.dataset.id;
      const product = allProducts.find(p => p.id == prodId);
      closeSearchModal();
      if (product) {
        openQuickView(product);
      }
    });
  });
}
