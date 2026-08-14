const fs = require('fs');
const path = require('path');
const vm = require('vm');

const baseDir = path.resolve(__dirname, '..');
const productsFilePath = path.join(baseDir, 'js', 'productsData.js');

// 1. Read existing raw or consolidated products
const dataStr = fs.readFileSync(productsFilePath, 'utf-8');
const sandbox = { window: {} };
sandbox.window = sandbox;
vm.runInNewContext(dataStr, sandbox);
const productsObj = sandbox.PRODUCTS_DATA;

// Get all raw variants (flatten if previously consolidated)
let allRawVariants = [];
Object.values(productsObj).forEach(item => {
  if (item.variants && item.variants.length > 0) {
    item.variants.forEach(v => {
      allRawVariants.push({
        ...v,
        categories: item.categories || ['all'],
        category: item.category || 'all',
        discountPercent: item.discountPercent,
        badgeText: item.badgeText,
        badgeColor: item.badgeColor
      });
    });
  } else {
    allRawVariants.push(item);
  }
});

console.log('Total raw variants to process:', allRawVariants.length);

// Color code dictionary with Vietnamese labels and Hex values
const COLOR_MAP = {
  'WH': { label: 'Trắng (WH)', hex: '#ffffff' },
  'WHT': { label: 'Trắng (WH)', hex: '#ffffff' },
  'WHITE': { label: 'Trắng', hex: '#ffffff' },
  'BK': { label: 'Đen (BK)', hex: '#0f172a' },
  'BLK': { label: 'Đen (BK)', hex: '#0f172a' },
  'BLACK': { label: 'Đen', hex: '#0f172a' },
  'NV': { label: 'Xanh than (NV)', hex: '#1e3a8a' },
  'NAVY': { label: 'Xanh than', hex: '#1e3a8a' },
  'D.NV': { label: 'Xanh than đậm', hex: '#172554' },
  'GRN': { label: 'Xanh lá (GRN)', hex: '#16a34a' },
  'GN': { label: 'Xanh lá (GN)', hex: '#16a34a' },
  'GREEN': { label: 'Xanh lá', hex: '#16a34a' },
  'L.GRN': { label: 'Xanh lá nhạt', hex: '#86efac' },
  'P.GRN': { label: 'Xanh bơ (P.GRN)', hex: '#4ade80' },
  'GRY': { label: 'Xám (GRY)', hex: '#94a3b8' },
  'GREY': { label: 'Xám (Grey)', hex: '#94a3b8' },
  'GRAY': { label: 'Xám (Gray)', hex: '#94a3b8' },
  'D.GRY': { label: 'Xám đậm', hex: '#475569' },
  'L.GRY': { label: 'Xám nhạt', hex: '#cbd5e1' },
  'MGRY': { label: 'Xám Melange', hex: '#94a3b8' },
  'BE': { label: 'Be / Kem (BE)', hex: '#f5f5dc' },
  'BG': { label: 'Be / Beige (BG)', hex: '#f5f5dc' },
  'BEIGE': { label: 'Màu Be', hex: '#f5f5dc' },
  'L.BE': { label: 'Be sáng', hex: '#fef08a' },
  'KH': { label: 'Khaki (KH)', hex: '#c3b091' },
  'KHA': { label: 'Khaki (KHA)', hex: '#c3b091' },
  'D.KHA': { label: 'Khaki đậm', hex: '#a39073' },
  'BR': { label: 'Nâu (BR)', hex: '#78350f' },
  'BRN': { label: 'Nâu (BRN)', hex: '#78350f' },
  'BROWN': { label: 'Nâu', hex: '#78350f' },
  'BL': { label: 'Xanh dương (BL)', hex: '#2563eb' },
  'BLU': { label: 'Xanh dương (BLU)', hex: '#2563eb' },
  'BLUE': { label: 'Xanh dương', hex: '#2563eb' },
  'L.BL': { label: 'Xanh biển nhạt', hex: '#60a5fa' },
  'SKY': { label: 'Xanh da trời', hex: '#38bdf8' },
  'PNK': { label: 'Hồng (PNK)', hex: '#ec4899' },
  'PK': { label: 'Hồng (PK)', hex: '#ec4899' },
  'PINK': { label: 'Hồng', hex: '#ec4899' },
  'L.PNK': { label: 'Hồng nhạt', hex: '#fbcfe8' },
  'RD': { label: 'Đỏ (RD)', hex: '#dc2626' },
  'RED': { label: 'Đỏ', hex: '#dc2626' },
  'OR': { label: 'Cam (OR)', hex: '#ea580c' },
  'ORANGE': { label: 'Cam', hex: '#ea580c' },
  'YL': { label: 'Vàng (YL)', hex: '#eab308' },
  'YE': { label: 'Vàng (YE)', hex: '#eab308' },
  'YEL': { label: 'Vàng (YEL)', hex: '#eab308' },
  'YELLOW': { label: 'Vàng', hex: '#eab308' },
  'LAV': { label: 'Tím Lavender', hex: '#c084fc' },
  'VIO': { label: 'Tím Violet (VIO)', hex: '#7c3aed' },
  'IV': { label: 'Ngà / Ivory (IV)', hex: '#fffff0' },
  'IVORY': { label: 'Màu Ngà', hex: '#fffff0' },
  'OL': { label: 'Xanh Olive (OL)', hex: '#556b2f' },
  'OLV': { label: 'Xanh Olive', hex: '#556b2f' },
  'CH': { label: 'Than chì (CH)', hex: '#334155' },
  'CHA': { label: 'Than chì (CHA)', hex: '#334155' },
  'CR': { label: 'Kem / Cream (CR)', hex: '#fdfbf7' },
  'CREAM': { label: 'Màu Kem', hex: '#fdfbf7' },
  'TB': { label: 'Teal Blue (TB)', hex: '#0f766e' },
  'IO': { label: 'Indigo (IO)', hex: '#312e81' },
  'IG': { label: 'Ice Gray (IG)', hex: '#e2e8f0' },
  'Off Wh': { label: 'Trắng Ngà (Off Wh)', hex: '#fafafa' },
  'COR': { label: 'San Hô (Coral)', hex: '#fb7185' },
  'MNT': { label: 'Bạc Hà (Mint)', hex: '#6ee7b7' },
  'LIM': { label: 'Xanh Chanh (Lime)', hex: '#a3e635' },
  'TAN': { label: 'Nâu Tan', hex: '#d2b48c' },
  'STONE': { label: 'Màu Đá (Stone)', hex: '#a8a29e' },
  'SAND': { label: 'Màu Cát (Sand)', hex: '#e7e5e4' },
  'WOOD': { label: 'Màu Gỗ (Wood)', hex: '#a16207' },
  'MAGNET': { label: 'Xám Magnet', hex: '#64748b' },
  'ICE': { label: 'Màu Băng (Ice)', hex: '#e0f2fe' },
  'DENIM': { label: 'Xanh Denim', hex: '#1d4ed8' },
  'DN': { label: 'Denim (DN)', hex: '#1d4ed8' },
  'BUR': { label: 'Đỏ Rượu Burgundy', hex: '#881337' },
  'PP': { label: 'Tím Purple', hex: '#9333ea' },
  'DG': { label: 'Xanh Rêu Đậm', hex: '#14532d' },
  'CM': { label: 'Màu Camel', hex: '#b45309' },
  'ROSE': { label: 'Hồng Rose', hex: '#f43f5e' }
};

