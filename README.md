# EDS Spectrum Simulator / EDS スペクトル・シミュレータ

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![CI](https://github.com/yharada520/EDS_simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/yharada520/EDS_simulator/actions/workflows/ci.yml)

An interactive **web app for building intuition about EDS/EDX measurements** — counting
statistics (Poisson noise), detector response, and thin-film / multilayer matrix effects.
Built with Streamlit, Plotly and [xraylib](https://github.com/tschoonj/xraylib).
教育・R&D 用のインタラクティブな EDS スペクトル・シミュレータです。

![Trace peak buried in sqrt(N) noise, revealed by more counts](docs/demo_statistics.png)

> A 1 % trace element (Ti) is invisible in the noise when under-counted (Max ~2,000),
> but emerges once enough counts are collected (Max ~90,000) — the same sample, only the
> measurement condition changed. 同じ試料でも測定条件（線量）次第で微量ピークは
> 統計ノイズに埋もれ、あるいは出現します。

---

## Why / このツールの狙い

Analysts often misread EDS results. Two common failure modes this tool makes tangible:

- **"No peak, so the element is absent."** A 1 % element can be completely buried in the
  √N background noise at a few thousand counts. Increase probe current / live time and it
  appears — no change in composition.
- **"Higher kV is always better."** For an ALD-thin film on a substrate, most of the
  interaction volume is the substrate. Lowering the accelerating voltage shrinks the
  φ(ρz) generation depth, suppresses the substrate signal, and relatively enhances the
  film S/N.

分析現場での「ピークが見えない＝存在しない」という誤認や、極薄膜分析での
加速電圧の取り過ぎ（情報体積の大半が基板由来）を、定量的に可視化します。

## Features / 機能

- **Counting statistics**: Kramers bremsstrahlung + Gaussian characteristic peaks, with
  `numpy.random.poisson` shot noise. Max counts scales linearly with probe current × live time.
- **xraylib database**: accurate line energies, radiative rates, absorption edges, and the
  Be-window / self-absorption via mass attenuation coefficients.
- **Multilayer thin film**: stack up to 5 layers (surface → substrate). Each layer/substrate
  is given as a **chemical formula** (e.g. `TiN`, `TiO2`, `Al2O3`); absorption by overlying
  layers is computed with Bragg's additivity rule. Analytical **Packwood-Brown φ(ρz)** depth
  distribution anchored to the **Kanaya-Okayama** electron range, integrated with
  `scipy.integrate.quad`.
- **Two modes**: *homogeneous bulk (statistics)* and *thin film / substrate (multilayer)*.

## Quick start / 起動方法

### Docker (recommended)

```bash
docker compose up --build
# open http://localhost:8501
```

### conda

```bash
conda env create -f environment.yml
conda activate eds-sim
streamlit run app.py
```

### pip (xraylib なしでも起動可)

```bash
pip install -r requirements.txt
streamlit run app.py
```

> Without `xraylib`, the app runs on a small built-in fallback table (Phase 1 fully works,
> Phase 2/3 accuracy limited). `xraylib` is best installed from **conda-forge**.
> xraylib 未導入時は内蔵の簡易テーブルにフォールバックします。

## Example structures / 構成例

| Structure | Layers (surface → substrate) | 何が学べるか |
| --- | --- | --- |
| Electrode with adhesion layer | `Au` / `Ti` / `Si` | Au の下の Ti 密着層が埋もれて見えにくい |
| Diffusion barrier + native oxide | `SiO2` / `TiN` / `Si` | 化合物層・自然酸化膜の扱い |
| Surface contamination | `C` / `O` / `Au` / `Si` | 付着物（軽元素）と Be 窓吸収の関係 |

## Project layout / ディレクトリ構成

```
EDS_Simulator/
├── app.py                 # Streamlit UI・描画
├── eds_sim/               # 物理演算パッケージ
│   ├── config.py          # 定数・データクラス設定
│   ├── continuum.py       # Kramers 制動X線
│   ├── characteristic.py  # 特性X線ライン → Gaussian（バルク／層構造）
│   ├── composition.py     # 化学式パース・化合物密度/質量吸収（Bragg 加算則）
│   ├── detector.py        # 分解能・窓吸収・効率
│   ├── depth.py           # φ(ρz) 深さ分布・薄膜/基板の深さ積分
│   ├── elements.py        # xraylib ヘルパ（遅延import・フォールバック）
│   └── spectrum.py        # 合成 ＋ ポアソンノイズ
├── tests/                 # スモークテスト（pytest）
├── environment.yml / requirements.txt
└── Dockerfile / docker-compose.yml
```

## Model assumptions & limitations / モデルの前提と限界

- Bremsstrahlung uses the **Kramers** approximation; characteristic lines use xraylib
  energies / radiative rates. 制動X線は Kramers 近似、特性X線は xraylib。
- Detector resolution follows the standard **Fano-statistics** formula (calibrated to
  130 eV at Mn Kα). 検出器分解能は Fano 統計の標準式。
- **Peak-to-background ratio and absolute counts are an empirical calibration** for
  visualization, not first-principles quantitative values
  (`peak_to_background`, `intensity_scale`). P/B・絶対カウントは可視化向けの経験較正。
- Thin-film φ(ρz) is **Packwood-Brown** with a **Kanaya-Okayama** depth scale; the electron
  scattering matrix is approximated by the substrate composition (thin films, ρz ≪ range).
  厚い重元素最上層では電子減速を過小評価しうる。
- Shell-to-shell relative intensities of multi-shell elements use RadRate only. 殻間差は未考慮。
- Compound formulas support **simple formulas only** (no parentheses). Densities come from a
  preset table / single-element values, otherwise a nominal default (manual entry recommended).
  化合物は単純式のみ（括弧なし）。密度は要手入力推奨。

## Roadmap / 今後の予定

- [ ] Parenthetical / hydrate formulas (e.g. `Ca(OH)2`). 括弧・水和物対応の組成パーサ。
- [ ] Multi-element compound density presets expansion. 化合物密度プリセットの拡充。
- [ ] Shell-dependent ionization (`CS_FluorLine_Kissel`) for multi-shell elements.
- [ ] Absorption-edge visualization on the spectrum.

## Tests / テスト

```bash
pip install pytest
pytest tests/ -v
```

## License / ライセンス

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

## Citation / 引用

If this tool is useful in your work, please cite it (see [CITATION.cff](CITATION.cff)).

## Author / 作者

**よっしー (Tohoku Yossy)** — materials scientist (thin-film synthesis, surface analysis).
GitHub: [@yharada520](https://github.com/yharada520)
