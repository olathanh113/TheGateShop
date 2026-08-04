/**
 * TheGateShop — Cart Drawer Component
 */

import { formatPrice, getCartItems, saveCartItems, showToast } from '../utils/helpers.js';
import { updateCartCount } from './navbar.js';

const FREE_SHIPPING_THRESHOLD = 500000;

export function initCartDrawer() {
  createDrawerElement();
  
  const cartBtn = document.getElementById('cartBtn');
  if (cartBtn) {
    cartBtn.addEventListener('click', (e) => {
      e.preventDefault();
      openCartDrawer();
    });
  }
}

function createDrawerElement() {
  if (document.getElementById('cartDrawer')) return;

  const drawerWrapper = document.createElement('div');
  drawerWrapper.className = 'drawer-wrapper';
  drawerWrapper.id = 'cartDrawer';
  drawerWrapper.setAttribute('aria-hidden', 'true');

  drawerWrapper.innerHTML = `
    <div class="drawer__backdrop" id="cartDrawerBackdrop"></div>
    <div class="drawer">
      <!-- Drawer Header -->
      <div class="drawer__header">
        <h3 class="drawer__title">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/>
          </svg>
          Giỏ Hàng Của Bạn (<span id="cartDrawerCount">0</span>)
        </h3>
        <button class="drawer__close" id="cartDrawerClose" aria-label="Đóng giỏ hàng">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <!-- Free shipping progress -->
      <div class="drawer__freeship" id="freeshipBar">
        <!-- Progress dynamically filled -->
      </div>

      <!-- Drawer Body (Items) -->
      <div class="drawer__body" id="cartDrawerBody">
        <!-- Cart items rendered here -->
      </div>

      <!-- Drawer Footer (Subtotal & Checkout) -->
      <div class="drawer__footer" id="cartDrawerFooter">
        <div class="drawer__summary">
          <div class="drawer__summary-row">
            <span>Tạm tính</span>
            <span class="drawer__subtotal" id="cartSubtotal">0đ</span>
          </div>
          <p class="drawer__note">Thành tiền chưa bao gồm thuế và chi phí giao hàng nếu có.</p>
        </div>
        <div class="drawer__actions">
          <button class="btn btn-primary btn-lg drawer__checkout-btn" id="cartCheckoutBtn">
            Thanh toán ngay — <span id="cartCheckoutTotal">0đ</span>
          </button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(drawerWrapper);

  // Close events
  document.getElementById('cartDrawerClose').addEventListener('click', closeCartDrawer);
  document.getElementById('cartDrawerBackdrop').addEventListener('click', closeCartDrawer);

  // Checkout action
  document.getElementById('cartCheckoutBtn').addEventListener('click', handleCheckout);
}

export function openCartDrawer() {
  const drawer = document.getElementById('cartDrawer');
  if (!drawer) return;

  renderCartItems();
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}

export function closeCartDrawer() {
  const drawer = document.getElementById('cartDrawer');
  if (!drawer) return;

  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}

export function renderCartItems() {
  const body = document.getElementById('cartDrawerBody');
  const countEl = document.getElementById('cartDrawerCount');
  const freeshipEl = document.getElementById('freeshipBar');
  const subtotalEl = document.getElementById('cartSubtotal');
  const checkoutTotalEl = document.getElementById('cartCheckoutTotal');
  const footerEl = document.getElementById('cartDrawerFooter');

  if (!body) return;

  const items = getCartItems();
  const totalCount = items.reduce((sum, i) => sum + i.quantity, 0);
  const totalPrice = items.reduce((sum, i) => sum + (i.price * i.quantity), 0);

  if (countEl) countEl.textContent = totalCount;

  // Render freeship status
  if (freeshipEl) {
    if (totalPrice >= FREE_SHIPPING_THRESHOLD) {
      freeshipEl.innerHTML = `
        <div class="freeship-msg success">
          <span>🎉 Chúc mừng! Bạn được <strong>MIỄN PHÍ VẬN CHUYỂN</strong></span>
        </div>
        <div class="freeship-progress"><div class="freeship-bar" style="width: 100%;"></div></div>
      `;
    } else {
      const remain = FREE_SHIPPING_THRESHOLD - totalPrice;
      const percent = Math.min(100, Math.round((totalPrice / FREE_SHIPPING_THRESHOLD) * 100));
      freeshipEl.innerHTML = `
        <div class="freeship-msg">
          Mua thêm <strong>${formatPrice(remain)}</strong> để được <strong>Miễn phí vận chuyển</strong>
        </div>
        <div class="freeship-progress"><div class="freeship-bar" style="width: ${percent}%;"></div></div>
      `;
    }
  }

  // Render Cart Body
  if (items.length === 0) {
    body.innerHTML = `
      <div class="drawer__empty">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/>
        </svg>
        <p>Giỏ hàng của bạn đang trống</p>
        <button class="btn btn-secondary" id="cartContinueBtn">Khám phá sản phẩm</button>
      </div>
    `;
    if (footerEl) footerEl.style.display = 'none';

    document.getElementById('cartContinueBtn')?.addEventListener('click', () => {
      closeCartDrawer();
      const featuredSec = document.getElementById('featured');
      if (featuredSec) featuredSec.scrollIntoView({ behavior: 'smooth' });
    });
    return;
  }

  if (footerEl) footerEl.style.display = 'block';
  if (subtotalEl) subtotalEl.textContent = formatPrice(totalPrice);
  if (checkoutTotalEl) checkoutTotalEl.textContent = formatPrice(totalPrice);

  body.innerHTML = `
    <div class="cart-items">
      ${items.map((item, idx) => `
        <div class="cart-item" data-index="${idx}">
          <img class="cart-item__img" src="${item.image}" alt="${item.name}" />
          <div class="cart-item__info">
            <h4 class="cart-item__title">${item.name}</h4>
            <div class="cart-item__meta">
              ${item.size ? `<span class="cart-item__tag">Size: ${item.size}</span>` : ''}
              ${item.color ? `<span class="cart-item__color-dot" style="background:${item.color};"></span>` : ''}
            </div>
            <div class="cart-item__price">${formatPrice(item.price)}</div>
            <div class="cart-item__bottom">
              <div class="quantity-picker quantity-picker--sm">
                <button class="quantity-btn cart-qty-minus" data-index="${idx}">-</button>
                <span class="cart-qty-val">${item.quantity}</span>
                <button class="quantity-btn cart-qty-plus" data-index="${idx}">+</button>
              </div>
              <button class="cart-item__remove" data-index="${idx}" title="Xóa">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      `).join('')}
    </div>
  `;

  // Item event listeners
  body.querySelectorAll('.cart-qty-minus').forEach(btn => {
    btn.addEventListener('click', () => updateQuantity(parseInt(btn.dataset.index), -1));
  });

  body.querySelectorAll('.cart-qty-plus').forEach(btn => {
    btn.addEventListener('click', () => updateQuantity(parseInt(btn.dataset.index), 1));
  });

  body.querySelectorAll('.cart-item__remove').forEach(btn => {
    btn.addEventListener('click', () => removeItem(parseInt(btn.dataset.index)));
  });
}

function updateQuantity(index, delta) {
  const items = getCartItems();
  if (!items[index]) return;

  items[index].quantity += delta;
  if (items[index].quantity <= 0) {
    items.splice(index, 1);
  }

  saveCartItems(items);
  updateCartCount();
  renderCartItems();
}

function removeItem(index) {
  const items = getCartItems();
  if (!items[index]) return;

  const removedName = items[index].name;
  items.splice(index, 1);

  saveCartItems(items);
  updateCartCount();
  renderCartItems();
  showToast(`Đã xóa "${removedName}" khỏi giỏ hàng`, 'info');
}

function handleCheckout() {
  const items = getCartItems();
  if (items.length === 0) return;

  saveCartItems([]);
  updateCartCount();
  closeCartDrawer();
  showToast('🎉 Đặt hàng thành công! Cảm ơn bạn đã mua sắm tại TheGateShop.', 'success');
}
