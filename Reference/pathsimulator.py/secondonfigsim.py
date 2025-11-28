import matplotlib.pyplot as plt
import numpy as np

# Height and width sets to explore
heights = [20, 30, 40, 50]
widths = [20, 30, 40, 50, 60, 70]

trajectories = []

# 1) SIMULATE ALL PATHS AND STORE DATA
for op in range(5):  # 0..4 -> opacities 10, 20, 30, 40, 50
    for hi in heights:
        for wi in widths:
            h = hi
            w = wi
            area = w * h
            o = (op * 10) + 10   # 10, 20, 30, 40, 50

            # Initial conditions
            x = 0.0
            y = 0.0
            time = 0.0

            # Base formulas
            vx = 600 - 2 * o - area / 10.0
            vy = 480 - (o * o) / 10.0 - h - w + (2 * vx / o)  # initial vy
            yi = 120 - 2 * o       # base vertical increment per 0.2s
            xi = -5.0              # base horizontal increment per 0.2s added to vx

            xpoints = [x]
            ypoints = [y]
            vy_history = [vy]      # keep ONLY vy history

            # Integrate until we hit the boundary or 3 seconds
            while x < 1000 and y < 600 and time < 3.0:
                # apply current velocities
                x = x + vx / 5.0
                y = y + vy / 5.0

                xpoints.append(x)
                ypoints.append(y)

                # --- DYNAMIC CURVE LOGIC ---
                # guards to avoid divide-by-zero
                if x > 300 and y < 150 and y != 0:
                    # xi = x/2y * (150 - y)
                    xi = (x / (2.0 * y)) * (150.0 - y)
                    yi = yi * (y / x) if x != 0 else yi
                elif x > 800 and y < 200 and y != 0:
                    # xi = o + w - vx
                    xi = o + w - vx
                    # yi = 100 * x/2y + yi - o
                    yi = 100.0 * (x / (2.0 * y)) + yi - o
                elif x > 600 and y < 200:
                    # 'l' not defined; assume you meant width
                    l = w
                    xi = vx - vy - l - h
                    yi = - (l + h)
                elif y > x:
                    xi = (x / 2.0) - (2.0 * vx)
                elif vy > vx:
                    # update vx/vy relationship
                    vx = vx - vy
                    vy = vy * 2.0 - vx
                else:
                    # fallback behaviour
                    yi = (30.0 - o)
                    xi = (xi - o)

                # update velocities using xi / yi
                vy = vy + yi         # accelerate vy
                vx = vx + xi         # accelerate vx

                vy_history.append(vy)

                time += 0.2

            xvals = np.array(xpoints, dtype=float)
            yvals = np.array(ypoints, dtype=float)

            trajectories.append({
                "width": w,
                "height": h,
                "opacity": o,
                "vx": vx,
                "vy_hist": vy_history,
                "x": xvals,
                "y": yvals,
            })

# 2) COMPUTE SPEED-BASED SCORES FOR COLOUR (FIRST 5 DATA POINTS)
scores = []
for traj in trajectories:
    vx_final = traj["vx"]      # note: this is final vx, not initial
    vy_hist = traj["vy_hist"]
    n_samples = min(5, len(vy_hist))
    s = 0.0
    for i in range(n_samples):
        s += (vx_final + vy_hist[i])   # your requirement: vx + vy over first 5
    s /= 10.0                          # divide by 10
    traj["speed_score"] = s
    scores.append(s)

min_s = min(scores)
max_s = max(scores)
range_s = max_s - min_s if max_s != min_s else 1.0

# 3) PLOT WITH POLYFIT + COLOUR + LINEWIDTH

plt.figure(figsize=(14, 8))

for traj in trajectories:
    xvals = traj["x"]
    yvals = traj["y"]
    w = traj["width"]
    s = traj["speed_score"]

    # Normalize speed score 0..1 and map to red->green
    norm = (s - min_s) / range_s
    color = plt.cm.RdYlGn(norm)  # red = slower, green = faster

    # Polynomial fit of degree 3 (or less if too few points)
    if len(xvals) >= 3:
        deg = min(3, len(xvals) - 1)
        coeffs = np.polyfit(xvals, yvals, deg)
        poly = np.poly1d(coeffs)

        x_smooth = np.linspace(xvals.min(), xvals.max(), 200)
        y_smooth = poly(x_smooth)

        # Line width: width / 3 + 5
        lw = w / 3.0 + 5.0

        plt.plot(x_smooth, y_smooth, color=color, linewidth=lw, alpha=0.8)

# Match your logical play area
plt.xlim(0, 1000)
plt.ylim(0, 600)

plt.grid(True, which="both", linestyle="--", linewidth=0.3, alpha=0.6)
plt.xlabel("x")
plt.ylabel("y")
plt.title("Polynomial-fitted cloud paths (colour = early speed, width = shape width)")

plt.tight_layout()
plt.savefig("cloud_paths.pdf", dpi=300)
plt.show()
