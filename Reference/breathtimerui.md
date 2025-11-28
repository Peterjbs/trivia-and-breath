Here’s a resolved, dev-facing spec you can build from. I’ll write it as if it’s a README for the breathing subsystem.

---

# Breath Phase – Aesthetics & Mechanics Specification

## 1. Scope

This spec covers:

* The **breath cycle** (Inhale → Hold → Exhale) and timings.
* How **shapes** (clouds) are spawned, move, cluster, get absorbed, and score.
* The **tube / absorb zone** and its queueing rules.
* How all of this fits into a fixed **1000×600** game container.

Out of scope: trivia logic, API key UI, video backgrounds – except where they have to align with the breathing UI.

---

## 2. Coordinate System & Layout

### 2.1 Game container

* Internal simulation space: **1000px (width) × 600px (height)**.
* Coordinate system:

  * `x ∈ [0, 1000]`: left → right
  * `y ∈ [0, 600]`: top → bottom
* This sits to the right of a separate **left HUD panel** (256px wide) in the full 1440×900 layout, but the breath simulation itself only uses the 1000×600 area.

### 2.2 Left HUD + Tube

* Left HUD panel (`width = 256px`) is **UI only**:

  * Phase label (`Inhale / Hold / Exhale`).
  * Breath timer.
  * Score.
  * “Start breathing” button.
* Shapes **never enter the HUD region** in simulation coordinates.

#### Tube

Conceptual S-shaped tube:

* Visually:

  * Mouth opening into the **bottom-left** of the game container.
  * Tube height ≈ **120px**; think of a “lazy river” that dips into the game area and curves back through the HUD.
* Simulation:

  * **Mouth region** in game coordinates:

    * `tubeMouthX ∈ [40, 60]`, `tubeMouthY ∈ [520, 560]`.
  * Shapes enter the tube when their **center crosses a vertical threshold** at `tubeEntryX ≈ 40–60` and `y` within the mouth band.

We simulate the tube mainly as:

* An **entry threshold** at the mouth.
* A **queue** inside (LIFO).
* An **internal travel time** with a delay before absorption.
* An **exit schedule**.

---

## 3. Breath Cycle State Machine

Global breath controller states, per “round”:

1. **PreBreath / Generation**

   * Duration: **20s** (or until 800–1000 shapes spawned).
   * Shapes spawn, cluster, and drift with “cloud” motion.
2. **Inhale** (`5s`)

   * Phase label: `"INHALE"`.
   * Tube mouth + absorb zone **visible and active**.
   * Shapes pulled towards bottom-left and into tube.
3. **Hold** (`3s`)

   * Phase label: `"HOLD"`.
   * Tube remains visible & absorb zone still active.
   * Velocities heavily damped.
4. **Exhale** (`4s`)

   * Phase label: `"EXHALE"`.
   * Tube mouth still visible but **absorption disabled**.
   * Shapes *inside* the tube are queued to exit and fly back into the game area.

Repeat for ~6 breaths total.

### State transitions

* `PreBreath → Inhale`: triggered when user presses “Start breathing”.
* `Inhale → Hold`: after 5 seconds.
* `Hold → Exhale`: after 3 seconds.
* `Exhale → next Inhale` or end: after 4 seconds (depending on session design).

Each phase knows:

* `phaseStartTime`, `phaseEndTime`.
* `phaseType ∈ {prebreath, inhale, hold, exhale}`.

---

## 4. Core Entities

### 4.1 Shape

