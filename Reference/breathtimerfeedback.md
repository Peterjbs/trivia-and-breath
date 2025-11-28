Here’s a consolidated “spec / working doc” for the breath phase, pulling together all the decisions you’ve made so far: vision, aesthetics, mechanics, constraints, and stuff to watch out for. I’ll keep it structured so you can hand it to yourself-in-3-weeks or another dev and they won’t drown.

---

## 0. Scope

This document covers **breath-phase aesthetics and mechanics** in the “cloud shapes + absorb tube” part of the game:

* The **Inhale → Hold → Exhale** cycle.
* How shapes look, spawn, move, cluster, get absorbed, and score.
* How the **tube / absorb zone** behaves.
* Constraints you’ve set (no discrete “roles”, emergent behaviour only).

It doesn’t re-spec the trivia game, API key stuff, or the video layer, except where breath UI interacts with them.

---

## 1. Vision & Feel

### 1.1 Core metaphor

* Shapes are **clouds / energy blobs** in a fixed play area.
* **Inhale**: world sucks towards the bottom-left, into an S-shaped absorb tube.
* **Hold**: clouds linger, slowly drawn inward, some being absorbed.
* **Exhale**: clouds are expelled back out of the tube, arcing across the screen in varied, organic trajectories.

The user should feel:

* A clear cue of **breathing rhythm** (even without reading labels).
* **Visual satisfaction** from shapes being pulled in and released, with:

  * some long low slipstreams along the bottom,
  * some near-vertical “fountains”,
  * some dramatic up-curves,
  * some random diagonals,
  * some wave/spiral-like arcs.
* **Gradual depletion**: by breath 4–6, most clouds have been absorbed, but later breaths are *still meaningful* (not all done by breath 2).

### 1.2 Design constraints

* **No discrete roles / buckets** (no explicit “this shape is type A / B / C”).
  Behaviour differences must emerge from **continuous rules**:

  * size, opacity, position,
  * random per-shape parameters,
  * common equations applied to everyone.
* Shapes **do not collide** with each other physically (no collision resolution).
  They can overlap visually; interaction is purely:

  * clustering at spawn,
  * colour / motion coupling rules,
  * absorption in the tube.
* The left HUD panel is **physically separate**: shapes cannot enter it, except via the tube.

---

## 2. Layout, Coordinates & Zones

### 2.1 Game container

* **Game container**: fixed **1000 × 600 px** internal coordinate space.

  * `x ∈ [0, 1000]` left → right.
  * `y ∈ [0, 600]` top → bottom.

This sits to the right of a **left HUD panel** (256px wide) in the full 1440×900 layout, but internal simulation uses the 1000×600 space for shapes.

### 2.2 Left HUD & tube

* Left HUD panel (256px wide) is **UI only** (score, button, timers).
* Shapes **cannot enter** the HUD area.
* **Tube**:

  * Conceptually an **S-shaped tube** that lives mostly in the left panel but opens into the **bottom-left** of the game area.
  * Visible form:

    * Height ≈ **120px**.
    * Mouth opening into the bottom-left of the game area: roughly **x ~ 40–60, y ~ 520–580**.
  * Path inside the tube curves up into the left panel and back down, like a lazy river.

### 2.3 Absorb zone

* The absorb zone is **not the whole tube**:

  * Only the section **150px deep into the tube** (from the mouth inwards) counts for **absorption**.
  * Shapes:

    * Start being tracked for absorption **0.5s after crossing** the mouth threshold.
    * Absorption only continues while **Inhale or Hold** is active.
    * Absorption stops the moment **Exhale** begins.

---

## 3. Breath Phase Timeline

Each breath cycle:

* **Inhale**: **5 seconds**.
* **Hold**: **3 seconds**.
* **Exhale**: **4 seconds**.

Total: **12 seconds per breath**.
Target: ~6 breaths per session → ~72 seconds of breath-phase animation.

The **absorb zone and tube**:

* Visible only during **Inhale + Hold** (fades in at Inhale start, fades out around Exhale start).
* Tube representation in left panel can remain faintly visible as a structural element, but the **active glow / emphasis** is only during Inhale/Hold.

---

## 4. Shapes: Types, Attributes, Colors & Clusters

### 4.1 Shape types

All shape types share the same simulation rules; they differ only visually (width/height and drawing primitive):

