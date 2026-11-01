declare module "urdf-loader" {
  import type { LoadingManager, Object3D } from "three";

  export default class URDFLoader {
    constructor(manager?: LoadingManager);
    loadMeshCb: (
      path: string,
      manager: LoadingManager,
      done: (obj: Object3D | null, err?: Error) => void,
    ) => void;
    workingPath: string;
    parseCollision: boolean;
    load(
      url: string,
      onLoad: (robot: Object3D) => void,
      onProgress?: (e: ProgressEvent) => void,
      onError?: (e: unknown) => void,
    ): void;
  }
}
