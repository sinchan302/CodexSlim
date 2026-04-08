# CodexSlim Benchmark Results

These results demonstrate the extreme token reduction capability of CodexSlim by executing it directly on its own core library architecture.

| File Module | Raw Tokens | Slim Tokens | Token Savings |
|:--- | ---:| ---:| ---:|
| `codexslim/__init__.py` | 27 | 16 | 40.7% |
| `codexslim/cli.py` | 791 | 258 | 67.4% |
| `codexslim/core/__init__.py` | 76 | 40 | 47.4% |
| `codexslim/core/cache_manager.py` | 1,479 | 611 | 58.7% |
| `codexslim/core/engine.py` | 1,065 | 396 | 62.8% |
| `codexslim/core/tokenizer.py` | 771 | 347 | 55.0% |
| `codexslim/filters/__init__.py` | 36 | 24 | 33.3% |
| `codexslim/filters/comment_pruner.py` | 450 | 217 | 51.8% |
| `codexslim/filters/skeletonizer.py` | 483 | 117 | 75.8% |
| `codexslim/parsers/__init__.py` | 45 | 26 | 42.2% |
| `codexslim/parsers/base_parser.py` | 571 | 319 | 44.1% |
| `codexslim/parsers/dotnet_driver.py` | 1,320 | 247 | **81.3%** |
| `codexslim/parsers/go_driver.py` | 1,147 | 240 | 79.1% |
| `codexslim/parsers/java_driver.py` | 1,052 | 240 | 77.2% |
| `codexslim/parsers/python_driver.py` | 1,511 | 330 | 78.2% |
| `codexslim/parsers/ruby_driver.py` | 1,194 | 240 | 79.9% |
| `codexslim/parsers/rust_driver.py` | 1,174 | 240 | 79.6% |
| `codexslim/parsers/web_driver.py` | 1,674 | 402 | 76.0% |

### 📊 Project Aggregates
- **Total Files Scanned:** 18
- **Raw Instruction Tokens:** 14,866
- **Optimized Blueprint Tokens:** 4,310
- **Overall Project Token Reduction:** **71.0%**