* **Circle**:

  * radius 5–10 px.
* **Oval** (cloudy blobs):

  * `width, height` ≈ **30–80 × 30–60 px**.
* **Egg** shapes:

  * `height`: 30–60 px, `width`: 30–80 px.
* **TV** shapes:

  * same size range as egg, but more rectangular with very rounded corners.
* **Curved form** (replacing sharp rhombus):

  * e.g. rounded triangle or L-shaped blob with curvature; uses same bounding box sizes.

All shapes:

* Exist as an **axis-aligned bounding box** for physics.
  Drawing details can be more complex but do **not** affect motion.

### 4.2 Shape attributes (per instance)

For each shape:

* Geometry:

  * `x, y`: current center position.
  * `w, h`: width, height.
* Motion:

  * `vx, vy`: current velocity (px/s).
  * Internal timers:

    * generation wait, inhale delay, exhale delay, etc. (see below).
* Visual:

  * `opacity`: 10–50 (integer). Always mapped to `alpha = opacity / 100` (or similar).
  * `color`: chosen from colour groups.
  * `blurStrength`: moderate; **shapes themselves are blurred** (not the whole scene).
* Absorption-related:

  * `initialOpacity`: stored for scoring.
  * `absorbedOpacityDelta`: how much opacity is scheduled to be lost in tube.
  * `isInTube`: boolean.
  * `tubeEntryTime`, `tubeExitTime`: actual times based on queue.
  * `tubeAbsorbDuration`: computed for Inhale+Hold.

### 4.3 Opacity logic

* **On spawn**:

  * `opacity ∈ [10, 50]`.
  * If spawned as part of a **cluster** (not a new cluster root): opacity reduced by **5**.
* **On edge impact**:

  * **No opacity change** (you explicitly reverted this; only absorption changes opacity).
* **In absorb zone**:

  * Opacity reduced by **5 units per second** of absorb time while in **Inhale+Hold**.
  * Depletion is continuous but **can be precomputed** per tube traversal (see tube logic).

### 4.4 Colour system & clusters

You provided a **colour palette grouped into named families** (VLightHotPink, PurpleyPinky, Greeny, Tealy, etc.), each with 3–5 related HEX colours.

**Cluster rules:**

* Shapes spawn **every 0.02s** during generation, total **800–1000 shapes**, forming around **200 clusters**.
* When creating a new shape:

  * ~**80% chance** it **joins the previous cluster**:

    * Its color must be **from the same colour group** as the previous shape in that cluster.
    * It shares the cluster’s initial `vx`, `vy`, and wait time.
    * It spawns with position offset:

      * New shape midpoint = previous shape midpoint

        * `(±(h/2 + 2n), ±(2w/3 - n))` with `n ∈ {1, 2, 3}`.
  * ~**20% chance** it starts a **new cluster**:

    * Random colour group picked.
    * Random `vx, vy` and wait time.
* When spawning “into empty space” but overlapping an existing cluster:

  * If random says “new cluster” but placement overlaps an existing shape:

    * Snap it to that cluster instead (inherit colour group + velocities).
    * This increases variety of cluster sizes: clusters can grow by **accidental overlap**, not just chain spawns.

This ensures large **colour-coherent clusters** that move like mini-flocks.

---

## 5. Breath-Phase Motion Overview

### 5.1 Separate motion regimes

There are three motion regimes:

1. **Pre-breath “cloud drift”** (during generation / light phase):

   * Shapes drift like clouds, generally rising but with varied slight arcs and occasional downward dips.
   * No tube interaction yet.
2. **Breath-phase**:

   1. **Inhale**: global pull towards bottom-left tube mouth.
   2. **Hold**: motion damped, slowly creeping toward tube.
   3. **Exhale**: shapes expelled from tube, following exhale dynamics.
3. **Tube interior**:

   * Once inside, shapes are not individually animated on screen; we only track:

     * entry times,
     * absorption schedule,
     * exit queue.

---

## 6. Inhale Phase Mechanics

### 6.1 Goals

* Most shapes should be **drawn towards bottom-left** during each inhale.
* Ideally:

  * By the end of each inhale, **≈90%** of shapes have **reached the tube mouth region** (some enter, some skim).
  * Shapes should **not all slam into the absorb zone and stop** — they should feel like clouds being *pulled* in, some captured, some flying past.

