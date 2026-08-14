/**
 * TheGateShop — Quick View Modal Component
 */

import { formatPrice, generateStars, showToast, getCartItems, saveCartItems, toggleWishlist } from '../utils/helpers.js';
import { updateCartCount, updateWishlistCount } from './navbar.js';
import { openCartDrawer } from './cartDrawer.js';

let allProducts = [];

export function initQuickView(products = []) {
  allProducts = products;
  createModalElement();
}

function createModalElement() {
  if (document.getElementById('quickViewModal')) return;

  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.id = 'quickViewModal';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  modal.setAttribute('aria-hidden', 'true');

  modal.innerHTML = `
    <div class="modal__backdrop" data-close="true"></div>
    <div class="modal__content glass-card">
      <button class="modal__close" data-close="true" aria-label="Đóng">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
      <div class="quickview" id="quickViewBody">
        <!-- Content dynamically inserted -->
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  // Close event listeners
  modal.addEventListener('click', (e) => {
    if (e.target.dataset.close === 'true') {
      closeQuickView();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('open')) {
      closeQuickView();
    }
  });
}

export function openQuickView(product) {
  let prod = product;
  if (typeof product === 'string' || typeof product === 'number') {
    prod = allProducts.find(p => p.id == product);
  }
  if (!prod) return;

  const body = document.getElementById('quickViewBody');
  const modal = document.getElementById('quickViewModal');
  if (!body || !modal) return;

  const badgeHtml = prod.badge
    ? `<span class="badge badge-${prod.badge}">${prod.badge === 'new' ? 'Mới' : prod.badge === 'sale' ? 'Sale' : 'Hot'}</span>`
    : '';

  const salePriceHtml = prod.salePrice
    ? `<span class="quickview__price">${formatPrice(prod.salePrice)}</span>
       <span class="quickview__price--old">${formatPrice(prod.price)}</span>`
    : `<span class="quickview__price">${formatPrice(prod.price)}</span>`;

  const thumbsHtml = prod.images && prod.images.length > 1
    ? `<div class="quickview__thumbs">
        ${prod.images.map((img, idx) => `
          <img class="quickview__thumb ${idx === 0 ? 'active' : ''}" src="${img}" alt="${prod.name}" data-index="${idx}" />
        `).join('')}
       </div>`
    : '';

  const sizes = prod.sizes || ['S', 'M', 'L', 'XL'];
  const colors = prod.colors || ['#000000', '#ffffff', '#c9a96e'];

  body.innerHTML = `
    <div class="quickview__gallery">
      <div class="quickview__main-img-wrapper">
        ${badgeHtml}
        <img class="quickview__main-img" id="qvMainImg" src="${prod.images[0]}" alt="${prod.name}" />
      </div>
      ${thumbsHtml}
    </div>

    <div class="quickview__details">
      <span class="quickview__category">${prod.categoryDisplay || 'Thời trang'}</span>
      <h2 class="quickview__title">${prod.name}</h2>

      <div class="quickview__prices">${salePriceHtml}</div>

      <p class="quickview__desc">${prod.description || 'Sản phẩm thời trang cao cấp với thiết kế hiện đại, tinh tế.'}</p>

      <!-- Option: Size -->
      <div class="quickview__option">
        <label class="quickview__option-label">Kích thước: <span id="qvSelectedSize">${sizes[0]}</span></label>
        <div class="quickview__sizes">
          ${sizes.map((s, idx) => `
            <button class="quickview__size-btn ${idx === 0 ? 'active' : ''}" data-size="${s}">${s}</button>
          `).join('')}
        </div>
      </div>

      <!-- Option: Color -->
      <div class="quickview__option">
        <label class="quickview__option-label">Màu sắc: <span id="qvSelectedColor">${colors[0]}</span></label>
        <div class="quickview__colors">
          ${colors.map((c, idx) => `
            <button class="quickview__color-btn ${idx === 0 ? 'active' : ''}" data-color="${c}" style="background-color: ${getColorHex(c)};" title="${c}"></button>
          `).join('')}
        </div>
      </div>

      <!-- Quantity & Add to cart -->
      <div class="quickview__actions">
        <div class="quantity-picker">
          <button class="quantity-btn" id="qvQtyMinus" aria-label="Giảm số lượng">-</button>
          <input type="number" class="quantity-input" id="qvQtyInput" name="quantity" aria-label="Số lượng sản phẩm" value="1" min="1" max="99" />
          <button class="quantity-btn" id="qvQtyPlus" aria-label="Tăng số lượng">+</button>
        </div>

        <button class="btn btn-primary btn-lg" id="qvAddToCartBtn">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/>
          </svg>
          Thêm vào giỏ
        </button>

        <button class="btn-icon" id="qvWishlistBtn" title="Thêm vào yêu thích">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
          </svg>
        </button>
      </div>
    </div>
  `;

  // Attach interactive events inside QuickView
  let selectedSize = sizes[0];
  let selectedColor = colors[0];

  // Thumbnail click
  body.querySelectorAll('.quickview__thumb').forEach(thumb => {
    thumb.addEventListener('click', () => {
      body.querySelectorAll('.quickview__thumb').forEach(t => t.classList.remove('active'));
      thumb.classList.add('active');
      const idx = thumb.dataset.index;
      document.getElementById('qvMainImg').src = prod.images[idx];
    });
  });

  // Size buttons
  body.querySelectorAll('.quickview__size-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      body.querySelectorAll('.quickview__size-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedSize = btn.dataset.size;
      document.getElementById('qvSelectedSize').textContent = selectedSize;
    });
  });

  // Color buttons
  body.querySelectorAll('.quickview__color-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      body.querySelectorAll('.quickview__color-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedColor = btn.dataset.color;
      document.getElementById('qvSelectedColor').textContent = selectedColor;
    });
  });

  // Quantity pickers
  const qtyInput = document.getElementById('qvQtyInput');
  document.getElementById('qvQtyMinus').addEventListener('click', () => {
    let val = parseInt(qtyInput.value) || 1;
    if (val > 1) qtyInput.value = val - 1;
  });
  document.getElementById('qvQtyPlus').addEventListener('click', () => {
    let val = parseInt(qtyInput.value) || 1;
    if (val < 99) qtyInput.value = val + 1;
  });

  // Add to Cart
  document.getElementById('qvAddToCartBtn').addEventListener('click', () => {
    const qty = parseInt(qtyInput.value) || 1;
    const items = getCartItems();
    const existingIndex = items.findIndex(i => i.id === prod.id && i.size === selectedSize && i.color === selectedColor);

    if (existingIndex >= 0) {
      items[existingIndex].quantity += qty;
    } else {
      items.push({
        id: prod.id,
        name: prod.name,
        price: prod.salePrice || prod.price,
        image: prod.images[0],
        quantity: qty,
        size: selectedSize,
        color: selectedColor
      });
    }

    saveCartItems(items);
    updateCartCount();
    closeQuickView();
    showToast(`Đã thêm ${qty} x "${prod.name}" vào giỏ hàng!`, 'success');
    openCartDrawer();
  });

  // Wishlist btn
  document.getElementById('qvWishlistBtn').addEventListener('click', () => {
    toggleWishlist(prod);
    updateWishlistCount();
  });

  // Show modal
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}

export function closeQuickView() {
  const modal = document.getElementById('quickViewModal');
  if (!modal) return;
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}
