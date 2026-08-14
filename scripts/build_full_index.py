import json
import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r'c:\laragon\www\TheGateShop'

# Read static cards HTML
with open(os.path.join(base_dir, 'scripts', 'static_cards.html'), 'r', encoding='utf-8') as f:
    static_cards_html = f.read()

# Read Product Schemas
with open(os.path.join(base_dir, 'scripts', 'product_schemas.json'), 'r', encoding='utf-8') as f:
    product_schemas = json.load(f)

local_business_schemas = [
  {
    "@type": "ClothingStore",
    "@id": "https://the-gate-shop.vercel.app/#store-hanoi-cs1",
    "name": "The Gate — Cơ sở Tôn Thất Thiệp (Ba Đình)",
    "description": "Chuyên bán quần áo Việt Nam Xuất Khẩu chính hãng, đồ outdoor, đồ thể thao cao cấp.",
    "url": "https://the-gate-shop.vercel.app/",
    "address": {
      "@type": "PostalAddress",
      "streetAddress": "27 ngõ 8 Tôn Thất Thiệp, Ba Đình",
      "addressLocality": "Hà Nội",
      "addressCountry": "VN"
    },
    "geo": {
      "@type": "GeoCoordinates",
      "latitude": 21.0315,
      "longitude": 105.8398
    },
    "telephone": "+84355393871",
    "openingHoursSpecification": {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
      "opens": "09:00",
      "closes": "21:30"
    },
    "sameAs": ["https://www.facebook.com/thegatevietnamxk"]
  },
  {
    "@type": "ClothingStore",
    "@id": "https://the-gate-shop.vercel.app/#store-hanoi-cs2",
    "name": "The Gate — Cơ sở Nguyễn Trãi (Thanh Xuân)",
    "description": "Chuyên bán quần áo Việt Nam Xuất Khẩu chính hãng, đồ outdoor, đồ thể thao cao cấp.",
    "url": "https://the-gate-shop.vercel.app/",
    "address": {
      "@type": "PostalAddress",
      "streetAddress": "86 ngõ 72 Nguyễn Trãi, Thanh Xuân",
      "addressLocality": "Hà Nội",
      "addressCountry": "VN"
    },
    "geo": {
      "@type": "GeoCoordinates",
      "latitude": 20.9947,
      "longitude": 105.8118
    },
    "telephone": "+84395251095",
    "openingHoursSpecification": {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
      "opens": "09:00",
      "closes": "21:30"
    }
  },
  {
    "@type": "ClothingStore",
    "@id": "https://the-gate-shop.vercel.app/#store-ninhbinh",
    "name": "The Gate Tam Cốc — Cơ sở Ninh Bình",
    "description": "Chuyên bán quần áo Việt Nam Xuất Khẩu chính hãng tại Tam Cốc Ninh Bình.",
    "url": "https://the-gate-shop.vercel.app/",
    "address": {
      "@type": "PostalAddress",
      "streetAddress": "Cổng làng Tuân Cáo, Ninh Thắng",
      "addressLocality": "Ninh Bình",
      "addressCountry": "VN"
    },
    "geo": {
      "@type": "GeoCoordinates",
      "latitude": 20.2163,
      "longitude": 105.9366
    },
    "telephone": "+84942326993"
  }
]

graph_json = {
    "@context": "https://schema.org",
    "@graph": local_business_schemas + product_schemas
}

json_ld_string = json.dumps(graph_json, ensure_ascii=False, indent=2)

