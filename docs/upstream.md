# Sources and attribution

PathWeaver code is licensed under Apache-2.0. The public package contains no
third-party placer binary, cell library, raw benchmark archive or search runtime.
Code was developed through an interactive human-directed, model-assisted workflow;
the results are not outputs of an implemented autonomous research controller.

The AES and Ibex inputs are author-published `default/cadb1021` converted layouts
from [Open3DBench Place-LoL](https://github.com/lamda-bbo/Open3DBench/tree/main/Place-LoL).
Pin geometry and connectivity use its tier-specific Nangate45 LEFs and typical
Liberty library. Inputs must be obtained from the upstream sources with their
notices retained. Our adapters and evaluation are independently implemented.
Preparation and model boundaries are described in [the case guide](eda_public_cases.md).

The optional Bookshelf adapter reads the terminal-stage format used by
[D2D-Placer-With-Differentiable-Partitioner](https://github.com/liW-J/D2D-Placer-With-Differentiable-Partitioner).
It handles a restricted geometric assignment subset, not circuit timing.
The adapter does not download or redistribute that repository's inputs.

[SkyDiscover](https://github.com/skydiscover-ai/skydiscover),
[OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve) and
[Creative-Intelligence](https://github.com/DeepMathLLM/Creative-Intelligence) are
references for future research-loop integration; they are not installed or bundled
by this public package, and no runtime integration is claimed.
