const BRAND_DISPLAY_MAP: Record<string, string> = {
  'Aer Matic': 'Lumière Noir',
  'Aer O': 'Velvet Bloom',
  'Aer PP': 'Cedar Mist',
  'Aer Spray': 'Amber Dusk',
  'Godrej Expert Rich Crème': 'Rosé Élite',
  'Godrej Shampoo Hair Color': 'Oud Royale',
}

export const displayBrand = (brand: string): string => BRAND_DISPLAY_MAP[brand] ?? brand

// Replace brand name substrings in driver labels (e.g. "Halo Media Reach Aer O" → "Halo Media Reach Velvet Bloom")
export const maskBrandInLabel = (label: string): string => {
  let result = label
  // Sort by length descending so longer names match first (e.g. "Aer Spray" before "Aer")
  const sorted = Object.entries(BRAND_DISPLAY_MAP).sort((a, b) => b[0].length - a[0].length)
  for (const [real, masked] of sorted) {
    result = result.replace(new RegExp(real, 'gi'), masked)
  }
  return result
}
