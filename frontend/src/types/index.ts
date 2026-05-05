export interface PipelineConfig {
  dicom_dir: string;
  output_dir: string;
  thickness_mm: number;
  hu_threshold: number;
  oversampling: number;
  smoothing_method: 'MEDIAN' | 'GAUSSIAN' | 'MORPHOLOGICAL_OPENING' | 'JOINT_TAUBIN';
  smoothing_kernel_mm: number;
  design_method: 'offset_subtract' | 'hollow';
  roi_mode: 'full_skin' | 'slicer_roi';
  roi_segment_id: string;
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
export interface SlicerState { volumes: SlicerVolume[]; segmentations: SlicerSegmentation[]; rois?: SlicerRoi[]; nodes_total: number; scene_modified: boolean; error?: string; }
