import json
import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open(r'c:\laragon\www\TheGateShop\js\productsData.js', 'r', encoding='utf-8') as f:
    content = f.read()

m = re.search(r'const\s+PRODUCTS_DATA\s*=\s*(\{.*\});', content, re.DOTALL)
if not m:
    sys.exit(1)

data = json.loads(m.group(1))

schema_list = []

for pid, p in data.items():
    imgs = p.get('images', [])
    if not imgs or any('product-01.svg' in img for img in imgs):
        continue

    img_path = imgs[0]
    base, _ = os.path.splitext(img_path)
    webp = base + '.webp'
    final_img = webp if os.path.exists(os.path.join(r'c:\laragon\www\TheGateShop', webp)) else img_path

    name = p.get('name', 'Sản phẩm The Gate')
    price_str = p.get('price', '299000')
    price_num = int(re.sub(r'[^\d]', '', str(price_str)) or '299000')

    img_url = final_img if final_img.startswith(('http://', 'https://')) else f"https://thegatevnxk.com/{final_img}"

    product_schema = {
        "@type": "Product",
        "@id": f"https://thegatevnxk.com/#product-{pid}",
        "name": name,
        "image": img_url,
        "description": f"{name} - Hàng Việt Nam Xuất Khẩu chất lượng cao chính hãng tại The Gate Shop.",
        "sku": f"THEGATE-{pid}",
        "brand": {
            "@type": "Brand",
            "name": "The Gate"
        },
        "offers": {
            "@type": "Offer",
            "url": "https://thegatevnxk.com/",
            "priceCurrency": "VND",
            "price": str(price_num),
            "priceValidUntil": "2026-12-31",
            "itemCondition": "https://schema.org/NewCondition",
            "availability": "https://schema.org/InStock",
            "seller": {
                "@type": "Organization",
                "name": "The Gate Shop"
            }
        }
    }
    schema_list.append(product_schema)

with open(r'c:\laragon\www\TheGateShop\scripts\product_schemas.json', 'w', encoding='utf-8') as f:
    json.dump(schema_list, f, ensure_ascii=False, indent=2)

print(f'Generated JSON-LD Product schemas for {len(schema_list)} products.')
