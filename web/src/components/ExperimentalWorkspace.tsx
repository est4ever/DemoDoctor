import { Canvas, useFrame } from "@react-three/fiber";
import {
  ContactShadows,
  Html,
  OrbitControls,
} from "@react-three/drei";
import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import URDFLoader from "urdf-loader";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import type { ProvenanceKind } from "../lib/types";
import { Badge } from "./ui";

type Props = {
  urdfRad: number[] | null;
  jointNames: string[];
  motorDeg: number[] | null;
  datasetNames: string[];
  highlightGripper?: boolean;
  highlightObjectId?: string | null;
  kinematicsProvenance: ProvenanceKind;
};

type UrdfRobot = THREE.Object3D & {
  setJointValue: (name: string, value: number) => void;
  joints: Record<string, unknown>;
};

function ProvenancePill({
  kind,
  text,
}: {
  kind: ProvenanceKind;
  text: string;
}) {
  const tone =
    kind === "observed"
      ? "observed"
      : kind === "inferred"
        ? "inferred"
        : kind === "estimated"
          ? "warn"
          : "muted";
  return <Badge tone={tone}>{text}</Badge>;
}

function So100Arm({
  urdfRad,
  jointNames,
}: {
  urdfRad: number[] | null;
  jointNames: string[];
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
  });

  return <group ref={group} position={[0, 0.02, 0]} />;
}

function Tabletop() {
  // Approximate 80×60 cm work surface under the arm (illustrative scale)
  return (
    <group>
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0.05, 0, -0.05]}
        receiveShadow
      >
        <planeGeometry args={[0.9, 0.7]} />
        <meshStandardMaterial color="#d9cfc0" roughness={0.92} metalness={0} />
      </mesh>
      <Html position={[-0.32, 0.02, 0.28]} center distanceFactor={1.1}>
        <div className="rounded bg-black/55 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white whitespace-nowrap">
          tabletop · illustrative
        </div>
      </Html>
    </group>
  );
}

function RackEdges({ highlighted }: { highlighted: boolean }) {
  const geom = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(0.25, 0.16, 0.18)),
    [],
  );
  return (
    <lineSegments geometry={geom} position={[0, 0.08, 0]}>
      <lineBasicMaterial color={highlighted ? "#0b6e99" : "#4a5a6c"} />
    </lineSegments>
  );
}

function DishRack({ highlighted }: { highlighted: boolean }) {
  // Simplified rack footprint (~25×18×16 cm) — approximate geometry
  const color = highlighted ? "#0b6e99" : "#6b7c8f";
  return (
    <group position={[0.28, 0.01, -0.18]}>
      <mesh position={[0, 0.08, 0]} castShadow>
        <boxGeometry args={[0.25, 0.16, 0.18]} />
        <meshStandardMaterial
          color={color}
          transparent
          opacity={0.22}
          roughness={0.6}
        />
      </mesh>
      <RackEdges highlighted={highlighted} />
      <Html position={[0, 0.2, 0]} center distanceFactor={1.15}>
        <div
          className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white whitespace-nowrap ${
            highlighted ? "bg-[var(--accent)]" : "bg-black/55"
          }`}
        >
          dish rack · approximate geometry
        </div>
      </Html>
    </group>
  );
}

const PLATE_SLOTS: Array<{
  id: string;
  position: [number, number, number];
  label: string;
}> = [
  // Illustrative only — not triangulated from SAM depth
  {
    id: "green plate:0",
    position: [-0.12, 0.012, 0.12],
    label: "plate:0",
  },
  {
    id: "green plate:1",
    position: [0.02, 0.012, 0.18],
    label: "plate:1",
  },
  {
    id: "green plate:2",
    position: [0.16, 0.012, 0.08],
    label: "plate:2",
  },
];

function Plate({
  id,
  position,
  label,
  highlighted,
}: {
  id: string;
  position: [number, number, number];
  label: string;
  highlighted: boolean;
}) {
  // ~18 cm diameter green plate proxy (illustrative)
  return (
    <group position={position}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.09, 0.09, 0.012, 32]} />
        <meshStandardMaterial
          color={highlighted ? "#3ecf6a" : "#2f9e4f"}
          roughness={0.45}
          metalness={0.05}
          emissive={highlighted ? "#145c2e" : "#000000"}
          emissiveIntensity={highlighted ? 0.35 : 0}
        />
      </mesh>
      <Html position={[0, 0.06, 0]} center distanceFactor={1.2}>
        <div
          className={`rounded px-2 py-0.5 text-[10px] font-semibold text-white whitespace-nowrap ${
            highlighted ? "bg-[var(--ok)]" : "bg-black/55"
          }`}
        >
          {label} · illustrative 3D
          <span className="opacity-80"> · id {id.split(":")[1]}</span>
        </div>
      </Html>
    </group>
  );
}

/**
 * Optional experimental workspace: URDF arm + illustrative scene props.
 * Kinematics are unvalidated; plates/rack are not measured 3D poses.
 */
export function ExperimentalWorkspace({
  urdfRad,
  jointNames,
  motorDeg,
  datasetNames,
  highlightGripper,
  highlightObjectId,
  kinematicsProvenance,
}: Props) {
  const gripperIdx = useMemo(
    () => datasetNames.findIndex((n) => n.includes("gripper")),
    [datasetNames],
  );
  const gripperOpen = motorDeg && gripperIdx >= 0 ? motorDeg[gripperIdx] : null;
  const rackHighlighted =
    highlightObjectId === "dish rack" || highlightObjectId === "target";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <ProvenancePill
          kind={kinematicsProvenance}
          text={`robot pose · ${kinematicsProvenance}`}
        />
        <ProvenancePill kind="illustrative" text="plates · illustrative" />
        <ProvenancePill kind="illustrative" text="rack · approximate" />
        <ProvenancePill kind="observed" text="joints · measured degrees" />
      </div>

      <div className="relative h-[400px] w-full overflow-hidden rounded-xl bg-gradient-to-b from-[#eef3f8] to-[#d9e2ec]">
        <Canvas
          shadows
          dpr={[1, 1.75]}
          camera={{ position: [0.72, 0.48, 0.78], fov: 38, near: 0.01, far: 20 }}
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
            <So100Arm urdfRad={urdfRad} jointNames={jointNames} />
            <Tabletop />
            <DishRack highlighted={rackHighlighted} />
            {PLATE_SLOTS.map((p) => (
              <Plate
                key={p.id}
                id={p.id}
                position={p.position}
                label={p.label}
                highlighted={highlightObjectId === p.id}
              />
            ))}
            <ContactShadows
              opacity={0.28}
              scale={2}
              blur={2.8}
              far={2}
              position={[0, 0.001, 0]}
            />
          </Suspense>
          <OrbitControls
            makeDefault
            target={[0.05, 0.12, 0]}
            minDistance={0.35}
            maxDistance={2.0}
            maxPolarAngle={Math.PI * 0.48}
            enablePan
          />
        </Canvas>
        <div className="pointer-events-none absolute inset-x-0 top-0 bg-gradient-to-b from-black/50 to-transparent p-3 text-[11px] text-white">
          Approximate reconstruction · unvalidated kinematics · not ground truth
          {highlightGripper ? (
            <span className="ml-2 text-[var(--ok-soft)]">· gripper event nearby</span>
          ) : null}
        </div>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/40 to-transparent p-3 text-[11px] text-white">
          SO-100 URDF driven by measured joints with heuristic motor→URDF map
          {gripperOpen != null ? (
            <span className="ml-2 opacity-90">
              · gripper {gripperOpen.toFixed(1)}° (observed)
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
