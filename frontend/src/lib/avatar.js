/**
 * Deterministic gradient avatar from agent name.
 * Same name always produces same gradient.
 */

function simpleHash(str) {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0
  }
  return Math.abs(hash)
}

/**
 * Generate a CSS gradient string from an agent name.
 * @param {string} name
 * @returns {{ gradient: string, initials: string }}
 */
export function avatarFromName(name) {
  const hash = simpleHash(name)
  const hue1 = hash % 360
  const hue2 = (hue1 + 40 + (hash % 80)) % 360
  const gradient = `linear-gradient(135deg, hsl(${hue1}, 70%, 55%), hsl(${hue2}, 65%, 45%))`
  const initials = name.charAt(0).toUpperCase()
  return { gradient, initials }
}
