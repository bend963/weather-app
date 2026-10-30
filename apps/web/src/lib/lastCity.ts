/** The city page the visitor last looked at, so "close" on the cities page goes back to it. */
const KEY = "last-city";

export function rememberCity(id: string) {
  try {
    sessionStorage.setItem(KEY, id);
  } catch {
    /* storage unavailable */
  }
}

export function lastCity(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}
