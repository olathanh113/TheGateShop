/**
 * The Gate VNXK — Product Modal với Zalo & Messenger Deep Link
 * ============================================================
 * Cung cấp modal chi tiết sản phẩm, chọn size, và tạo deep link
 * tư vấn tự động cho Zalo và Messenger.
 *
 * CẤU HÌNH — Điền thông tin thực tế vào đây:
 */

const STORE_CONFIG = {
  // ⚠️ Số điện thoại Zalo hotline chính (CS1)
  ZALO_PHONE: '0355393871',

  // ⚠️ TODO: Thay bằng Fanpage ID hoặc username Messenger thực tế
  MESSENGER_PAGE_ID: 'thegatevietnamxk',

  // Tên cửa hàng dùng trong tin nhắn mẫu
  STORE_NAME: 'The Gate VNXK',
};

// ─── Tạo Deep Link ────────────────────────────────────────────────────────────

/**
 * Tạo Zalo deep link tư vấn tự động
 * @param {Object} product - sản phẩm
 * @param {string} selectedSize - size đã chọn
 */
export function buildZaloLink(product, selectedSize = '') {
  const price = product.salePrice || product.price;
  const priceStr = new Intl.NumberFormat('vi-VN').format(price) + 'đ';
  const sizeStr = selectedSize || product.sizes[0];

  const message = `Xin chào ${STORE_CONFIG.STORE_NAME}! Tôi muốn tư vấn sản phẩm:\n📦 ${product.name}\n📐 Size: ${sizeStr}\n💰 Giá: ${priceStr}\nShop có thể tư vấn thêm cho mình không?`;

  return `https://zalo.me/${STORE_CONFIG.ZALO_PHONE}?text=${encodeURIComponent(message)}`;
}

/**
 * Tạo Messenger deep link
 * @param {Object} product - sản phẩm (dùng cho ref nếu cần)
 */
export function buildMessengerLink(product, selectedSize = '') {
  // Messenger deep link với ref để tracking (tùy chọn)
  const ref = encodeURIComponent(`sp_${product.id}_${(selectedSize || product.sizes[0]).replace(/\s/g, '')}`);
  return `https://m.me/${STORE_CONFIG.MESSENGER_PAGE_ID}?ref=${ref}`;
}

// ─── Modal HTML Template ───────────────────────────────────────────────────────

