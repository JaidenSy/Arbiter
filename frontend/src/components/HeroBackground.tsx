/**
 * HeroBackground — Arbiter landing page ambient background.
 *
 * Two layers:
 * 1. @shader-gradient/react — slow flowing WebGL color wash (deep zinc + amber)
 * 2. @react-three/fiber — sparse particle mesh representing the agent network
 *
 * Respects prefers-reduced-motion: particles freeze, gradient pauses.
 */

import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { ShaderGradient, ShaderGradientCanvas } from '@shader-gradient/react'
import * as THREE from 'three'
import ErrorBoundary from './ErrorBoundary'

const dpr = (): number => Math.min(typeof window !== 'undefined' ? window.devicePixelRatio : 1, 1.5)

// ── Particle network ──────────────────────────────────────────────────────────

const NODE_COUNT   = 60
const SPREAD       = 14     // world-space radius
const EDGE_DIST    = 4.5    // max distance to draw an edge
const NODE_SIZE    = 0.055
const NODE_COLOR   = '#D97706'   // amber-600 — matches brand accent
const EDGE_COLOR   = '#78350F'   // amber-900 dim
const EDGE_OPACITY = 0.35

function ParticleNetwork({ reduced }: { reduced: boolean }) {
  const meshRef  = useRef<THREE.InstancedMesh>(null)
  const linesRef = useRef<THREE.LineSegments>(null)
  const t        = useRef(0)

  // Generate stable node positions
  const nodes = useMemo(() => {
    const rng = (seed: number) => {
      let x = Math.sin(seed) * 10000
      return x - Math.floor(x)
    }
    return Array.from({ length: NODE_COUNT }, (_, i) => ({
      base: new THREE.Vector3(
        (rng(i * 3 + 0) - 0.5) * SPREAD * 2,
        (rng(i * 3 + 1) - 0.5) * SPREAD,
        (rng(i * 3 + 2) - 0.5) * SPREAD * 0.6,
      ),
      speed: rng(i * 7) * 0.3 + 0.05,
      phase: rng(i * 11) * Math.PI * 2,
    }))
  }, [])

  // Build edge index pairs once
  const edgePairs = useMemo(() => {
    const pairs: number[] = []
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        if (nodes[i].base.distanceTo(nodes[j].base) < EDGE_DIST) {
          pairs.push(i, j)
        }
      }
    }
    return pairs
  }, [nodes])

  const dummy   = useMemo(() => new THREE.Object3D(), [])
  const posArr  = useMemo(() => new Float32Array(NODE_COUNT * 3), [])

  useFrame((_, delta) => {
    if (reduced) return
    t.current += delta * 0.15

    const mesh  = meshRef.current
    const lines = linesRef.current
    if (!mesh || !lines) return

    // Drift each node gently
    for (let i = 0; i < NODE_COUNT; i++) {
      const n = nodes[i]
      const x = n.base.x + Math.sin(t.current * n.speed + n.phase) * 0.4
      const y = n.base.y + Math.cos(t.current * n.speed * 0.7 + n.phase) * 0.25
      const z = n.base.z

      posArr[i * 3]     = x
      posArr[i * 3 + 1] = y
      posArr[i * 3 + 2] = z

      dummy.position.set(x, y, z)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
    }
    mesh.instanceMatrix.needsUpdate = true

    // Rebuild edge geometry positions each frame (edges are sparse — cheap)
    const edgePositions = new Float32Array(edgePairs.length * 3)
    for (let k = 0; k < edgePairs.length; k += 2) {
      const ai = edgePairs[k]
      const bi = edgePairs[k + 1]
      const ei = (k / 2) * 6
      edgePositions[ei]     = posArr[ai * 3]
      edgePositions[ei + 1] = posArr[ai * 3 + 1]
      edgePositions[ei + 2] = posArr[ai * 3 + 2]
      edgePositions[ei + 3] = posArr[bi * 3]
      edgePositions[ei + 4] = posArr[bi * 3 + 1]
      edgePositions[ei + 5] = posArr[bi * 3 + 2]
    }
    const geo = lines.geometry
    const attr = geo.attributes.position as THREE.BufferAttribute
    attr.array = edgePositions
    attr.needsUpdate = true
    geo.computeBoundingSphere()
  })

  const edgeGeo = useMemo(() => {
    const g = new THREE.BufferGeometry()
    const buf = new Float32Array((edgePairs.length / 2) * 6)
    g.setAttribute('position', new THREE.BufferAttribute(buf, 3))
    return g
  }, [edgePairs])

  const nodeMat = useMemo(() =>
    new THREE.MeshBasicMaterial({ color: NODE_COLOR, transparent: true, opacity: 0.75 })
  , [])

  const nodeGeo = useMemo(() => new THREE.SphereGeometry(NODE_SIZE, 6, 6), [])

  const edgeMat = useMemo(() =>
    new THREE.LineBasicMaterial({ color: EDGE_COLOR, transparent: true, opacity: EDGE_OPACITY })
  , [])

  return (
    <>
      <instancedMesh ref={meshRef} args={[nodeGeo, nodeMat, NODE_COUNT]} />
      <lineSegments ref={linesRef} geometry={edgeGeo} material={edgeMat} />
    </>
  )
}

