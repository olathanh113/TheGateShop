/**
 * TheGateShop — Product Card Component
 */

import { formatPrice, showToast, getCartItems, saveCartItems, toggleWishlist, isInWishlist } from '../utils/helpers.js';
import { updateCartCount, updateWishlistCount } from './navbar.js';
import { openProductModal } from './productModal.js';
import { openCartDrawer } from './cartDrawer.js';

export function createProductCard(product) {
  const card = document.createElement('article');
  card.className = 'product-card reveal group relative rounded-3xl overflow-hidden bg-white border border-slate-200/80 shadow-md hover:shadow-xl transition-all duration-300 flex flex-col';
  card.dataset.category = product.category;
  card.dataset.id = product.id;

  const isLiked = isInWishlist(product.id);

  const salePercent = product.salePrice
    ? Math.round((1 - product.salePrice / product.price) * 100)
    : 0;

  const badgeHtml = product.badge
    ? `<span class="badge badge-${product.badge}">${getBadgeLabel(product.badge, salePercent)}</span>`
    : '';

  const salePriceHtml = product.salePrice
    ? `<span class="product-card__price font-extrabold text-orange-600 text-lg">${formatPrice(product.salePrice)}</span>
       <span class="product-card__price--old text-xs text-slate-400 line-through">${formatPrice(product.price)}</span>`
    : `<span class="product-card__price font-extrabold text-orange-600 text-lg">${formatPrice(product.price)}</span>`;

  const imageSrc = product.images[0].replace(/\.(png|jpg|jpeg)$/i, '.webp');

  card.innerHTML = `
    <div class="product-card__image-wrapper relative aspect-[4/5] w-full overflow-hidden bg-slate-100">
      ${badgeHtml}
      <img
        class="product-card__image w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
        src="${imageSrc}"
        alt="${product.name} - The Gate VNXK"
        loading="lazy"
        width="400"
        height="500"
      />
      <div class="product-card__overlay absolute inset-0 bg-slate-950/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center gap-2 p-3">
        <button class="w-10 h-10 rounded-full bg-white/90 text-slate-800 hover:bg-orange-600 hover:text-white flex items-center justify-center transition-all shadow ${isLiked ? 'active' : ''}" data-action="wishlist" data-id="${product.id}" title="Yêu thích" aria-label="Thêm ${product.name} vào yêu thích">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="${isLiked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
        </button>
        <button class="w-10 h-10 rounded-full bg-orange-600 text-white hover:bg-orange-700 flex items-center justify-center transition-all shadow" data-action="cart" data-id="${product.id}" title="Thêm vào giỏ" aria-label="Thêm ${product.name} vào giỏ hàng">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>
        </button>
        <button class="w-10 h-10 rounded-full bg-white/90 text-slate-800 hover:bg-orange-600 hover:text-white flex items-center justify-center transition-all shadow" data-action="quickview" data-id="${product.id}" title="Xem nhanh" aria-label="Xem nhanh ${product.name}">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
    </div>
    <div class="product-card__body p-5 flex flex-col flex-grow">
      <span class="product-card__category text-[11px] font-bold text-orange-600 uppercase tracking-wider mb-1">${product.categoryDisplay}</span>
      <h3 class="product-card__name font-bold text-slate-900 text-base mb-2 line-clamp-2 leading-snug">${product.name}</h3>
      <div class="product-card__prices mt-auto flex items-center gap-2">${salePriceHtml}</div>
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
    openProductModal(product);
  });

  // Clicking on card opens Product Modal
  card.addEventListener('click', () => {
    openProductModal(product);
  });

  return card;
}

function getBadgeLabel(badge, salePercent = 0) {
  if (badge === 'sale' && salePercent > 0) return `SALE -${salePercent}%`;
  const labels = { new: '✨ Mới', sale: 'SALE', hot: '🔥 HOT' };
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
      image: product.images[0].replace(/\.(png|jpg|jpeg)$/i, '.webp'),
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