function createModalHTML(product) {
  const price = product.salePrice || product.price;
  const salePercent = product.salePrice
    ? Math.round((1 - product.salePrice / product.price) * 100)
    : 0;

  const priceFormatted = new Intl.NumberFormat('vi-VN').format(price) + 'đ';
  const origPriceFormatted = new Intl.NumberFormat('vi-VN').format(product.price) + 'đ';

  const sizeOptions = product.sizes.map((size, i) =>
    `<button class="modal__size-btn ${i === 0 ? 'modal__size-btn--active' : ''}" data-size="${size}">${size}</button>`
  ).join('');

  const colorDots = product.colors.map(color =>
    `<span class="modal__color-tag">${color}</span>`
  ).join('');

  return `
<div class="modal-overlay" id="productModal" role="dialog" aria-modal="true" aria-label="Chi tiết sản phẩm">
  <div class="modal-box">
    <!-- Close -->
    <button class="modal__close" id="modalClose" aria-label="Đóng">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>

    <div class="modal__body">
      <!-- Left: Image -->
      <div class="modal__image-col">
        <div class="modal__main-image-wrap">
          ${product.badge ? `<span class="modal__badge badge badge-${product.badge}">${product.badge === 'hot' ? '🔥 HOT' : product.badge === 'sale' ? `SALE -${salePercent}%` : 'MỚI'}</span>` : ''}
          <img
            id="modalMainImage"
            class="modal__main-image"
            src="${product.images[0]}"
            alt="${product.name}"
            width="500" height="667"
          />
        </div>
      </div>

      <!-- Right: Info -->
      <div class="modal__info-col">
        <span class="modal__category">${product.categoryDisplay} · VNXK</span>
        <h2 class="modal__product-name">${product.name}</h2>

        <!-- Price -->
        <div class="modal__prices">
          <span class="modal__price-sale">${priceFormatted}</span>
          ${product.salePrice ? `<span class="modal__price-orig">${origPriceFormatted}</span><span class="modal__price-badge">-${salePercent}%</span>` : ''}
        </div>

        <!-- Description -->
        <p class="modal__desc">${product.description}</p>

        <!-- Size Picker -->
        <div class="modal__section">
          <div class="modal__section-label">
            Chọn size <span id="selectedSizeLabel" style="color:var(--color-gold);font-weight:600;"></span>
          </div>
          <div class="modal__sizes" id="modalSizes">
            ${sizeOptions}
          </div>
          <div class="modal__size-guide">
            <a href="javascript:void(0)" class="modal__size-guide-link" onclick="return false;">📏 Hướng dẫn chọn size →</a>
          </div>
        </div>

        <!-- Colors -->
        <div class="modal__section">
          <div class="modal__section-label">Màu sắc có sẵn</div>
          <div class="modal__colors">${colorDots}</div>
        </div>

        <!-- Stock note -->
        <div class="modal__stock ${product.inStock ? 'modal__stock--in' : 'modal__stock--out'}">
          ${product.inStock ? '✔ Còn hàng · Giao toàn quốc 2-3 ngày' : '✖ Tạm hết hàng'}
        </div>

        <!-- CTA Buttons -->
        <div class="modal__cta">
          <a
            id="modalZaloBtn"
            href="${buildZaloLink(product, product.sizes[0])}"
            target="_blank"
            rel="noopener noreferrer"
            class="modal__btn modal__btn--zalo"
          >
            <svg width="20" height="20" viewBox="0 0 40 40" fill="currentColor">
              <path d="M20 2C10.06 2 2 10.06 2 20c0 3.55 1 6.87 2.73 9.69L2 38l8.62-2.67A17.92 17.92 0 0020 38c9.94 0 18-8.06 18-18S29.94 2 20 2zm-3.5 10h7c.83 0 1.5.67 1.5 1.5S24.33 15 23.5 15h-7c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5zm9.5 13h-4.5l-5.5 4v-4H13c-.83 0-1.5-.67-1.5-1.5v-8c0-.83.67-1.5 1.5-1.5h13c.83 0 1.5.67 1.5 1.5v8c0 .83-.67 1.5-1.5 1.5z"/>
            </svg>
            Tư vấn qua Zalo
          </a>
          <a
            id="modalMessengerBtn"
            href="${buildMessengerLink(product, product.sizes[0])}"
            target="_blank"
            rel="noopener noreferrer"
            class="modal__btn modal__btn--messenger"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.477 2 2 6.145 2 11.258c0 2.91 1.455 5.51 3.734 7.188V22l3.414-1.874c.907.25 1.867.384 2.852.384 5.523 0 10-4.145 10-9.258S17.523 2 12 2zm1.06 12.544l-2.545-2.716-4.97 2.716 5.466-5.8 2.607 2.716 4.908-2.716-5.466 5.8z"/>
            </svg>
            Chat Messenger
          </a>
        </div>

        <p class="modal__notice">🔒 Cam kết hàng VNXK chính hãng · Đổi trả trong 30 ngày</p>
      </div>
    </div>
  </div>
</div>`;
}

// ─── Modal CSS (inject vào <head>) ────────────────────────────────────────────

