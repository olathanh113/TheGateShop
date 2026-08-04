/**
 * TheGateShop — Product Card Component
 */

import { formatPrice, generateStars, showToast, getCartItems, saveCartItems, toggleWishlist, isInWishlist } from '../utils/helpers.js';
import { updateCartCount, updateWishlistCount } from './navbar.js';
import { openQuickView } from './quickView.js';
import { openCartDrawer } from './cartDrawer.js';

export function createProductCard(product) {
  const card = document.createElement('div');
  card.className = 'product-card reveal';
  card.dataset.category = product.category;

  const isLiked = isInWishlist(product.id);

  const badgeHtml = product.badge
    ? `<span class="badge badge-${product.badge}">${getBadgeLabel(product.badge)}</span>`
    : '';

  const salePriceHtml = product.salePrice
    ? `<span class="product-card__price">${formatPrice(product.salePrice)}</span>
       <span class="product-card__price--old">${formatPrice(product.price)}</span>`
    : `<span class="product-card__price">${formatPrice(product.price)}</span>`;

  card.innerHTML = `
    <div class="product-card__image-wrapper">
      ${badgeHtml}
      <img
        class="product-card__image"
        src="${product.images[0]}"
        alt="${product.name}"
        loading="lazy"
      />
      <div class="product-card__overlay">
        <button class="product-card__action ${isLiked ? 'active' : ''}" data-action="wishlist" data-id="${product.id}" title="Yêu thích" aria-label="Thêm vào yêu thích">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="${isLiked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
        </button>
        <button class="product-card__action" data-action="cart" data-id="${product.id}" title="Thêm vào giỏ" aria-label="Thêm vào giỏ hàng">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>
        </button>
        <button class="product-card__action" data-action="quickview" data-id="${product.id}" title="Xem nhanh" aria-label="Xem nhanh sản phẩm">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
    </div>
    <div class="product-card__body">
      <span class="product-card__category">${product.categoryDisplay}</span>
      <h3 class="product-card__name">${product.name}</h3>
      <div class="product-card__prices">${salePriceHtml}</div>
      <div class="product-card__rating">
        <div class="product-card__stars">${generateStars(product.rating)}</div>
        <span class="product-card__rating-count">(${product.reviewCount})</span>
      </div>
    </div>
  `;

  // Event listeners
  card.querySelector('[data-action="cart"]')?.addEventListener('click', (e) => {
    e.stopPropagation();
    addToCart(product);
  });

  const wishBtn = card.querySelector('[data-action="wishlist"]');
  wishBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    const added = toggleWishlist(product);
    updateWishlistCount();

    if (added) {
      wishBtn.classList.add('active');
      wishBtn.querySelector('svg')?.setAttribute('fill', 'currentColor');
    } else {
      wishBtn.classList.remove('active');
      wishBtn.querySelector('svg')?.setAttribute('fill', 'none');
    }
  });

  const qvBtn = card.querySelector('[data-action="quickview"]');
  qvBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    openQuickView(product);
  });

  // Clicking on card opens QuickView
  card.addEventListener('click', () => {
    openQuickView(product);
  });

  return card;
}

function getBadgeLabel(badge) {
  const labels = { new: 'Mới', sale: 'Sale', hot: 'Hot' };
  return labels[badge] || badge;
}

function addToCart(product) {
  const items = getCartItems();
  const existing = items.find(item => item.id === product.id);

  if (existing) {
    existing.quantity += 1;
  } else {
    items.push({
      id: product.id,
      name: product.name,
      price: product.salePrice || product.price,
      image: product.images[0],
      quantity: 1,
      size: product.sizes ? product.sizes[0] : 'M',
      color: product.colors ? product.colors[0] : '#000000'
    });
  }

  saveCartItems(items);
  updateCartCount();
  showToast(`Đã thêm "${product.name}" vào giỏ hàng!`, 'success');
  openCartDrawer();
}

export function renderProducts(container, products) {
  if (!container) return;
  container.innerHTML = '';

  products.forEach(product => {
    container.appendChild(createProductCard(product));
  });
}