### 6.2 Inhale timing & delays

Per shape at inhale start:

* **Inhale response delay**:
  Each shape delays reacting to inhale by:

  ```text
  delay_ms = (x / 10 - y / 20 + opacity) * n   (for n ∈ {1, 2, 3})
  ```

  * So shapes further right, higher up, or more opaque respond slightly later.
  * This gives **staggered “oh, now I’m getting sucked in”** behaviour.

### 6.3 Inhale motion rules

After its delay:

1. **Exhale → Inhale transition**:

   * Velocities don’t snap instantly; they change at most **±25 units per 0.1s** for both `vx` and `vy`.
   * This prevents ugly “teleport” direction changes; shapes **arc** into their new courses.

2. **Initial leftward slip (50% chance)**:

   * For each shape:

     * Once it starts reacting to inhale, **50% chance** it first moves almost directly left for **0.5–1.0 seconds**:

       * `vx` ≈ negative (left), `vy` ≈ small downward `(≈ 3n)`.
     * Only after this does it reorient towards the tube mouth.

3. **General targeting**:

   * Target point for inhale is near **bottom-left**, something like:

     * `target ≈ (mouthX, mouthY + n*h)` → a little below center based on `n` and height.
   * Velocity adjustment:

     * At each step, adjust `vx, vy` **gradually** (capped change per 0.1s) to reduce the vector from shape to target.

4. **Field-like behaviour**:

   * In addition to explicit targeting, a continuous field can bias:

     * More pull as shapes get closer to bottom,
     * Slight lateral convergence to the tube mouth.

### 6.4 Absorb zone interaction during inhale

* The absorb zone is only active during **Inhale + Hold**.
* **Tube entry**:

  * A shape can only enter the tube if:

    * Its **midpoint crosses the tube mouth threshold** (roughly the vertical line of the mouth).
    * Only **one shape midpoint** can cross this threshold every **0.01s** (queue constraint).
    * Overlapping shapes cannot enter at the exact same instant; if they’re stacked, they’ll enter one after another at 0.01s intervals.
  * Shapes should ideally **approach from below or horizontally**:

    * The design intent is that shapes should not “drop in diagonally from above” too much.
    * Motion field near the mouth should bias shapes to move slightly **downwards then in**.

---

## 7. Hold Phase Mechanics

### 7.1 Goals

* Shapes **slow down** significantly.
* Many shapes **linger near the tube** or in the bottom-left area.
* Some shapes continue drifting lazily, giving a sense of tension.

### 7.2 Motion

* At the moment Hold starts:

  * Divide both `vx` and `vy` by ~10 (or equivalently apply heavy damping with a short time constant).
  * No direction change from inhale; shapes keep their direction, just **much slower**.
* Shapes already being pulled towards the tube continue to move, but very slowly.
* Tube remains active:

  * Shapes can **still enter** and be absorbed during Hold.
  * The same **0.01s one-entry** constraint applies.

---

## 8. Exhale Phase Mechanics

### 8.1 High-level goals

You defined desired qualitative behaviour for exhale:

* **≈25–30%**:

  * Shoot out low along the bottom (near tube exit),
  * Then **steeply curve up** around 60–80% of container width,
  * Some curving up dramatically near the right side.
* **≈10–15%**:

  * Almost vertical **wobbly fountains**.
  * Not too fast; they fill vertical space.
* **≈10–15%**:

  * Travel ~200px right,
  * Then sharply pitch almost vertically up.
* **≈20%**:

  * Varied **diagonal trajectories**,
  * Hitting the top-right, mid-top, mid-right, etc.
* **≈10–15%**:

  * **Wave / spiral-like** arcs:

    * Shoot out horizontally,
    * Loop up and back on themselves at least once.

All of this must emerge from a **single continuous dynamic field**, not discrete “this shape is type X”.

### 8.2 Exhale delays & tube exit

* Shapes in the tube exit:

  * **One shape can exit every 0.01 seconds maximum**.
  * Shapes exit the tube in **reverse order they entered** → **LIFO** (stack).
  * Each shape:

    * Takes **0.1s** to fully vanish into the tube from mouth.
    * Takes **0.2s** to fully emerge from the tube during exhale:

      * During this 0.2s, it counts as “out” but still close to the mouth.

