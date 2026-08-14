const fs = require('fs');

async function testMapping() {
  const urlCatalog = 'https://catalog-api-production-6f96.up.railway.app/v1/website/catalog';
  const cRes = await fetch(urlCatalog, { headers: { 'Accept': 'application/json' } });
  const data = await cRes.json();
  
  console.log('Total items fetched:', data.items.length);
  
  let withSaleCount = 0;
  let inStockCount = 0;
  
  data.items.forEach(it => {
    if (it.is_sale || (it.regular_price && it.regular_price > it.sale_price)) withSaleCount++;
    const avail = it.availability || {};
    if (avail.ton_that_thiep === 'in_stock' || avail.nguyen_trai === 'in_stock' || avail.tam_coc === 'in_stock') {
      inStockCount++;
    }
  });
  
  console.log('Items with Sale:', withSaleCount);
  console.log('Items In Stock at >= 1 store:', inStockCount);
}

testMapping().catch(console.error);
