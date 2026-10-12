// Wire types of the Python compute API (api/serialize.py + routers). Keep in
// sync by hand; tests/golden/responses/*.json are the fixtures.

export type Meta = { engine_version: string; elapsed_ms: number; cached: boolean; request_hash: string | null };

export type CellJSON = {
  id: string;
  mode: string;
  index: number;
  name: string;
  degrees: string[];
  start: string;
  end: string;
  movement: string | null;
  type: string;
  nominal_mismatch: boolean;
  pivot_hint: string | null;
  raw_degrees?: string[];
  raw_start?: string;
  raw_end?: string;
  steps?: string[];
  error?: string | null;
};

export type CellRef = { id?: string; name?: string; mode?: string; degrees?: string[]; movement?: string | null };

export type PlacedJSON = {
  i: number;
  midi: number;
  name: string;
  onset: number;
  beat: number;
  string: number;
  fret: number;
  finger: number;
  stretch: boolean;
  stroke: "D" | "U" | "h" | "po";
  run_len: number;
  rest: boolean;
  role: string | null;
  degree: string | null;
  cell: string | null;
  phrase_start: boolean;
  grace: boolean;
};

export type ChordJSON = { start_beat: number; symbol: string };

export type VoicingJSON = {
  layout: string;
  encoding: string;
  cost: number;
  n_up: number;
  n_flags: number;
  fret_lo: number;
  fret_hi: number;
  positions: string[];
  where: string;
  placed: PlacedJSON[];
  contributions: [string, number][];
  flags: string[];
  drop_sites: { target_index: number; prev_index: number; from_string: number; to_string: number; beat: number; fix: string }[];
};

export type FingeringJSON = VoicingJSON & {
  mode: "enumerated" | "optimum" | "free" | "ranked";
  warnings: string[];
  beats_per_bar: number;
  density: "quarter" | "eighth";
  chords: ChordJSON[];
  key: string | null;
  report: string | null;
  alternate: VoicingJSON | null;
};

export type ChunkReport = { box: number | null; offset: number; layouts: number; mode: string };

export type ConstantsJSON = {
  keys: string[];
  modes: string[];
  chord_modes: string[];
  degree_order: string[];
  chord_tones: string[];
  note_options: string[];
  movements: string[];
  line_movement_options: string[];
  positions: string[];
  position_desc: Record<string, string>;
  position_slack: number;
  penta_position_slack: number;
  line_types: string[];
  default_line_type: string;
  line_structures: Record<string, string[]>;
  combo_line_type: string;
  no_first_last_note_types: string[];
  all_notes_default_types: string[];
  translations: string[];
};

export type PositionsJSON = {
  key: string;
  positions: { index: number; name: string; desc: string; boxes: { fret_lo: number; fret_hi: number; strings: number[]; root_strings: number[]; root_midi: number }[] }[];
  constants: ConstantsJSON;
  meta: Meta;
};

export type HealthJSON = {
  ok: boolean;
  engine_version: string;
  python: string;
  auth: string;
  limits: { max_layouts: number; max_layouts_ceiling: number; time_budget_ms: number };
  catalog: Record<string, { total: number; essential: number }>;
  warnings: string[];
  vision: boolean;
  meta: Meta;
};

export type CellsJSON = { mode: string; bonus: boolean; translate: string; cells: CellJSON[]; warnings: string[]; meta: Meta };

export type PairsRequest = {
  chord1: string;
  chord2: string;
  bonus?: boolean;
  dom_to_minor1?: boolean;
  dom_to_minor2?: boolean;
  movement?: string | null;
  pivot?: string | null;
  key?: string | null;
};

export type PairsJSON = {
  chord1: string;
  chord2: string;
  pivot: string | null;
  raw_pivot: string | null;
  pivots: { value: string; raw1: string; raw2: string }[];
  myxo_to_dorian: boolean;
  single_chord: boolean;
  read1: string;
  read2: string;
  dom_to_minor2_effective: boolean;
  sym1: string | null;
  harmony_info: string | null;
  anchors: Record<string, string> | null;
  mapping_info: string | null;
  ending: CellJSON[];
  starting: CellJSON[];
  pairs: { end_id: string; start_id: string; pair_key: string }[];
  positions: string[];
  free_label: string;
  meta: Meta;
};

export type ConnectionRequest = {
  key: string;
  chord1: string;
  chord2: string;
  cell1: CellRef;
  cell2: CellRef;
  bonus?: boolean;
  dom_to_minor1?: boolean;
  dom_to_minor2?: boolean;
  position?: string | null;
  anchor?: "key" | "chord1" | "chord2";
  box?: number | null;
  max_layouts?: number | null;
  max_cost?: number | null;
  with_reports?: boolean;
};

