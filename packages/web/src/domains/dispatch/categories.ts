export type DispatchCategory = 'Fire' | 'EMS' | 'MVC' | 'Alarm' | 'Service' | 'Other';

export const DISPATCH_CATEGORIES: DispatchCategory[] = ['Fire', 'EMS', 'MVC', 'Alarm', 'Service', 'Other'];

export const CATEGORY_COLOR_CLASS: Record<DispatchCategory, string> = {
  Fire: 'bg-dispatch-fire/15 text-dispatch-fire border-dispatch-fire/45',
  EMS: 'bg-dispatch-ems/15 text-dispatch-ems border-dispatch-ems/45',
  MVC: 'bg-dispatch-mvc/15 text-dispatch-mvc border-dispatch-mvc/45',
  Alarm: 'bg-dispatch-alarm/15 text-dispatch-alarm border-dispatch-alarm/45',
  Service: 'bg-dispatch-service/15 text-dispatch-service border-dispatch-service/45',
  Other: 'bg-dispatch-other/15 text-dispatch-other border-dispatch-other/45',
};

export const CATEGORY_DOT_CLASS: Record<DispatchCategory, string> = {
  Fire: 'bg-dispatch-fire',
  EMS: 'bg-dispatch-ems',
  MVC: 'bg-dispatch-mvc',
  Alarm: 'bg-dispatch-alarm',
  Service: 'bg-dispatch-service',
  Other: 'bg-dispatch-other',
};

export const CATEGORY_TEXT_CLASS: Record<DispatchCategory, string> = {
  Fire: 'text-dispatch-fire',
  EMS: 'text-dispatch-ems',
  MVC: 'text-dispatch-mvc',
  Alarm: 'text-dispatch-alarm',
  Service: 'text-dispatch-service',
  Other: 'text-dispatch-other',
};

export const CATEGORY_BG_CLASS: Record<DispatchCategory, string> = {
  Fire: 'bg-dispatch-fire',
  EMS: 'bg-dispatch-ems',
  MVC: 'bg-dispatch-mvc',
  Alarm: 'bg-dispatch-alarm',
  Service: 'bg-dispatch-service',
  Other: 'bg-dispatch-other',
};

function normalizeIncidentType(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\b([a-z])\.\s*([a-z])\.\s*([a-z])\.?/g, '$1$2$3')
    .replace(/&/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const EXACT_CATEGORY_ENTRIES: [string, DispatchCategory][] = [
    ['Structure Fire', 'Fire'],
    ['Working Fire', 'Fire'],
    ['House Fire', 'Fire'],
    ['Apartment Fire', 'Fire'],
    ['Mobile Home Fire', 'Fire'],
    ['Vehicle Fire', 'Fire'],
    ['Brush Fire', 'Fire'],
    ['Dumpster Fire', 'Fire'],
    ['Smoke Investigation', 'Fire'],
    ['Fire Investigation', 'Fire'],
    ['Gas Leak', 'Fire'],
    ['Hazmat', 'Fire'],

    ['Breathing Problem', 'EMS'],
    ['Difficulty Breathing', 'EMS'],
    ['Ill Person', 'EMS'],
    ['Unknown Medical', 'EMS'],
    ['Cardiac Arrest', 'EMS'],
    ['Heart Problem', 'EMS'],
    ['Chest Pain', 'EMS'],
    ['Internal Bleeding', 'EMS'],
    ['Overdose', 'EMS'],
    ['Seizure', 'EMS'],
    ['Stroke', 'EMS'],
    ['Diabetic Problem', 'EMS'],
    ['Fall Injury', 'EMS'],
    ['Injured Person', 'EMS'],
    ['Unconscious Person', 'EMS'],
    ['Behavioral Health', 'EMS'],

    ['Traffic Collision', 'MVC'],
    ['Vehicle Collision', 'MVC'],
    ['Motor Vehicle Accident', 'MVC'],
    ['MVC', 'MVC'],
    ['MVA', 'MVC'],
    ['Pedestrian Struck', 'MVC'],

    ['Alarm', 'Alarm'],
    ['Fire Alarm', 'Alarm'],
    ['Smoke Detector', 'Alarm'],
    ['Waterflow Alarm', 'Alarm'],
    ['Sprinkler Alarm', 'Alarm'],

    ['Service Call', 'Service'],
    ['Public Assist', 'Service'],
    ['Check Welfare', 'Service'],
    ['Lift Assist', 'Service'],
    ['Lockout', 'Service'],
    ['Wires Down', 'Service'],
    ['Citizen Assist', 'Service'],
];

const INCIDENT_TYPE_CATEGORY: Record<string, DispatchCategory> = Object.fromEntries(
  EXACT_CATEGORY_ENTRIES.map(([incidentType, category]) => [normalizeIncidentType(incidentType), category])
);

const CATEGORY_PATTERNS: { category: DispatchCategory; pattern: RegExp }[] = [
  { category: 'MVC', pattern: /\b(mvc|mva)\b/ },
  { category: 'MVC', pattern: /\b(vehicle|traffic|motor vehicle|auto|car)\s+(collision|accident|crash|rollover)\b/ },
  { category: 'MVC', pattern: /\b(pedestrian|bicyclist|motorcyclist)\s+(struck|hit)\b/ },

  { category: 'Alarm', pattern: /\b(alarm|waterflow|sprinkler|smoke detector|detector activation)\b/ },

  { category: 'Fire', pattern: /\b(structure|house|apartment|mobile home|room and contents|working)\s+fire\b/ },
  { category: 'Fire', pattern: /\b(vehicle|car|auto|brush|grass|dumpster|trash|shed|garage)\s+fire\b/ },
  { category: 'Fire', pattern: /\b(smoke|hazmat|gas leak|odor of gas|fire investigation|fire response)\b/ },

  { category: 'EMS', pattern: /^\d{3}[a-z]?$/ },
  { category: 'EMS', pattern: /\b(medical|unknown medical|ill person|sick person|injured person|fall injury)\b/ },
  { category: 'EMS', pattern: /\b(breathing|difficulty breathing|chest pain|heart problem|cardiac|stroke|seizure)\b/ },
  { category: 'EMS', pattern: /\b(overdose|unconscious|bleeding|diabetic|psychiatric|behavioral health|pregnancy)\b/ },

  { category: 'Service', pattern: /\b(public assist|check welfare|lift assist|lockout|citizen assist|service call)\b/ },
  { category: 'Service', pattern: /\b(wires down|tree down|snake removal|water problem|assist invalid)\b/ },
];

export function categoryOfIncidentType(incidentType: string): DispatchCategory {
  const normalized = normalizeIncidentType(incidentType);
  if (!normalized) {
    return 'Other';
  }

  const exactCategory = INCIDENT_TYPE_CATEGORY[normalized];
  if (exactCategory) {
    return exactCategory;
  }

  return CATEGORY_PATTERNS.find(({ pattern }) => pattern.test(normalized))?.category ?? 'Other';
}
