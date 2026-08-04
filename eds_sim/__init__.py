"""EDS スペクトル・シミュレータ 物理演算パッケージ。

フェーズ構成:
    - continuum:      制動X線（Kramers 近似）
    - characteristic: 特性X線（xraylib 連携、Gaussian ピーク）
    - detector:       検出器応答（分解能・窓吸収・効率）
    - spectrum:       スペクトル合成＋ポアソンノイズ
"""

__version__ = "0.3.0"  # Phase 1 + 2 + 3（薄膜/基板 φ(ρz)）統合版
