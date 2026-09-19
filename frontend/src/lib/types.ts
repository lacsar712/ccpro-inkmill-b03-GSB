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
  /** 原始取样粘度,永不被更正覆盖 */
  viscosityPaS: number;
  originalViscosityPaS: number;
  /** 有效粘度:取更正链(correctedAt, id)最新一条;无更正时等于原始值 */
  effectiveViscosityPaS: number;
  correctionCount: number;
  tempC: number | null;
  notes: string | null;
  corrections: SampleCorrection[];
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
