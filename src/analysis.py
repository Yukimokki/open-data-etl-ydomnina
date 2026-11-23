"""Exploratory analysis of the processed goodrecmovies data.

Outputs:
  - data/processed/movies_basic_statistics.pdf   (summary tables)
  - data/processed/rank_vs_runtime_analysis.png  (scatter + conclusion box)

Run: python -m src.analysis
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd

# --- Paths -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_PATH = PROJECT_ROOT / "data" / "processed" / "output.csv"
PDF_PATH = PROJECT_ROOT / "data" / "processed" / "movies_basic_statistics.pdf"
PNG_PATH = PROJECT_ROOT / "data" / "processed" / "rank_vs_runtime_analysis.png"

df = pd.read_csv(PROCESSED_PATH)

# --- Stats -------------------------------------------------------------------
describe = df["runtime_min"].describe()
quantiles = df["runtime_min"].quantile([0.0, 0.01, 0.25, 0.5, 0.75, 0.99, 1.0])

q1, q3 = df["runtime_min"].quantile(0.25), df["runtime_min"].quantile(0.75)
iqr = q3 - q1
upper, lower = q3 + 1.5 * iqr, q1 - 1.5 * iqr
outliers = df[(df["runtime_min"] > upper) | (df["runtime_min"] < lower)]
top10 = df.nlargest(10, "runtime_min")[["primary_title", "start_year", "runtime_min", "rank"]]
bottom10 = df.nsmallest(10, "runtime_min")[["primary_title", "start_year", "runtime_min", "rank"]]

rho = df[["rank", "runtime_min"]].corr(method="spearman").iloc[0, 1]
df["local_rank"] = df["rank"].rank(method="first")
rho_local = df[["local_rank", "runtime_min"]].corr(method="spearman").iloc[0, 1]

# --- Conclusion text ---------------------------------------------------------
def interpret(rho: float) -> str:
    a = abs(rho)
    strength = (
        "no meaningful" if a < 0.1 else
        "a weak" if a < 0.3 else
        "a moderate" if a < 0.5 else
        "a strong"
    )
    direction = "negative" if rho < 0 else "positive"
    if a < 0.1:
        return f"No meaningful correlation (|ρ| = {a:.2f} < 0.10)."
    return f"There is {strength} {direction} correlation (ρ = {rho:+.2f})."

conclusion = interpret(rho)
conclusion_local = interpret(rho_local)

# --- PDF: basic statistics ---------------------------------------------------
with PdfPages(PDF_PATH) as pdf:
    # Page 1 — summary
    fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4 portrait
    ax.axis("off")
    lines = [
        "Movies — basic statistics",
        f"Source: goodrecmovies /api/list (movies, start_year > 2000)",
        f"Rows: {len(df)}",
        "",
        "runtime_min — describe()",
        describe.to_string(),
        "",
        "runtime_min — quantiles",
        quantiles.to_string(),
        "",
        f"IQR fence: lower = {lower:.1f}, upper = {upper:.1f}",
        f"Outliers by IQR: {len(outliers)}",
    ]
    ax.text(0.02, 0.98, "\n".join(lines), va="top", ha="left",
            family="monospace", fontsize=9, transform=ax.transAxes)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    # Page 2 — top/bottom 10
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    lines = [
        "Top 10 longest",
        top10.to_string(index=False),
        "",
        "Bottom 10 shortest",
        bottom10.to_string(index=False),
    ]
    ax.text(0.02, 0.98, "\n".join(lines), va="top", ha="left",
            family="monospace", fontsize=9, transform=ax.transAxes)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

print(f"[saved] {PDF_PATH}")

# --- PNG: scatter + conclusion box ------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))
ax.scatter(df["runtime_min"], df["rank"], alpha=0.6, edgecolors="none")

long_films = df[df["runtime_min"] > 350]
if not long_films.empty:
    ax.scatter(long_films["runtime_min"], long_films["rank"],
               color="red", s=80, label="runtime > 350 min", zorder=5)
    ax.legend(loc="upper right")

ax.set_xlabel("Runtime (min)")
ax.set_ylabel("Rank (lower = better)")
ax.set_title(
    "Does movie rank depend on duration?\n"
    f"goodrecmovies top-100 pool, movies released after 2000 (n={len(df)})",
    fontsize=11,
)
ax.grid(True, alpha=0.3)

box_text = (
    "CONCLUSION\n"
    f"Global rank: {conclusion}\n"
    f"Local rank:  {conclusion_local}\n"
    f"Spearman ρ (global) = {rho:+.3f}\n"
    f"Spearman ρ (local)  = {rho_local:+.3f}"
)
ax.text(
    0.02, 0.02, box_text, transform=ax.transAxes,
    fontsize=9, family="monospace", va="bottom", ha="left",
    bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="black", alpha=0.9),
)

fig.tight_layout()
fig.savefig(PNG_PATH, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"[saved] {PNG_PATH}")

# --- Console summary ---------------------------------------------------------
print("\n--- runtime_min describe ---")
print(describe)
print(f"\nIQR fence: lower={lower:.1f}, upper={upper:.1f}")
print(f"Outliers by IQR: {len(outliers)}")
print(f"\nSpearman ρ (global rank) = {rho:+.3f} -> {conclusion}")
print(f"Spearman ρ (local rank)  = {rho_local:+.3f} -> {conclusion_local}")

"""Year vs duration scatter (+ binned median trend).

