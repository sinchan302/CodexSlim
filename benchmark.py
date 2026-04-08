import sys
from pathlib import Path

# Try importing matplotlib, fail gracefully if missing
try:
    import matplotlib.pyplot as plt
    import numpy as np
    _VISUALS_ENABLED = True
except ImportError:
    _VISUALS_ENABLED = False

from codexslim.core.engine import Engine

def generate_benchmark():
    print("🚀 Initializing CodexSlim Benchmark Suite...")
    print("Targeting internal repository: ./codexslim")
    target = Path("codexslim").resolve()
    
    # Engine evaluation
    engine = Engine(workspace_root=target.parent, use_cache=False, tokenizer_backend="openai")
    
    print("⏳ Parsing AST and computing token metrics...")
    result = engine.run(target)
    
    # --- 1. Markdown Table Generation ---
    lines = [
        "# CodexSlim Benchmark Results",
        "",
        "These results demonstrate the extreme token reduction capability of CodexSlim by executing it directly on its own core library architecture.",
        "",
        "| File Module | Raw Tokens | Slim Tokens | Token Savings |",
        "|:--- | ---:| ---:| ---:|"
    ]
    
    sorted_files = sorted(result.files, key=lambda x: str(x.source_path.relative_to(target.parent)))
    
    for f in sorted_files:
        rel_path = f.source_path.relative_to(target.parent)
        report = f.token_reports[0]
        savings_str = f"**{report.savings_pct}%**" if report.savings_pct > 80 else f"{report.savings_pct}%"
        lines.append(f"| `{rel_path}` | {report.original_tokens:,} | {report.slim_tokens:,} | {savings_str} |")
    
    lines.extend([
        "",
        "### 📊 Project Aggregates",
        f"- **Total Files Scanned:** {len(result.files)}",
        f"- **Raw Instruction Tokens:** {result.total_original_tokens:,}",
        f"- **Optimized Blueprint Tokens:** {result.total_slim_tokens:,}",
        f"- **Overall Project Token Reduction:** **{result.overall_savings_pct}%**"
    ])
    
    output_path = Path("BENCHMARKS.md")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n✅ Markdown benchmark text generated: {output_path.name}")
    
    # --- 2. Matplotlib Visualization Generation ---
    if _VISUALS_ENABLED:
        files = sorted(result.files, 
                       key=lambda x: x.token_reports[0].original_tokens - x.token_reports[0].slim_tokens, 
                       reverse=True)
        top_files = files[:15]
        
        file_labels = [f.source_path.name for f in top_files]
        raw_tokens = [f.token_reports[0].original_tokens for f in top_files]
        slim_tokens = [f.token_reports[0].slim_tokens for f in top_files]
        
        x = np.arange(len(file_labels))
        width = 0.35
        
        fig, ax = plt.subplots(figsize=(14, 8))
        rects1 = ax.bar(x - width/2, raw_tokens, width, label='Raw Tokens (Noise)', color='#ff6b6b')
        rects2 = ax.bar(x + width/2, slim_tokens, width, label='Slim Tokens (Signal)', color='#4dabf7')
        
        ax.set_ylabel('Token Count')
        ax.set_title('CodexSlim: Token Reduction Before & After (Top 15 Files)')
        ax.set_xticks(x)
        ax.set_xticklabels(file_labels, rotation=45, ha="right")
        ax.legend()
        
        for i, file in enumerate(top_files):
            pct = file.token_reports[0].savings_pct
            max_height = max(raw_tokens[i], slim_tokens[i])
            ax.annotate(f'-{pct}%', xy=(x[i], max_height), xytext=(0, 3),
                        textcoords="offset points", ha='center', va='bottom', 
                        fontweight='bold', color='#2b8a3e')
                        
        global_text = (f"Project Total Raw Tokens: {result.total_original_tokens:,} | "
                       f"Project Total Slim Tokens: {result.total_slim_tokens:,} | "
                       f"Overall Savings: {result.overall_savings_pct}%")
        plt.figtext(0.5, 0.95, global_text, ha="center", fontsize=12, bbox={"facecolor":"#f8f9fa", "alpha":0.5, "pad":5})

        fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        output_img = "codexslim_benchmark_chart.png"
        plt.savefig(output_img, dpi=300, bbox_inches='tight')
        print(f"✅ Visual benchmark graph generated: {output_img}")
    else:
        print("⚠️ Matplotlib not installed. Skipping visual generation. Run 'pip install -e \".[dev]\"' to enable.")

    print(f"\nOverall Space Saved: {result.overall_savings_pct}%")

if __name__ == "__main__":
    generate_benchmark()
