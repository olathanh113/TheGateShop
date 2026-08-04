/**
 * TheGateShop — Wishlist Drawer Component
 */

import { formatPrice, getWishlistItems, saveWishlistItems, getCartItems, saveCartItems, showToast } from '../utils/helpers.js';
import { updateWishlistCount, updateCartCount } from './navbar.js';
import { openCartDrawer } from './cartDrawer.js';

export function initWishlistDrawer() {
  createDrawerElement();

  const wishlistBtn = document.getElementById('wishlistBtn');
  if (wishlistBtn) {
    wishlistBtn.addEventListener('click', (e) => {
      e.preventDefault();
      openWishlistDrawer();
    });
  }
}

function createDrawerElement() {
  if (document.getElementById('wishlistDrawer')) return;

  const drawerWrapper = document.createElement('div');
  drawerWrapper.className = 'drawer-wrapper';
  drawerWrapper.id = 'wishlistDrawer';
  drawerWrapper.setAttribute('aria-hidden', 'true');

  drawerWrapper.innerHTML = `
    <div class="drawer__backdrop" id="wishlistDrawerBackdrop"></div>
    <div class="drawer">
      <!-- Header -->
      <div class="drawer__header">
        <h3 class="drawer__title">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
          </svg>
          Sản Phẩm Yêu Thích (<span id="wishlistDrawerCount">0</span>)
        </h3>
        <button class="drawer__close" id="wishlistDrawerClose" aria-label="Đóng">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- Body -->
      <div class="drawer__body" id="wishlistDrawerBody">
        <!-- Wishlist items rendered here -->
      </div>
    </div>
  `;

  document.body.appendChild(drawerWrapper);

  // Close events
  document.getElementById('wishlistDrawerClose').addEventListener('click', closeWishlistDrawer);
  document.getElementById('wishlistDrawerBackdrop').addEventListener('click', closeWishlistDrawer);
}

export function openWishlistDrawer() {
  const drawer = document.getElementById('wishlistDrawer');
  if (!drawer) return;

  renderWishlistItems();
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}

export function closeWishlistDrawer() {
  const drawer = document.getElementById('wishlistDrawer');
  if (!drawer) return;

  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}

export function renderWishlistItems() {
  const body = document.getElementById('wishlistDrawerBody');
  const countEl = document.getElementById('wishlistDrawerCount');
  if (!body) return;

  const items = getWishlistItems();
  if (countEl) countEl.textContent = items.length;

  if (items.length === 0) {
    body.innerHTML = `
      <div class="drawer__empty">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
        <p>Danh sách yêu thích của bạn đang trống</p>
        <button class="btn btn-secondary" id="wishlistExploreBtn">Khám phá ngay</button>
      </div>
    `;

    document.getElementById('wishlistExploreBtn')?.addEventListener('click', () => {
      closeWishlistDrawer();
      const featuredSec = document.getElementById('featured');
      if (featuredSec) featuredSec.scrollIntoView({ behavior: 'smooth' });
    });
    return;
  }

  body.innerHTML = `
    <div class="wishlist-items">
      ${items.map((item, idx) => `
        <div class="wishlist-item" data-index="${idx}">
          <img class="wishlist-item__img" src="${item.image}" alt="${item.name}" />
          <div class="wishlist-item__info">
            <span class="wishlist-item__category">${item.categoryDisplay || ''}</span>
            <h4 class="wishlist-item__title">${item.name}</h4>
            <div class="wishlist-item__price">${formatPrice(item.price)}</div>
            <div class="wishlist-item__actions">
              <button class="btn btn-primary btn-sm move-to-cart-btn" data-index="${idx}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>
                Thêm vào giỏ
              </button>
              <button class="btn-icon btn-sm remove-wishlist-btn" data-index="${idx}" title="Xóa">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>
        </div>
      `).join('')}
    </div>
  `;

  // Listeners
  body.querySelectorAll('.move-to-cart-btn').forEach(btn => {
    btn.addEventListener('click', () => moveToCart(parseInt(btn.dataset.index)));
  });

  body.querySelectorAll('.remove-wishlist-btn').forEach(btn => {
    btn.addEventListener('click', () => removeFromWishlist(parseInt(btn.dataset.index)));
  });
}

function moveToCart(index) {
  const wishItems = getWishlistItems();
  const item = wishItems[index];
  if (!item) return;

  // Add to cart
  const cartItems = getCartItems();
  const existing = cartItems.find(i => i.id === item.id);
  if (existing) {
    existing.quantity += 1;
  } else {
    cartItems.push({
      id: item.id,
      name: item.name,
      price: item.price,
      image: item.image,
      quantity: 1,
      size: 'M',
      color: '#000000'
    });
  }

  saveCartItems(cartItems);
  updateCartCount();

  // Remove from wishlist
  wishItems.splice(index, 1);
  saveWishlistItems(wishItems);
  updateWishlistCount();

  closeWishlistDrawer();
  showToast(`Đã chuyển "${item.name}" sang giỏ hàng!`, 'success');
  openCartDrawer();
}

function removeFromWishlist(index) {
  const wishItems = getWishlistItems();
  const item = wishItems[index];
  if (!item) return;

  wishItems.splice(index, 1);
  saveWishlistItems(wishItems);
  updateWishlistCount();
  renderWishlistItems();
  showToast(`Đã xóa "${item.name}" khỏi danh sách yêu thích`, 'info');
}
