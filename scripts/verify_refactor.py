import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r'c:\laragon\www\TheGateShop'

def check(name, condition, details=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f": {details}" if details else ""))
    return condition

passed = 0
total = 0

def run_test(name, condition, details=""):
    global passed, total
    total += 1
    if check(name, condition, details):
        passed += 1

print("=== BEGINNING ACCURATE AUTOMATED AUDIT & VERIFICATION ===")

# Read index.html
with open(os.path.join(base_dir, 'index.html'), 'r', encoding='utf-8') as f:
    index_content = f.read()

# 1. Domain & Canonical
run_test("N1: Dead domain thegateshop.vn removed from index.html", "thegateshop.vn" not in index_content)
run_test("N1: Canonical URL is updated", 'link rel="canonical" href="https://the-gate-shop.vercel.app/"' in index_content)

with open(os.path.join(base_dir, 'sitemap.xml'), 'r', encoding='utf-8') as f:
    sitemap_content = f.read()
run_test("N1: Sitemap URL is updated", "https://the-gate-shop.vercel.app/" in sitemap_content)

# 2. Block Google Index (D6)
run_test("D6: Meta robots noindex present in index.html", 'meta name="robots" content="noindex, nofollow"' in index_content)

with open(os.path.join(base_dir, 'vercel.json'), 'r', encoding='utf-8') as f:
    vercel_content = f.read()
run_test("D6: X-Robots-Tag in vercel.json", "X-Robots-Tag" in vercel_content and "noindex, nofollow" in vercel_content)

with open(os.path.join(base_dir, '.htaccess'), 'r', encoding='utf-8') as f:
    htaccess_content = f.read()
run_test("D6: X-Robots-Tag in .htaccess", "X-Robots-Tag" in htaccess_content)

# 3. Pin CDN (N2)
run_test("N2: Lucide CDN pinned version", "lucide@0.344.0" in index_content and "lucide@latest" not in index_content)

# 4. Static HTML Rendering (C1)
run_test("C1: Static product cards embedded in index.html", index_content.count('<article class="product-card') >= 80)

# 5. Clean Fake Reviews (N17)
run_test("N17: Hero fake stats 10.000+ removed", "10.000+" not in index_content)
run_test("N17: Hero fake rating span 4.9 removed", "<span>4.9</span>" not in index_content)
run_test("N17: Fake rating stars in productCard.js removed", "generateStars" not in open(os.path.join(base_dir, 'js/components/productCard.js'), 'r', encoding='utf-8').read())

# 6. Tailwind CDN Removal & Minified CSS (N3, N4)
run_test("N3: Tailwind CDN script removed", "cdn.tailwindcss.com" not in index_content)
run_test("N4: Tailwind minified CSS linked", "css/tailwind.min.css" in index_content and os.path.exists(os.path.join(base_dir, 'css', 'tailwind.min.css')))
run_test("N4: Custom minified CSS linked", "css/custom.min.css" in index_content and os.path.exists(os.path.join(base_dir, 'css', 'custom.min.css')))

# 7. Images WebP & Dimensions (C3, N15)
run_test("C3: WebP banner image linked in index.html", "hero-banner.webp" in index_content)

imgs = re.findall(r'<img\s+[^>]*>', index_content)
missing_dims = [img for img in imgs if 'width=' not in img or 'height=' not in img]
run_test("N15: All img tags have width & height attributes", len(missing_dims) == 0, f"Missing: {len(missing_dims)}")

# 8. HTML Standards & Accessibility (A4, A5, A6)
search_modal_content = open(os.path.join(base_dir, 'js/components/searchModal.js'), 'r', encoding='utf-8').read()
run_test("A4: Search input has aria-label & name in searchModal.js", 'id="searchInput"' in search_modal_content and 'name="q"' in search_modal_content and 'aria-label=' in search_modal_content)
run_test("A5: Newsletter input has aria-label & name in index.html", 'name="email"' in index_content and 'aria-label="Email nhận ưu đãi"' in index_content)

h1_count = len(re.findall(r'<h1[\s>]', index_content))
run_test("A6: Single h1 element on page", h1_count == 1, f"Found {h1_count} h1 tags")

# 9. Schema JSON-LD (N16, N12)
run_test("N12: Geo coordinates in LocalBusiness schema", '"latitude": 21.0315' in index_content)
run_test("N16: Product schemas present without aggregateRating", '"@type": "Product"' in index_content and '"aggregateRating"' not in index_content)

# 10. Title & Meta Description (N7, N8, B4)
title_m = re.search(r'<title>(.*?)</title>', index_content)
title_len = len(title_m.group(1)) if title_m else 0
run_test("N7: Title length < 60 characters", title_len < 60, f"Length: {title_len}")

desc_m = re.search(r'<meta name="description" content="(.*?)"', index_content)
desc_len = len(desc_m.group(1)) if desc_m else 0
run_test("N8: Meta description length ~150 characters", 130 <= desc_len <= 165, f"Length: {desc_len}")

run_test("B4: Favicon files generated & linked", os.path.exists(os.path.join(base_dir, 'favicon.ico')) and 'favicon.ico' in index_content)

print(f"\nAUDIT COMPLETE: {passed}/{total} TESTS PASSED.")
if passed == total:
    print("ALL TECHNICAL CHECKLIST V4 AUDIT TESTS PASSED SUCCESSFULLY! 🚀")
else:
    print("SOME TESTS FAILED, PLEASE REVIEW OUTPUT ABOVE.")
