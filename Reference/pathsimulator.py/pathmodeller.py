import matplotlib.pyplot as plt
import numpy as np

# Height and width sets to explore
heights = [20, 30, 40, 50]
widths = [20, 30, 40, 50, 60, 70]

# Create a big figure, shaped roughly like the 1000x600 grid
plt.figure(figsize=(14, 8))
# Match your logical play area
plt.xlim(0, 1000)
plt.ylim(0, 600)

# Only 5 opacity bands: o = 10, 20, 30, 40, 50
for op in range(5):  # 0..4
    for hi in heights:
        for wi in widths:
            h = hi
            w = wi
            area = w * h
            o = (op * 10) + 10   # 10, 20, 30, 40, 50
            
            colour = Concat()

            # Initial conditions
            x = 0.0
            y = 0.0
            time = 0.0

            # Your formulas
            vx = 600 - 2 * o - area / 10.0
            vy = 480 - (o * o) / 10.0 - h - w   # initial vy
            yi = 60 - o                         # vertical increment per 0.2s

            xpoints = [x]
            ypoints = [y]


            # Integrate until we hit the boundary or 3 seconds
            while x < 1000 and y < 600 and time < 3.0:
                x = x + vx / 5.0      # consistent with your vx*0.2 logic
                y = y + vy / 5.0

                xpoints.append(x)
                ypoints.append(y)

                vy = vy + yi         # accelerate vy
                time += 0.2

            xvals = np.array(xpoints)
            yvals = np.array(ypoints)

            z = np.polyfit(xvals, yvals, 3)
            p = np.poly1d(z)

            plt.plot(x, p(x), c = 

# Match your logical play area
plt.xlim(0, 1000)
plt.ylim(0, 600)

# Nice grid
plt.grid(True, which="both", linestyle="--", linewidth=0.3, alpha=0.6)

# Tighter layout
plt.tight_layout()

# Save as high-res PDF
plt.savefig("cloud_paths.pdf", dpi=300)

# Also pop up a window so you can see it immediately
plt.show()