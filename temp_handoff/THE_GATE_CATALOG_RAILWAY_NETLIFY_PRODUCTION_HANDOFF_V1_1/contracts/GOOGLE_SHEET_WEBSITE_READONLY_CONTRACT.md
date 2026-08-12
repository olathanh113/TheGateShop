# Google Sheet website read-only contract

Target file: `1kWGZy7Stnrs842lnt36Y_3ROO-t_pfNvRcz-cVwU1Eg`.

Only `WEBSITE_PRODUCTS!A1:U1002` is read. `SALE_IMPORT_STAGING`, `KIOT_CATALOG_AUTO` and every other tab are excluded from the runtime publication path. The adapter performs one bounded `spreadsheets.values.get` request and never exposes a range parameter to HTTP callers.

Exact ordered headers:

```text
priority,product_code,product_id,kiot_name,custom_name,final_name,source_group,category,audience,collection,display_order,featured,publish,kiot_price,primary_image_url,custom_image_url,final_image_url,image_preview,sync_status,note,slug
```

Contract:

- Header missing, duplicate, reordered or renamed: fail the complete rebuild and preserve LKG.
- Join key: case-sensitive `trim(product_code) == Kiot code`; never name, product_id or fuzzy matching.
- Any non-empty row with blank code, or duplicate trimmed code: fail the complete rebuild.
- Only boolean `TRUE` or the exact formatted string `TRUE` publishes. `TRUE `, `true`, `yes` and `1` are invalid, not truthy.
- Sheet fields permitted in website output: custom/final name, source_group, category, audience, collection, display_order, featured, custom image and slug.
- Sheet price, inventory, eligibility, product_id, sync_status and note never override KiotViet authority and are never emitted in the public payload.
- Valid custom image must be an HTTPS URL without embedded credentials or fragment. Otherwise the first valid HTTPS KiotViet image is used. No image means exclude the item.
- Explicit slug must match lowercase letters/digits joined by single hyphens. Blank slug is derived deterministically from code. Invalid or duplicate slug fails the complete rebuild.

Google OAuth scope is exactly `https://www.googleapis.com/auth/spreadsheets.readonly`. Because Google scopes apply at spreadsheet-file level rather than tab level, Owner must share only this target file to the service account with Viewer permission. The code separately pins the spreadsheet ID and tab/range.
