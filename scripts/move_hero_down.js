const fs = require('fs');
const path = require('path');

const indexPath = path.resolve(__dirname, '../index.html');
let html = fs.readFileSync(indexPath, 'utf-8');
const isCRLF = html.includes('\r\n');
html = html.replace(/\r\n/g, '\n');

// 1. Locate Section 2 & 3 (Hero & Commitments)
const heroComment = '<!-- ================================================================= -->\n    <!-- 2. HERO BANNER';
const heroStartIdx = html.indexOf('<!-- 2. HERO BANNER');
const sec2Start = html.lastIndexOf('<!-- ================================================================= -->', heroStartIdx);

const catComment = '<!-- ================================================================= -->\n    <!-- 4. DANH MỤC TUYỂN CHỌN';
const catStartIdx = html.indexOf('<!-- 4. DANH MỤC TUYỂN CHỌN');
const sec4Start = html.lastIndexOf('<!-- ================================================================= -->', catStartIdx);

if (sec2Start === -1 || sec4Start === -1) {
  console.error('Cannot locate Section 2 or Section 4:', { sec2Start, sec4Start });
  process.exit(1);
}

const heroAndCommitmentsHtml = html.substring(sec2Start, sec4Start);

// Remove Section 2 & 3 from the top
html = html.substring(0, sec2Start) + html.substring(sec4Start);

// 2. Locate insertion point (right after Section 5 and before Dark Banner #collection)
const darkBannerComment = '<!-- Dark Banner "The Gate Outdoor & Sportswear" -->';
const darkBannerIdx = html.indexOf(darkBannerComment);

if (darkBannerIdx === -1) {
  console.error('Cannot locate Dark Banner insertion point');
  process.exit(1);
}

// Insert Section 2 & 3 right before Dark Banner
html = html.substring(0, darkBannerIdx) + heroAndCommitmentsHtml + '\n    ' + html.substring(darkBannerIdx);

if (isCRLF) {
  html = html.replace(/\n/g, '\r\n');
}

fs.writeFileSync(indexPath, html, 'utf-8');
console.log('Successfully moved Hero Banner and Commitments below Section 5 (Products Grid)!');