# Read clean original index.html
with open(os.path.join(base_dir, 'index.html'), 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Replace image links with .webp
html = html.replace('assets/images/banners/hero-banner.png', 'assets/images/banners/hero-banner.webp')
html = html.replace('assets/images/banners/parallax-banner.png', 'assets/images/banners/parallax-banner.webp')
html = html.replace('assets/images/sale/3.png', 'assets/images/sale/3.webp')
html = html.replace('assets/images/sale/2.png', 'assets/images/sale/2.webp')
html = html.replace('assets/images/sale/5.png', 'assets/images/sale/5.webp')
html = html.replace('assets/images/sale/6.png', 'assets/images/sale/6.webp')
html = html.replace('assets/images/sale/7.png', 'assets/images/sale/7.webp')
html = html.replace('https://thegateshop.vn/', 'https://the-gate-shop.vercel.app/')

# 2. Update <head>
head_start = html.find('<head>')
head_end = html.find('</head>') + len('</head>')

new_head = f'''<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="The Gate chuyên thời trang Việt Nam Xuất Khẩu chính hãng, đồ thể thao, áo khoác dù & outdoor cao cấp. 2 cơ sở tại Hà Nội, 1 cơ sở tại Ninh Bình." />
  <meta name="author" content="The Gate" />
  <meta name="robots" content="noindex, nofollow" />

  <!-- Open Graph -->
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="The Gate" />
  <meta property="og:locale" content="vi_VN" />
  <meta property="og:title" content="The Gate — Thời Trang Việt Nam Xuất Khẩu & Outdoor" />
  <meta property="og:description" content="Chuyên đồ thời trang Việt Nam Xuất Khẩu chính hãng, chất lượng cao, thiết kế năng động và bền đẹp." />
  <meta property="og:url" content="https://the-gate-shop.vercel.app/" />
  <meta property="og:image" content="https://the-gate-shop.vercel.app/assets/images/banners/hero-banner.webp" />

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="The Gate — Thời Trang Việt Nam Xuất Khẩu & Outdoor" />
  <meta name="twitter:description" content="Chuyên đồ thời trang Việt Nam Xuất Khẩu chính hãng, chất lượng cao xuất Châu Âu & Nhật Bản." />

  <title>The Gate — Thời Trang Việt Nam Xuất Khẩu & Outdoor</title>

  <!-- Canonical -->
  <link rel="canonical" href="https://the-gate-shop.vercel.app/" />

  <!-- Favicons -->
  <link rel="icon" type="image/x-icon" href="favicon.ico" />
  <link rel="icon" type="image/png" sizes="32x32" href="favicon.png" />
  <link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon.png" />
  <link rel="icon" type="image/svg+xml" href="assets/images/favicon.svg" />

  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:ital,wght@0,400;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet" />

  <!-- Preload hero image -->
  <link rel="preload" as="image" href="assets/images/banners/hero-banner.webp" fetchpriority="high" />

  <!-- Compiled Minified CSS Stylesheets -->
  <link rel="stylesheet" href="css/tailwind.min.css" />
  <link rel="stylesheet" href="css/custom.min.css" />

  <!-- Pinned Lucide Icons CDN -->
  <script src="https://unpkg.com/lucide@0.344.0/dist/umd/lucide.min.js" defer></script>

  <!-- JSON-LD LocalBusiness & Product Schemas -->
  <script type="application/ld+json">
{json_ld_string}
  </script>
</head>'''

html = html[:head_start] + new_head + html[head_end:]

# 3. Clean Hero fake stats section
hero_stats_old = re.search(r'<div class="w-full max-w-3xl bg-white/95 backdrop-blur-md border border-orange-200/80 rounded-2xl p-4 sm:p-6 mb-6 sm:mb-10 shadow-xl">.*?</div>\s*</div>\s*</div>', html, re.DOTALL)
if hero_stats_old:
    new_hero_stats = '''<div class="w-full max-w-3xl bg-white/95 backdrop-blur-md border border-orange-200/80 rounded-2xl p-4 sm:p-6 mb-6 sm:mb-10 shadow-xl">
          <div class="grid grid-cols-3 divide-x divide-slate-200 text-center">
            <div class="px-1.5 sm:px-2">
              <div class="text-xl sm:text-3xl font-extrabold text-slate-900 mb-0.5 sm:mb-1">100%</div>
              <div class="text-xs sm:text-sm text-slate-600 font-medium leading-tight">Hàng Xuất Khẩu</div>
            </div>
            <div class="px-1.5 sm:px-2">
              <div class="text-xl sm:text-3xl font-extrabold text-orange-600 mb-0.5 sm:mb-1">3 Cơ Sở</div>
              <div class="text-xs sm:text-sm text-slate-600 font-medium leading-tight">Hà Nội & Ninh Bình</div>
            </div>
            <div class="px-1.5 sm:px-2">
              <div class="text-xl sm:text-3xl font-extrabold text-emerald-600 mb-0.5 sm:mb-1">30 Ngày</div>
              <div class="text-xs sm:text-sm text-slate-600 font-medium leading-tight">Đổi Trả Tận Nơi</div>
            </div>
          </div>
        </div>'''
    html = html.replace(hero_stats_old.group(0), new_hero_stats)

# 4. Insert static cards inside productsGridContainer
grid_target = '<div class="flex overflow-x-auto snap-x snap-mandatory gap-4 lg:grid lg:grid-cols-4 no-scrollbar pb-4" id="productsGridContainer">'
if grid_target in html:
    end_grid = html.find('</div>', html.find(grid_target))
    html = html[:html.find(grid_target) + len(grid_target)] + '\n' + static_cards_html + '\n        ' + html[end_grid:]

# 5. Accessibility for inputs in index.html
html = html.replace('placeholder="Nhập địa chỉ email của bạn..."', 'name="email" aria-label="Email nhận ưu đãi" placeholder="Nhập địa chỉ email của bạn..."')

# 6. Defer scripts
html = html.replace('<script src="js/productsData.js"></script>', '<script src="js/productsData.js" defer></script>')

# 7. Update inline filter script without breaking footer
script_marker = 'const STORES_INFO = {'
if script_marker in html:
    start_script_idx = html.find(script_marker)
    end_script_idx = html.find('</script>', start_script_idx)
    
    new_script_code = '''const STORES_INFO = {
      cs1: { code: "CS1", name: "HN CS1: Tôn Thất Thiệp (Ba Đình)", shortAddr: "27 ngõ 8 Tôn Thất Thiệp, Ba Đình, Hà Nội", phone: "0355393871", zalo: "0355393871" },
      cs2: { code: "CS2", name: "HN CS2: Nguyễn Trãi (Thanh Xuân)", shortAddr: "86 ngõ 72 Nguyễn Trãi, Thanh Xuân, Hà Nội", phone: "0395251095", zalo: "0395251095" },
      cs3: { code: "CS3", name: "Ninh Bình: Tam Cốc (Ninh Thắng)", shortAddr: "Cổng làng Tuân Cáo, Ninh Thắng, Ninh Bình", phone: "0942326993", zalo: "0942326993" }
    };

    let currentPage = 1;
    const itemsPerPage = 8;
    let currentCategoryFilter = 'all';

    window.scrollTabsNav = function(direction) {
      const tabsContainer = document.getElementById('filterTabs');
      if (!tabsContainer) return;
      tabsContainer.scrollBy({ left: direction * 280, behavior: 'smooth' });
    };

    window.setActiveFilterTab = function(category) {
      currentCategoryFilter = category;
      currentPage = 1;

      const filterBtns = document.querySelectorAll('.filter-tab-btn');
      filterBtns.forEach(btn => {
        const cat = btn.getAttribute('data-category') || 'all';
        if (cat === category) {
          btn.className = 'px-5 py-2.5 rounded-full text-xs font-bold transition-all bg-orange-600 text-white shadow-md filter-tab-btn shrink-0 ring-2 ring-orange-400/40 scale-105';
        } else {
          btn.className = 'px-5 py-2.5 rounded-full text-xs font-bold transition-all bg-white text-slate-700 border border-slate-200 hover:bg-orange-50 filter-tab-btn shrink-0';
        }
      });

      filterStaticProductCards();
    };

    window.selectCategoryAndScroll = function(category) {
      setActiveFilterTab(category);
      const featuredSec = document.getElementById('featured');
      if (featuredSec) featuredSec.scrollIntoView({ behavior: 'smooth' });
    };

    function filterStaticProductCards() {
      const gridContainer = document.getElementById('productsGridContainer');
      const paginationContainer = document.getElementById('paginationContainer');
      if (!gridContainer) return;

      const cards = Array.from(gridContainer.querySelectorAll('.product-card'));
      const matchingCards = cards.filter(card => {
        const cat = card.getAttribute('data-category');
        if (currentCategoryFilter === 'all') return true;
        if (currentCategoryFilter === 'sale') return cat === 'sale';
        return cat === currentCategoryFilter;
      });

      cards.forEach(card => card.style.display = 'none');

      const totalPages = Math.ceil(matchingCards.length / itemsPerPage) || 1;
      if (currentPage > totalPages) currentPage = totalPages;

      const startIndex = (currentPage - 1) * itemsPerPage;
      const visibleCards = matchingCards.slice(startIndex, startIndex + itemsPerPage);
      visibleCards.forEach(card => card.style.display = 'flex');

      if (paginationContainer) {
        let pagHtml = '';
        for (let i = 1; i <= totalPages; i++) {
          const activeClass = i === currentPage ? 'bg-orange-600 text-white shadow-md' : 'bg-white text-slate-700 border border-slate-200 hover:bg-orange-50';
          pagHtml += `<button onclick="goToPage(${i})" class="w-10 h-10 rounded-full font-bold text-xs transition-all ${activeClass}">${i}</button>`;
        }
        paginationContainer.innerHTML = pagHtml;
      }
    }

    window.goToPage = function(page) {
      currentPage = page;
      filterStaticProductCards();
      const featuredSec = document.getElementById('featured');
      if (featuredSec) featuredSec.scrollIntoView({ behavior: 'smooth' });
    };

    document.addEventListener('DOMContentLoaded', () => {
      filterStaticProductCards();
    });\n  '''
    html = html[:start_script_idx] + new_script_code + html[end_script_idx:]

with open(os.path.join(base_dir, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(html)

print('Updated index.html safely preserving all sections!')
