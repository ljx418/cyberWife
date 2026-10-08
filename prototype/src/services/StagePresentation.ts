export type LayoutMode = 'standard' | 'portrait' | 'ultratall' | 'strip';
export type CompositionMode = 'close' | 'half' | 'full';

export type StagePresentation = {
  layout: LayoutMode;
  requested: CompositionMode;
  effective: CompositionMode;
  focus: { x: number; y: number };
  degradedReason: string | null;
};

const clamp = (value: number, minimum: number, maximum: number) => Math.min(maximum, Math.max(minimum, value));

export function classifyStageLayout(width: number, height: number): LayoutMode {
  const ratio = Math.max(1, width) / Math.max(1, height);
  if (height <= 260 && ratio >= 4) return 'strip';
  if (ratio <= 0.72) return 'ultratall';
  if (ratio < 1) return 'portrait';
  return 'standard';
}

export function resolveStagePresentation(
  requested: CompositionMode,
  width: number,
  height: number,
  focus = { x: 50, y: 32 },
): StagePresentation {
  const layout = classifyStageLayout(width, height);
  const effective = layout === 'strip' ? 'close' : requested;
  return {
    layout,
    requested,
    effective,
    focus: { x: clamp(focus.x, 10, 90), y: clamp(focus.y, 8, 72) },
    degradedReason: layout === 'strip' && requested !== 'close'
      ? '条幅窗口优先保留面部与主操作，已暂时使用近景'
      : null,
  };
}
