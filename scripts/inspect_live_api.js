const fs = require('fs');

async function inspect() {
  const urlCatalog = 'https://catalog-api-production-6f96.up.railway.app/v1/website/catalog';
  const cRes = await fetch(urlCatalog, { headers: { 'Accept': 'application/json' } });
  const data = await cRes.json();
  
  console.log('Total products from live API:', data.total);
  
  const sampleItems = data.items.slice(0, 10);
  console.log('Sample items:');
  sampleItems.forEach((it, idx) => {
    console.log(`\n[${idx + 1}] Code: ${it.code} | Name: ${it.name}`);
    console.log(`Sale Price: ${it.sale_price} | Regular Price: ${it.regular_price} | Is Sale: ${it.is_sale}`);
    console.log(`Images: ${it.images ? it.images.length : 0} | Image 0: ${it.images ? it.images[0] : 'none'}`);
    console.log(`Availability:`, it.availability);
  });
}

inspect().catch(console.error);