// ── Slow camera drift ─────────────────────────────────────────────────────────

function CameraDrift({ reduced }: { reduced: boolean }) {
  const t = useRef(0)
  useFrame(({ camera }, delta) => {
    if (reduced) return
    t.current += delta * 0.04
    camera.position.x = Math.sin(t.current) * 1.2
    camera.position.y = Math.cos(t.current * 0.7) * 0.6
    camera.lookAt(0, 0, 0)
  })
  return null
}

// ── Exported component ────────────────────────────────────────────────────────

interface HeroBackgroundProps {
  /** opacity of the particle layer — default 1 */
  particleOpacity?: number
}

function HeroBackgroundInner({ particleOpacity = 1 }: HeroBackgroundProps) {
  const reduced = typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden>

      {/* Layer 1 — shader gradient base, isolated so WebGL failure doesn't kill particles */}
      <ErrorBoundary fallback={<div className="absolute inset-0 bg-gradient-to-b from-[#1C0A00] to-[#0A0A0B]" />}>
        <div className="absolute inset-0" style={{ opacity: 0.55 }}>
          <ShaderGradientCanvas
            style={{ width: '100%', height: '100%', display: 'block' }}
            pixelDensity={dpr()}
          >
            <ShaderGradient
              type="waterPlane"
              animate={reduced ? false : 'on'}
              uTime={0}
              uSpeed={0.12}
              uStrength={2.5}
              uDensity={1.2}
              uFrequency={5.5}
              uAmplitude={3}
              positionX={0}
              positionY={0}
              positionZ={0}
              rotationX={50}
              rotationY={0}
              rotationZ={-60}
              color1="#0A0A0B"
              color2="#1C0A00"
              color3="#78350F"
              reflection={0.05}
              wireframe={false}
              shader="defaults"
              grain="on"
              cAzimuthAngle={180}
            />
          </ShaderGradientCanvas>
        </div>
      </ErrorBoundary>

      {/* Layer 2 — particle mesh, isolated so shader failure doesn't kill this */}
      <ErrorBoundary fallback={null}>
        <div className="absolute inset-0" style={{ opacity: particleOpacity * 0.7 }}>
          <Canvas
            camera={{ position: [0, 0, 18], fov: 50 }}
            gl={{ antialias: false, alpha: true, powerPreference: 'low-power' }}
            style={{ background: 'transparent' }}
            dpr={dpr()}
          >
            <CameraDrift reduced={reduced} />
            <ParticleNetwork reduced={reduced} />
          </Canvas>
        </div>
      </ErrorBoundary>

      {/* Vignette */}
      <div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse 80% 80% at 50% 50%, transparent 20%, rgba(10,10,11,0.75) 100%)',
        }}
      />
    </div>
  )
}

export default function HeroBackground(props: HeroBackgroundProps) {
  return (
    <ErrorBoundary fallback={
      <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-[#1C0A00] via-[#0A0A0B] to-[#0A0A0B]" aria-hidden />
    }>
      <HeroBackgroundInner {...props} />
    </ErrorBoundary>
  )
}
