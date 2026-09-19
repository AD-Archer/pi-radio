export const DURATIONS = [
  { value: 'once', label: 'until it finishes' },
  { value: '15', label: 'loop for 15 min' },
  { value: '30', label: 'loop for 30 min' },
  { value: '60', label: 'loop for 1 hour' },
  { value: '120', label: 'loop for 2 hours' },
  { value: '240', label: 'loop for 4 hours' },
  { value: 'forever', label: 'loop until changed' },
]

export function parseDuration(value) {
  const once = value === 'once'
  const minutes = once || value === 'forever' ? null : parseInt(value, 10)
  return { once, minutes }
}
