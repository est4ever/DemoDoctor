import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows, OrbitControls } from "@react-three/drei";
import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import URDFLoader from "urdf-loader";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

type Props = {
  urdfRad: number[] | null;
  jointNames: string[];
  motorDeg: number[] | null;
  datasetNames: string[];
  highlightGripper?: boolean;
};

type UrdfRobot = THREE.Object3D & {
  setJointValue: (name: string, value: number) => void;
  joints: Record<string, unknown>;
};

function So100Arm({
  urdfRad,
  jointNames,
  highlightGripper,
}: {
  urdfRad: number[] | null;
  jointNames: string[];
  highlightGripper?: boolean;
}) {
  const robotRef = useRef<UrdfRobot | null>(null);
  const group = useRef<THREE.Group>(null);

  useEffect(() => {
    const manager = new THREE.LoadingManager();
    const loader = new URDFLoader(manager);
    loader.parseCollision = false;
    loader.loadMeshCb = (path, _manager, done) => {
      const stl = new STLLoader(_manager);
      stl.load(
        path,
        (geom) => {
          geom.computeVertexNormals();
          const isMotor = path.toLowerCase().includes("motor");
          const mat = new THREE.MeshPhysicalMaterial({
            color: isMotor ? 0x1c2430 : 0xe8b83a,
            metalness: isMotor ? 0.55 : 0.08,
            roughness: isMotor ? 0.35 : 0.42,
            clearcoat: isMotor ? 0.35 : 0.15,
            clearcoatRoughness: 0.4,
          });
          const mesh = new THREE.Mesh(geom, mat);
          mesh.castShadow = true;
          mesh.receiveShadow = true;
          done(mesh);
        },
        undefined,
        (err) => done(null as unknown as THREE.Object3D, err as Error),
      );
    };
    loader.load(
      "/robots/so100/so100.urdf",
      (robot) => {
        robot.rotation.x = -Math.PI / 2;
        robot.traverse((c) => {
          c.castShadow = true;
          c.receiveShadow = true;
        });
        robotRef.current = robot as unknown as UrdfRobot;
        if (group.current) {
          group.current.clear();
          group.current.add(robot);
        }
      },
      undefined,
      (err) => console.error("URDF load failed", err),
    );
  }, []);

  useFrame(() => {
    const robot = robotRef.current;
    if (!robot || !urdfRad) return;
    for (let i = 0; i < jointNames.length; i++) {
      const name = jointNames[i];
      const v = urdfRad[i];
      if (name && Number.isFinite(v)) robot.setJointValue(name, v);
    }
    void highlightGripper;
  });

  return <group ref={group} position={[0, 0.02, 0]} />;
}

function Ground() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <circleGeometry args={[0.85, 64]} />
        <meshStandardMaterial color="#e8edf3" roughness={0.95} metalness={0} />
      </mesh>
      <gridHelper
        args={[1.6, 16, "#b7c4d4", "#d5dde8"]}
        position={[0, 0.001, 0]}
      />
    </group>
  );
}

export function RobotViewport({
  urdfRad,
  jointNames,
  motorDeg,
  datasetNames,
  highlightGripper,
}: Props) {
  const gripperIdx = useMemo(
    () => datasetNames.findIndex((n) => n.includes("gripper")),
    [datasetNames],
  );
  const gripperOpen = motorDeg && gripperIdx >= 0 ? motorDeg[gripperIdx] : null;

  return (
    <div className="relative h-full min-h-[280px] w-full overflow-hidden rounded-xl bg-gradient-to-b from-[#eef3f8] to-[#d9e2ec]">
      <Canvas
        shadows
        dpr={[1, 1.75]}
        camera={{ position: [0.62, 0.42, 0.72], fov: 38, near: 0.01, far: 20 }}
      >
        <color attach="background" args={["#e8eef5"]} />
        <hemisphereLight args={["#ffffff", "#9aabbc", 0.85]} />
        <directionalLight
          castShadow
          intensity={1.25}
          position={[1.2, 2.4, 1.0]}
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
        />
        <directionalLight intensity={0.35} position={[-1.2, 0.8, -0.6]} />
        <Suspense fallback={null}>
          <So100Arm
            urdfRad={urdfRad}
            jointNames={jointNames}
            highlightGripper={highlightGripper}
          />
          <ContactShadows
            opacity={0.28}
            scale={2}
            blur={2.8}
            far={2}
            position={[0, 0.001, 0]}
          />
          <Ground />
        </Suspense>
        <OrbitControls
          makeDefault
          target={[0, 0.18, 0]}
          minDistance={0.35}
          maxDistance={1.8}
          maxPolarAngle={Math.PI * 0.48}
          enablePan={false}
        />
      </Canvas>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/35 to-transparent p-3 text-[11px] text-white">
        Joint-driven SO-100 visualization · not scene reconstruction
        {gripperOpen != null ? (
          <span className="ml-2 opacity-90">
            · gripper {gripperOpen.toFixed(1)}
          </span>
        ) : null}
      </div>
    </div>
  );
}
