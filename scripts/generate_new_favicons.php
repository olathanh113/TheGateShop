<?php
/**
 * THE GATE SHOP - ULTRA CRISP VECTOR & HD FAVICON GENERATOR
 */

$baseDir = dirname(__DIR__);

// 1. Vector SVG Favicon with high-aesthetic typography matching "the GATE" logo
$svgContent = <<<SVG
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <linearGradient id="gateGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ea580c"/>
      <stop offset="100%" stop-color="#c2410c"/>
    </linearGradient>
    <filter id="subtleGlow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000000" flood-opacity="0.25"/>
    </filter>
  </defs>

  <!-- Squircle Background (24% corner radius for iOS/Android/Browser standard) -->
  <rect width="512" height="512" rx="120" fill="url(#gateGradient)"/>
  
  <!-- Subtle Glow Edge -->
  <rect x="6" y="6" width="500" height="500" rx="114" fill="none" stroke="#ffffff" stroke-width="4" stroke-opacity="0.25"/>

  <!-- Iconic 'G' with Dynamic Wave Wave Gate Character inside -->
  <g filter="url(#subtleGlow)" transform="translate(0, 0)">
    <!-- Elegant Geometric 'G' -->
    <path d="M 370 170 C 335 110 270 90 205 90 C 100 90 40 165 40 256 C 40 347 100 422 205 422 C 280 422 345 380 375 315 L 210 315 L 210 255 L 430 255 C 434 270 435 285 435 300 C 435 410 340 478 205 478 C 65 478 -15 370 -15 256 C -15 142 65 34 205 34 C 300 34 390 75 428 152 Z" 
          fill="#ffffff" 
          transform="translate(48, 0) scale(0.82)"/>
  </g>
</svg>
SVG;

file_put_contents($baseDir . '/favicon.svg', $svgContent);
file_put_contents($baseDir . '/assets/images/favicon.svg', $svgContent);

// 2. High-Resolution Supersampled Anti-Aliased PNG Generator (renders at 4x and downsamples smoothly)
function renderCrispGateFavicon($targetSize) {
    $scale = 4;
    $s = $targetSize * $scale;

    $canvas = imagecreatetruecolor($s, $s);
    imagealphablending($canvas, false);
    imagesavealpha($canvas, true);

    $trans = imagecolorallocatealpha($canvas, 0, 0, 0, 127);
    imagefilledrectangle($canvas, 0, 0, $s, $s, $trans);
    imagealphablending($canvas, true);

    $radius = intval($s * 0.23);
    $orange = imagecolorallocate($canvas, 234, 88, 12); // #ea580c

    // Draw high-res squircle
    imagefilledrectangle($canvas, $radius, 0, $s - $radius, $s, $orange);
    imagefilledrectangle($canvas, 0, $radius, $s, $s - $radius, $orange);
    imagefilledellipse($canvas, $radius, $radius, $radius * 2, $radius * 2, $orange);
    imagefilledellipse($canvas, $s - $radius, $radius, $radius * 2, $radius * 2, $orange);
    imagefilledellipse($canvas, $radius, $s - $radius, $radius * 2, $radius * 2, $orange);
    imagefilledellipse($canvas, $s - $radius, $s - $radius, $radius * 2, $radius * 2, $orange);

    // Draw Crisp White Brand Typography 'G' with high precision
    $white = imagecolorallocate($canvas, 255, 255, 255);

    $cx = $s * 0.49;
    $cy = $s * 0.50;
    $outerR = $s * 0.35;
    $innerR = $s * 0.23;

    // Draw main ring
    for ($r = $innerR; $r <= $outerR; $r += 0.4) {
        for ($angle = 35; $angle <= 360; $angle += 0.2) {
            $rad = deg2rad($angle);
            $px = intval($cx + $r * cos($rad));
            $py = intval($cy + $r * sin($rad));
            imagesetpixel($canvas, $px, $py, $white);
        }
    }

    // Inward horizontal bar of 'G'
    $barLeft = intval($cx - $s * 0.03);
    $barRight = intval($cx + $outerR);
    $barTop = intval($cy - $s * 0.055);
    $barBottom = intval($cy + $s * 0.055);
    imagefilledrectangle($canvas, $barLeft, $barTop, $barRight, $barBottom, $white);

    // Vertical right spur/stem of 'G'
    $stemLeft = intval($cx + $outerR - ($outerR - $innerR));
    $stemRight = intval($cx + $outerR);
    $stemTop = intval($cy);
    $stemBottom = intval($cy + $outerR * 0.70);
    imagefilledrectangle($canvas, $stemLeft, $stemTop, $stemRight, $stemBottom, $white);

    // Top-right serif / cap terminal of 'G'
    $capX = intval($cx + $outerR * cos(deg2rad(35)));
    $capY = intval($cy + $outerR * sin(deg2rad(35)));
    imagefilledellipse($canvas, $capX, $capY, intval(($outerR - $innerR) * 0.9), intval(($outerR - $innerR) * 0.9), $white);

    // Downsample using bicubic resampling for ultra-smooth anti-aliasing
    $out = imagecreatetruecolor($targetSize, $targetSize);
    imagealphablending($out, false);
    imagesavealpha($out, true);
    imagecopyresampled($out, $canvas, 0, 0, 0, 0, $targetSize, $targetSize, $s, $s);

    imagedestroy($canvas);
    return $out;
}

// Generate all standard sizes
$sizes = [
    512 => $baseDir . '/assets/images/favicon-512.png',
    192 => $baseDir . '/assets/images/favicon-192.png',
    180 => $baseDir . '/apple-touch-icon.png',
    48  => $baseDir . '/assets/images/favicon.png',
    32  => $baseDir . '/favicon.png',
];

$icoFrames = [];

foreach ($sizes as $s => $dest) {
    $img = renderCrispGateFavicon($s);
    imagepng($img, $dest, 9);
    if ($s <= 48) {
        $icoFrames[] = $img;
    }
}

// 16x16 frame for classic ICO
$icon16 = renderCrispGateFavicon(16);
$icoFrames[] = $icon16;

// Pack multi-resolution ICO
function writeIcoFile($outputPath, $images) {
    $icoHeader = pack('vvv', 0, 1, count($images));
    $icoDir = '';
    $icoData = '';
    $offset = 6 + (16 * count($images));

    foreach ($images as $img) {
        $w = imagesx($img);
        $h = imagesy($img);
        
        ob_start();
        imagepng($img, null, 9);
        $pngData = ob_get_clean();
        $len = strlen($pngData);

        $icoDir .= pack('CCCCvvVV', 
            $w >= 256 ? 0 : $w, 
            $h >= 256 ? 0 : $h, 
            0, 
            0, 
            1, 
            32, 
            $len, 
            $offset
        );

        $icoData .= $pngData;
        $offset += $len;
    }

    file_put_contents($outputPath, $icoHeader . $icoDir . $icoData);
}

writeIcoFile($baseDir . '/favicon.ico', $icoFrames);

echo "SUCCESS: Vector SVG + Ultra-smooth HD Favicons generated!\n";