const KNOWN_SIZES = new Set([
  'XXS', 'XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL', '2X', '3X', '4X', 'F', 'FREESIZE', 'FREE SIZE',
  '2', '4', '6', '8', '10', '12', '14', '16', '18', '20', '22', '24', '26',
  '28', '29', '30', '31', '32', '33', '34', '35', '36', '38', '40',
  '70', '73', '76', '80', '85', '90', '95', '100', '105', '110', '115', '120', '130', '140', '150', '160',
  '15 1/2', '16 1/2', '17 1/2'
]);

function isSize(val) {
  if (!val) return false;
  const upper = val.trim().toUpperCase();
  return KNOWN_SIZES.has(upper);
}

function parseName(fullName) {
  const parts = fullName.split(' - ').map(s => s.trim()).filter(Boolean);
  if (parts.length === 1) {
    return { baseName: fullName, size: 'Tiêu chuẩn', color: 'Tiêu chuẩn' };
  }

  let size = 'Tiêu chuẩn';
  let color = 'Tiêu chuẩn';
  let nameParts = [];

  // Check from the end of the parts array
  const last = parts[parts.length - 1];
  const secondLast = parts.length > 2 ? parts[parts.length - 2] : null;
  const thirdLast = parts.length > 3 ? parts[parts.length - 3] : null;

  if (parts.length === 2) {
    if (isSize(last)) {
      size = last;
      nameParts = [parts[0]];
    } else {
      color = last;
      nameParts = [parts[0]];
    }
  } else if (parts.length >= 3) {
    if (isSize(last)) {
      size = last;
      if (secondLast && !/^\d+$/.test(secondLast)) {
        color = secondLast;
        nameParts = parts.slice(0, parts.length - 2);
      } else if (thirdLast) {
        color = thirdLast;
        nameParts = parts.slice(0, parts.length - 3);
      } else {
        nameParts = parts.slice(0, parts.length - 1);
      }
    } else if (isSize(secondLast)) {
      size = secondLast;
      color = last;
      nameParts = parts.slice(0, parts.length - 2);
    } else {
      color = last;
      nameParts = parts.slice(0, parts.length - 1);
    }
  }

  const baseName = nameParts.join(' - ').trim();
  return { baseName: baseName || parts[0], size, color };
}

const parentMap = {};

