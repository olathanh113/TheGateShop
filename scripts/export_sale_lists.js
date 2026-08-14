const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');

async function extractSaleLists() {
  const urlCatalog = 'https://catalog-api-production-6f96.up.railway.app/v1/website/catalog';
  console.log('Fetching live catalog from Railway...');
  const res = await fetch(urlCatalog, { headers: { 'Accept': 'application/json' } });
  const data = await res.json();
  
  const items = data.items || [];
  console.log(`Total products: ${items.length}`);
  
  const list99k = [];
  const list199k = [];
  const list299k = [];
  const listSale50 = [];
  const listSale30 = [];
  const listSale10 = [];

  function formatVND(num) {
    return new Intl.NumberFormat('vi-VN').format(num) + 'đ';
  }

  items.forEach(it => {
    const salePrice = it.sale_price || it.price || 0;
    const regPrice = it.regular_price || 0;
    const discount = (regPrice > 0 && regPrice > salePrice) ? Math.round(((regPrice - salePrice) / regPrice) * 100) : 0;
    
    const info = {
      code: it.code || 'N/A',
      name: it.name || 'Sản phẩm The Gate',
      salePrice: salePrice,
      salePriceStr: formatVND(salePrice),
      regPrice: regPrice,
      regPriceStr: regPrice > 0 ? formatVND(regPrice) : 'N/A',
      discount: discount,
      image: (it.images && it.images[0]) || ''
    };

    // 1. Phân loại theo mức giá đồng giá
    if (salePrice === 99000 || (salePrice >= 90000 && salePrice <= 99000)) {
      list99k.push(info);
    }
    if (salePrice === 199000 || (salePrice >= 190000 && salePrice <= 199000)) {
      list199k.push(info);
    }
    if (salePrice === 299000 || (salePrice >= 290000 && salePrice <= 299000)) {
      list299k.push(info);
    }

    // 2. Phân loại theo tỷ lệ % giảm giá (Sale)
    if (discount >= 45 && discount <= 55) {
      listSale50.push(info);
    }
    if (discount >= 25 && discount <= 35) {
      listSale30.push(info);
    }
    if (discount >= 8 && discount <= 15) {
      listSale10.push(info);
    }
  });

  console.log(`- Đồng giá 99K: ${list99k.length}`);
  console.log(`- Đồng giá 199K: ${list199k.length}`);
  console.log(`- Đồng giá 299K: ${list299k.length}`);
  console.log(`- Sale 50% (45%-55%): ${listSale50.length}`);
  console.log(`- Sale 30% (25%-35%): ${listSale30.length}`);
  console.log(`- Sale 10% (8%-15%): ${listSale10.length}`);

  // TẠO FILE TXT
  let txt = `================================================================================\n`;
  txt += `THE GATE SHOP — DANH SÁCH LỌC SẢN PHẨM THEO DEAL ĐỒNG GIÁ & % SALE\n`;
  txt += `Nguồn dữ liệu: Live Railway API KiotViet (${items.length} sản phẩm)\n`;
  txt += `Thời gian xuất báo cáo: ${new Date().toLocaleString('vi-VN')}\n`;
  txt += `================================================================================\n\n`;

  txt += `TỔNG HỢP SỐ LƯỢNG:\n`;
  txt += `1. Sản phẩm Đồng giá 99K         : ${list99k.length} sản phẩm\n`;
  txt += `2. Sản phẩm Đồng giá 199K        : ${list199k.length} sản phẩm\n`;
  txt += `3. Sản phẩm Đồng giá 299K        : ${list299k.length} sản phẩm\n`;
  txt += `4. Sản phẩm SALE 50% (45% - 55%) : ${listSale50.length} sản phẩm\n`;
  txt += `5. Sản phẩm SALE 30% (25% - 35%) : ${listSale30.length} sản phẩm\n`;
  txt += `6. Sản phẩm SALE 10% (8% - 15%)  : ${listSale10.length} sản phẩm\n`;
  txt += `\n` + `=`.repeat(80) + `\n\n`;

  function appendSection(title, list) {
    let out = `### ${title.toUpperCase()} (TỔNG: ${list.length} SẢN PHẨM)\n`;
    out += `-`.repeat(80) + `\n`;
    list.forEach((p, idx) => {
      out += `${idx + 1}. [Mã: ${p.code}] ${p.name}\n`;
      out += `   - Giá bán / Deal: ${p.salePriceStr} | Giá gốc: ${p.regPriceStr} | Giảm: ${p.discount}%\n`;
      if (p.image) out += `   - Link ảnh: ${p.image}\n`;
    });
    out += `\n` + `=`.repeat(80) + `\n\n`;
    return out;
  }

  txt += appendSection('1. Danh sách sản phẩm Đồng giá 99K', list99k);
  txt += appendSection('2. Danh sách sản phẩm Đồng giá 199K', list199k);
  txt += appendSection('3. Danh sách sản phẩm Đồng giá 299K', list299k);
  txt += appendSection('4. Danh sách sản phẩm SALE 50% (Giảm 45% - 55%)', listSale50);
  txt += appendSection('5. Danh sách sản phẩm SALE 30% (Giảm 25% - 35%)', listSale30);
  txt += appendSection('6. Danh sách sản phẩm SALE 10% (Giảm 8% - 15%)', listSale10);

  const txtPath = path.join(baseDir, 'DANH_SACH_SAN_PHAM_SALE_THE_GATE.txt');
  fs.writeFileSync(txtPath, txt, 'utf-8');
  console.log(`Created TXT file: ${txtPath}`);

  // TẠO FILE MARKDOWN / DOCS
  let md = `# 🏷️ BẢNG TỔNG HỢP SẢN PHẨM SALE & ĐỒNG GIÁ THE GATE\n\n`;
  md += `> **Nguồn dữ liệu**: Live API Railway \`/v1/website/catalog\` (KiotViet)\n`;
  md += `> **Tổng số sản phẩm quét**: **${items.length}** sản phẩm\n`;
  md += `> **Thời gian tạo**: ${new Date().toLocaleString('vi-VN')}\n\n`;

  md += `## 📊 1. Bảng tóm tắt số lượng\n\n`;
  md += `| Danh mục Deal | Tiêu chí lọc | Số lượng sản phẩm |\n`;
  md += `| :--- | :--- | :--- |\n`;
  md += `| **Đồng giá 99K** | Giá bán ~ 99.000đ | **${list99k.length}** sản phẩm |\n`;
  md += `| **Đồng giá 199K** | Giá bán ~ 199.000đ | **${list199k.length}** sản phẩm |\n`;
  md += `| **Đồng giá 299K** | Giá bán ~ 299.000đ | **${list299k.length}** sản phẩm |\n`;
  md += `| **SALE 50%** | Giảm từ 45% - 55% | **${listSale50.length}** sản phẩm |\n`;
  md += `| **SALE 30%** | Giảm từ 25% - 35% | **${listSale30.length}** sản phẩm |\n`;
  md += `| **SALE 10%** | Giảm từ 8% - 15% | **${listSale10.length}** sản phẩm |\n\n`;
  md += `---\n\n`;

  function appendMdSection(title, list) {
    let out = `## ${title} (${list.length} sản phẩm)\n\n`;
    out += `| STT | Mã SP | Tên sản phẩm | Giá Deal / Bán | Giá Gốc | % Giảm |\n`;
    out += `| :--- | :--- | :--- | :--- | :--- | :--- |\n`;
    list.slice(0, 150).forEach((p, idx) => {
      out += `| ${idx + 1} | \`${p.code}\` | ${p.name} | **${p.salePriceStr}** | ~~${p.regPriceStr}~~ | -${p.discount}% |\n`;
    });
    if (list.length > 150) {
      out += `\n*(Hiển thị 150 sản phẩm tiêu biểu trên tài liệu tóm tắt, xem toàn bộ ${list.length} sản phẩm đầy đủ trong file \`DANH_SACH_SAN_PHAM_SALE_THE_GATE.txt\`)*\n\n`;
    }
    out += `\n---\n\n`;
    return out;
  }

  md += appendMdSection('🔥 2. Danh sách Đồng giá 99K', list99k);
  md += appendMdSection('🏷️ 3. Danh sách Đồng giá 199K', list199k);
  md += appendMdSection('💎 4. Danh sách Đồng giá 299K', list299k);
  md += appendMdSection('⚡ 5. Danh sách SALE 50%', listSale50);
  md += appendMdSection('✨ 6. Danh sách SALE 30%', listSale30);
  md += appendMdSection('🎉 7. Danh sách SALE 10%', listSale10);

  const mdPath = path.join(baseDir, 'DANH_SACH_SAN_PHAM_SALE_THE_GATE.md');
  fs.writeFileSync(mdPath, md, 'utf-8');
  console.log(`Created MD/DOCS file: ${mdPath}`);
}

extractSaleLists().catch(console.error);
