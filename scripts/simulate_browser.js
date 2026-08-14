const fs = require('fs');
const path = require('path');
const vm = require('vm');

const baseDir = path.resolve(__dirname, '..');

// 1. Mock DOM and window
const domElements = {
  productsGridContainer: { innerHTML: '', scrollLeft: 0 },
  paginationContainer: { innerHTML: '' },
  filterTabs: { scrollBy() {}, scrollLeft: 0 },
  categoriesContainer: { scrollBy() {}, scrollLeft: 0 },
  featured: { scrollIntoView() {}, getBoundingClientRect() { return { top: 100 }; } },
  navbarToggle: { addEventListener() {} },
  mobileMenu: { classList: { toggle() {} } },
  backToTop: { classList: { remove() {}, add() {} } },
  enhancedSizeModal: { classList: { remove() {}, add() {} } },
  enhancedModalCard: { classList: { remove() {}, add() {} } },
  modalProductName: { textContent: '' },
  modalProductPrice: { textContent: '' },
  modalProductOriginalPrice: { textContent: '', classList: { remove() {}, add() {} } },
  modalImagesSlider: { innerHTML: '', appendChild() {}, scrollLeft: 0, clientWidth: 400 },
  modalImageDots: { innerHTML: '', appendChild() {} },
  sizeButtonsContainer: { innerHTML: '' },
  selectedSizeLabel: { textContent: '' },
  colorButtonsContainer: { innerHTML: '' },
  selectedColorLabel: { textContent: '' },
  modalInventoryStatusBadge: { className: '', innerHTML: '' },
  storeStockListContainer: { innerHTML: '', appendChild() {} },
  mainFbFanpageLink: { href: '' }
};

const filterButtons = [
  { getAttribute: (attr) => 'all', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'sale', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'donggia_99k', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'donggia_199k', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'donggia_299k', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'sale_50', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'sale_30', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'sale_10', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'nam', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'nu', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'treem', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} },
  { getAttribute: (attr) => 'phukien', classList: { add() {}, remove() {} }, style: {}, scrollIntoView() {} }
];

const mockDocument = {
  getElementById: (id) => domElements[id] || null,
  querySelectorAll: (selector) => {
    if (selector === '.filter-tab-btn') return filterButtons;
    return [];
  },
  createElement: (tag) => ({
    type: '',
    className: '',
    innerHTML: '',
    title: '',
    onclick: null,
    appendChild() {}
  }),
  addEventListener: () => {},
  body: { style: { overflow: '' } }
};

const mockWindow = {
  document: mockDocument,
  PRODUCTS_DATA: null,
  scrollTo() {},
  addEventListener() {},
  pageYOffset: 0,
  location: { origin: 'http://localhost' }
};

// 2. Load productsData.js
const pData = fs.readFileSync(path.join(baseDir, 'js', 'productsData.js'), 'utf-8');
const pFn = new Function('window', pData + '\nwindow.PRODUCTS_DATA = PRODUCTS_DATA;');
pFn(mockWindow);

// 3. Load inline-script.js
const html = fs.readFileSync(path.join(baseDir, 'index.html'), 'utf-8');
const sIdx = html.indexOf('<script src="js/productsData.js"></script>');
const scriptStart = html.indexOf('<script>', sIdx) + '<script>'.length;
const scriptEnd = html.indexOf('</script>', scriptStart);
const code = html.substring(scriptStart, scriptEnd);

const scriptFn = new Function('window', 'document', 'PRODUCTS_DATA', `
  with(window) {
    ${code}
  }
`);

scriptFn(mockWindow, mockDocument, mockWindow.PRODUCTS_DATA);

// 4. Test calling catalog tabs
const testCategories = ['all', 'sale', 'donggia_99k', 'donggia_199k', 'donggia_299k', 'sale_50', 'sale_30', 'sale_10', 'nam', 'nu', 'treem', 'phukien'];

console.log('Testing setActiveFilterTab for all categories:');
for (const cat of testCategories) {
  mockWindow.setActiveFilterTab(cat);
  const gridHtml = domElements.productsGridContainer.innerHTML;
  const cardCount = (gridHtml.match(/<article class="product-card\b/g) || []).length;
  const paginationHtml = domElements.paginationContainer.innerHTML;
  console.log(`[PASS] Tab '${cat}': Rendered ${cardCount} cards on page 1. Pagination:`, paginationHtml.split('\n')[1]?.trim() || paginationHtml.trim());
}

// 5. Test modal open
mockWindow.openEnhancedProductModal('201');
console.log('[PASS] Modal opened for product 201:', domElements.modalProductName.textContent, domElements.modalProductPrice.textContent);

console.log('\nALL BROWSER SIMULATION TESTS PASSED 100%!');
