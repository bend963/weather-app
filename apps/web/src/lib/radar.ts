/**
 * Live radar from the National Weather Service. Each WSR-88D (NEXRAD) site
 * publishes an animated reflectivity loop on radar.weather.gov, so a location
 * gets the loop from its nearest site. US states and territories only.
 */

/** [site id, latitude, longitude], from Py-ART's NEXRAD_LOCATIONS (NOAA HOMR). */
const SITES: readonly [string, number, number][] = [
  ["KABR", 45.456, -98.413],
  ["KABX", 35.15, -106.823],
  ["KAKQ", 36.984, -77.007],
  ["KAMA", 35.233, -101.709],
  ["KAMX", 25.611, -80.413],
  ["KAPX", 44.907, -84.72],
  ["KARX", 43.823, -91.191],
  ["KATX", 48.195, -122.494],
  ["KBBX", 39.496, -121.632],
  ["KBGM", 42.2, -75.985],
  ["KBHX", 40.498, -124.292],
  ["KBIS", 46.771, -100.76],
  ["KBLX", 45.854, -108.606],
  ["KBMX", 33.172, -86.77],
  ["KBOX", 41.956, -71.138],
  ["KBRO", 25.916, -97.419],
  ["KBUF", 42.949, -78.737],
  ["KBYX", 24.597, -81.703],
  ["KCAE", 33.949, -81.119],
  ["KCBW", 46.039, -67.807],
  ["KCBX", 43.491, -116.234],
  ["KCCX", 40.923, -78.004],
  ["KCLE", 41.413, -81.86],
  ["KCLX", 32.656, -81.042],
  ["KCRI", 35.238, -97.46],
  ["KCRP", 27.784, -97.511],
  ["KCXX", 44.511, -73.166],
  ["KCYS", 41.152, -104.806],
  ["KDAX", 38.501, -121.677],
  ["KDDC", 37.761, -99.968],
  ["KDFX", 29.273, -100.28],
  ["KDGX", 32.28, -89.984],
  ["KDIX", 39.947, -74.411],
  ["KDLH", 46.837, -92.21],
  ["KDMX", 41.731, -93.723],
  ["KDOX", 38.826, -75.44],
  ["KDTX", 42.7, -83.472],
  ["KDVN", 41.612, -90.581],
  ["KDYX", 32.538, -99.254],
  ["KEAX", 38.81, -94.264],
  ["KEMX", 31.894, -110.63],
  ["KENX", 42.586, -74.064],
  ["KEOX", 31.46, -85.459],
  ["KEPZ", 31.873, -106.698],
  ["KESX", 35.701, -114.891],
  ["KEVX", 30.564, -85.921],
  ["KEWX", 29.704, -98.028],
  ["KEYX", 35.098, -117.56],
  ["KFCX", 37.024, -80.274],
  ["KFDR", 34.362, -98.976],
  ["KFDX", 34.635, -103.629],
  ["KFFC", 33.363, -84.566],
  ["KFSD", 43.588, -96.729],
  ["KFSX", 34.574, -111.198],
  ["KFTG", 39.787, -104.545],
  ["KFWS", 32.573, -97.303],
  ["KGGW", 48.206, -106.624],
  ["KGJX", 39.062, -108.213],
  ["KGLD", 39.367, -101.7],
  ["KGRB", 44.498, -88.111],
  ["KGRK", 30.722, -97.383],
  ["KGRR", 42.894, -85.545],
  ["KGSP", 34.883, -82.22],
  ["KGWX", 33.897, -88.329],
  ["KGYX", 43.891, -70.257],
  ["KHDC", 30.519, -90.407],
  ["KHDX", 33.076, -106.122],
  ["KHGX", 29.472, -95.079],
  ["KHNX", 36.314, -119.631],
  ["KHPX", 36.737, -87.285],
  ["KHTX", 34.931, -86.084],
  ["KICT", 37.654, -97.442],
  ["KICX", 37.591, -112.862],
  ["KILN", 39.42, -83.822],
  ["KILX", 40.151, -89.337],
  ["KIND", 39.708, -86.28],
  ["KINX", 36.175, -95.564],
  ["KIWA", 33.289, -111.669],
  ["KIWX", 41.409, -85.7],
  ["KJAX", 30.484, -81.702],
  ["KJGX", 32.675, -83.351],
  ["KJKL", 37.591, -83.313],
  ["KLBB", 33.654, -101.814],
  ["KLCH", 30.125, -93.216],
  ["KLGX", 47.116, -124.107],
  ["KLIX", 30.337, -89.825],
  ["KLNX", 41.958, -100.576],
  ["KLOT", 41.604, -88.085],
  ["KLRX", 40.74, -116.803],
  ["KLSX", 38.699, -90.683],
  ["KLTX", 33.989, -78.429],
  ["KLVX", 37.975, -85.944],
  ["KLWX", 38.976, -77.488],
  ["KLZK", 34.836, -92.262],
  ["KMAF", 31.943, -102.189],
  ["KMAX", 42.081, -122.716],
  ["KMBX", 48.392, -100.864],
  ["KMHX", 34.776, -76.876],
  ["KMKX", 42.968, -88.551],
  ["KMLB", 28.113, -80.654],
  ["KMOB", 30.679, -88.24],
  ["KMPX", 44.849, -93.565],
  ["KMQT", 46.531, -87.548],
  ["KMRX", 36.168, -83.402],
  ["KMSX", 47.041, -113.986],
  ["KMTX", 41.263, -112.447],
  ["KMUX", 37.155, -121.897],
  ["KMVX", 47.528, -97.325],
  ["KMXX", 32.537, -85.79],
  ["KNKX", 32.919, -117.042],
  ["KNQA", 35.345, -89.873],
  ["KOAX", 41.32, -96.366],
  ["KOHX", 36.247, -86.562],
  ["KOKX", 40.866, -72.864],
  ["KOTX", 47.681, -117.626],
  ["KPAH", 37.068, -88.772],
  ["KPBZ", 40.532, -80.218],
  ["KPDT", 45.691, -118.853],
  ["KPOE", 31.155, -92.976],
  ["KPUX", 38.459, -104.181],
  ["KRAX", 35.665, -78.49],
  ["KRGX", 39.754, -119.461],
  ["KRIW", 43.066, -108.477],
  ["KRLX", 38.312, -81.724],
  ["KRTX", 45.715, -122.964],
  ["KSFX", 43.106, -112.685],
  ["KSGF", 37.235, -93.4],
  ["KSHV", 32.451, -93.841],
  ["KSJT", 31.371, -100.492],
  ["KSOX", 33.818, -117.635],
  ["KSRX", 35.291, -94.362],
  ["KTBW", 27.705, -82.402],
  ["KTFX", 47.46, -111.384],
  ["KTLH", 30.398, -84.329],
  ["KTLX", 35.333, -97.278],
  ["KTWX", 38.997, -96.233],
  ["KTYX", 43.756, -75.68],
  ["KUDX", 44.125, -102.829],
  ["KUEX", 40.321, -98.442],
  ["KVAX", 30.89, -83.002],
  ["KVBX", 34.838, -120.396],
  ["KVNX", 36.741, -98.127],
  ["KVTX", 34.412, -119.179],
  ["KVWX", 38.26, -87.725],
  ["KYUX", 32.495, -114.656],
  ["PABC", 60.793, -161.874],
  ["PACG", 56.853, -135.529],
  ["PAEC", 64.511, -165.295],
  ["PAHG", 60.726, -151.351],
  ["PAIH", 59.462, -146.301],
  ["PAKC", 58.679, -156.629],
  ["PAPD", 65.036, -147.499],
  ["PGUA", 13.454, 144.808],
  ["PHKI", 21.894, -159.552],
  ["PHKM", 20.126, -155.778],
  ["PHMO", 21.133, -157.18],
  ["PHWA", 19.095, -155.569],
  ["TJUA", 18.117, -66.079],
];

/** A loop covers about 230 km around its site; past this, the nearest one isn't useful. */
export const MAX_RADAR_KM = 300;

export type RadarSite = { id: string; km: number };

function distanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rad = Math.PI / 180;
  const a =
    Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
}

/** The closest NWS radar to a point, or null when none covers it. */
export function nearestRadar(lat: number, lon: number): RadarSite | null {
  let best: RadarSite | null = null;
  for (const [id, sLat, sLon] of SITES) {
    const km = distanceKm(lat, lon, sLat, sLon);
    if (!best || km < best.km) best = { id, km };
  }
  return best && best.km <= MAX_RADAR_KM ? best : null;
}

/** The site's animated loop; `stamp` changes every few minutes so the browser fetches a fresh one. */
export function radarLoopUrl(id: string, stamp?: number): string {
  const url = `https://radar.weather.gov/ridge/standard/${id}_loop.gif`;
  return stamp === undefined ? url : `${url}?t=${stamp}`;
}

/** The NWS page for the site, with its full controls. */
export function radarPageUrl(id: string): string {
  return `https://radar.weather.gov/station/${id.toLowerCase()}/standard`;
}