export type ConnectionJSON = {
  end: string;
  start: string;
  end_id: string | null;
  start_id: string | null;
  pair_key: string;
  pivot: { index: number; label: string; name: string | null };
  pivot_indices: number[];
  sym1: string;
  sym2: string | null;
  anchor: { name: string; pc: number | null; sym: string | null };
  read1: string;
  read2: string;
  myxo_to_dorian: boolean;
  single_chord: boolean;
  position: string;
  fingerings: FingeringJSON[];
  n_total: number;
  best: number | null;
  truncated: boolean;
  chunks: ChunkReport[];
  error: string | null;
  budget: { max_layouts: number; used: number; elapsed_ms: number };
  meta: Meta;
};

export type SampledLineJSON = {
  cells: CellJSON[];
  structure: string[];
  reading_modes: string[];
  movement_modes: string[];
  line_type: string;
  signature: string[];
  harmony_caption: string | null;
};

export type SampleRequest = {
  line_type: string;
  length?: number;
  n_dorian?: number;
  n_myxo?: number;
  bonus?: boolean;
  dom_to_minor?: boolean;
  sus4?: boolean;
  movement?: string | null;
  starting_note?: string | null;
  ending_note?: string | null;
  connecting_notes?: string[] | null;
  chord_tones?: boolean;
  n?: number;
  seed?: number | null;
  key?: string | null;
};

export type SampleJSON = {
  line_type: string;
  structure_preview: string[];
  connecting_notes: string[][];
  lines: SampledLineJSON[];
  message: string | null;
  harmony_caption: string | null;
  mapping_info: string | null;
  chord_tones_info: string | null;
  meta: Meta;
};

export type LineFingeringRequest = {
  key: string;
  cells: CellRef[];
  reading_modes: string[];
  movement_modes?: string[] | null;
  position?: string | null;
  pos_key?: string | null;
  max_layouts?: number | null;
  max_cost?: number | null;
  with_reports?: boolean;
};

export type LineFingeringJSON = {
  key: string;
  pos_key: string;
  position: string;
  cells: { name: string; degrees: string[]; movement: string | null; reading_mode: string; movement_mode: string }[];
  pivot_indices: number[];
  fingerings: FingeringJSON[];
  n_total: number;
  best: number | null;
  truncated: boolean;
  chunks: ChunkReport[];
  error: string | null;
  harmony_caption: string;
  meta: Meta;
};

export type PositionsFingeringJSON = {
  key: string;
  mode: string;
  cell: { name: string; degrees: string[]; movement: string | null };
  positions: { name: string; index: number; best_cost: number | null; octaves: { cost: number; register: string; note: string | null; fingering: FingeringJSON }[] }[];
  meta: Meta;
};

export type NoteIn = { pitch: number | string; start?: number | null; phrase_start?: boolean; degree?: string | null; cell?: string | null; role?: string | null };

export type RankAbsoluteJSON = {
  key: string;
  density: string;
  beats_per_bar: number;
  rows: { label: string; cost: number | null; where: string; n_up: number | null; also: string[]; shift: number | null; shift_text: string; fingering: FingeringJSON | null }[];
  n_feasible: number;
  all_shifted: boolean;
  meta: Meta;
};

export type ScoreNoteJSON = { i: number; midi: number; name: string; start: number; duration: number | null; phrase_start: boolean; bar: number; chord: string; degree: string | null };
export type ScoreParseJSON = { notes: ScoreNoteJSON[]; chords: ChordJSON[]; beats_per_bar: number; density: string; uncertain: { measure: number; reason: string }[]; filename?: string; pages?: number; meta: Meta };

export type PatternsJSON = {
  patterns: { name: string; offsets: number[]; stride: number; description?: string }[];
  pentatonics: Record<string, { intervals: number[]; degrees: string[] }>;
  names: string[];
  directions: string[];
  shift_choices: string[];
  exercises: { id: string; label: string }[];
  position_slack: number;
  meta: Meta;
};

export type LineNote = { pitch: number; role?: string; degree?: string; cell?: string };
export type GenerateJSON = { title: string; group: number | null; exercise: string; start_labels: string[]; lines_by_start: Record<string, LineNote[]>; message?: string | null; meta: Meta };

export type RankRow = { position: string; cost: number | null; cpn: number | null; covered: number; where: string; layout: string | null; start: string | null; fingering: FingeringJSON | null };
export type RankJSON = { key: string; position: string | null; generic: boolean; n_total: number; rows: RankRow[]; meta: Meta };

export type TriadPairJSON = {
  title: string;
  interval_name: string;
  triads: { root: string; quality: string; symbol: string; names: string[]; degrees: string[]; pcs: number[] }[];
  hexatonic: { pc: number; offset: number; name: string; label: string; triads: number[]; labels: string[] }[];
  hexatonic_names: string[];
  common: string[];
  identical: boolean;
  markers: { string: number; fret: number; midi: number; pc: number; triads: number[]; name: string; degree: string | null; roots: number[] }[];
  boxes: Record<string, { fret_lo: number; fret_hi: number; strings: number[] }[]>;
  colours: string[];
  slack: number;
  constants: { roots: string[]; qualities: string[]; default_interval: number; scale_directions: string[]; alternating_directions: string[] };
  meta: Meta;
};