* Exiting shapes of the **same colour**:

  * If shapes of the same colour exit within **0.2s of each other**, then:

    * The later one copies the initial exhale `vx, vy` of the earliest one in that 0.2s window.
    * Creates colour-based “flocks” that fly together initially, but they **do not remain permanently coupled**; bouncing & field can still separate them.

### 8.3 Exhale initial conditions

At the moment each shape is fully out of the tube (after its 0.2s emergence):

* Position:

  * Near the tube mouth opening in the **bottom-left**, e.g. `(x≈40–60, y≈520–560)`.
* Delay:

  * Additional **launch delay**: random 0–2 seconds before it fully engages exhale logic.
* Base velocities (conceptual; formula can be tuned):

  * Horizontal speed roughly:

    ```text
    vx0 ≈ 600 - 2*opacity - (w*h)/10
    ```

    → smaller + low-opacity shapes are faster.
  * Vertical speed shaped to generate upward curves:

    ```text
    vy0 ≈ 480 - (opacity^2)/10 - h - w
    ```

    plus incremental updates each 0.2s, something like:

    ```text
    vy += (60 - opacity)   // lighter => accelerates upward faster
    ```
* You’ve experimented extensively with these formulas; the exact numbers can be tuned, but the design constraints are:

  * Smaller + lower opacity → **faster + steeper upward arc**.
  * Larger + higher opacity → **slower, lower, more horizontal**.

### 8.4 Additional exhale shaping rules

You’ve added finer-grained behavioural tweaks (still to be unified into the continuous model):

* **Opacity → vertical curve speed**:

  * Lower opacity → vy increments faster → shape arcs upward sooner.
  * High opacity → slower climb; may stay low and then curve later.
* **Size → base speed**:

  * `horizontal speed ~ 600 - 2*o - area/10`
    → bigger area reduces speed.
* **Directional perturbations**:

  * On exhale start, shapes:

    * Keep previous orientation for **0–1s** before fully accepting exhale vectors.
    * This preserves a sense of continuity across the phase boundary.
* **No hard snap**:

  * Changes in `vx` and `vy` between inhale and exhale are clamped (e.g., `±25` per 0.1s).

The continuous exhale field should encode all these behaviours smoothly, not via hard-coded branches like `if x>300 && y<150`.

---

## 9. Tube Logic, Absorption & Scoring

### 9.1 Tube entry constraints

* Only shapes whose **midpoint crosses the tube mouth threshold** can enter.
* **Max 1 midpoint crossing per 0.01 seconds** → at most 100 entries per second.
* Two smaller shapes can cross in close time if they are vertically separated enough that their midpoints don’t cross the threshold *simultaneously* (practically, still one per 0.01s).

### 9.2 Interior behaviour & queue

* Once a shape enters:

  1. It takes **0.5 seconds** of travel **before absorption begins**.
  2. From `t_entry + 0.5s` until:

     * `min(breathInhaleEnd+HoldEnd, t_entry + tubeTravelTime)`
       the shape accrues absorption time.
  3. Tube travel duration is up to ~3–4 seconds:

     * This ensures shapes that enter late in Inhale might still be in the tube for the next breath’s exhale.
* Shapes exit in **reverse order** (LIFO): last in, first out, at most one exit every 0.01s.

### 9.3 Absorption computation

Instead of decrementing opacity every frame while hidden in the tube, you precompute:

* When a shape enters during Inhale or Hold:

  1. Compute effective absorption window:

     ```text
     t_absorb_start = max(entry_time + 0.5s, inhale_start)
     t_absorb_end   = min(hold_end, t_absorb_start + maxTubeAbsorbDuration)
     absorb_duration = max(0, t_absorb_end - t_absorb_start)
     ```
  2. Compute opacity loss:

     ```text
     deltaOpacity = 5 * absorb_duration  (per second)
     newOpacity = initialOpacity - deltaOpacity
     ```
  3. Cases:

     * If `newOpacity <= 0`:

       * Shape is **fully absorbed in-tube**.
       * Schedule a **score pop-up** (score marker) at `t_absorb_exhaust`.
       * Shape **never exits** the tube.
     * Else:

       * Shape exits with `opacity = newOpacity` at its queue-driven exit time in Exhale.

This means you **don’t have to animate opacity changes inside the tube**; they happen logically.

### 9.4 Scoring

