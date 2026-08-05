/**
 * The Gate VNXK — Floating Bottom Bar (Mobile)
 * =============================================
 * Hiển thị 2 nút Zalo + Messenger cố định ở cuối màn hình trên mobile.
 * Tự động ẩn trên desktop.
 */

const FLOATING_CONFIG = {
  // ⚠️ TODO: Thay bằng số điện thoại Zalo thực tế
  ZALO_PHONE: '0366631498',

  // ⚠️ TODO: Thay bằng Fanpage ID Messenger thực tế
  MESSENGER_PAGE_ID: 'thegatevietnamxk',
};

const FLOATING_CSS = `
.floating-bar {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  z-index: 800;
  display: flex;
  height: 60px;
  /* Chỉ hiển thị mobile — ẩn desktop bằng CSS */
}
.floating-bar__btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 60px;       /* ≥ 48px touch target (lỗi K3) */
  font-size: 0.9rem;
  font-weight: 700;
  color: #fff;
  text-decoration: none;
  transition: opacity 0.2s, filter 0.2s;
  -webkit-tap-highlight-color: transparent;
  cursor: pointer;
}
.floating-bar__btn:active {
  filter: brightness(0.85);
}
.floating-bar__btn--zalo {
  background: #0068ff;
  border-right: 1px solid rgba(255,255,255,0.2);
}
.floating-bar__btn--messenger {
  background: linear-gradient(135deg, #0095f6 0%, #a855f7 100%);
}
.floating-bar__icon {
  flex-shrink: 0;
}
.floating-bar__label {
  font-size: 0.85rem;
  white-space: nowrap;
}

/* ─── Chỉ hiển thị trên mobile ─── */
@media (min-width: 768px) {
  .floating-bar { display: none; }
}

/* Đảm bảo footer không bị che khuất bởi floating bar trên mobile */
@media (max-width: 767px) {
  body { padding-bottom: 60px; }
}
`;

const ZALO_SVG = `<svg class="floating-bar__icon" width="24" height="24" viewBox="0 0 40 40" fill="currentColor" aria-hidden="true">
  <path d="M20 2C10.06 2 2 10.06 2 20c0 3.55 1 6.87 2.73 9.69L2 38l8.62-2.67A17.92 17.92 0 0020 38c9.94 0 18-8.06 18-18S29.94 2 20 2zm-3.5 10h7c.83 0 1.5.67 1.5 1.5S24.33 15 23.5 15h-7c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5zm9.5 13h-4.5l-5.5 4v-4H13c-.83 0-1.5-.67-1.5-1.5v-8c0-.83.67-1.5 1.5-1.5h13c.83 0 1.5.67 1.5 1.5v8c0 .83-.67 1.5-1.5 1.5z"/>
</svg>`;

const MESSENGER_SVG = `<svg class="floating-bar__icon" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
  <path d="M12 2C6.477 2 2 6.145 2 11.258c0 2.91 1.455 5.51 3.734 7.188V22l3.414-1.874c.907.25 1.867.384 2.852.384 5.523 0 10-4.145 10-9.258S17.523 2 12 2zm1.06 12.544l-2.545-2.716-4.97 2.716 5.466-5.8 2.607 2.716 4.908-2.716-5.466 5.8z"/>
</svg>`;

export function initFloatingBar() {
  // Inject CSS once
  if (!document.getElementById('floating-bar-styles')) {
    const style = document.createElement('style');
    style.id = 'floating-bar-styles';
    style.textContent = FLOATING_CSS;
    document.head.appendChild(style);
  }

  const zaloHref = `https://zalo.me/${FLOATING_CONFIG.ZALO_PHONE}?text=${encodeURIComponent('Xin chào The Gate VNXK! Tôi muốn được tư vấn về sản phẩm.')}`;
  const messengerHref = `https://m.me/${FLOATING_CONFIG.MESSENGER_PAGE_ID}`;

  const bar = document.createElement('div');
  bar.className = 'floating-bar';
  bar.setAttribute('role', 'navigation');
  bar.setAttribute('aria-label', 'Liên hệ nhanh');
  bar.innerHTML = `
    <a
      href="${zaloHref}"
      target="_blank"
      rel="noopener noreferrer"
      class="floating-bar__btn floating-bar__btn--zalo"
      aria-label="Nhắn tin tư vấn qua Zalo"
    >
      ${ZALO_SVG}
      <span class="floating-bar__label">Tư vấn Zalo</span>
    </a>
    <a
      href="${messengerHref}"
      target="_blank"
      rel="noopener noreferrer"
      class="floating-bar__btn floating-bar__btn--messenger"
      aria-label="Nhắn tin tư vấn qua Messenger"
    >
      ${MESSENGER_SVG}
      <span class="floating-bar__label">Chat Messenger</span>
    </a>
  `;

  document.body.appendChild(bar);
}