Output: data/processed/year_vs_duration.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_PATH = PROJECT_ROOT / "data" / "processed" / "output.csv"
PLOT_PATH = PROJECT_ROOT / "data" / "processed" / "year_vs_duration.png"

df = pd.read_csv(PROCESSED_PATH)

# Drop rows missing either axis (scatter would silently drop them anyway)
plot_df = df.dropna(subset=["start_year", "runtime_min"]).copy()
plot_df["start_year"] = plot_df["start_year"].astype(int)

# Correlations
rho_all = plot_df[["start_year", "runtime_min"]].corr(method="spearman").iloc[0, 1]
pearson = plot_df[["start_year", "runtime_min"]].corr(method="pearson").iloc[0, 1]
print(f"n = {len(plot_df)}")
print(f"Spearman ρ(year, runtime) = {rho_all:+.3f}")
print(f"Pearson  r(year, runtime) = {pearson:+.3f}")
print("\nmedian runtime by year:")
print(plot_df.groupby("start_year")["runtime_min"].agg(["count", "median"]).to_string())

# --- Plot --------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))

ax.scatter(
    plot_df["start_year"], plot_df["runtime_min"],
    alpha=0.6, edgecolors="none", label="movies",
)

# Median per year (only years with >= 2 films, so the line isn't noise)
yearly = (
    plot_df.groupby("start_year")["runtime_min"]
    .agg(["count", "median"])
    .query("count >= 2")
)
ax.plot(
    yearly.index, yearly["median"],
    color="darkorange", marker="o", linewidth=1.8,
    label="median runtime (years with ≥2 films)",
)

# Overall median as a reference line
overall_median = plot_df["runtime_min"].median()
ax.axhline(overall_median, color="grey", linestyle="--", linewidth=1,
           label=f"overall median = {overall_median:.0f} min")

# Highlight the >350 outlier if present
long_films = plot_df[plot_df["runtime_min"] > 350]
if not long_films.empty:
    ax.scatter(long_films["start_year"], long_films["runtime_min"],
               color="red", s=80, zorder=5, label="runtime > 350 min")

ax.set_xlabel("Release year")
ax.set_ylabel("Runtime (min)")
ax.set_title(
    "Runtime vs release year\n"
    f"goodrecmovies, movies after 2000 (n={len(plot_df)}); "
    f"Spearman ρ = {rho_all:+.3f}"
)
ax.grid(True, alpha=0.3)
ax.legend(loc="upper left", fontsize=8)

fig.tight_layout()
fig.savefig(PLOT_PATH, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\n[saved] {PLOT_PATH}")


"""Year vs rank scatter (+ binned median trend).

Output: data/processed/year_vs_rank.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_PATH = PROJECT_ROOT / "data" / "processed" / "output.csv"
PLOT_PATH = PROJECT_ROOT / "data" / "processed" / "year_vs_rank.png"

df = pd.read_csv(PROCESSED_PATH)

plot_df = df.dropna(subset=["start_year", "rank"]).copy()
plot_df["start_year"] = plot_df["start_year"].astype(int)

# Correlations. Rank is ordinal -> Spearman is the primary number.
rho = plot_df[["start_year", "rank"]].corr(method="spearman").iloc[0, 1]
pearson = plot_df[["start_year", "rank"]].corr(method="pearson").iloc[0, 1]
print(f"n = {len(plot_df)}")
print(f"Spearman ρ(year, rank) = {rho:+.3f}")
print(f"Pearson  r(year, rank) = {pearson:+.3f}")
print("\nmedian rank by year:")
print(plot_df.groupby("start_year")["rank"].agg(["count", "median"]).to_string())

# --- Plot --------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))

ax.scatter(
    plot_df["start_year"], plot_df["rank"],
    alpha=0.6, edgecolors="none", label="movies",
)

# Median per year (only years with >= 2 films)
yearly = (
    plot_df.groupby("start_year")["rank"]
    .agg(["count", "median"])
    .query("count >= 2")
)
ax.plot(
    yearly.index, yearly["median"],
    color="darkorange", marker="o", linewidth=1.8,
    label="median rank (years with ≥2 films)",
)

overall_median = plot_df["rank"].median()
ax.axhline(overall_median, color="grey", linestyle="--", linewidth=1,
           label=f"overall median = {overall_median:.0f}")

# Invert y-axis so "better" (lower rank number) is visually higher
ax.invert_yaxis()

ax.set_xlabel("Release year")
ax.set_ylabel("Rank (lower = better; axis inverted)")
ax.set_title(
    "Rank vs release year\n"
    f"goodrecmovies, movies after 2000 (n={len(plot_df)}); "
    f"Spearman ρ = {rho:+.3f}"
)
ax.grid(True, alpha=0.3)
ax.legend(loc="upper right", fontsize=8)

fig.tight_layout()
fig.savefig(PLOT_PATH, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\n[saved] {PLOT_PATH}")