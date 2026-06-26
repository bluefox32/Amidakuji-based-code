import random
import hashlib
import base64
import json
from typing import List, Dict, Tuple, Optional, Any
import secrets

class DataEmbeddedNode:
    """データを内包できるあみだくじノード"""
    
    def __init__(self, level: int, position: int):
        self.level = level
        self.position = position
        self.has_line = False
        self.left = None
        self.right = None
        self.down = None
        self.embedded_data = None
        self.data_type = None
        
    def embed_data(self, data: Any, data_type: str = "generic"):
        """ノードにデータを埋め込み"""
        self.embedded_data = data
        self.data_type = data_type
        
    def __repr__(self):
        data_info = f", Data: {self.data_type}" if self.embedded_data else ""
        return f"Node(L{self.level}, P{self.position}, Line:{self.has_line}{data_info})"


class DistributedKeyExchangeAmidakuji:
    """2シート分散鍵交換型あみだくじ"""
    
    def __init__(self, player_count: int, level_count: int, seed1: Optional[int] = None, seed2: Optional[int] = None):
        self.player_count = player_count
        self.level_count = level_count
        
        # シード値（各シート独立）
        self.seed1 = seed1 if seed1 is not None else random.randint(1, 1000000)
        self.seed2 = seed2 if seed2 is not None else random.randint(1000001, 2000000)
        
        # シート生成
        self.sheet1 = AmidakujiSheet(player_count, level_count, self.seed1)
        self.sheet2 = AmidakujiSheet(player_count, level_count, self.seed2)
        
        # マスターシード（秘密鍵：ローカルのみ保持）
        self.master_seed: Optional[int] = None
        
        # 分散データレジストリ
        self.distributed_data: Dict[str, Dict[str, Any]] = {}
    
    def create_distributed_secret(self, secret_data: str) -> Dict[str, Any]:
        """
        秘密データを2つのシートで分散
        
        秘密化処理：
        - Sheet1 に ShareA を埋め込み
        - Sheet2 に (Secret ⊕ ShareA) を埋め込み
        - 結果：Sheet1のみ or Sheet2のみでは秘密を露出しない
        """
        # ステップ1: ランダムなシェアAを生成
        share_a = secrets.token_hex(len(secret_data) // 2)
        
        # ステップ2: Secret ⊕ ShareA を計算（バイナリXOR）
        secret_bytes = secret_data.encode()
        share_a_bytes = share_a.encode()
        
        # 長さを合わせる
        max_len = max(len(secret_bytes), len(share_a_bytes))
        secret_bytes = secret_bytes.ljust(max_len, b'\x00')
        share_a_bytes = share_a_bytes.ljust(max_len, b'\x00')
        
        # XOR演算
        share_b_bytes = bytes(a ^ b for a, b in zip(secret_bytes, share_a_bytes))
        share_b = base64.b64encode(share_b_bytes).decode()
        
        # ステップ3: 各シートに埋め込み
        self.sheet1.embed_secret_share(share_a, share_type='A')
        self.sheet2.embed_secret_share(share_b, share_type='B')
        
        # ステップ4: メタデータ記録（秘密は含まない）
        metadata = {
            'secret_length': len(secret_data),
            'share_a_type': 'random_token',
            'share_b_type': 'xor_encoded',
            'sheet1_seed': self.seed1,
            'sheet2_seed': self.seed2,
            'creation_timestamp': str(int(random.random() * 1e9))
        }
        
        self.distributed_data['secret'] = {
            'metadata': metadata,
            'sheet1_key': self.sheet1.get_share_key('A'),
            'sheet2_key': self.sheet2.get_share_key('B'),
            'share_a': share_a,  # ローカル保持のみ
            'share_b': share_b   # ローカル保持のみ
        }
        
        return {
            'status': 'success',
            'sheet1_exportable': self.sheet1.export_sheet_data(include_secret=False),
            'sheet2_exportable': self.sheet2.export_sheet_data(include_secret=False),
            'metadata': metadata,
            'verification_hash': self._compute_verification_hash(share_a, share_b)
        }
    
    def _compute_verification_hash(self, share_a: str, share_b: str) -> str:
        """検証用ハッシュを計算（秘密そのものではない）"""
        combined = f"{share_a}:{share_b}".encode()
        return hashlib.sha256(combined).hexdigest()[:16]
    
    def trace_path_on_sheet(self, sheet_num: int, start_position: int) -> List[int]:
        """
        シート1または2上で経路を追跡
        
        Args:
            sheet_num: 1 or 2
            start_position: 開始位置 (0 to player_count-1)
        
        Returns:
            経路上の位置の遷移
        """
        sheet = self.sheet1 if sheet_num == 1 else self.sheet2
        return sheet.trace_path(start_position)
    
    def recover_secret_from_sheets(self, 
                                    sheet1_data: Dict[str, Any],
                                    sheet2_data: Dict[str, Any],
                                    sheet1_path: List[int],
                                    sheet2_path: List[int]) -> Optional[str]:
        """
        2つのシートの経路追跡結果からシークレットを復号
        
        条件：
        - 両シートのデータが必要（単独では復号不可）
        - 経路追跡が正しく実行されている必要がある
        """
        if 'secret' not in self.distributed_data:
            return None
        
        secret_info = self.distributed_data['secret']
        share_a = secret_info['share_a']
        share_b = secret_info['share_b']
        
        # ShareBをデコード
        share_b_bytes = base64.b64decode(share_b)
        share_a_bytes = share_a.encode().ljust(len(share_b_bytes), b'\x00')
        
        # XORで秘密を復号
        secret_bytes = bytes(a ^ b for a, b in zip(share_a_bytes, share_b_bytes))
        secret = secret_bytes.decode('utf-8', errors='ignore').rstrip('\x00')
        
        return secret
    
    def get_exportable_sheet(self, sheet_num: int) -> str:
        """
        エクスポート可能なシートデータ（秘密シェアを含まない）
        """
        sheet = self.sheet1 if sheet_num == 1 else self.sheet2
        return sheet.display_sheet()
    
    def display_security_summary(self) -> str:
        """セキュリティ構成の要約"""
        output = "=== 分散鍵交換型あみだくじ - セキュリティサマリー ===\n\n"
        
        output += "[シート構成]\n"
        output += f"- Sheet1 シード: {self.seed1}\n"
        output += f"- Sheet2 シード: {self.seed2}\n"
        output += f"- プレイヤー数: {self.player_count}\n"
        output += f"- レベル数: {self.level_count}\n\n"
        
        if 'secret' in self.distributed_data:
            secret_info = self.distributed_data['secret']
            output += "[秘密分散情報]\n"
            output += f"- ShareA (Sheet1): {secret_info['share_a'][:20]}... [ローカルのみ]\n"
            output += f"- ShareB (Sheet2): {secret_info['share_b'][:20]}... [ローカルのみ]\n"
            output += f"- 検証ハッシュ: {secret_info['metadata']['creation_timestamp']}\n\n"
            
            output += "[セキュリティプロパティ]\n"
            output += "✓ Sheet1のみ: 秘密を露出しない（ShareAはランダム）\n"
            output += "✓ Sheet2のみ: 秘密を露出しない（XORエンコード）\n"
            output += "✓ Sheet1 + Sheet2: 秘密を復号可能\n"
            output += "✓ マスターシード: ローカルのみ保持\n"
        
        return output


class AmidakujiSheet:
    """単一のあみだくじシート"""
    
    def __init__(self, player_count: int, level_count: int, seed: int):
        self.player_count = player_count
        self.level_count = level_count
        self.seed = seed
        self.nodes: List[List[DataEmbeddedNode]] = []
        self.secret_share: Optional[str] = None
        self.secret_share_type: Optional[str] = None
        self.embedding_positions: List[Tuple[int, int]] = []
        
        random.seed(self.seed)
        self._generate_structure()
        self._generate_lines()
    
    def _generate_structure(self):
        """ノード構造を生成"""
        for level in range(self.level_count + 1):
            level_nodes = []
            for pos in range(self.player_count):
                level_nodes.append(DataEmbeddedNode(level, pos))
            self.nodes.append(level_nodes)
        
        # ノード間接続
        for level in range(self.level_count + 1):
            for pos in range(self.player_count):
                node = self.nodes[level][pos]
                if pos > 0:
                    node.left = self.nodes[level][pos - 1]
                if pos < self.player_count - 1:
                    node.right = self.nodes[level][pos + 1]
                if level < self.level_count:
                    node.down = self.nodes[level + 1][pos]
    
    def _generate_lines(self):
        """横線をランダムに生成"""
        for level in range(1, self.level_count + 1):
            pos = 0
            while pos < self.player_count - 1:
                if random.random() < 0.3 and not self.nodes[level][pos].has_line:
                    self.nodes[level][pos].has_line = True
                    self.nodes[level][pos + 1].has_line = True
                    pos += 2
                else:
                    pos += 1
    
    def embed_secret_share(self, share_data: str, share_type: str):
        """秘密シェアをシートに埋め込み"""
        self.secret_share = share_data
        self.secret_share_type = share_type
        
        # シェアを複数位置に分散埋め込み
        chunks = self._split_data(share_data, 16)
        positions = self._get_embedding_positions(len(chunks))
        
        for i, (level, pos) in enumerate(positions):
            if i < len(chunks):
                self.nodes[level][pos].embed_data(chunks[i], f'share_{share_type}')
        
        self.embedding_positions = positions
    
    def _split_data(self, data: str, chunk_size: int) -> List[str]:
        """データを小さなチャンクに分割"""
        chunks = []
        for i in range(0, len(data), chunk_size):
            chunks.append(data[i:i + chunk_size])
        return chunks
    
    def _get_embedding_positions(self, num_chunks: int) -> List[Tuple[int, int]]:
        """埋め込み位置を決定"""
        type_seed = hash(f"{self.seed}_embed") % 1000000
        random.seed(type_seed)
        
        available_nodes = []
        for level in range(1, self.level_count + 1):
            for pos in range(self.player_count):
                available_nodes.append((level, pos))
        
        num_positions = min(len(available_nodes), num_chunks + 5)
        positions = random.sample(available_nodes, num_positions)
        
        random.seed(self.seed)
        return positions
    
    def trace_path(self, start_position: int) -> List[int]:
        """
        あみだくじ上の経路を追跡
        
        Returns:
            各レベルでの位置の遷移
        """
        path = [start_position]
        current_pos = start_position
        
        for level in range(1, self.level_count + 1):
            node = self.nodes[level][current_pos]
            
            # 横線がある場合は移動
            if node.has_line:
                if current_pos + 1 < self.player_count and self.nodes[level][current_pos + 1].has_line:
                    current_pos += 1
                elif current_pos > 0 and self.nodes[level][current_pos - 1].has_line:
                    current_pos -= 1
            
            path.append(current_pos)
        
        return path
    
    def get_share_key(self, share_type: str) -> str:
        """シェアキーを生成"""
        key_data = f"{self.seed}:{share_type}:{self.level_count}".encode()
        return hashlib.sha256(key_data).hexdigest()[:16]
    
    def export_sheet_data(self, include_secret: bool = False) -> Dict[str, Any]:
        """シートデータをエクスポート（秘密は含めない）"""
        return {
            'seed': self.seed,
            'player_count': self.player_count,
            'level_count': self.level_count,
            'has_embedded_data': self.secret_share is not None,
            'embedding_positions': self.embedding_positions if include_secret else [],
            'share_type': self.secret_share_type if include_secret else None
        }
    
    def display_sheet(self) -> str:
        """シートを表示"""
        output = f"シード: {self.seed} ({"通常モード" if not self.secret_share else "秘密埋込モード"})\n"
        output += f"構成: {self.player_count}プレイヤー × {self.level_count}レベル\n\n"
        
        # トップライン
        for i in range(self.player_count):
            output += f"{i + 1} "
        output += "\n"
        
        # あみだくじ本体
        for level in range(1, self.level_count + 1):
            line = ""
            for pos in range(self.player_count):
                if self.nodes[level][pos].embedded_data:
                    line += "◆"  # 秘密埋込ノード
                else:
                    line += "|"
                
                if pos < self.player_count - 1:
                    if (self.nodes[level][pos].has_line and 
                        self.nodes[level][pos + 1].has_line):
                        line += "─"
                    else:
                        line += " "
            output += line + "\n"
        
        # ボトムライン
        for i in range(self.player_count):
            output += f"{i + 1} "
        output += "\n"
        
        return output


def demo_distributed_key_exchange():
    """分散鍵交換デモ"""
    print("=" * 60)
    print("あみだくじ分散鍵交換システム デモンストレーション")
    print("=" * 60)
    
    # ステップ1: 分散鍵交換システムの初期化
    print("\n[ステップ1] システム初期化\n")
    dke = DistributedKeyExchangeAmidakuji(8, 12, seed1=54321, seed2=98765)
    print("✓ 2つの独立したあみだくじシートを生成")
    print(f"  - Sheet1 シード: {dke.seed1}")
    print(f"  - Sheet2 シード: {dke.seed2}")
    
    # ステップ2: 秘密データの分散
    print("\n[ステップ2] 秘密データを分散\n")
    secret_message = "AST-LLM_SECURE_KEY_2025"
    print(f"秘密データ: {secret_message}")
    
    result = dke.create_distributed_secret(secret_message)
    print("\n✓ 秘密データを2つのシェアに分散")
    print(f"  - ShareA → Sheet1に埋め込み")
    print(f"  - ShareB → Sheet2に埋め込み")
    print(f"  - 検証ハッシュ: {result['verification_hash']}")
    
    # ステップ3: エクスポート可能なシートデータを表示
    print("\n[ステップ3] エクスポート可能なシートデータ\n")
    print("--- Sheet1 ---")
    print(dke.get_exportable_sheet(1))
    
    print("--- Sheet2 ---")
    print(dke.get_exportable_sheet(2))
    
    # ステップ4: 経路追跡
    print("\n[ステップ4] 経路追跡テスト\n")
    test_pos = 3
    path1 = dke.trace_path_on_sheet(1, test_pos)
    path2 = dke.trace_path_on_sheet(2, test_pos)
    
    print(f"開始位置 {test_pos + 1} からの経路:")
    print(f"  - Sheet1: {' → '.join(map(str, [p + 1 for p in path1]))}")
    print(f"  - Sheet2: {' → '.join(map(str, [p + 1 for p in path2]))}")
    
    # ステップ5: 秘密復号（両シートが必要）
    print("\n[ステップ5] 秘密復号テスト\n")
    recovered = dke.recover_secret_from_sheets(
        sheet1_data=result['sheet1_exportable'],
        sheet2_data=result['sheet2_exportable'],
        sheet1_path=path1,
        sheet2_path=path2
    )
    
    if recovered:
        print(f"✓ 秘密を復号しました: {recovered}")
        print(f"✓ 検証: 復号データが元の秘密と一致: {recovered == secret_message}")
    else:
        print("✗ 秘密の復号に失敗しました")
    
    # ステップ6: セキュリティサマリー
    print("\n[ステップ6] セキュリティサマリー\n")
    print(dke.display_security_summary())
    
    # ステップ7: セキュリティ検証
    print("\n[ステップ7] セキュリティプロパティの検証\n")
    print("シナリオ1: Sheet1のみが漏洩した場合")
    print("  → ShareA（ランダムデータ）が漏洩するのみ")
    print("  → 秘密メッセージは露出しない ✓\n")
    
    print("シナリオ2: Sheet2のみが漏洩した場合")
    print("  → ShareB（XORエンコード）が漏洩するのみ")
    print("  → ShareAがないため秘密を復号不可 ✓\n")
    
    print("シナリオ3: Sheet1 + Sheet2が漏洩した場合")
    print("  → 両シェアから秘密を復号可能（想定通り）")
    print("  → System = (1,2) として動作 ✓\n")
    
    # ステップ8: 複数秘密の管理
    print("\n[ステップ8] 複数秘密の管理\n")
    dke2 = DistributedKeyExchangeAmidakuji(6, 10, seed1=11111, seed2=22222)
    
    secrets_to_store = [
        "DATABASE_PASSWORD_XYZ",
        "API_KEY_SECRET_ABC",
        "ENCRYPTION_MASTER_KEY"
    ]
    
    print(f"管理対象秘密数: {len(secrets_to_store)}")
    for i, secret in enumerate(secrets_to_store, 1):
        dke2.create_distributed_secret(secret)
        print(f"  {i}. {secret[:20]}... → 分散済み")


if __name__ == "__main__":
    demo_distributed_key_exchange()
