import json
import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open(r'c:\laragon\www\TheGateShop\js\productsData.js', 'r', encoding='utf-8') as f:
    content = f.read()

m = re.search(r'const\s+PRODUCTS_DATA\s*=\s*(\{.*\});', content, re.DOTALL)
if not m:
    print('Failed to match PRODUCTS_DATA')
    sys.exit(1)

data = json.loads(m.group(1))

def get_webp(img_path):
    if not img_path:
        return 'assets/images/sale/1.webp'
    base, _ = os.path.splitext(img_path)
    webp = base + '.webp'
    if os.path.exists(os.path.join(r'c:\laragon\www\TheGateShop', webp)):
        return webp
    return img_path

cards_html = []

for pid, p in data.items():
    imgs = p.get('images', [])
    if not imgs or any('product-01.svg' in img for img in imgs):
        continue

    main_img = get_webp(imgs[0])
    name = p.get('name', 'Sản phẩm The Gate')
    category = p.get('category', 'all')
    price = p.get('price', '299.000đ')
    orig_price = p.get('originalPrice', '')
    badge = p.get('badge', '')
    badge_color = p.get('badgeColor', 'bg-red-600 text-white')

    badge_html = f'<span class="absolute top-3 left-3 z-10 px-3 py-1 text-xs rounded-full shadow-md font-extrabold {badge_color}">{badge}</span>' if badge else ''
    orig_html = f'<span class="text-xs text-slate-400 line-through">{orig_price}</span>' if orig_price else ''

    cat_display = 'HÀNG SALE' if category == 'sale' else ('ĐỒ NAM' if category == 'nam' else ('ĐỒ NỮ' if category == 'nu' else 'OUTDOOR'))

    card = f'''          <article class="product-card group relative rounded-3xl overflow-hidden bg-white border border-slate-200/80 shadow-md hover:shadow-xl transition-all duration-300 flex flex-col w-[260px] shrink-0 snap-start lg:w-auto lg:shrink" data-id="{pid}" data-category="{category}">
            <div class="product-card__image-wrapper relative aspect-[4/5] w-full overflow-hidden bg-slate-100">
              {badge_html}
              <img class="product-card__image w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" src="{main_img}" alt="{name} - The Gate VNXK" loading="lazy" width="400" height="500" />
              <div class="product-card__overlay absolute inset-0 bg-slate-950/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center gap-2 p-3">
                <button class="w-10 h-10 rounded-full bg-white/90 text-slate-800 hover:bg-orange-600 hover:text-white flex items-center justify-center transition-all shadow" data-action="wishlist" data-id="{pid}" title="Yêu thích" aria-label="Thêm {name} vào yêu thích">
                  <i data-lucide="heart" class="w-5 h-5"></i>
                </button>
                <button class="w-10 h-10 rounded-full bg-orange-600 text-white hover:bg-orange-700 flex items-center justify-center transition-all shadow" data-action="cart" data-id="{pid}" title="Thêm vào giỏ" aria-label="Thêm {name} vào giỏ hàng">
                  <i data-lucide="shopping-bag" class="w-5 h-5"></i>
                </button>
                <button class="w-10 h-10 rounded-full bg-white/90 text-slate-800 hover:bg-orange-600 hover:text-white flex items-center justify-center transition-all shadow" data-action="quickview" data-id="{pid}" title="Xem nhanh" aria-label="Xem nhanh {name}">
                  <i data-lucide="eye" class="w-5 h-5"></i>
                </button>
              </div>
            </div>
            <div class="product-card__body p-5 flex flex-col flex-grow">
              <span class="product-card__category text-[11px] font-bold text-orange-600 uppercase tracking-wider mb-1">{cat_display}</span>
              <h3 class="product-card__name font-bold text-slate-900 text-base mb-2 line-clamp-2 leading-snug">{name}</h3>
              <div class="product-card__prices mt-auto flex items-center gap-2">
                <span class="product-card__price font-extrabold text-orange-600 text-lg">{price}</span>
                {orig_html}
              </div>
            </div>
          </article>'''
    cards_html.append(card)

out_html = "\n".join(cards_html)
with open(r'c:\laragon\www\TheGateShop\scripts\static_cards.html', 'w', encoding='utf-8') as f:
    f.write(out_html)

print(f'Successfully written {len(cards_html)} static product cards to scripts/static_cards.html')
