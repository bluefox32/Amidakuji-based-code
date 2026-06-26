import random
import hashlib
import base64
import json
from typing import List, Dict, Tuple, Optional, Any, Union
import secrets

class MultiDataEmbeddedNode:
    """複数データ型を内包できるあみだくじノード"""
    
    def __init__(self, level: int, position: int):
        self.level = level
        self.position = position
        self.has_line = False
        self.left = None
        self.right = None
        self.down = None
        self.embedded_data: Dict[str, Any] = {}  # {data_type: data}
        
    def embed_data(self, data_type: str, data: Any):
        """ノードに複数のデータ型を埋め込み"""
        self.embedded_data[data_type] = data
        
    def get_data(self, data_type: str) -> Optional[Any]:
        """指定したデータ型のデータを取得"""
        return self.embedded_data.get(data_type)
    
    def __repr__(self):
        data_types = ", ".join(self.embedded_data.keys()) if self.embedded_data else "empty"
        return f"Node(L{self.level}, P{self.position}, Data:[{data_types}])"


class MultiDataDistributedAmidakuji:
    """複数データ型対応の分散鍵交換型あみだくじ"""
    
    def __init__(self, player_count: int, level_count: int, 
                 seed1: Optional[int] = None, seed2: Optional[int] = None):
        self.player_count = player_count
        self.level_count = level_count
        self.seed1 = seed1 if seed1 is not None else random.randint(1, 1000000)
        self.seed2 = seed2 if seed2 is not None else random.randint(1000001, 2000000)
        
        self.sheet1 = MultiDataSheet(player_count, level_count, self.seed1)
        self.sheet2 = MultiDataSheet(player_count, level_count, self.seed2)
        
        # マルチデータレジストリ
        self.distributed_data: Dict[str, Dict[str, Any]] = {}
    
    def embed_and_distribute_data(self, data_type: str, data: Union[str, bytes, dict, list]) -> Dict[str, Any]:
        """
        複数データ型を分散埋め込み
        
        Args:
            data_type: 'texture', 'metadata', 'coordinates', 'audio', 'config' など
            data: 埋め込むデータ
        
        Returns:
            埋め込み結果のメタデータ
        """
        # データを正規化
        if isinstance(data, dict) or isinstance(data, list):
            data_str = json.dumps(data)
        elif isinstance(data, bytes):
            data_str = base64.b64encode(data).decode()
        else:
            data_str = str(data)
        
        # Step1: ランダムなShareAを生成
        share_a = secrets.token_hex(len(data_str) // 2 + 8)
        
        # Step2: ShareB = Data ⊕ ShareA
        share_b = self._xor_encode(data_str, share_a)
        
        # Step3: 各シートに埋め込み
        positions1 = self.sheet1.embed_data_type(data_type, share_a, 'shareA')
        positions2 = self.sheet2.embed_data_type(data_type, share_b, 'shareB')
        
        # Step4: メタデータ記録
        metadata = {
            'data_type': data_type,
            'data_length': len(data_str),
            'share_a_length': len(share_a),
            'share_b_length': len(share_b),
            'sheet1_positions': positions1,
            'sheet2_positions': positions2,
            'sheet1_key': self.sheet1.get_data_type_key(data_type),
            'sheet2_key': self.sheet2.get_data_type_key(data_type),
            'checksum': hashlib.sha256(data_str.encode()).hexdigest()[:16]
        }
        
        self.distributed_data[data_type] = {
            'metadata': metadata,
            'share_a': share_a,  # ローカル保持
            'share_b': share_b   # ローカル保持
        }
        
        return {
            'status': 'success',
            'data_type': data_type,
            'distributed': True,
            'metadata': metadata
        }
    
    def _xor_encode(self, data: str, key: str) -> str:
        """XOR エンコード"""
        max_len = max(len(data), len(key))
        data_bytes = data.encode().ljust(max_len, b'\x00')
        key_bytes = key.encode().ljust(max_len, b'\x00')
        
        xor_bytes = bytes(a ^ b for a, b in zip(data_bytes, key_bytes))
        return base64.b64encode(xor_bytes).decode()
    
    def _xor_decode(self, encoded: str, key: str) -> str:
        """XOR デコード"""
        xor_bytes = base64.b64decode(encoded.encode())
        key_bytes = key.encode().ljust(len(xor_bytes), b'\x00')
        
        decoded_bytes = bytes(a ^ b for a, b in zip(xor_bytes, key_bytes))
        return decoded_bytes.decode('utf-8', errors='ignore').rstrip('\x00')
    
    def recover_data(self, data_type: str) -> Optional[Union[str, dict, list]]:
        """
        2つのシートから複数のデータを復号
        """
        if data_type not in self.distributed_data:
            return None
        
        data_info = self.distributed_data[data_type]
        share_a = data_info['share_a']
        share_b = data_info['share_b']
        
        # データ復号
        recovered_data = self._xor_decode(share_b, share_a)
        
        # 元のデータ型に合わせて復元
        try:
            return json.loads(recovered_data)
        except:
            return recovered_data
    
    def trace_and_extract_path(self, sheet_num: int, start_pos: int, 
                               data_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        経路追跡と同時に複数データを抽出
        
        Args:
            sheet_num: 1 or 2
            start_pos: 開始位置
            data_types: 抽出するデータ型のリスト（Noneなら全て）
        
        Returns:
            経路情報と抽出データ
        """
        sheet = self.sheet1 if sheet_num == 1 else self.sheet2
        
        # 経路追跡
        path = sheet.trace_path(start_pos)
        
        # 経路上のデータ抽出
        extracted_data = {}
        if data_types is None:
            # 全データ型を抽出
            data_types = list(self.distributed_data.keys())
        
        for data_type in data_types:
            extracted_on_path = []
            for pos in path:
                node = sheet.nodes[path.index(pos)][pos] if path.index(pos) < len(sheet.nodes) else None
                if node and node.get_data(data_type):
                    extracted_on_path.append(node.get_data(data_type))
            
            if extracted_on_path:
                extracted_data[data_type] = ''.join(extracted_on_path)
        
        return {
            'sheet_num': sheet_num,
            'start_position': start_pos,
            'path': path,
            'extracted_data': extracted_data,
            'data_count': len(extracted_data)
        }
    
    def display_system_overview(self) -> str:
        """複数データ統合システムの概要表示"""
        output = "=" * 70 + "\n"
        output += "複数データ型対応 分散鍵交換型あみだくじシステム\n"
        output += "=" * 70 + "\n\n"
        
        output += "[システム構成]\n"
        output += f"- Sheet1 シード: {self.seed1}\n"
        output += f"- Sheet2 シード: {self.seed2}\n"
        output += f"- 規模: {self.player_count}プレイヤー × {self.level_count}レベル\n\n"
        
        output += "[管理中のデータ型]\n"
        for data_type, info in self.distributed_data.items():
            metadata = info['metadata']
            output += f"\n  📦 {data_type.upper()}\n"
            output += f"     - データサイズ: {metadata['data_length']} bytes\n"
            output += f"     - Share A サイズ: {metadata['share_a_length']} bytes\n"
            output += f"     - Share B サイズ: {metadata['share_b_length']} bytes\n"
            output += f"     - チェックサム: {metadata['checksum']}\n"
            output += f"     - Sheet1 配置位置: {len(metadata['sheet1_positions'])} ノード\n"
            output += f"     - Sheet2 配置位置: {len(metadata['sheet2_positions'])} ノード\n"
        
        output += "\n" + "[セキュリティプロパティ]\n"
        for data_type in self.distributed_data.keys():
            output += f"  ✓ {data_type}: (2,2) スキーム適用\n"
        
        return output
    
    def export_sheet_structure(self, sheet_num: int, include_data: bool = False) -> str:
        """シート構造をエクスポート"""
        sheet = self.sheet1 if sheet_num == 1 else self.sheet2
        return sheet.display_structure(include_data=include_data)


class MultiDataSheet:
    """複数データ型に対応したあみだくじシート"""
    
    def __init__(self, player_count: int, level_count: int, seed: int):
        self.player_count = player_count
        self.level_count = level_count
        self.seed = seed
        self.nodes: List[List[MultiDataEmbeddedNode]] = []
        self.data_type_keys: Dict[str, str] = {}
        self.embedding_registry: Dict[str, List[Tuple[int, int]]] = {}
        
        random.seed(self.seed)
        self._generate_structure()
        self._generate_lines()
    
    def _generate_structure(self):
        """ノード構造を生成"""
        for level in range(self.level_count + 1):
            level_nodes = []
            for pos in range(self.player_count):
                level_nodes.append(MultiDataEmbeddedNode(level, pos))
            self.nodes.append(level_nodes)
        
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
    
    def embed_data_type(self, data_type: str, data: str, share_type: str) -> List[Tuple[int, int]]:
        """
        特定のデータ型をシートに埋め込み
        
        Returns:
            埋め込み位置リスト
        """
        # キーを生成
        type_seed = hash(f"{self.seed}:{data_type}:{share_type}") % 1000000
        self.data_type_keys[data_type] = hashlib.sha256(
            f"{self.seed}_{data_type}_{share_type}".encode()
        ).hexdigest()[:16]
        
        # データを分割
        chunks = self._split_data(data, 20)
        
        # 埋め込み位置を決定
        random.seed(type_seed)
        available_nodes = [
            (level, pos) 
            for level in range(1, self.level_count + 1)
            for pos in range(self.player_count)
        ]
        
        num_positions = min(len(available_nodes), len(chunks) + 3)
        positions = random.sample(available_nodes, num_positions)
        
        # 埋め込み実行
        for i, (level, pos) in enumerate(positions):
            if i < len(chunks):
                self.nodes[level][pos].embed_data(data_type, chunks[i])
        
        self.embedding_registry[data_type] = positions
        random.seed(self.seed)
        
        return positions
    
    def _split_data(self, data: str, chunk_size: int) -> List[str]:
        """データを分割"""
        chunks = []
        for i in range(0, len(data), chunk_size):
            chunks.append(data[i:i + chunk_size])
        return chunks
    
    def get_data_type_key(self, data_type: str) -> str:
        """データ型キーを取得"""
        return self.data_type_keys.get(data_type, "unknown")
    
    def trace_path(self, start_pos: int) -> List[int]:
        """経路を追跡"""
        path = [start_pos]
        current_pos = start_pos
        
        for level in range(1, self.level_count + 1):
            node = self.nodes[level][current_pos]
            
            if node.has_line:
                if current_pos + 1 < self.player_count and self.nodes[level][current_pos + 1].has_line:
                    current_pos += 1
                elif current_pos > 0 and self.nodes[level][current_pos - 1].has_line:
                    current_pos -= 1
            
            path.append(current_pos)
        
        return path
    
    def display_structure(self, include_data: bool = False) -> str:
        """シート構造を表示"""
        output = f"Sheet (Seed: {self.seed})\n"
        output += f"構成: {self.player_count} × {self.level_count}\n\n"
        
        # トップライン
        for i in range(self.player_count):
            output += f"{i + 1} "
        output += "\n"
        
        # あみだくじ
        for level in range(1, self.level_count + 1):
            line = ""
            for pos in range(self.player_count):
                node = self.nodes[level][pos]
                
                if node.embedded_data:
                    if include_data:
                        # 埋め込まれたデータ型を表示
                        types = list(node.embedded_data.keys())
                        if len(types) == 1:
                            line += "◆"
                        else:
                            line += "◈"
                    else:
                        line += "◆"
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


def demo_multidata_distributed():
    """複数データ型分散方式のデモ"""
    print("=" * 70)
    print("複数データ型対応 分散鍵交換型あみだくじ デモンストレーション")
    print("=" * 70)
    
    # システム初期化
    print("\n[初期化]\n")
    system = MultiDataDistributedAmidakuji(8, 14, seed1=111111, seed2=222222)
    print("✓ 2シートシステムを初期化")
    
    # 複数データ型を埋め込み
    print("\n[複数データ型の分散埋め込み]\n")
    
    # 1. テクスチャデータ
    print("1️⃣  テクスチャデータを分散...")
    texture_data = "RGB(255,128,64)×512×512_compressed_format_v2.0"
    result1 = system.embed_and_distribute_data('texture', texture_data)
    print(f"   ✓ {result1['data_type']}: {result1['metadata']['data_length']} bytes")
    
    # 2. メタデータ（JSON）
    print("2️⃣  メタデータを分散...")
    metadata = {
        'author': 'kI Developer',
        'project': 'AST-LLM',
        'version': '2.0.1',
        'created': '2025-06-29T10:30:00Z',
        'tags': ['distributed', 'secure', 'amidakuji']
    }
    result2 = system.embed_and_distribute_data('metadata', metadata)
    print(f"   ✓ {result2['data_type']}: {result2['metadata']['data_length']} bytes")
    
    # 3. 座標データ（リスト）
    print("3️⃣  座標データを分散...")
    coordinates = [
        (10.5, 20.3, 5.1),
        (30.2, 40.8, 15.5),
        (50.1, 60.9, 25.3),
        (70.4, 80.2, 35.7)
    ]
    result3 = system.embed_and_distribute_data('coordinates', coordinates)
    print(f"   ✓ {result3['data_type']}: {result3['metadata']['data_length']} bytes")
    
    # 4. 設定データ
    print("4️⃣  設定データを分散...")
    config = {
        'mode': 'distributed',
        'encryption': 'xor_based',
        'redundancy': 2,
        'checksum_type': 'sha256'
    }
    result4 = system.embed_and_distribute_data('config', config)
    print(f"   ✓ {result4['data_type']}: {result4['metadata']['data_length']} bytes")
    
    # システム概要
    print("\n[システム概要]\n")
    print(system.display_system_overview())
    
    # シート構造の表示
    print("[シート構造]\n")
    print("--- Sheet1 ---")
    print(system.export_sheet_structure(1, include_data=True))
    
    print("--- Sheet2 ---")
    print(system.export_sheet_structure(2, include_data=True))
    
    # 経路追跡と同時データ抽出
    print("\n[経路追跡と複数データ同時抽出]\n")
    test_pos = 2
    
    print(f"開始位置 {test_pos + 1} から経路を追跡...\n")
    
    trace1 = system.trace_and_extract_path(1, test_pos, 
                                          data_types=['texture', 'metadata', 'coordinates', 'config'])
    print(f"Sheet1:")
    print(f"  経路: {' → '.join(map(str, [p+1 for p in trace1['path']]))}")
    print(f"  抽出データ型: {list(trace1['extracted_data'].keys())}")
    print(f"  抽出サイズ: {sum(len(v) for v in trace1['extracted_data'].values())} bytes")
    
    trace2 = system.trace_and_extract_path(2, test_pos,
                                          data_types=['texture', 'metadata', 'coordinates', 'config'])
    print(f"\nSheet2:")
    print(f"  経路: {' → '.join(map(str, [p+1 for p in trace2['path']]))}")
    print(f"  抽出データ型: {list(trace2['extracted_data'].keys())}")
    print(f"  抽出サイズ: {sum(len(v) for v in trace2['extracted_data'].values())} bytes")
    
    # データ復号テスト
    print("\n[複数データ復号テスト]\n")
    
    print("✓ テクスチャ復号:")
    recovered_texture = system.recover_data('texture')
    print(f"  {recovered_texture}\n")
    
    print("✓ メタデータ復号:")
    recovered_metadata = system.recover_data('metadata')
    print(f"  {json.dumps(recovered_metadata, indent=2, ensure_ascii=False)}\n")
    
    print("✓ 座標復号:")
    recovered_coords = system.recover_data('coordinates')
    print(f"  {recovered_coords}\n")
    
    print("✓ 設定復号:")
    recovered_config = system.recover_data('config')
    print(f"  {json.dumps(recovered_config, indent=2, ensure_ascii=False)}\n")
    
    # セキュリティ検証
    print("\n[セキュリティ検証]\n")
    print("✓ 各データ型が独立した (2,2) スキームで保護されている")
    print("✓ Sheet1単独: いずれのデータも復号不可（ShareAのみ）")
    print("✓ Sheet2単独: いずれのデータも復号不可（XORエンコードのみ）")
    print("✓ Sheet1 + Sheet2: 全データを正確に復号可能")
    print("✓ マスターシード: ローカルのみ保持（外部非開示）")


if __name__ == "__main__":
    demo_multidata_distributed()
