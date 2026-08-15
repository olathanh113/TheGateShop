import json
import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r'c:\laragon\www\TheGateShop'

# Read static cards HTML
with open(os.path.join(base_dir, 'scripts', 'static_cards.html'), 'r', encoding='utf-8') as f:
    static_cards_html = f.read()

# Read Product Schemas JSON
with open(os.path.join(base_dir, 'scripts', 'product_schemas.json'), 'r', encoding='utf-8') as f:
    product_schemas = json.load(f)

# Combine LocalBusiness + Product schemas into graph array
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
    "telephone": "+84395251095",
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
    "telephone": "+84355393871",
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

graph_data = {
    "@context": "https://schema.org",
    "@graph": local_business_schemas + product_schemas
}

json_ld_string = json.dumps(graph_data, ensure_ascii=False, indent=2)

print('Graph JSON-LD compiled successfully. Length:', len(json_ld_string))
