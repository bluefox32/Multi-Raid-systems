# 貢献ガイドライン

RAID 100 XOR Systemプロジェクトへの貢献をありがとうございます！

このドキュメントは、プロジェクトへの貢献方法を説明しています。

## 行動規範

このプロジェクトでは、すべての参加者に対して敬意を持った行動を期待しています。

## 貢献方法

### 1. Issue報告

バグを見つけた場合やアイデアがある場合は、GitHubのIssuesで報告してください。

**バグレポート:**
```
タイトル: [BUG] 簡潔な説明
内容:
- 再現手順
- 期待される動作
- 実際の動作
- 環境情報 (Python版, OS, iOS版など)
```

**機能リクエスト:**
```
タイトル: [FEATURE] 簡潔な説明
内容:
- 目的
- 実装方法の提案（あれば）
- 利点
```

### 2. Pull Request

1. フォークしたリポジトリでブランチを作成
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. コードを修正

3. テストを実行
   ```bash
   python3 -m pytest
   ```

4. コミット
   ```bash
   git commit -m "feat: 機能説明"
   ```
   
   **コミットメッセージの形式:**
   - `feat:` 新機能
   - `fix:` バグ修正
   - `docs:` ドキュメント更新
   - `style:` コード整形（機能変更なし）
   - `refactor:` リファクタリング
   - `test:` テスト追加

5. プッシュ
   ```bash
   git push origin feature/your-feature-name
   ```

6. Pull Request を作成

### 3. コーディング規約

```python
# PEP 8に準拠
# - インデント: 4スペース
# - 行長: 最大88文字（Blackフォーマッタに準拠）
# - クラス名: PascalCase
# - 関数名: snake_case
# - 定数: UPPER_SNAKE_CASE

# 型ヒントの使用を推奨
def write_file(self, filename: str, data: bytes) -> bool:
    """ファイルを書き込む
    
    Args:
        filename: ファイル名
        data: 書き込みデータ
    
    Returns:
        成功時True、失敗時False
    """
    pass

# docstring形式（NumPy形式）
def calculate_parity(data_chunks: List[bytes]) -> bytes:
    """XORパリティを計算
    
    複数のバイト列からXOR演算でパリティを生成します。
    
    Parameters
    ----------
    data_chunks : List[bytes]
        パリティ計算対象のデータリスト
    
    Returns
    -------
    bytes
        計算されたパリティデータ
    
    Examples
    --------
    >>> data1 = b'\\x01\\x02'
    >>> data2 = b'\\x03\\x04'
    >>> parity = calculate_parity([data1, data2])
    """
    pass
```

## 開発環境のセットアップ

```bash
# リポジトリをクローン
git clone https://github.com/yourusername/raid-xor-system.git
cd raid-xor-system

# 開発用パッケージをインストール
pip install -r requirements.txt

# 動作確認
python3 raid100_simulator.py
```

## テストの実行

```bash
# 全テストを実行
python3 -m pytest

# カバレッジを確認
python3 -m pytest --cov=.

# 特定のテストを実行
python3 -m pytest tests/test_raid100.py
```

## コード品質チェック

```bash
# 型チェック
mypy raid100_simulator.py

# Linting
flake8 raid100_simulator.py

# フォーマット確認
black --check raid100_simulator.py

# フォーマット自動修正
black raid100_simulator.py
```

## ドキュメント更新

- README.mdは重要な変更が発生した場合、更新してください
- 新機能追加時は、ドキュメントも一緒に更新してください
- CHANGELOG.mdに変更内容を記載してください

## iOS Pythonista向けの変更

iOS Pythonista版に変更を加える場合:

1. `ramdisk_raid100_ios.py`の動作確認
2. iOSメモリ制限を考慮した実装
3. `import ui`のエラーハンドリングを確認
4. ドキュメント（README.md）を更新

## セキュリティについて

セキュリティ脆弱性を発見した場合:

1. **公開しないでください**
2. プロジェクトメンテナーに直接報告してください
3. メール: your-email@example.com（ここに記載）

## 質問やサポート

- **一般的な質問**: GitHubのDiscussions
- **バグ報告**: GitHub Issues
- **機能提案**: GitHub Issues + Feature Request

## ライセンス

本プロジェクトへの貢献は、MIT Licenseの下でライセンスされることに同意したものとみなします。

## 謝辞

貢献いただくすべての方に感謝します！

---

**Happy Contributing!** 🎉
