export type DecodedGatewayMessage = {
  type: string;
  id?: string;
  payload?: Record<string, unknown>;
};

export type GatewayStateSnapshot = {
  player?: {
    username?: string;
    x?: number;
    y?: number;
    plane?: number;
    hp?: number;
    prayer?: number;
    run_energy?: number;
    animation?: number | null;
    in_combat?: boolean;
  };
  inventory?: { items: Array<{ id?: number; name?: string; qty: number }> };
  equipment?: { items: Array<{ id?: number; name?: string; qty: number }> };
  skills?: Record<string, { level: number; xp?: number }>;
  target?: { id?: string; name?: string } | null;
  raw?: Record<string, unknown>;
};

export type PendingRequest = {
  resolve: (value: Record<string, unknown>) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
};
