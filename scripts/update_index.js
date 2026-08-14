const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(__dirname, '..');
const indexPath = path.join(baseDir, 'index.html');
const staticCardsPath = path.join(baseDir, 'scripts', 'static_cards.html');

let html = fs.readFileSync(indexPath, 'utf-8');
const staticCards = fs.readFileSync(staticCardsPath, 'utf-8');

// Find productsGridContainer start and end
const gridStartMarker = '<div class="flex overflow-x-auto snap-x snap-mandatory gap-4 lg:grid lg:grid-cols-4 no-scrollbar pb-4" id="productsGridContainer">';
const gridStartIndex = html.indexOf(gridStartMarker);

if (gridStartIndex === -1) {
  console.error('Could not find productsGridContainer in index.html');
  process.exit(1);
}

// Find the closing </div> of productsGridContainer and pagination
// Search after gridStartIndex for the next section or container end
const searchAfter = gridStartIndex + gridStartMarker.length;
const nextSectionMarker = '<!-- Dark Banner "The Gate Outdoor & Sportswear" -->';
const nextSectionIndex = html.indexOf(nextSectionMarker, searchAfter);

let gridEndIndex = -1;
if (nextSectionIndex !== -1) {
  // Find </section> before nextSectionMarker
  const lastSectionClose = html.lastIndexOf('</section>', nextSectionIndex);
  gridEndIndex = lastSectionClose;
}

console.log('gridStartIndex:', gridStartIndex);
console.log('gridEndIndex:', gridEndIndex);

// Let's inspect the block around gridEndIndex
const snippet = html.substring(gridStartIndex, gridEndIndex + 10);
console.log('Snippet length:', snippet.length);

const newFeaturedBody = `${gridStartMarker}
${staticCards}
        </div>

        <!-- Dãy nút Phân trang Pagination -->
        <div class="flex flex-wrap items-center justify-center gap-2 mt-8 pt-6 border-t border-slate-200" id="paginationContainer"></div>
      </div>
    </section>`;

// Replace from gridStartIndex up to gridEndIndex + '</section>'.length
html = html.substring(0, gridStartIndex) + newFeaturedBody + html.substring(gridEndIndex + '</section>'.length);

fs.writeFileSync(indexPath, html, 'utf-8');
console.log('Updated index.html successfully!');