allRawVariants.forEach(p => {
  const code = (p.code || p.id || '').trim();
  const baseCode = code.replace(/[-_]\d+$/, '').trim();
  const parsed = parseName(p.name || '');

  // If variant already had explicit size/color, prioritize valid ones
  let size = (p.size && p.size !== 'Tiêu chuẩn') ? p.size : parsed.size;
  let color = (p.color && p.color !== 'Tiêu chuẩn') ? p.color : parsed.color;

  // Swap if size was put into color or vice versa
  if (isSize(color) && !isSize(size)) {
    const temp = size;
    size = color;
    color = temp;
  }

  if (!parentMap[baseCode]) {
    parentMap[baseCode] = {
      id: baseCode,
      code: baseCode,
      name: parsed.baseName,
      price: p.price,
      priceVal: p.priceVal,
      originalPrice: p.originalPrice,
      discountPercent: p.discountPercent,
      badgeText: p.badgeText,
      badgeColor: p.badgeColor,
      category: p.category,
      categoriesSet: new Set(p.categories || ['all']),
      colorImages: {}, // Map: colorName -> [img1, img2...]
      sizesSet: new Set(),
      colorsSet: new Set(),
      variants: []
    };
  }

  const parent = parentMap[baseCode];
  (p.categories || []).forEach(cat => parent.categoriesSet.add(cat));

  parent.sizesSet.add(size);
  parent.colorsSet.add(color);

  // Group images under this specific color
  if (!parent.colorImages[color]) {
    parent.colorImages[color] = [];
  }
  const variantImgs = p.images || [];
  variantImgs.forEach(img => {
    if (img && !parent.colorImages[color].includes(img)) {
      // Keep up to 3 unique photos per color
      if (parent.colorImages[color].length < 3) {
        parent.colorImages[color].push(img);
      }
    }
  });

  parent.variants.push({
    code: p.code || code,
    name: p.name,
    size: size,
    color: color,
    price: p.price,
    originalPrice: p.originalPrice,
    images: variantImgs.slice(0, 2),
    availability: p.availability || { ton_that_thiep: 'in_stock', nguyen_trai: 'in_stock', tam_coc: 'in_stock' }
  });
});

const STANDARD_SIZES_ORDER = [
  'XXS', 'XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL', '2X', '3X', '4X', 'F', 'FreeSize',
  '2', '4', '6', '8', '10', '12', '14', '16', '18', '20', '22', '24', '26',
  '28', '29', '30', '31', '32', '33', '34', '35', '36', '38', '40',
  '70', '73', '76', '80', '85', '90', '95', '100', '105', '110', '115', '120', '130', '140', '150', '160',
  '15 1/2', '16 1/2'
];

function sortSizes(sizes) {
  return [...sizes].sort((a, b) => {
    const idxA = STANDARD_SIZES_ORDER.indexOf(a);
    const idxB = STANDARD_SIZES_ORDER.indexOf(b);
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    return a.localeCompare(b);
  });
}

const finalProductsData = {};

Object.keys(parentMap).forEach(key => {
  const p = parentMap[key];
  const sortedSizes = sortSizes(Array.from(p.sizesSet));

  const colorsList = Array.from(p.colorsSet).map(cName => {
    const upper = cName.trim().toUpperCase();
    const mapped = COLOR_MAP[cName] || COLOR_MAP[upper];
    if (mapped) {
      return { name: cName, label: mapped.label, hex: mapped.hex };
    }
    return { name: cName, label: cName, hex: '#475569' };
  });

  // Build clean deduplicated parent.images (1-2 representative photos per color)
  const masterImages = [];
  Object.keys(p.colorImages).forEach(cName => {
    const cImgs = p.colorImages[cName];
    if (cImgs && cImgs.length > 0) {
      cImgs.forEach(img => {
        if (!masterImages.includes(img) && masterImages.length < 8) {
          masterImages.push(img);
        }
      });
    }
  });

  if (masterImages.length === 0) {
    masterImages.push('assets/images/products/product-01.svg');
  }

  finalProductsData[key] = {
    id: p.id,
    code: p.code,
    name: p.name,
    price: p.price,
    priceVal: p.priceVal,
    originalPrice: p.originalPrice,
    discountPercent: p.discountPercent,
    badgeText: p.badgeText,
    badgeColor: p.badgeColor,
    category: p.category,
    categories: Array.from(p.categoriesSet),
    images: masterImages,
    colorImages: p.colorImages, // Map of color -> unique photos
    sizes: sortedSizes.length ? sortedSizes : ['Tiêu chuẩn'],
    colors: colorsList.length ? colorsList : [{ name: 'Tiêu chuẩn', label: 'Tiêu chuẩn', hex: '#1e293b' }],
    variants: p.variants
  };
});

console.log('Consolidated into parent products count:', Object.keys(finalProductsData).length);

// Write to js/productsData.js
const fileContent = `/**
 * THE GATE SHOP - CONSOLIDATED PRODUCT CATALOG (KIOTVIET LIVE SYNC)
 * Total parent products: ${Object.keys(finalProductsData).length}
 * Total variants consolidated: ${allRawVariants.length}
 */
const PRODUCTS_DATA = ${JSON.stringify(finalProductsData, null, 2)};

if (typeof window !== 'undefined') {
  window.PRODUCTS_DATA = PRODUCTS_DATA;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = PRODUCTS_DATA;
}
`;

fs.writeFileSync(productsFilePath, fileContent, 'utf-8');
console.log('Successfully wrote deduplicated colorImages to productsData.js!');