const MODAL_CSS = `
.modal-overlay {
  position: fixed; inset: 0; z-index: 900;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  display: flex; align-items: center; justify-content: center;
  padding: 1rem;
  opacity: 0; visibility: hidden;
  transition: opacity 0.3s ease, visibility 0.3s ease;
}
.modal-overlay.active {
  opacity: 1; visibility: visible;
}
.modal-box {
  background: #141414;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  max-width: 900px; width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
  transform: scale(0.95) translateY(20px);
  transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1);
}
.modal-overlay.active .modal-box {
  transform: scale(1) translateY(0);
}
.modal__close {
  position: absolute; top: 1rem; right: 1rem;
  width: 40px; height: 40px; border-radius: 50%;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  color: #f5f5f5; cursor: pointer; z-index: 10;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.modal__close:hover { background: rgba(201,169,110,0.2); border-color: #c9a96e; color: #c9a96e; }
.modal__body {
  display: grid; grid-template-columns: 1fr 1fr; gap: 0;
}
.modal__image-col { padding: 1.5rem; }
.modal__main-image-wrap {
  position: relative; border-radius: 12px; overflow: hidden;
  background: #1a1a1a; aspect-ratio: 3/4;
}
.modal__main-image {
  width: 100%; height: 100%; object-fit: cover;
}
.modal__badge {
  position: absolute; top: 0.75rem; left: 0.75rem; z-index: 2;
}
.modal__info-col {
  padding: 2rem 2rem 2rem 0.5rem;
  display: flex; flex-direction: column; gap: 1rem;
}
.modal__category {
  font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.15em;
  color: #666;
}
.modal__product-name {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: clamp(1.1rem, 2.5vw, 1.5rem);
  font-weight: 700; color: #f5f5f5; line-height: 1.3;
}
.modal__prices { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.modal__price-sale { font-size: 1.6rem; font-weight: 700; color: #c9a96e; }
.modal__price-orig { font-size: 1rem; color: #666; text-decoration: line-through; }
.modal__price-badge {
  background: #f87171; color: #fff;
  font-size: 0.7rem; font-weight: 700;
  padding: 2px 8px; border-radius: 4px; letter-spacing: 0.05em;
}
.modal__desc { font-size: 0.9rem; color: #a0a0a0; line-height: 1.7; }
.modal__section { display: flex; flex-direction: column; gap: 0.6rem; }
.modal__section-label { font-size: 0.8rem; font-weight: 600; color: #a0a0a0; text-transform: uppercase; letter-spacing: 0.1em; }
.modal__sizes { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.modal__size-btn {
  min-width: 48px; height: 40px; padding: 0 0.75rem;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 6px; background: transparent;
  color: #f5f5f5; font-size: 0.85rem; font-weight: 500;
  cursor: pointer; transition: all 0.2s;
}
.modal__size-btn:hover { border-color: #c9a96e; color: #c9a96e; }
.modal__size-btn--active {
  background: #c9a96e; border-color: #c9a96e; color: #0a0a0a;
  font-weight: 700;
}
.modal__size-guide { margin-top: -0.2rem; }
.modal__size-guide-link { font-size: 0.8rem; color: #888; text-decoration: underline; cursor: pointer; }
.modal__colors { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.modal__color-tag {
  padding: 3px 10px; border-radius: 99px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  font-size: 0.78rem; color: #a0a0a0;
}
.modal__stock { font-size: 0.82rem; font-weight: 600; }
.modal__stock--in { color: #4ade80; }
.modal__stock--out { color: #f87171; }
.modal__cta { display: flex; flex-direction: column; gap: 0.75rem; margin-top: 0.5rem; }
.modal__btn {
  display: flex; align-items: center; justify-content: center; gap: 0.6rem;
  min-height: 52px; border-radius: 8px;
  font-size: 0.95rem; font-weight: 700;
  text-decoration: none; transition: all 0.25s; cursor: pointer;
}
.modal__btn--zalo {
  background: #0068ff; color: #fff;
}
.modal__btn--zalo:hover { background: #0052cc; transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,104,255,0.4); color: #fff; }
.modal__btn--messenger {
  background: linear-gradient(135deg, #0095f6, #a855f7);
  color: #fff;
}
.modal__btn--messenger:hover { opacity: 0.9; transform: translateY(-2px); box-shadow: 0 8px 25px rgba(168,85,247,0.3); color: #fff; }
.modal__notice {
  font-size: 0.78rem; color: #555; text-align: center; margin-top: -0.25rem;
}

/* Responsive */
@media (max-width: 640px) {
  .modal__body { grid-template-columns: 1fr; }
  .modal__info-col { padding: 0 1.25rem 1.5rem; }
  .modal__image-col { padding: 1.25rem 1.25rem 0.5rem; }
  .modal__main-image-wrap { aspect-ratio: 4/3; }
}
`;

// ─── Modal Controller ──────────────────────────────────────────────────────────

let currentProduct = null;
let currentSize = null;

export function openProductModal(product) {
  currentProduct = product;
  currentSize = product.sizes[0];

  // Inject styles once
  if (!document.getElementById('modal-styles')) {
    const style = document.createElement('style');
    style.id = 'modal-styles';
    style.textContent = MODAL_CSS;
    document.head.appendChild(style);
  }

  // Remove old modal if any
  const old = document.getElementById('productModal');
  if (old) old.remove();

  // Create & insert
  const wrapper = document.createElement('div');
  wrapper.innerHTML = createModalHTML(product);
  document.body.appendChild(wrapper.firstElementChild);

  const modal = document.getElementById('productModal');
  document.body.style.overflow = 'hidden';

  // Animate in
  requestAnimationFrame(() => modal.classList.add('active'));

  // Size selection logic
  const sizeLabel = document.getElementById('selectedSizeLabel');
  if (sizeLabel) sizeLabel.textContent = currentSize;

  document.querySelectorAll('.modal__size-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.modal__size-btn').forEach(b => b.classList.remove('modal__size-btn--active'));
      btn.classList.add('modal__size-btn--active');
      currentSize = btn.dataset.size;
      if (sizeLabel) sizeLabel.textContent = currentSize;

      // Update deep links dynamically
      const zaloBtn = document.getElementById('modalZaloBtn');
      const messengerBtn = document.getElementById('modalMessengerBtn');
      if (zaloBtn) zaloBtn.href = buildZaloLink(product, currentSize);
      if (messengerBtn) messengerBtn.href = buildMessengerLink(product, currentSize);
    });
  });

  // Close handlers
  document.getElementById('modalClose')?.addEventListener('click', closeProductModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeProductModal();
  });
  document.addEventListener('keydown', handleEscKey);
}

function handleEscKey(e) {
  if (e.key === 'Escape') closeProductModal();
}

export function closeProductModal() {
  const modal = document.getElementById('productModal');
  if (!modal) return;

  modal.classList.remove('active');
  document.body.style.overflow = '';
  document.removeEventListener('keydown', handleEscKey);

  setTimeout(() => {
    modal.remove();
  }, 300);
}
