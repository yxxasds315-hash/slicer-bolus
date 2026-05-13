export interface PipelineConfig {
  dicom_dir: string;
  output_dir: string;
  thickness_mm: number;
  smoothing_method: 'MEDIAN' | 'GAUSSIAN' | 'MORPHOLOGICAL_OPENING' | 'JOINT_TAUBIN';
  smoothing_kernel_mm: number;
  design_method: 'offset_subtract' | 'hollow';
  roi_mode: 'full_skin' | 'slicer_roi';
  roi_segment_id: string;
  seal_kernel_1_mm: number;
  seal_kernel_2_mm: number;
  mold_shell_thickness_mm: number;
  mold_sprue_radius_mm: number;
  mold_vent_radius_mm: number;
  mold_with_sprue: boolean;
  mold_type: 'closed' | 'open_top';
  mold_base_plate: boolean;
}

export interface BolusInfo {
  bolus: string;
  vertices: number;
  bounds_mm: [number, number, number];
  volume_cm3: number;
}

export type MoldStatus = 'idle' | 'running' | 'completed' | 'error';

export interface MoldResult {
  node: string;
  type: string;
  subtype: 'closed' | 'open_top';
  open_top_direction: string | null;
  vertices: number;
  vent_ok: boolean | null;
}
export type ValidateStatus = 'idle' | 'running' | 'completed' | 'error';

export interface ValidateThresholds {
  MHD_mm: number;
  HD95_mm: number;
  Dice: number;
  volume_ratio_min: number;
  volume_ratio_max: number;
  overlap_cm3: number;
}

export interface ValidateResult {
  status: 'PASS' | 'FAIL';
  MHD_mm: number;
  HD95_mm: number;
  Dice: number;
  volume_ratio: number;
  mold_skin_overlap_cm3: number;
  mold_skin_overlap_centroid_ras: [number, number, number] | null;
  non_manifold_edges: number;
  ct_voxel_max_mm: number;
  thresholds: ValidateThresholds;
}

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

export type PipelineStatus = 'idle' | 'running' | 'completed' | 'error';

export interface SlicerVolume { name: string; id: string; dimensions: number[]; spacing_mm: number[]; has_image: boolean; }
export interface SlicerSegmentation { name: string; id: string; segments: string[]; }
export interface SlicerRoi { name: string; id: string; center: number[]; radius: number[]; }
export interface SlicerModel { name: string; id: string; vertices: number; }
export interface SlicerState { volumes: SlicerVolume[]; segmentations: SlicerSegmentation[]; rois?: SlicerRoi[]; models?: SlicerModel[]; nodes_total: number; scene_modified: boolean; error?: string; }
