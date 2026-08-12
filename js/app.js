/**
 * TheGateShop — Main Application Entry
 */

import { initNavbar } from './components/navbar.js';
import { renderProducts } from './components/productCard.js';
import { initScrollAnimations, initParallax } from './utils/animations.js';
import { initCartDrawer } from './components/cartDrawer.js';
import { initWishlistDrawer } from './components/wishlistDrawer.js';
import { initSearchModal } from './components/searchModal.js';
import { showToast } from './utils/helpers.js';

class App {
  constructor() {
    this.products = [];
    this.currentFilter = 'all';
  }

  async init() {
    // Load products
    await this.loadProducts();

    // Initialize navbar & drawers
    initNavbar();
    initCartDrawer();
    initWishlistDrawer();
    initSearchModal(this.products);

    // Render & tabs
    this.renderFeaturedProducts(this.currentFilter, 8);
    this.initProductTabs();
    this.initLoadMore();
    this.initBackToTop();
    this.initNewsletter();

    // Animations (after DOM is ready)
    requestAnimationFrame(() => {
      initScrollAnimations();
      initParallax();
    });
  }

  async loadProducts() {
    // Attempt loading live catalog from /api/catalog first via window.TheGateCatalog
    if (typeof window !== 'undefined' && window.TheGateCatalog && typeof window.TheGateCatalog.load === 'function') {
      try {
        const payload = await window.TheGateCatalog.load({ endpoint: '/api/catalog', timeoutMs: 5000, attempts: 2 });
        if (payload && Array.isArray(payload.items) && payload.items.length > 0) {
          this.products = payload.items.map((item, idx) => ({
            id: item.code || `catalog-${idx + 1}`,
            code: item.code,
            name: item.name,
            price: item.sale_price,
            salePrice: item.sale_price,
            category: 'all',
            categoryDisplay: 'Catalog Master',
            images: item.images,
            rating: 5,
            reviewCount: 18,
            sizes: ['S', 'M', 'L', 'XL'],
            colors: ['#0f172a', '#ea580c']
          }));
          return;
        }
      } catch (catalogErr) {
        console.warn('Live catalog degraded or offline, activating fallback local data:', catalogErr.message);
      }
    }

    // Fallback to local static dataset
    try {
      const res = await fetch('data/products.json');
      this.products = await res.json();
    } catch (err) {
      console.error('Failed to load products:', err);
      this.products = [];
    }
  }

  renderFeaturedProducts(filter = 'all', limit = 8) {
    const container = document.getElementById('featuredProductsGrid');
    if (!container) return;

    let filtered = this.products;
    if (filter !== 'all') {
      filtered = this.products.filter(p => {
        const price = typeof p.salePrice === 'number' ? p.salePrice : (typeof p.price === 'number' ? p.price : 0);
        if (filter === 'sale') return p.category === 'sale' || p.salePrice < p.price;
        if (filter === 'sale_50') return p.category === 'sale' || (p.price > 0 && (p.price - price) / p.price >= 0.4);
        if (filter === 'price_under_200') return price > 0 && price < 200000;
        if (filter === 'price_200_350') return price >= 200000 && price <= 350000;
        if (filter === 'price_350_500') return price > 350000 && price <= 500000;
        if (filter === 'price_over_500') return price > 500000;
        return p.category === filter;
      });
    }

    if (limit && limit < filtered.length) {
      filtered = filtered.slice(0, limit);
    }

    renderProducts(container, filtered);

    // Re-init animations for new cards
    requestAnimationFrame(() => initScrollAnimations());
  }

  initProductTabs() {
    const tabs = document.querySelectorAll('.featured-products__tab');

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        // Update active state
        tabs.forEach(t => t.classList.remove('featured-products__tab--active'));
        tab.classList.add('featured-products__tab--active');

        // Filter products
        const filter = tab.dataset.filter;
        this.currentFilter = filter;
        this.renderFeaturedProducts(filter, 8);

        // Reset load more button
        const btn = document.getElementById('loadMoreBtn');
        if (btn) btn.style.display = 'inline-flex';
      });
    });
  }

  initLoadMore() {
    const btn = document.getElementById('loadMoreBtn');
    if (!btn) return;

    btn.addEventListener('click', () => {
      this.renderFeaturedProducts(this.currentFilter, 99);
      btn.style.display = 'none';
      showToast('Đã tải toàn bộ danh sách sản phẩm!', 'info');
    });
  }

  initBackToTop() {
    const btn = document.getElementById('backToTop');
    if (!btn) return;

    window.addEventListener('scroll', () => {
      if (window.scrollY > 600) {
        btn.classList.add('visible');
      } else {
        btn.classList.remove('visible');
      }
    }, { passive: true });

    btn.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  initNewsletter() {
    const form = document.getElementById('newsletterForm');
    const input = document.getElementById('newsletterEmail');
    if (!form || !input) return;

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = input.value.trim();
      if (email) {
        showToast(`Cảm ơn bạn! "${email}" đã được thêm vào danh sách ưu đãi.`, 'success');
        input.value = '';
      }
    });
  }
}

// Start app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init();
});