```ts
type Shape = {
  id: number;

  // Geometry
  x: number; // center
  y: number;
  w: number;
  h: number;

  // Motion
  vx: number; // px/s
  vy: number; // px/s

  // Visual
  opacity: number;        // 10–50
  initialOpacity: number; // stored at spawn
  colorGroup: string;     // key from colour groups
  colorHex: string;       // actual hex chosen
  shapeType: "circle" | "oval" | "egg" | "tv" | "curved"; // drawing variant

  // Clustering
  clusterId: number; // id of cluster this shape belongs to

  // Breath-phase metadata
  n: 1 | 2 | 3;   // small integer used in some timings / offsets

  // Timers (ms)
  spawnTime: number;
  inhaleDelayMs: number;   // when it starts reacting to inhale
  exhaleDelayMs: number;   // extra delay at exhale start (0–2000ms)

  // Tube / absorption
  isInTube: boolean;
  tubeEntryTime: number | null;
  tubeAbsorbStartTime: number | null;
  tubeAbsorbEndTime: number | null;
  tubeExitTime: number | null;
  scheduledOpacityLoss: number; // computed once
  scheduledScoreTime: number | null; // if fully absorbed

  // Bookkeeping
  active: boolean;   // true if still in simulation (not fully absorbed & gone)
  inGameArea: boolean; // true if currently in 1000x600 space
};
```

### 4.2 TubeSlot

We model tube occupancy and queueing:

```ts
type TubeSlot = {
  shapeId: number;
  entryTime: number;    // when midpoint crosses the mouth threshold
  absorbStartTime: number;
  absorbEndTime: number;
  exitTime: number;     // scheduled exit time (for exhale)
  fullyAbsorbed: boolean;
};
```

### 4.3 Global controllers

* `BreathController`:

  * `phaseType`, `phaseStartTime`, `phaseEndTime`.
* `TubeController`:

  * `tubeStack: TubeSlot[]` (LIFO).
  * Enforces **max 1 entry per 0.01s** and **max 1 exit per 0.01s**.
* `ScoreState`:

  * `totalScore: number`.
  * `scoreEvents: { time: number; value: number; }[]`.

---

## 5. Shape Generation & Clustering (PreBreath)

### 5.1 Generation cadence

* Target: **800–1000 shapes** total.
* Spawn interval: **every 0.02s**.
* Each spawn chooses:

  * `shapeType` ∈ {circle, oval, egg, tv, curved}.
  * `w` ∈ [30, 80], `h` ∈ [30, 60]. (Circles may use smaller 5–10 radius if desired.)
  * `opacityInitial` ∈ [10, 50].

### 5.2 Cluster logic

Let `spawnIndex` be the index of the shape being spawned (0-based).

#### 5.2.1 Cluster formation probability

On each spawn:

