/**
 * The Gate VNXK — Floating Bottom Bar (Disabled as requested)
 */

export function initFloatingBar() {
  const existing = document.querySelector('.floating-bar');
  if (existing) {
    existing.remove();
  }
}
