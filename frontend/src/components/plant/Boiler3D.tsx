import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame, RootState } from '@react-three/fiber';
import { OrbitControls, Environment, ContactShadows, Html } from '@react-three/drei';
import * as THREE from 'three';

interface Boiler3DProps {
  telemetryData?: { tag_name: string; value: number; unit?: string }[];
}

const BoilerModel: React.FC<{ telemetry: Record<string, number> }> = ({ telemetry }) => {
  const furnaceRef = useRef<THREE.Mesh>(null);
  const drumRef = useRef<THREE.Mesh>(null);
  const chimneyRef = useRef<THREE.Mesh>(null);

  // Extract key values with fallbacks
  const furnaceTemp = telemetry['TE-304'] || 800; // Furnace Temp
  const drumLevel = telemetry['LT-201'] || 50; // Drum Level %
  const steamPressure = telemetry['PT-201'] || 45; // Steam Drum Pressure
  const feedFlow = telemetry['FT-101'] || 35; // Feed water flow

  // Dynamic materials
  const furnaceColor = new THREE.Color().setHSL(0.05, 1, Math.min(0.9, furnaceTemp / 1200));
  const drumColor = new THREE.Color().setHSL(0.6, 0.8, 0.2 + (drumLevel / 200));

  useFrame(({ clock }: RootState) => {
    // Animate flow in pipes or slight vibrations based on pressure
    if (furnaceRef.current) {
      // Slight glow/pulse
      const pulse = Math.sin(clock.elapsedTime * 2) * 0.05;
      furnaceRef.current.scale.set(1 + pulse, 1 + pulse, 1 + pulse);
    }
  });

  return (
    <group position={[0, -2, 0]}>
      {/* Base Foundation */}
      <mesh position={[0, -0.25, 0]}>
        <boxGeometry args={[10, 0.5, 8]} />
        <meshStandardMaterial color="#475569" roughness={0.8} />
      </mesh>

      {/* Furnace Body */}
      <mesh ref={furnaceRef} position={[0, 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[4, 4, 5]} />
        <meshStandardMaterial color={furnaceColor} emissive={furnaceColor} emissiveIntensity={furnaceTemp > 500 ? 0.5 : 0} roughness={0.2} metalness={0.8} />

        {/* Furnace Label */}
        <Html position={[0, 2.5, 2.51]} center>
          <div className="bg-slate-900/80 backdrop-blur-sm text-white px-3 py-1.5 rounded border border-slate-700/50 text-xs shadow-xl whitespace-nowrap">
            <div className="font-bold text-slate-300">FURNACE (TE-304)</div>
            <div className="text-orange-400 font-mono text-lg">{furnaceTemp.toFixed(1)} °C</div>
          </div>
        </Html>
      </mesh>

      {/* Steam Drum (Horizontal Cylinder on top) */}
      <mesh ref={drumRef} position={[0, 5, 0]} rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
        <cylinderGeometry args={[1.5, 1.5, 6, 32]} />
        <meshStandardMaterial color={drumColor} metalness={0.6} roughness={0.4} />

        {/* Drum Label */}
        <Html position={[0, 2, 0]} center rotation={[0, 0, -Math.PI / 2]}>
          <div className="bg-slate-900/80 backdrop-blur-sm text-white px-3 py-1.5 rounded border border-slate-700/50 text-xs shadow-xl whitespace-nowrap">
            <div className="font-bold text-slate-300">STEAM DRUM (LT-201 / PT-201)</div>
            <div className="flex gap-4 mt-1">
              <div>
                <span className="text-slate-400 text-[10px]">LEVEL</span>
                <div className="text-blue-400 font-mono text-lg">{drumLevel.toFixed(1)} %</div>
              </div>
              <div>
                <span className="text-slate-400 text-[10px]">PRESSURE</span>
                <div className="text-emerald-400 font-mono text-lg">{steamPressure.toFixed(1)} kg/cm²</div>
              </div>
            </div>
          </div>
        </Html>
      </mesh>

      {/* Connecting Pipes (Risers/Downcomers) */}
      <mesh position={[-1.5, 3.5, 1.5]} castShadow>
        <cylinderGeometry args={[0.2, 0.2, 2, 16]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
      </mesh>
      <mesh position={[1.5, 3.5, 1.5]} castShadow>
        <cylinderGeometry args={[0.2, 0.2, 2, 16]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
      </mesh>
      <mesh position={[-1.5, 3.5, -1.5]} castShadow>
        <cylinderGeometry args={[0.2, 0.2, 2, 16]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
      </mesh>
      <mesh position={[1.5, 3.5, -1.5]} castShadow>
        <cylinderGeometry args={[0.2, 0.2, 2, 16]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Main Steam Pipe coming out of drum */}
      <mesh position={[4.5, 5, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.4, 0.4, 3, 16]} />
        <meshStandardMaterial color="#cbd5e1" metalness={0.9} roughness={0.1} />

        <Html position={[0, 2, 0]} center rotation={[0, 0, -Math.PI/2]}>
          <div className="bg-slate-900/80 backdrop-blur-sm text-white px-2 py-1 rounded border border-slate-700/50 text-xs shadow-xl whitespace-nowrap">
            <span className="text-slate-400 text-[10px]">FLOW (FT-101)</span>
            <div className="text-cyan-400 font-mono">{feedFlow.toFixed(1)} TPH</div>
          </div>
        </Html>
      </mesh>

      {/* Chimney / Stack */}
      <mesh ref={chimneyRef} position={[-3.5, 4, -2.5]} castShadow receiveShadow>
        <cylinderGeometry args={[0.8, 1.2, 8, 32]} />
        <meshStandardMaterial color="#334155" metalness={0.2} roughness={0.9} />
      </mesh>
    </group>
  );
};

export default function Boiler3D({ telemetryData = [] }: Boiler3DProps) {
  // Map telemetry array to key-value object for easy lookup
  const telemetryMap = useMemo(() => {
    const map: Record<string, number> = {};
    telemetryData.forEach(item => {
      map[item.tag_name] = item.value;
    });
    return map;
  }, [telemetryData]);

  return (
    <div className="w-full h-[500px] bg-slate-50 rounded-2xl border border-slate-200 overflow-hidden relative shadow-inner">
      <div className="absolute top-4 left-4 z-10 bg-white/90 backdrop-blur-sm px-4 py-2 rounded-xl shadow-sm border border-slate-200">
        <h3 className="font-bold text-slate-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          3D Digital Twin
        </h3>
        <p className="text-xs text-slate-500 mt-0.5">Real-time Boiler Visualization</p>
      </div>

      <div className="absolute bottom-4 right-4 z-10 flex gap-2">
        <div className="bg-slate-900/80 backdrop-blur-sm text-white text-[10px] px-2 py-1 rounded font-medium">Left Click: Rotate</div>
        <div className="bg-slate-900/80 backdrop-blur-sm text-white text-[10px] px-2 py-1 rounded font-medium">Right Click: Pan</div>
        <div className="bg-slate-900/80 backdrop-blur-sm text-white text-[10px] px-2 py-1 rounded font-medium">Scroll: Zoom</div>
      </div>

      <Canvas camera={{ position: [10, 8, 12], fov: 45 }} shadows>
        <color attach="background" args={['#f8fafc']} />

        <ambientLight intensity={0.4} />
        <directionalLight
          position={[10, 20, 10]}
          intensity={1.5}
          castShadow
          shadow-mapSize={[2048, 2048]}
        />
        <pointLight position={[-10, 0, -20]} intensity={0.5} />

        <BoilerModel telemetry={telemetryMap} />

        <ContactShadows position={[0, -2.2, 0]} opacity={0.5} scale={20} blur={2} far={10} />
        <Environment preset="city" />
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          maxPolarAngle={Math.PI / 2 - 0.05} // Don't go below ground
          minDistance={5}
          maxDistance={30}
        />
      </Canvas>
    </div>
  );
}
