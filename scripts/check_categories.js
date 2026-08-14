const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');
const prodDataPath = path.join(baseDir, 'js', 'productsData.js');
let content = fs.readFileSync(prodDataPath, 'utf-8');
const dataStr = content.replace(/^const\s+PRODUCTS_DATA\s*=\s*/, '').replace(/;\s*$/, '');
const data = JSON.parse(dataStr);

const products = Object.values(data);
console.log('Total products:', products.length);

const categoryCounts = {
  all: products.length,
  sale: 0,
  sale_50: 0,
  nam: 0,
  nu: 0,
  phukien: 0,
  price_under_200: 0,
  price_200_350: 0,
  price_350_500: 0,
  price_over_500: 0
};

products.forEach(p => {
  const cat = p.category || '';
  const price = p.salePriceNum || 0;
  const isSale = p.isSale || (p.regularPriceNum && p.regularPriceNum > p.salePriceNum);
  
  if (isSale) categoryCounts.sale++;
  if (p.regularPriceNum && p.salePriceNum) {
    const discount = Math.round(((p.regularPriceNum - p.salePriceNum) / p.regularPriceNum) * 100);
    if (discount >= 40) categoryCounts.sale_50++;
  }
  
  if (cat === 'nam') categoryCounts.nam++;
  if (cat === 'nu') categoryCounts.nu++;
  if (cat === 'phukien') categoryCounts.phukien++;
  
  if (price > 0 && price < 200000) categoryCounts.price_under_200++;
  if (price >= 200000 && price <= 350000) categoryCounts.price_200_350++;
  if (price > 350000 && price <= 500000) categoryCounts.price_350_500++;
  if (price > 500000) categoryCounts.price_over_500++;
});

console.log('Category counts:', categoryCounts);

const emptyCategories = Object.entries(categoryCounts).filter(([k, v]) => v === 0);
console.log('Empty categories:', emptyCategories);