* If `spawnIndex === 0`: always start a **new cluster**.
* Else:

  * Let `prevShape = last spawned shape`.
  * `joinPrevCluster` = Bernoulli(0.8) (80% chance).
  * If `joinPrevCluster` **and** the new shape’s generated position will overlap the previous one:

    * Join `prevShape.clusterId`.
  * Else:

    * Try to place random position; if overlaps any existing shape → **join that shape’s cluster** instead of forming a new one.
    * Otherwise, create a **new clusterId`.

#### 5.2.2 Position offsets in cluster

If joining an existing cluster and aligning with `prevShape`:

```text
Δx = ±(prevShape.h/2 + 2n)
Δy = ±(2*prevShape.w/3 - n)
newShape.x = prevShape.x + Δx
newShape.y = prevShape.y + Δy
```

`n ∈ {1,2,3}` is the shape’s `n` value, assigned at spawn.

#### 5.2.3 Colour grouping

* Colour palette is provided as **groups of related colours** (e.g. VLightHotPink, Greeny, Tealy, etc.).
* When a **new cluster** starts:

  * Choose a random colour group.
  * Choose a random colour within that group.
* When a shape **joins an existing cluster**:

  * It must pick its colour from the **same colour group** as the previous cluster shape.
  * The exact colour in that group can be random.

#### 5.2.4 Shared initial motion in clusters

* When a shape joins a cluster:

  * It inherits the **cluster’s current `vx`, `vy`, and any wait timers**.
* When generating a brand-new cluster root:

  * Randomise `vx`, `vy` within the pre-breath drift ranges (see below).

### 5.3 PreBreath drift (cloud motion)

Goal: slow, organic “cloud” movement, mostly upwards but not all stuck at the top.

**Initial velocities at spawn:**

* `vx`:

  * Base: `vx0 = randomUniform(-40, 40)`.
* `vy`:

  * Base: `vy0 = randomUniform(-20, 20)`.
  * Then **every 1s**:

    * If total active shapes ≥ 100:

      * Pick 5 random shapes → `vy -= 40` (nudge downward).
      * Pick 5 random shapes → `vy += 40` (nudge upward).
      * Pick 5 random shapes → `vx += 40`.
      * Pick 5 random shapes → `vx -= 40`.
* General upward drift:

  * On spawn, add `-20` or `+20` to `vy` (depending on coordinate orientation and “up” direction – for your current y-down system, “up” = negative vy, so use `vy -= 20`).

**Edge behaviour (pre-breath):**

* When touching any edge:

  * 50% chance:

    * Change direction by a random angle ∈ [160°, 200°] and **half the speed**.
* When crossing `y > 300` (bottom half):

  * 30% chance: give shape a slow rising behaviour.
* When crossing `y < 200` (top band):

  * Another 30% chance for slow rising behaviour (prevent permanent top-stuck shapes).
* Every second:

  * Pick 5 shapes and set their `vx, vy` equal to another shape they are touching (copy motion).

Result: shallow arcs of different heights/widths, some drifting down, some up, like clouds.

---

## 6. Inhale Phase – Mechanics

### 6.1 Timing

* Phase duration: **5,000ms**.
* Phase start time: `tInhaleStart`.

### 6.2 Inhale activation delay (per shape)

On entering Inhale, compute per shape:

```ts
// all in ms
// NOTE: clamp to a sane range, e.g. [0, 2000]
shape.inhaleDelayMs = clamp(
  (shape.x / 10 - shape.y / 20 + shape.opacity) * shape.n,
  0,
  2000
);
```

A shape only starts reacting to inhale when:

```ts
now >= tInhaleStart + shape.inhaleDelayMs
```

Before that, it continues its pre-breath / exhale motion.

### 6.3 Inhale velocity adjustments

Let `tubeMouthTarget` be the target point for inhale (approx bottom-left where tube starts pulling):

```ts
const tubeMouthTarget = {
  x: 50,                           // center of mouth in x
  y: 520 + shape.n * shape.h * 0.5 // slightly below center based on n & height
};
```

Once inhale is “active” for a shape:

1. **Optional left-slip (50% chance)**:

   * If `shape.didInhaleLeftSlip === false`:

     * On first activation:

       ```ts
       if (random() < 0.5) {
         shape.inhaleSlipUntil = now + randomUniform(500, 1000); // ms
         shape.didInhaleLeftSlip = true;
       } else {
         shape.inhaleSlipUntil = null;
         shape.didInhaleLeftSlip = true;
       }
       ```

   * While `now < shape.inhaleSlipUntil`:

     * Force a leftward drift with mild downward nudge:

       ```ts
       shape.vx ≈ -|shape.vx| (clamped magnitude)
       shape.vy ≈  3 * shape.n  // small downward (in y-down coordinate space)
       ```
     * Keep damping changes so speeds don’t explode.

2. **Reorient towards tube mouth (after slip finished)**:

   * Compute vector to target:

     ```ts
     dx = tubeMouthTarget.x - shape.x;
     dy = tubeMouthTarget.y - shape.y;
     ```

   * Desired unit direction:

     ```ts
     const len = Math.hypot(dx, dy) || 1;
     const dirX = dx / len;
     const dirY = dy / len;
     ```

   * Desired speed (per shape):

     * e.g. `desiredSpeed = baseSpeed * f(distance, opacity, size)`:

       ```ts
       const baseSpeed = 120; // px/s
       const lightness = (60 - shape.opacity) / 50; // 0..1
       const distanceFactor = clamp(len / 400, 0.5, 2.0);

       const desiredSpeed =
         baseSpeed * (0.8 + 0.6 * lightness) * distanceFactor;
       ```

   * Desired velocity vector:

     ```ts
     const desiredVx = desiredSpeed * dirX;
     const desiredVy = desiredSpeed * dirY;
     ```

   * **Smooth change** (no snapping): limit velocity change per 0.1s to `±25`:

     ```ts
     const maxDeltaPerSecond = 250; // 25 per 0.1s
     const dvx = desiredVx - shape.vx;
     const dvy = desiredVy - shape.vy;

     const maxDv = maxDeltaPerSecond * dt; // dt in seconds
     const factor = Math.min(1, maxDv / (Math.hypot(dvx, dvy) || 1));

     shape.vx += dvx * factor;
     shape.vy += dvy * factor;
     ```

3. Apply motion:

   ```ts
   shape.x += shape.vx * dt;
   shape.y += shape.vy * dt;
   ```

4. Boundaries:

   * On hitting container edges, apply **shallow bounces** (mirror the normal component of velocity, damp magnitude slightly).

### 6.4 Tube entry during Inhale

A shape is eligible to **enter the tube** if:

* It is within the mouth band:

  ```ts
  shape.x <= tubeEntryXThreshold && shape.y ∈ [tubeMouthYMin, tubeMouthYMax]
  ```

* Its midpoint is moving into the tube (vector roughly leftwards / into mouth).

* Tube entry constraint:

  * Maintain `lastTubeEntryTime`.
  * New entry allowed only if `now >= lastTubeEntryTime + 10ms`.
  * Entry is **one at a time**; others wait just outside the threshold.

On entry:

```ts
shape.isInTube = true;
shape.inGameArea = false;
shape.tubeEntryTime = now;
```

Add a `TubeSlot` to `TubeController.tubeStack` (push at end).

---

## 7. Hold Phase – Mechanics

### 7.1 Timing

* Phase duration: **3,000ms**.
* Phase start time: `tHoldStart`.

### 7.2 Motion

At `tHoldStart`:

* For all shapes *not in tube*:

  * Scale velocities:

    ```ts
    shape.vx *= 0.1;
    shape.vy *= 0.1;
    ```

* Continue applying **very weak** inhale targeting (or just let them coast).

* Shapes can still **enter the tube** using the same entry thresholds & queue constraints.

---

## 8. Tube Interior, Absorption & Scoring

### 8.1 Tube travel & absorption window

For each new tube entry (`TubeSlot`):

1. **Initial travel**:

   * From `entryTime` to `entryTime + 0.5s`: travelling into the tube; **no absorption yet**.

2. **Absorption window**:

   * Absorption only happens during **Inhale + Hold**.
   * Effective absorption interval:

     ```ts
     absorbStartTime = max(entryTime + 500ms, tInhaleStart);
     absorbEndTime   = min(tHoldEnd, absorbStartTime + maxTubeAbsorbDuration);
     absorbDuration  = max(0, absorbEndTime - absorbStartTime);
     ```

     `maxTubeAbsorbDuration` can be e.g. 4000ms.

3. **Opacity loss**:

   ```ts
   const opacityLossPerSecond = 5;
   const secondsAbsorbing = absorbDuration / 1000;
   const deltaOpacity = opacityLossPerSecond * secondsAbsorbing;

   shape.scheduledOpacityLoss = deltaOpacity;
   const projectedOpacity = shape.initialOpacity - deltaOpacity;
   ```

4. Cases:

   * **Fully absorbed in-tube**:

     ```ts
     if (projectedOpacity <= 0) {
       slot.fullyAbsorbed = true;
       shape.active = false;
       shape.inGameArea = false;

       // Score
       const baseScore = shape.w * shape.h * (shape.initialOpacity / 100);
       const scoreTime = absorbStartTime + absorbDuration;

       scoreState.totalScore += baseScore;
       scoreState.scoreEvents.push({
         time: scoreTime,
         value: baseScore,
       });
     }
     ```

   * **Partially absorbed**:

     * Mark `slot.fullyAbsorbed = false`.
     * Schedule **tubeExitTime** (see below), and set:

       ```ts
       shape.opacity = projectedOpacity;
       shape.scheduledOpacityLoss = deltaOpacity;
       ```

### 8.2 Tube exit (Exhale queue)

* Slots in `tubeStack` exit in **reverse entry order** → treat `tubeStack` as a **stack**.

* At exhale start (`tExhaleStart`):

  * We begin popping slots from the stack and scheduling exits.
  * Tube exit constraint:

    * Maintain `lastTubeExitTime`.
    * New exit allowed only if `nextExitTime >= lastTubeExitTime + 10ms`.
  * For each `TubeSlot` in LIFO order that is **not fully absorbed**:

    * Assign:

      ```ts
      slot.exitTime = max(tExhaleStart, lastTubeExitTime + 10ms);
      lastTubeExitTime = slot.exitTime;
      ```

* At `slot.exitTime`:

  * The associated `Shape` reappears near the tube mouth (bottom-left), ready for exhale:

    ```ts
    shape.isInTube = false;
    shape.inGameArea = true;
    shape.x = randomUniform(40, 60);
    shape.y = randomUniform(520, 560);
    shape.exhaleDelayMs = randomUniform(0, 2000); // additional launch stagger
    shape.vx, shape.vy = ??? (see exhale model)
    ```

---

## 9. Exhale Phase – Continuous Dynamics Model

### 9.1 Timing

* Phase duration: **4,000ms**.
* Phase start time: `tExhaleStart`.

Each shape exiting the tube:

* Becomes “active” in the game area at `slot.exitTime`.
* Applies its own local exhale delay:

  ```ts
  exhaleActivationTime = tExhaleStart + shape.exhaleDelayMs;
  ```

Until `now >= exhaleActivationTime`, shape continues any existing motion but typically near the mouth.

### 9.2 Initial conditions at exhale activation

We use a **continuous, per-shape field** rather than modes.

For a shape with `width w`, `height h`, `opacity o`:

* `area = w * h`.
* `size = sqrt(area)`.
* `lightness = clamp((60 - o) / 50, 0, 1)`.

Define per-shape random seeds:

```ts
const rSpeed   = random(); // 0..1
const rAngle   = random();
const rUp      = random();
const rWobble1 = random();
const rWobble2 = random();
```

**On exhale activation:**

* **Initial position**: near tube mouth:

  ```ts
  shape.x = randomUniform(40, 60);
  shape.y = randomUniform(520, 560);
  ```

* **Initial velocities**:

  ```ts
  // Horizontal: some slow, some very fast
  let baseVx = 120 + 380 * rSpeed;           // 120..500
  baseVx *= (0.7 + 0.6 * lightness);         // ~0.7x..1.3x
  shape.vx = baseVx;

  // Vertical: some slightly down, some up
  let baseVy = -40 + 260 * rAngle;           // -40..220
  baseVy -= (1 - lightness) * 40;            // heavier -> more downwards
  shape.vy = baseVy;
  ```

* **Upward field profile**:

  ```ts
  shape.upProfile = rUp;  // 0..1
  shape.globalUpStrength =
    20 + 200 * (0.5 * shape.upProfile + 0.5 * lightness); // ~20..220
  ```

* **Wobble / wave parameters**:

  ```ts
  shape.wobbleAmp  = 5 + 80 * rWobble1;      // 5..85 px
  shape.wobbleFreq = 0.5 + 3 * rWobble2;     // 0.5..3.5 Hz
  shape.swirlPhase = randomUniform(0, 2π);
  ```

* Optionally keep a **memory of previous vx, vy** and clamp how fast these change at activation (±25 per 0.1s) to smooth inhale→exhale transition.

### 9.3 Per-frame exhale update

For each active shape during Exhale, each frame:

```ts
function updateExhale(shape: Shape, dt: number) {
  let { x, y, vx, vy } = shape;

  shape.tLocal += dt; // time since exhale activation

  const xFrac = clamp(x / 1000, 0, 1);
  const yFrac = clamp(y / 600,  0, 1);

  // Smoothstep in x (0..1): near 0 on left, 1 on right
  const s = 3 * xFrac * xFrac - 2 * xFrac * xFrac * xFrac;

  // Upward field: stronger to the right, weaker high up
  const ayField =
    shape.globalUpStrength *
    s *
    (1 - 0.5 * yFrac);

  // Horizontal damping (friction)
  const frictionStrength = 0.15 + 0.35 * shape.upProfile;
  const axFriction = -frictionStrength * vx;

  // Wobble / wave
  const wobble = shape.wobbleAmp *
    Math.sin(2 * Math.PI * shape.wobbleFreq * shape.tLocal + shape.swirlPhase);

  const axWobble = wobble * 0.10;
  const ayWobble = wobble * 0.30;

  // Tiny random jitter
  const jitterX = randomUniform(-8, 8);
  const jitterY = randomUniform(-8, 8);

  const ax = axFriction + axWobble + 0.03 * jitterX;
  const ay = ayField + ayWobble + 0.03 * jitterY;

  // Update velocities
  vx += ax * dt;
  vy += ay * dt;

  // Update positions
  x += vx * dt;
  y += vy * dt;

  shape.vx = vx;
  shape.vy = vy;
  shape.x = x;
  shape.y = y;

  // Deactivate if far out of bounds
  if (x < -100 || x > 1100 || y < -100 || y > 700) {
    shape.active = false;
  }
}
```

This continuous model, with different random seeds per shape, is what produces:

* Some long low slipstreams that curve up.
* Some vertical-ish wobblers.
* Some that pitch up quickly.
* Some diagonals.
* Some wave-ish / spiral-like arcs.

No explicit “mode” flags – just emergent from `rSpeed`, `rUp`, wobble params, and the upward field.

---

## 10. Rendering & Aesthetics

### 10.1 Backgrounds

* Inhale: **deep dark red** (e.g. `#190005` gradient).
* Hold: **purple transition** between inhale and exhale colours.
* Exhale: **deep navy blue** (e.g. `#020320` gradient).

