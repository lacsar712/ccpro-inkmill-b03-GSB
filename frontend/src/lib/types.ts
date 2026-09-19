export type UserRole = 'admin' | 'grinder';

export interface AuthUser {
  id: number;
  username: string;
  displayName: string;
  role: UserRole | string;
}

export interface Workshop {
  id: number;
  name: string;
  site: string | null;
  notes: string | null;
}

export type MillStatus = 'grinding' | 'idle' | 'wash';

export interface Mill {
  id: number;
  workshopId: number;
  millCode: string;
  pigmentBase: string;
  bowlLiters: number;
  status: MillStatus;
}

export interface SampleCorrection {
  id: number;
  sampleId: number;
  viscosityPaS: number;
  reason: string;
  correctedAt: string;
}

export interface ViscositySample {
  id: number;
  millId: number;
  sampledAt: string;
  /** 原始测量粘度（不可变）；与 originalViscosityPaS 相同 */
  viscosityPaS: number;
  originalViscosityPaS: number;
  /** 有效粘度：无更正时等于原始值，否则取最新一条更正（按 correctedAt、id） */
  effectiveViscosityPaS: number;
  correctionCount: number;
  /** 仅单条 GET 返回，按 correctedAt、id 倒序 */
  corrections?: SampleCorrection[];
  tempC: number | null;
  notes: string | null;
}

export interface GrindPass {
  id: number;
  millId: number;
  startedAt: string;
  passNo: number;
  durationMin: number;
  mediaType: string;
  operatorName: string;
}

export interface DashboardStats {
  workshopTotal: number;
  grindingMillCount: number;
  samplesLast24h: number;
  passesLast7d: number;
}