* When a shape’s opacity hits ≤0 (i.e., fully absorbed):

  * Score increment:

    ```text
    score += w * h * (initialOpacity / 100)
    ```

    (equivalent to `rx * ry * opacity%` in earlier oval model).
  * Add **UI feedback**:

    * Small floating number near score, or glow in the score panel.
* Score panel is in the left HUD:

  * Always visible.
  * Shows **cumulative score** across the session.
  * Updates in real time as shapes are absorbed.

---

## 10. Aesthetics, Overlays & UI

### 10.1 Backgrounds

* **Inhale background**: deep, dark red.
  (Breath-in = warm, internal, intense.)
* **Exhale background**: deep navy blue.
  (Breath-out = cool, expansive, external.)
* **Hold background**: transition colour between the two (purplish).

The backgrounds are **solid / gradient fills**, not overlays; shapes are rendered **on top** of them.

### 10.2 Shape rendering

* Shapes:

  * Blurred edges (Gaussian or CSS blur filter).
  * Increased contrast and saturation vs background.
  * Blend mode:

    * Ideally something like **screen / additive / hard-light-esque**, to create **bright pops** when shapes overlap.
  * Very soft edges → “light blobs” not harsh geometry.

### 10.3 Text & timers

Current direction (after experiments):

* **Game container**:

  * No big “INHALE / EXHALE / HOLD” text over the shapes (you trialled it, then moved text to HUD).
  * No large countdown numbers overlaid in the play area in the final plan.
* **Left HUD**:

  * Shows:

    * Current phase label (“Inhale / Hold / Exhale”).
    * Time remaining in the current phase.
    * Total score.
    * “Start breathing” button to begin the breath cycle after generation.

At earlier stages shapes slowed down as they passed over large text in the game area; since text moved to HUD, **that slowing effect is no longer used**.

---

## 11. Implementation Considerations & Pitfalls

### 11.1 Time step vs. frame rate

* Use real delta time (`dt`) based on `performance.now()` / timestamps.
* Do not assume 10 FPS or any fixed rate.
* For stability:

  * Cap `dt` per frame (e.g. `dt ≤ 0.05s`).
  * Integrate with `vx, vy` and acceleration (fields) to ensure smooth motion.

### 11.2 Velocity updates (avoiding explosions)

You’ve seen already:

* Aggressively computed `yi` / `xi` terms (like `100 * (x/(2*y))`) can blow vy up into crazy values.
* `vx = vx - vy; vy = vy*2 - vx` style logic can easily produce massive velocities.

Constraints:

* **Clamp velocity deltas**:

  * e.g. `Δvx, Δvy ∈ [-ΔMax, ΔMax]` per 0.1s.
* Avoid dividing by `y` near `y≈0` without guard.
* Prefer **continuous, smooth functions** (like smoothstep, sin, low coefficients) over spikes.

### 11.3 Doing emergent behaviour without “roles”

To keep the “no roles” constraint and still hit your distribution of path types:

* Use **per-shape random factors** (`rSpeed, rAngle, rUp, rWobble…`) that:

  * Influence base speeds, up-field strength, wobble amplitude/frequency.
* Define a single **velocity field** `a(x, y, shapeProps, randomSeeds)`:

  * Horizontal friction term (damps vx).
  * Upward field increasing with `x` and decreasing with `y`.
  * Wobble term (sinusoidal component).
  * Noise term (small random jitter).
* Let the mixture of these plus `size/opacity` create the variety **statistically**:

  * Some shapes get strong up-field + large wobble → wavy arcs.
  * Some get weaker up-field + strong vx → long low slipstreams.
  * Etc.

---

## 12. Open / Tunable Points

This doc locks in **behavioural goals and constraints**, but some numeric knobs are intentionally **tunable** through visual testing:

* Exact formulas for exhale `vx0`, `vy0`, and incremental `vy` changes.
* Strength and shape of the upward field (`ay_field` as a function of `x_frac, y_frac, lightness`).
* Wobble amplitude, frequency ranges.
* How strongly size vs opacity influence:

  * base speed,
  * upward curvature timing.

Those should be adjusted while **looking at live simulations** (like the HTML prototypes we’ve been working on), until the distribution of paths matches the feel:

> “25–30% low-slipstream + big up-curve;
> 10–15% vertical-ish wobblers;
> 10–15% early sharp upturn;
> ~20% diagonals;
> ~10–15% wave/spiral-like.”
