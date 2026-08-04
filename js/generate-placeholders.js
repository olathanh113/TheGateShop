/**
 * TheGateShop — Product Image Placeholder Generator
 * Creates bright, clean & vibrant SVG placeholders for The Gate - VNXK & Outdoor products
 */

const products = [
  { name: 'Áo Khoác Dù VNXK',       icon: '🧥', gradient: ['#fff7ed', '#ffedd5'] },
  { name: 'Áo Polo Supplex Cotton', icon: '👕', gradient: ['#f8fafc', '#fff7ed'] },
  { name: 'Quần Kaki Co Giãn',      icon: '👖', gradient: ['#f1f5f9', '#e2e8f0'] },
  { name: 'Áo Rashguard UPF50+',     icon: '🏄', gradient: ['#fff1f2', '#ffe4e6'] },
  { name: 'Áo Phao Outwear VNXK',    icon: '🧥', gradient: ['#ffedd5', '#fed7aa'] },
  { name: 'Đầm Thun Cotton Nữ',      icon: '👗', gradient: ['#fdf4ff', '#fae8ff'] },
  { name: 'Quần Short Quick-Dry',    icon: '🩳', gradient: ['#f0fdf4', '#dcfce7'] },
  { name: 'Áo Sơ Mi Oxford',        icon: '👔', gradient: ['#f0f9ff', '#e0f2fe'] },
  { name: 'Túi Outdoor Waterproof', icon: '🎒', gradient: ['#fff7ed', '#ffe4d6'] },
  { name: 'Mũ Lưỡi Trai Sport',     icon: '🧢', gradient: ['#f8fafc', '#ffedd5'] },
  { name: 'Áo Hoodie Fleece VNXK',  icon: '🧥', gradient: ['#fff7ed', '#ffe4d6'] },
  { name: 'Quần Jogger VNXK Sport',  icon: '👖', gradient: ['#f1f5f9', '#e2e8f0'] },
];

function createSVG(product, index) {
  const [c1, c2] = product.gradient;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800">
  <defs>
    <linearGradient id="bg${index}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="${c1}"/>
      <stop offset="100%" stop-color="${c2}"/>
    </linearGradient>
  </defs>
  <rect width="600" height="800" fill="url(#bg${index})"/>
  <circle cx="300" cy="380" r="160" fill="rgba(255,85,0,0.08)"/>
  <text x="300" y="370" text-anchor="middle" font-size="95">${product.icon}</text>
  <text x="300" y="460" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="700" font-size="24" fill="#0f172a" letter-spacing="0.5">${product.name}</text>
  <text x="300" y="495" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="800" font-size="13" fill="#ff5500" letter-spacing="3">THE GATE — VNXK</text>
</svg>`;
}

// Generate SVG files using Node.js fs
import { writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';

const dir = join(import.meta.dirname, '..', 'assets', 'images', 'products');
mkdirSync(dir, { recursive: true });

products.forEach((product, i) => {
  const filename = `product-${String(i + 1).padStart(2, '0')}.svg`;
  writeFileSync(join(dir, filename), createSVG(product, i));
  console.log(`Created bright VNXK placeholder: ${filename}`);
});

console.log('\nAll bright VNXK product placeholders generated!');
