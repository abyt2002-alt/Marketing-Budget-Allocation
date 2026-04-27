const BRAND_DISPLAY_MAP: Record<string, string> = {
  'Aer Matic': 'Lumière Noir',
  'Aer O': 'Velvet Bloom',
  'Aer PP': 'Cedar Mist',
  'Aer Spray': 'Amber Dusk',
  'Godrej Expert Rich Crème': 'Rosé Élite',
  'Godrej Shampoo Hair Color': 'Oud Royale',
}

export const displayBrand = (brand: string): string => BRAND_DISPLAY_MAP[brand] ?? brand
