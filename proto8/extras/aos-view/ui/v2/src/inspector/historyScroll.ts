// History follows layout growth without mistaking a resize-generated scroll event for user scrolling.
export interface ScrollMetrics { top: number; height: number; client: number }
export function followsLayout(previous: ScrollMetrics | null, current: ScrollMetrics, following: boolean): boolean {
  return following && previous !== null && current.top >= previous.top &&
    (current.height !== previous.height || current.client !== previous.client);
}
