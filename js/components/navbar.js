/**
 * TheGateShop — Navbar Component
 */

import { getCartCount, getWishlistCount } from '../utils/helpers.js';

export function initNavbar() {
  const navbar = document.getElementById('navbar');
  const toggle = document.getElementById('navbarToggle');
  const mobileMenu = document.getElementById('mobileMenu');

  if (!navbar) return;

  // Scroll behavior — transparent to solid
  let lastScroll = 0;

  function handleScroll() {
    const scrollY = window.scrollY;

    if (scrollY > 80) {
      navbar.classList.remove('navbar--transparent');
      navbar.classList.add('navbar--solid');
    } else {
      navbar.classList.add('navbar--transparent');
      navbar.classList.remove('navbar--solid');
    }

    lastScroll = scrollY;
  }

  window.addEventListener('scroll', handleScroll, { passive: true });
  handleScroll();

  // Mobile menu toggle
  if (toggle && mobileMenu) {
    toggle.addEventListener('click', () => {
      toggle.classList.toggle('active');
      mobileMenu.classList.toggle('open');
      document.body.style.overflow = mobileMenu.classList.contains('open') ? 'hidden' : '';
    });

    // Close mobile menu when clicking a link
    mobileMenu.querySelectorAll('.navbar__mobile-link').forEach(link => {
      link.addEventListener('click', () => {
        toggle.classList.remove('active');
        mobileMenu.classList.remove('open');
        document.body.style.overflow = '';
      });
    });
  }

  // Update counts
  updateCartCount();
  updateWishlistCount();
}

export function updateCartCount() {
  const count = getCartCount();
  document.querySelectorAll('.navbar__cart-count').forEach(el => {
    el.textContent = count;
    el.style.display = count > 0 ? 'flex' : 'none';
  });
}

export function updateWishlistCount() {
  const count = getWishlistCount();
  document.querySelectorAll('.navbar__wishlist-count').forEach(el => {
    el.textContent = count;
    el.style.display = count > 0 ? 'flex' : 'none';
  });
}

