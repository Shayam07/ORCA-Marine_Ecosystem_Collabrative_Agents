// Comprehensive INCOIS Coastal Threat Warning Ribbons and Offshore Alert Polygons
// Matching the official INCOIS Ocean State Forecast Composite Alerts & Coastal Bulletins.

export type ThreatLevel = 'WARNING' | 'ALERT' | 'WATCH' | 'NO_THREAT';

export interface CoastalAlertFeature {
  id: string;
  name: string;
  threatLevel: ThreatLevel;
  waveHeightRange: string;
  swellHeightRange: string;
  windSpeedRange: string;
  advisory: string;
  geometry: {
    type: 'LineString' | 'Polygon';
    coordinates: number[][] | number[][][];
  };
}

export const THREAT_COLORS: Record<ThreatLevel, string> = {
  WARNING: '#e53935', // Red (> 3.5m)
  ALERT: '#fb8c00',   // Orange (2.5 - 3.5m)
  WATCH: '#fdd835',   // Yellow (1.8 - 2.5m)
  NO_THREAT: '#43a047', // Green (< 1.8m)
};

export const INCOIS_COASTAL_ALERTS_GEOJSON: any = {
  type: 'FeatureCollection',
  features: [
    // 1. Gujarat - Kachchh & Gulf of Khambhat (Alert & Watch ribbons)
    {
      type: 'Feature',
      properties: {
        id: 'GUJ-01',
        name: 'Gujarat Coast (Kachchh - Dwarka)',
        threatLevel: 'ALERT',
        waveHeightRange: '2.8 - 3.4 m',
        swellHeightRange: '2.2 - 2.8 m',
        windSpeedRange: '35 - 45 km/h',
        advisory: 'High waves and swell surges expected. Fishermen advised to exercise extreme caution.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [68.6, 23.8],
          [68.8, 23.2],
          [69.1, 22.8],
          [69.0, 22.4],
          [69.3, 22.2],
          [69.8, 22.5],
          [70.4, 22.9],
        ],
      },
    },
    {
      type: 'Feature',
      properties: {
        id: 'GUJ-02',
        name: 'Gujarat Coast (Saurashtra - Veraval - Diu)',
        threatLevel: 'WATCH',
        waveHeightRange: '2.0 - 2.5 m',
        swellHeightRange: '1.6 - 2.1 m',
        windSpeedRange: '25 - 35 km/h',
        advisory: 'Moderate sea condition. Nearshore recreation to be monitored.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [69.8, 22.5],
          [69.5, 21.8],
          [70.0, 21.1],
          [70.4, 20.9],
          [71.0, 20.7],
          [71.8, 20.9],
          [72.2, 21.4],
          [72.6, 21.7],
        ],
      },
    },

    // 2. Maharashtra - Mumbai & Konkan Coast (Watch & Alert ribbons)
    {
      type: 'Feature',
      properties: {
        id: 'MAH-01',
        name: 'Maharashtra Coast (Palghar - Mumbai)',
        threatLevel: 'WATCH',
        waveHeightRange: '2.1 - 2.6 m',
        swellHeightRange: '1.7 - 2.2 m',
        windSpeedRange: '25 - 35 km/h',
        advisory: 'Watch status: High waves expected near low-lying coastal areas during high tide.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [72.7, 20.1],
          [72.8, 19.5],
          [72.82, 19.05],
          [72.88, 18.75],
        ],
      },
    },
    {
      type: 'Feature',
      properties: {
        id: 'MAH-02',
        name: 'Maharashtra Coast (Raigad - Ratnagiri - Sindhudurg)',
        threatLevel: 'ALERT',
        waveHeightRange: '2.6 - 3.2 m',
        swellHeightRange: '2.0 - 2.7 m',
        windSpeedRange: '30 - 40 km/h',
        advisory: 'Alert status: Swell surges likely to cause sea water intrusion along rocky beaches.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [72.88, 18.75],
          [73.0, 18.2],
          [73.1, 17.5],
          [73.3, 16.8],
          [73.5, 16.0],
          [73.7, 15.75],
        ],
      },
    },

    // 3. Goa & Karnataka Coast (Watch & Alert ribbons)
    {
      type: 'Feature',
      properties: {
        id: 'GOA-KAR-01',
        name: 'Goa & North Karnataka (Karwar)',
        threatLevel: 'WATCH',
        waveHeightRange: '2.0 - 2.5 m',
        swellHeightRange: '1.8 - 2.3 m',
        windSpeedRange: '25 - 35 km/h',
        advisory: 'Watch: Fishermen advised to anchor boats securely away from breaking wave zones.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [73.7, 15.75],
          [73.8, 15.3],
          [74.0, 14.8],
          [74.3, 14.3],
        ],
      },
    },
    {
      type: 'Feature',
      properties: {
        id: 'KAR-02',
        name: 'South Karnataka (Bhatkal - Udupi - Mangaluru)',
        threatLevel: 'ALERT',
        waveHeightRange: '2.7 - 3.3 m',
        swellHeightRange: '2.2 - 2.8 m',
        windSpeedRange: '30 - 42 km/h',
        advisory: 'Alert: Wave surges and strong rip currents along beaches.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [74.3, 14.3],
          [74.6, 13.8],
          [74.75, 13.3],
          [74.85, 12.85],
        ],
      },
    },

    // 4. Kerala Coast (Alert & Warning ribbons - prominent orange ribbon in Screenshot 2)
    {
      type: 'Feature',
      properties: {
        id: 'KER-01',
        name: 'North Kerala (Kasaragod - Kannur - Kozhikode)',
        threatLevel: 'ALERT',
        waveHeightRange: '2.8 - 3.4 m',
        swellHeightRange: '2.3 - 2.9 m',
        windSpeedRange: '35 - 45 km/h',
        advisory: 'Alert: High swell surge warning (Kallakkadal). Small craft advised not to venture.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [74.85, 12.85],
          [75.1, 12.3],
          [75.4, 11.75],
          [75.75, 11.25],
        ],
      },
    },
    {
      type: 'Feature',
      properties: {
        id: 'KER-02',
        name: 'South Kerala (Kochi - Alappuzha - Kollam - Vizhinjam)',
        threatLevel: 'ALERT',
        waveHeightRange: '3.0 - 3.6 m',
        swellHeightRange: '2.5 - 3.1 m',
        windSpeedRange: '38 - 48 km/h',
        advisory: 'Alert: Kallakkadal surge warning. High wave threat along South Kerala coast.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [75.75, 11.25],
          [76.0, 10.75],
          [76.2, 9.95],
          [76.4, 9.4],
          [76.6, 8.85],
          [76.9, 8.35],
          [77.2, 8.1],
        ],
      },
    },

    // 5. Tamil Nadu Coast & Gulf of Mannar (Alert & Watch ribbons)
    {
      type: 'Feature',
      properties: {
        id: 'TN-01',
        name: 'Tamil Nadu South (Kanyakumari - Gulf of Mannar)',
        threatLevel: 'ALERT',
        waveHeightRange: '2.9 - 3.5 m',
        swellHeightRange: '2.4 - 3.0 m',
        windSpeedRange: '35 - 46 km/h',
        advisory: 'Alert: High energy wave convergence in Gulf of Mannar. Heavy swells.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [77.2, 8.1],
          [77.6, 8.2],
          [78.1, 8.5],
          [78.5, 9.0],
          [79.2, 9.25],
        ],
      },
    },
    {
      type: 'Feature',
      properties: {
        id: 'TN-02',
        name: 'Tamil Nadu North (Palk Bay - Nagapattinam - Cuddalore - Chennai)',
        threatLevel: 'WATCH',
        waveHeightRange: '1.9 - 2.4 m',
        swellHeightRange: '1.5 - 2.0 m',
        windSpeedRange: '20 - 32 km/h',
        advisory: 'Watch: Moderate sea state. Beach activities to proceed with caution.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [79.2, 9.25],
          [79.8, 10.3],
          [79.9, 10.8],
          [79.85, 11.75],
          [80.25, 13.1],
          [80.3, 13.5],
        ],
      },
    },

    // 6. Andhra Pradesh Coast (Watch & Alert ribbons)
    {
      type: 'Feature',
      properties: {
        id: 'AP-01',
        name: 'Andhra Pradesh (Nellore - Machilipatnam - Kakinada - Visakhapatnam)',
        threatLevel: 'WATCH',
        waveHeightRange: '2.0 - 2.5 m',
        swellHeightRange: '1.6 - 2.1 m',
        windSpeedRange: '24 - 35 km/h',
        advisory: 'Watch: Coastal sea conditions moderately rough.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [80.3, 13.5],
          [80.1, 14.8],
          [80.8, 15.8],
          [81.6, 16.3],
          [82.3, 16.9],
          [83.3, 17.7],
          [84.1, 18.5],
        ],
      },
    },

    // 7. Odisha & West Bengal Coast (Watch ribbons)
    {
      type: 'Feature',
      properties: {
        id: 'ODI-WB-01',
        name: 'Odisha & West Bengal (Gopalpur - Puri - Paradip - Digha)',
        threatLevel: 'WATCH',
        waveHeightRange: '2.1 - 2.6 m',
        swellHeightRange: '1.7 - 2.2 m',
        windSpeedRange: '25 - 36 km/h',
        advisory: 'Watch: Swell surges during spring tide periods.',
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [84.1, 18.5],
          [85.0, 19.3],
          [85.8, 19.8],
          [86.7, 20.3],
          [87.5, 21.2],
          [88.0, 21.6],
          [88.8, 21.6],
        ],
      },
    },

    // 8. Offshore Alert Polygons (Shown in Screenshot 2 southwest of Sri Lanka & west of Andaman)
    {
      type: 'Feature',
      properties: {
        id: 'OFFSHORE-SW-01',
        name: 'South-West Offshore Alert Block A',
        threatLevel: 'ALERT',
        waveHeightRange: '3.2 - 3.8 m',
        swellHeightRange: '2.8 - 3.4 m',
        windSpeedRange: '40 - 52 km/h',
        advisory: 'Alert: High oceanic swell field. Deep-sea fishing vessels maintain alert.',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [74.6, 8.8],
          [75.4, 8.9],
          [75.3, 8.2],
          [74.5, 8.1],
          [74.6, 8.8],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        id: 'OFFSHORE-SW-02',
        name: 'South-West Offshore Alert Block B',
        threatLevel: 'ALERT',
        waveHeightRange: '3.1 - 3.7 m',
        swellHeightRange: '2.7 - 3.3 m',
        windSpeedRange: '38 - 50 km/h',
        advisory: 'Alert: Elevated wave height block in open Arabian Sea.',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [74.8, 7.8],
          [75.6, 7.9],
          [75.5, 7.2],
          [74.7, 7.1],
          [74.8, 7.8],
        ]],
      },
    },

    // 9. Andaman & Nicobar Alert Polygons & Ribbons (Screenshot 2 right side)
    {
      type: 'Feature',
      properties: {
        id: 'ANDAMAN-POLY-01',
        name: 'Andaman Sea Warning Sector A',
        threatLevel: 'ALERT',
        waveHeightRange: '3.0 - 3.6 m',
        swellHeightRange: '2.6 - 3.2 m',
        windSpeedRange: '36 - 48 km/h',
        advisory: 'Alert: Strong monsoon winds and high swells across Ten Degree Channel.',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [92.6, 12.6],
          [93.2, 12.8],
          [93.3, 12.1],
          [92.7, 11.9],
          [92.6, 12.6],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        id: 'ANDAMAN-POLY-02',
        name: 'Andaman Sea Warning Sector B',
        threatLevel: 'ALERT',
        waveHeightRange: '3.2 - 3.9 m',
        swellHeightRange: '2.8 - 3.5 m',
        windSpeedRange: '40 - 52 km/h',
        advisory: 'Alert: Rough seas around Little Andaman and South Andaman.',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [92.4, 11.5],
          [93.0, 11.7],
          [93.1, 10.8],
          [92.5, 10.6],
          [92.4, 11.5],
        ]],
      },
    },
    {
      type: 'Feature',
      properties: {
        id: 'ANDAMAN-POLY-03',
        name: 'Nicobar Offshore Sector C',
        threatLevel: 'ALERT',
        waveHeightRange: '3.4 - 4.1 m',
        swellHeightRange: '3.0 - 3.7 m',
        windSpeedRange: '42 - 55 km/h',
        advisory: 'Alert: High swell surges across Great Channel.',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [93.2, 9.4],
          [93.8, 9.6],
          [93.9, 8.8],
          [93.3, 8.6],
          [93.2, 9.4],
        ]],
      },
    },
  ],
};
