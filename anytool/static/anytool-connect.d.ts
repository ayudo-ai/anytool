/**
 * anytool Connect — TypeScript definitions
 */

interface AnytoolConnectConfig {
  apiKey: string;
  baseUrl?: string;
}

interface AnytoolConnectOptions {
  provider: string;
  userId: string;
  onSuccess?: (connection: { provider: string; userId: string; connected: boolean }) => void;
  onError?: (error: string) => void;
  popupWidth?: number;
  popupHeight?: number;
}

interface AnytoolConnect {
  init(config: AnytoolConnectConfig): void;
  open(opts: AnytoolConnectOptions): void;
  isConnected(opts: { provider: string; userId: string }): Promise<boolean>;
}

declare const AnytoolConnect: AnytoolConnect;
export default AnytoolConnect;
