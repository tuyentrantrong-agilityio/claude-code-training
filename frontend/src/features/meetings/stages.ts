const LABELS: Record<string, string> = {
  uploading: 'Uploading',
  transcribing: 'Transcribing',
  summarizing: 'Summarizing',
  filing: 'Filing',
};

export function stageLabel(stage: string | null | undefined): string {
  if (!stage) return 'Starting';
  return LABELS[stage] ?? stage.charAt(0).toUpperCase() + stage.slice(1);
}

export const STAGE_ORDER = ['uploading', 'transcribing', 'summarizing', 'filing'];
