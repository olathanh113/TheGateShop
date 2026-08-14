const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');

// Mock DOM
let sliderContent = [];
const domElements = {
  modalImagesSlider: {
    innerHTML: '',
    appendChild(child) { sliderContent.push(child.innerHTML); },
    scrollLeft: 0,
    clientWidth: 360
  },
  modalImageDots: { innerHTML: '', appendChild() {} },
  sizeButtonsContainer: { innerHTML: '' },
  selectedSizeLabel: { textContent: '' },
  colorButtonsContainer: { innerHTML: '' },
  selectedColorLabel: { textContent: '' },
  modalProductName: { textContent: '' },
  modalSelectedVariantCode: { innerHTML: '' },
  modalProductPrice: { textContent: '' },
  modalProductOriginalPrice: { textContent: '', classList: { remove() {}, add() {} } },
  stockBadgeContainer: { className: '', innerHTML: '' },
  storeStockListContainer: { innerHTML: '', appendChild() {} },
  mainFbFanpageLink: { href: '' },
  enhancedSizeModal: { classList: { remove() {}, add() {} } },
  enhancedModalCard: { classList: { remove() {}, add() {} } }
};

const mockWindow = {
  document: {
    getElementById: id => domElements[id] || null,
    querySelectorAll: () => [],
    createElement: () => ({ innerHTML: '', className: '', onclick: null, title: '' }),
    addEventListener: () => {},
    body: { style: { overflow: '' } }
  },
  scrollTo() {},
  addEventListener() {},
  location: { origin: 'http://localhost' }
};

// Load productsData.js
const pData = fs.readFileSync(path.join(baseDir, 'js', 'productsData.js'), 'utf-8');
const pFn = new Function('window', pData + '\nwindow.PRODUCTS_DATA = PRODUCTS_DATA;');
pFn(mockWindow);

// Load inline script
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

scriptFn(mockWindow, mockWindow.document, mockWindow.PRODUCTS_DATA);

// Test Product 231
console.log('Testing open modal for 231 (Tee Cộc Mode Of One Graphic 1025):');
sliderContent = [];
mockWindow.openEnhancedProductModal('231');
console.log('  Initial Color:', mockWindow.document.getElementById('selectedColorLabel').textContent);
console.log('  Loaded Slider Photos count:', sliderContent.length);
sliderContent.forEach((c, idx) => console.log('    Photo ' + (idx+1) + ':', c));

console.log('\nCustomer clicks Color Tag "WH" (Trắng):');
sliderContent = [];
mockWindow.selectModalColor('WH');
console.log('  Selected Color:', mockWindow.document.getElementById('selectedColorLabel').textContent);
console.log('  Loaded Slider Photos count:', sliderContent.length);
sliderContent.forEach((c, idx) => console.log('    Photo ' + (idx+1) + ':', c));

console.log('\nCustomer clicks Color Tag "GRY" (Xám):');
sliderContent = [];
mockWindow.selectModalColor('GRY');
console.log('  Selected Color:', mockWindow.document.getElementById('selectedColorLabel').textContent);
console.log('  Loaded Slider Photos count:', sliderContent.length);
sliderContent.forEach((c, idx) => console.log('    Photo ' + (idx+1) + ':', c));

console.log('\nCustomer clicks Color Tag "IO" (Indigo):');
sliderContent = [];
mockWindow.selectModalColor('IO');
console.log('  Selected Color:', mockWindow.document.getElementById('selectedColorLabel').textContent);
console.log('  Loaded Slider Photos count:', sliderContent.length);
sliderContent.forEach((c, idx) => console.log('    Photo ' + (idx+1) + ':', c));
