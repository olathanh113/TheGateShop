/**
 * TheGateShop — Helper Utilities
 */

export function formatPrice(price) {
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
    maximumFractionDigits: 0
  }).format(price);
}

export function generateStars(rating) {
  const fullStars = Math.floor(rating);
  const hasHalf = rating % 1 >= 0.5;
  let html = '';

  for (let i = 0; i < fullStars; i++) {
    html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>';
  }

  if (hasHalf) {
    html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" opacity="0.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>';
  }

  const empty = 5 - fullStars - (hasHalf ? 1 : 0);
  for (let i = 0; i < empty; i++) {
    html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>';
  }

  return html;
}

export function debounce(fn, delay = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

export function throttle(fn, limit = 100) {
  let inThrottle;
  return (...args) => {
    if (!inThrottle) {
      fn.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

export function getCartItems() {
  try {
    return JSON.parse(localStorage.getItem('thegateshop_cart')) || [];
  } catch {
    return [];
  }
}

export function saveCartItems(items) {
  localStorage.setItem('thegateshop_cart', JSON.stringify(items));
}

export function getCartCount() {
  return getCartItems().reduce((sum, item) => sum + item.quantity, 0);
}

export function getWishlistItems() {
  try {
    return JSON.parse(localStorage.getItem('thegateshop_wishlist')) || [];
  } catch {
    return [];
  }
}

export function saveWishlistItems(items) {
  localStorage.setItem('thegateshop_wishlist', JSON.stringify(items));
}

export function isInWishlist(productId) {
  const items = getWishlistItems();
  return items.some(item => item.id === productId);
}

export function toggleWishlist(product) {
  const items = getWishlistItems();
  const index = items.findIndex(item => item.id === product.id);
  let added = false;

  if (index >= 0) {
    items.splice(index, 1);
    showToast(`Đã xóa "${product.name}" khỏi danh sách yêu thích`, 'info');
  } else {
    items.push({
      id: product.id,
      name: product.name,
      price: product.salePrice || product.price,
      oldPrice: product.salePrice ? product.price : null,
      image: product.images[0],
      categoryDisplay: product.categoryDisplay,
      badge: product.badge
    });
    added = true;
    showToast(`Đã thêm "${product.name}" vào danh sách yêu thích!`, 'success');
  }

  saveWishlistItems(items);
  return added;
}

export function getWishlistCount() {
  return getWishlistItems().length;
}

export function showToast(message, type = 'success') {
  const icons = {
    success: '✓',
    error: '✕',
    info: 'ℹ'
  };

  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.innerHTML = `
    <span class="toast__icon">${icons[type]}</span>
    <span class="toast__message">${message}</span>
  `;

  document.body.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

