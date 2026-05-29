export interface DispatchAgency {
  name: string;
  min: number;
  max: number;
}

/* Phoenix Regional Dispatch — official agency unit-number blocks.
   Source: City of Phoenix Fire "Fire Departments/Fire Districts" numbering (Rev. 2012),
   phoenix.gov/.../094635.pdf. Agencies exceeding their block append a 4th digit in
   sequence (e.g. Glendale 151–159 → 1510, 1511…), handled by cityOfUnit(). */
export const AGENCIES: DispatchAgency[] = [
  { name: 'Phoenix', min: 1, max: 99 },
  { name: 'Sun City West', min: 101, max: 109 },
  { name: 'El Mirage', min: 121, max: 129 },
  { name: 'Sun City', min: 131, max: 139 },
  { name: 'Daisy Mountain', min: 141, max: 149 },
  { name: 'Glendale', min: 151, max: 159 },
  { name: 'Tolleson', min: 161, max: 169 },
  { name: 'Avondale', min: 171, max: 179 },
  { name: 'Goodyear', min: 181, max: 189 },
  { name: 'Peoria', min: 191, max: 199 },
  { name: 'Mesa', min: 201, max: 229 },
  { name: 'Sun Lakes', min: 231, max: 239 },
  { name: 'Guadalupe', min: 241, max: 249 },
  { name: 'Gilbert', min: 251, max: 259 },
  { name: 'Apache Junction', min: 261, max: 269 },
  { name: 'Tempe', min: 271, max: 279 },
  { name: 'Chandler', min: 281, max: 289 },
  { name: 'Salt River', min: 291, max: 299 },
  { name: 'Surprise', min: 301, max: 319 },
  { name: 'Buckeye Valley', min: 321, max: 329 },
  { name: 'Black Canyon City', min: 331, max: 339 },
  { name: 'Tonopah', min: 341, max: 349 },
  { name: 'Palo Verde', min: 351, max: 359 },
  { name: 'Luke Air Force Base', min: 361, max: 369 },
  { name: 'Harquahala', min: 371, max: 379 },
  { name: 'Gila Bend', min: 381, max: 389 },
  { name: 'Fort McDowell', min: 401, max: 409 },
  { name: 'Queen Creek', min: 411, max: 419 },
  { name: 'Gila River', min: 421, max: 439 },
  { name: 'Rio Verde', min: 441, max: 449 },
  { name: 'Casa Grande', min: 501, max: 515 },
  { name: 'Stanfield', min: 516, max: 519 },
  { name: 'Eloy', min: 521, max: 529 },
  { name: 'Coolidge', min: 531, max: 539 },
  { name: 'Florence', min: 541, max: 549 },
  { name: 'Queen Valley', min: 551, max: 555 },
  { name: 'Thunderbird Farms', min: 556, max: 559 },
  { name: 'Ak-Chin', min: 561, max: 565 },
  { name: 'Arizona City', min: 566, max: 569 },
  { name: 'Maricopa', min: 571, max: 585 },
  { name: 'Regional Fire Rescue', min: 586, max: 589 },
  { name: 'Western Fire', min: 591, max: 595 },
  { name: 'Evergreen Fire', min: 596, max: 599 },
  { name: 'Scottsdale', min: 601, max: 629 },
  { name: 'Superior', min: 631, max: 639 },
  { name: 'Hayden', min: 641, max: 649 },
  { name: 'Kearney', min: 651, max: 659 },
  { name: 'Mammoth', min: 661, max: 669 },
  { name: 'Dudleyville', min: 671, max: 679 },
  { name: 'San Manuel', min: 681, max: 689 },
  { name: 'Oracle', min: 691, max: 699 },
  { name: 'Buckeye', min: 701, max: 749 },
  { name: 'Wickenburg', min: 751, max: 759 },
  { name: 'Wittman', min: 761, max: 764 },
  { name: 'Circle City / Morristown', min: 765, max: 769 },
  { name: 'Rural/Metro', min: 800, max: 899 },
  { name: 'Phoenix Adaptive Response', min: 900, max: 999 },
];

export const ALL_CITIES = AGENCIES.map((agency) => agency.name);

export function agencyRange(name: string): string {
  const agency = AGENCIES.find((item) => item.name === name);
  return agency ? `${agency.min}-${agency.max}` : '';
}

export function unitNumber(unit: string): number | null {
  const match = unit.match(/(\d+)/);
  if (!match) {
    return null;
  }
  const parsed = Number.parseInt(match[1], 10);
  return Number.isFinite(parsed) ? parsed : null;
}

export function cityOfUnit(unit: string): string {
  let number = unitNumber(unit);
  if (number === null) {
    return 'Other';
  }

  while (number > 999) {
    number = Math.floor(number / 10);
  }

  const agency = AGENCIES.find((item) => number >= item.min && number <= item.max);
  return agency?.name ?? 'Other';
}

export function citiesOfIncident(units: string[]): string[] {
  return [...new Set(units.map(cityOfUnit))].sort((left, right) => {
    const leftIndex = ALL_CITIES.indexOf(left);
    const rightIndex = ALL_CITIES.indexOf(right);
    if (leftIndex === -1 || rightIndex === -1) {
      return left.localeCompare(right);
    }
    return leftIndex - rightIndex;
  });
}