Background is drawn **behind shapes**, not as an overlay.

### 10.2 Shape rendering

* Draw filled shapes with blurred edges:

  * Use canvas shadow blur or CSS filter blur.
* Blend mode:

  * If possible: use **screen / additive / hard-light** to create bright overlaps.
* Opacity:

  * `alpha = opacity / 100`, clamped to `[0.15, 0.85]` to avoid totally invisible or solid bricks.

### 10.3 HUD

Left panel:

* Top: phase label (`INHALE / HOLD / EXHALE`).
* Below: a large countdown timer.
* Middle: “Start breathing” / “Next round” button.
* Bottom: score panel that visually lines up with the tube/absorb concept (i.e., the tube graphics integrate with the score region).

---

## 11. Implementation Notes & Failsafes

* Always base motion on **real dt** (`timestamp` diffs).
* **Clamp dt** to e.g. `≤0.05s` to avoid jumpy frames on stalls.
* **Guard divisions** (e.g. divide by `(y || 1)` if you use `1/y` anywhere).
* Don’t let velocities grow unbounded:

  * Cap `|vx|, |vy|` to a max, e.g. 800 px/s.
* Tube queue and absorb schedule:

  * Do a dry run with a simulator (like the HTML exhale simulator you built) to verify that:

    * **Distribution of absorption per breath** matches your desired curve.
    * You don’t get all shapes absorbed in breath 1–2.
* If timing bugs happen:

  * You can always fall back to recomputing `absorbDuration` on the fly at each phase transition, using the same logic as in §8.1, and re-deriving `deltaOpacity`.

---

